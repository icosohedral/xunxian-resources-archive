from __future__ import annotations

import base64
import json
import re
import zlib
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from urllib.parse import urlencode

import asgi
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from jinja2 import BaseLoader, Environment, select_autoescape
from workers import WorkerEntrypoint

from generated_config import CONFIG
from generated_template import TEMPLATE_SOURCE


PAGE_SIZE = 15
CHINA_TIMEZONE = timezone(timedelta(hours=8))
VISITOR_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{16,80}$")

templates = Environment(
    loader=BaseLoader(),
    autoescape=select_autoescape(default=True),
)
index_template = templates.from_string(TEMPLATE_SOURCE)

app = FastAPI(
    title="寻仙资源存档",
    description="Cloudflare Workers 上的寻仙资源资料库",
    version=CONFIG["site_version"],
)


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        return await asgi.fetch(app, request, self.env)


def _to_python(value: Any) -> Any:
    if hasattr(value, "to_py"):
        return value.to_py()
    return value


def _result_rows(result: Any) -> list[dict[str, Any]]:
    rows = _to_python(result.results)
    return [dict(_to_python(row)) for row in rows]


def _decode_detail(value: str) -> dict[str, Any]:
    compressed = base64.b64decode(value)
    return json.loads(zlib.decompress(compressed).decode("utf-8"))


def _title_group_filter_values() -> set[str]:
    return {
        option["value"]
        for family in CONFIG["title_group_options"]
        for option in (family, *family["groups"])
    }


def _known_search_total(
    *,
    query: str,
    kind: str,
    category: str,
) -> int | None:
    if query.strip():
        return None
    if category:
        value = CONFIG["category_counts"].get(kind, {}).get(category)
        return int(value) if value is not None else None
    if not kind:
        return int(CONFIG["stats"]["resource_count"])
    return int(CONFIG["stats"]["filter_counts"].get(kind, 0))


async def _search(
    database: Any,
    *,
    query: str = "",
    kind: str = "",
    category: str = "",
    page: int = 1,
) -> dict[str, Any]:
    if kind not in {"", "items", "companions", "title"}:
        raise ValueError("未知资源类型")
    valid_categories = (
        CONFIG["item_category_labels"]
        if kind == "items"
        else (
            CONFIG["companion_category_labels"]
            if kind == "companions"
            else (
                _title_group_filter_values()
                if kind == "title"
                else set()
            )
        )
    )
    if category and category not in valid_categories:
        raise ValueError("未知筛选分类")

    page = max(1, page)
    conditions = ["1=1"]
    parameters: list[Any] = []
    order_parameters: list[Any] = []
    if kind == "items":
        if category:
            conditions.append("resource_kind = ?")
            parameters.append(category)
        else:
            conditions.append("resource_kind IN ('item', 'quest_item')")
    elif kind == "companions":
        conditions.append("companion_category IS NOT NULL")
        if category:
            conditions.append("companion_category = ?")
            parameters.append(category)
    elif kind == "title":
        conditions.append("resource_kind = 'title'")
        if category:
            filter_type, filter_value = category.split(":", 1)
            if filter_type == "family":
                conditions.append("title_group_family_id = ?")
                parameters.append(int(filter_value))
            else:
                conditions.append("title_group_name = ?")
                parameters.append(filter_value)

    normalized_query = query.strip()
    order_by = [
        "resource_kind",
        "placeholder_rank",
        "display_name COLLATE NOCASE",
        "resource_id",
    ]
    if normalized_query:
        if normalized_query.isdecimal():
            # IDs are exact integers. Keeping this outside the text-search OR
            # allows SQLite/D1 to use the (resource_kind, resource_id) key.
            conditions.append("resource_id = ?")
            parameters.append(int(normalized_query))
        else:
            escaped = (
                normalized_query.replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_")
            )
            like = f"%{escaped}%"
            conditions.append(
                """
                (
                    display_name LIKE ? ESCAPE '\\'
                    OR search_text LIKE ? ESCAPE '\\'
                )
                """
            )
            parameters.extend([like, like])
            search_priority = """
                CASE
                    WHEN display_name = ? THEN 0
                    WHEN display_name LIKE ? ESCAPE '\\' THEN 1
                    ELSE 2
                END
            """
            order_by.insert(0, search_priority)
            order_parameters.extend([normalized_query, f"{escaped}%"])

    where_sql = " AND ".join(conditions)
    table_sql = "web_resource"
    if kind == "items" and not normalized_query:
        # The name-only index can otherwise win the planner's estimate and
        # force a sort of every item because it omits placeholder_rank.
        table_sql += " INDEXED BY idx_web_resource_kind_listing"
    total = _known_search_total(
        query=query,
        kind=kind,
        category=category,
    )
    total_column = ", COUNT(*) OVER () AS search_total" if total is None else ""
    list_statement = database.prepare(
        f"""
        SELECT summary_json{total_column}
        FROM {table_sql}
        WHERE {where_sql}
        ORDER BY {", ".join(order_by)}
        LIMIT ? OFFSET ?
        """
    ).bind(
        *parameters,
        *order_parameters,
        PAGE_SIZE,
        (page - 1) * PAGE_SIZE,
    )
    rows = _result_rows(await list_statement.run())
    if total is None:
        total = int(rows[0]["search_total"]) if rows else 0
    page_count = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    if page > page_count:
        page = page_count
    return {
        "items": [json.loads(row["summary_json"]) for row in rows],
        "total": total,
        "page": page,
        "page_count": page_count,
    }


async def _get_detail(
    database: Any,
    resource_kind: str,
    resource_id: int,
) -> dict[str, Any] | None:
    rows = _result_rows(
        await database.prepare(
            """
            SELECT detail_chunk
            FROM web_resource_detail
            WHERE resource_kind = ? AND resource_id = ?
            ORDER BY chunk_no
            """
        )
        .bind(resource_kind, resource_id)
        .run()
    )
    if not rows:
        return None
    return _decode_detail("".join(row["detail_chunk"] for row in rows))


async def _visitor_count(database: Any) -> int:
    today = datetime.now(CHINA_TIMEZONE).date().isoformat()
    rows = _result_rows(
        await database.prepare(
            """
            SELECT visitor_count
            FROM daily_visit
            WHERE visit_day = ?
            """
        )
        .bind(today)
        .run()
    )
    return int(rows[0]["visitor_count"]) if rows else 0


async def _record_visit(
    database: Any,
    visitor_id: str,
) -> tuple[int, str, bool]:
    today = datetime.now(CHINA_TIMEZONE).date().isoformat()
    inserted = _result_rows(
        await database.prepare(
            """
            INSERT OR IGNORE INTO daily_visitor (visit_day, visitor_id)
            VALUES (?, ?)
            RETURNING visitor_id
            """
        )
        .bind(today, visitor_id)
        .run()
    )
    is_new = bool(inserted)
    if is_new:
        await database.prepare(
            """
            INSERT INTO daily_visit (visit_day, visitor_count)
            VALUES (?, 1)
            ON CONFLICT(visit_day) DO UPDATE
            SET visitor_count = visitor_count + 1
            """
        ).bind(today).run()
    return await _visitor_count(database), today, is_new


async def _render(
    request: Request,
    *,
    query: str,
    kind: str,
    category: str,
    page: int,
    detail: dict[str, Any] | None = None,
    select_first_result: bool = False,
) -> HTMLResponse:
    env = request.scope["env"]
    is_overview = (
        not kind and not query.strip() and not category and detail is None
    )
    if is_overview:
        search = {
            "items": [],
            "total": 0,
            "page": 1,
            "page_count": 1,
        }
    else:
        try:
            search = await _search(
                env.RESOURCE_DB,
                query=query,
                kind=kind,
                category=category,
                page=page,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    if detail is None and select_first_result and search["items"]:
        first_result = search["items"][0]
        detail = await _get_detail(
            env.RESOURCE_DB,
            first_result["resource_kind"],
            first_result["resource_id"],
        )

    filters = {"q": query, "kind": kind, "category": category}
    previous_query = urlencode(
        {**filters, "page": max(1, search["page"] - 1)}
    )
    next_query = urlencode(
        {
            **filters,
            "page": min(search["page_count"], search["page"] + 1),
        }
    )
    html = index_template.render(
        request=request,
        detail=detail,
        site_version=CONFIG["site_version"],
        today_visitors=await _visitor_count(env.VISITS_DB),
        search=SimpleNamespace(**search),
        stats=CONFIG["stats"],
        external_collection_counts=CONFIG["external_collection_counts"],
        filter_kind_labels=CONFIG["filter_kind_labels"],
        item_category_labels=CONFIG["item_category_labels"],
        companion_category_labels=CONFIG["companion_category_labels"],
        title_group_options=CONFIG["title_group_options"],
        metadata_labels=CONFIG["metadata_labels"],
        filters=filters,
        is_overview=is_overview,
        empty_resource_label=CONFIG["filter_kind_labels"].get(
            kind, "资源"
        ),
        previous_url=f"/?{previous_query}",
        next_url=f"/?{next_query}",
    )
    return HTMLResponse(html)


@app.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    q: str = Query(default="", max_length=100),
    kind: str = Query(default=""),
    category: str = Query(default=""),
    page: int = Query(default=1, ge=1),
) -> HTMLResponse:
    detail = None
    if not q.strip() and not category:
        default_resource = CONFIG["default_filter_details"].get(kind)
        if default_resource is not None:
            detail = await _get_detail(
                request.scope["env"].RESOURCE_DB,
                default_resource[0],
                default_resource[1],
            )
    return await _render(
        request,
        query=q,
        kind=kind,
        category=category,
        page=page,
        detail=detail,
        select_first_result=bool(q.strip() or category),
    )


@app.get("/resources/{kind}/{resource_id}", response_class=HTMLResponse)
async def resource_detail(
    request: Request,
    kind: str,
    resource_id: int,
    q: str = Query(default="", max_length=100),
    filter_kind: str = Query(default="", alias="kind"),
    category: str = Query(default=""),
    page: int = Query(default=1, ge=1),
) -> HTMLResponse:
    detail = await _get_detail(
        request.scope["env"].RESOURCE_DB,
        kind,
        resource_id,
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="没有找到该资源")
    if not filter_kind:
        filter_kind = {
            "item": "items",
            "quest_item": "items",
            "pet": "companions",
            "ride": "companions",
            "title": "title",
        }.get(kind, "")
    return await _render(
        request,
        query=q,
        kind=filter_kind,
        category=category,
        page=page,
        detail=detail,
    )


@app.post("/api/visit", response_class=JSONResponse)
async def api_visit(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="无效的访问标识") from None
    visitor_id = (
        str(payload.get("visitor_id", ""))
        if isinstance(payload, dict)
        else ""
    )
    if not VISITOR_ID_PATTERN.fullmatch(visitor_id):
        raise HTTPException(status_code=422, detail="无效的访问标识")
    count, visit_day, is_new = await _record_visit(
        request.scope["env"].VISITS_DB,
        visitor_id,
    )
    return JSONResponse(
        {"count": count, "visit_day": visit_day, "is_new": is_new}
    )


@app.get("/api/search")
async def api_search(
    request: Request,
    q: str = Query(default="", max_length=100),
    kind: str = Query(default=""),
    category: str = Query(default=""),
    page: int = Query(default=1, ge=1),
) -> dict[str, Any]:
    try:
        return await _search(
            request.scope["env"].RESOURCE_DB,
            query=q,
            kind=kind,
            category=category,
            page=page,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/resources/{kind}/{resource_id}")
async def api_detail(
    request: Request,
    kind: str,
    resource_id: int,
) -> dict[str, Any]:
    detail = await _get_detail(
        request.scope["env"].RESOURCE_DB,
        kind,
        resource_id,
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="没有找到该资源")
    return detail
