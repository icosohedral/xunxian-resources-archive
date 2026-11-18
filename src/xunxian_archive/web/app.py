"""寻仙资源资料库本地只读网站。"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlencode

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from xunxian_archive.models import ResourceKind
from xunxian_archive.web.repository import (
    COMPANION_CATEGORY_LABELS,
    FILTER_KIND_LABELS,
    ITEM_CATEGORY_LABELS,
    METADATA_LABELS,
    CatalogRepository,
    SearchResult,
)
from xunxian_archive.web.visits import VisitorStore


PROJECT_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
SITE_VERSION = "1.1.0"
VISITOR_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{16,80}$")
# 每页条数由浏览器按索引卡片能放下的行数写入 Cookie；缺失或异常时用默认值。
PAGE_SIZE_COOKIE = "xunxian-archive-page-size"
DEFAULT_PAGE_SIZE = 15
MIN_PAGE_SIZE = 4
MAX_PAGE_SIZE = 40


def page_size_from_cookie(value: str | None) -> int:
    if value is None or not value.isdigit():
        return DEFAULT_PAGE_SIZE
    return min(MAX_PAGE_SIZE, max(MIN_PAGE_SIZE, int(value)))
EXTERNAL_COLLECTION_COUNTS = {
    "quests": 8828,
    "music": 6414,
}


def create_app(
    database_path: Path = PROJECT_ROOT / "outputs/catalog.db",
    static_path: Path = PROJECT_ROOT / "public",
    visits_database_path: Path | None = None,
) -> FastAPI:
    repository = CatalogRepository(database_path)
    visitor_store = VisitorStore(
        visits_database_path or database_path.with_name("visits.db")
    )
    templates = Jinja2Templates(directory=TEMPLATE_DIR)
    app = FastAPI(
        title="寻仙资源存档",
        description="道具、宠物、骑乘配置与称号资料",
        version=SITE_VERSION,
    )
    app.mount("/static", StaticFiles(directory=static_path), name="static")

    def render(
        request: Request,
        *,
        query: str,
        kind: str,
        category: str,
        page: int,
        detail: dict | None = None,
        select_first_result: bool = False,
    ) -> HTMLResponse:
        is_overview = (
            not kind
            and not query.strip()
            and not category
            and detail is None
        )
        page_size = page_size_from_cookie(
            request.cookies.get(PAGE_SIZE_COOKIE)
        )
        if is_overview:
            result = SearchResult([], 0, 1, 1)
        else:
            try:
                result = repository.search(
                    query=query,
                    kind=kind,
                    category=category,
                    page=page,
                    page_size=page_size,
                )
            except ValueError as exc:
                raise HTTPException(
                    status_code=404,
                    detail="未知资源类型",
                ) from exc
        # 自动选中的详情在手机端先隐藏，只显示列表
        auto_selected = False
        if detail is None and select_first_result and result.items:
            auto_selected = True
            first_result = result.items[0]
            detail = repository.detail(
                first_result["resource_kind"],
                first_result["resource_id"],
            )
        filters = {"q": query, "kind": kind, "category": category}
        stats = repository.stats()
        previous_query = urlencode(
            {**filters, "page": max(1, result.page - 1)}
        )
        next_query = urlencode(
            {**filters, "page": min(result.page_count, result.page + 1)}
        )
        list_query = urlencode({**filters, "page": result.page})
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "detail": detail,
                "site_version": SITE_VERSION,
                "today_visitors": visitor_store.count_today(),
                "search": result,
                "page_size": page_size,
                "stats": stats,
                "external_collection_counts": EXTERNAL_COLLECTION_COUNTS,
                "filter_kind_labels": FILTER_KIND_LABELS,
                "item_category_labels": ITEM_CATEGORY_LABELS,
                "companion_category_labels": COMPANION_CATEGORY_LABELS,
                "title_group_options": repository.title_group_options(),
                "metadata_labels": METADATA_LABELS,
                "filters": filters,
                "is_overview": is_overview,
                "empty_resource_label": FILTER_KIND_LABELS.get(kind, "资源"),
                "previous_url": f"/?{previous_query}",
                "next_url": f"/?{next_query}",
                "list_url": f"/?{list_query}",
                "auto_selected": auto_selected,
            },
        )

    @app.post("/api/visit", response_class=JSONResponse)
    async def record_visit(request: Request) -> JSONResponse:
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
        count, visit_day, is_new = visitor_store.record(visitor_id)
        return JSONResponse(
            {"count": count, "visit_day": visit_day, "is_new": is_new}
        )

    @app.get("/", response_class=HTMLResponse)
    def index(
        request: Request,
        q: str = Query(default="", max_length=100),
        kind: str = Query(default=""),
        category: str = Query(default=""),
        page: int = Query(default=1, ge=1),
    ) -> HTMLResponse:
        # 打开道具、宠物、称号或检索后，默认选中当前列表的第一条。
        return render(
            request,
            query=q,
            kind=kind,
            category=category,
            page=page,
            select_first_result=bool(kind or q.strip() or category),
        )

    @app.get("/resources/{kind}/{resource_id}", response_class=HTMLResponse)
    def resource_detail(
        request: Request,
        kind: str,
        resource_id: int,
        q: str = Query(default="", max_length=100),
        filter_kind: str = Query(default="", alias="kind"),
        category: str = Query(default=""),
        page: int = Query(default=1, ge=1),
    ) -> HTMLResponse:
        try:
            ResourceKind(kind)
            detail = repository.detail(kind, resource_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="未知资源类型") from exc
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
        return render(
            request,
            query=q,
            kind=filter_kind,
            category=category,
            page=page,
            detail=detail,
        )

    @app.get("/api/search")
    def api_search(
        q: str = Query(default="", max_length=100),
        kind: str = Query(default=""),
        category: str = Query(default=""),
        page: int = Query(default=1, ge=1),
    ) -> dict:
        try:
            result = repository.search(
                query=q,
                kind=kind,
                category=category,
                page=page,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=404,
                detail="未知资源类型或筛选分类",
            ) from exc
        return {
            "items": result.items,
            "total": result.total,
            "page": result.page,
            "page_count": result.page_count,
        }

    @app.get("/api/resources/{kind}/{resource_id}")
    def api_detail(kind: str, resource_id: int) -> dict:
        try:
            detail = repository.detail(kind, resource_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="未知资源类型") from exc
        if detail is None:
            raise HTTPException(status_code=404, detail="没有找到该资源")
        return detail

    return app
