"""面向网站的只读资源查询。"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from xunxian_archive.models import ResourceKind
from xunxian_archive.web.item_use_types import describe_item_use_type
from xunxian_archive.web.links import quest_url


KIND_LABELS = {
    "item": "普通道具",
    "quest_item": "任务道具",
    "pet": "宠物",
    "title": "称号",
    "ride": "骑乘配置",
}

FILTER_KIND_LABELS = {
    "items": "道具",
    "companions": "宠物",
    "title": "称号",
}

ITEM_CATEGORY_LABELS = {
    "item": "普通道具",
    "quest_item": "任务道具",
}

COMPANION_CATEGORY_LABELS = {
    "servant_pet": "侍宠",
    "spirit_mount": "灵兽坐骑",
    "item_mount": "道具坐骑",
    "system_mount": "系统／场景坐骑",
    "turret": "炮台",
    "interaction": "互动配置",
    "unclassified": "其他",
}

COMPANION_TEST_PREDICATE = """
(
    resource.display_name LIKE '(x)%'
    OR resource.display_name LIKE '（x）%'
    OR resource.display_name LIKE '%测试%'
    OR resource.display_name LIKE '%占位%'
)
"""

COMPANION_INTERACTION_PREDICATE = """
(
    resource.display_name LIKE '（互）%'
    OR resource.display_name LIKE '(互)%'
    OR resource.display_name LIKE '%把目标%'
    OR resource.display_name LIKE '%把他%'
    OR resource.display_name LIKE '%把它%'
    OR resource.display_name LIKE '%托起来%'
    OR resource.display_name LIKE '%顶起来%'
)
"""

COMPANION_SYSTEM_PREDICATE = """
(
    resource.display_name LIKE '%副本%'
    OR resource.display_name LIKE '%情景%'
    OR resource.display_name LIKE '%九天劫%'
    OR resource.display_name LIKE '%混元劫%'
    OR resource.display_name LIKE '%不周山%'
    OR resource.display_name LIKE '%拉力赛%'
    OR resource.display_name LIKE '（特）%'
    OR resource.display_name LIKE '(特)%'
    OR resource.display_name LIKE '%NPC%'
    OR resource.display_name LIKE '%人）'
    OR resource.display_name LIKE '%人)'
    OR resource.display_name LIKE '%船%'
)
"""

COMPANION_TURRET_PREDICATE = """
resource.display_name LIKE '%炮%'
"""

COMPANION_HAS_PET_RELATION = """
EXISTS (
    SELECT 1
    FROM resource_relation pet_ride
    WHERE pet_ride.relation_type = 'uses_ride'
      AND pet_ride.source_kind = 'pet'
      AND pet_ride.target_kind = 'ride'
      AND pet_ride.target_id = resource.resource_id
)
"""

COMPANION_HAS_DIRECT_ITEM = """
EXISTS (
    SELECT 1
    FROM resource_relation item_ride
    WHERE item_ride.relation_type = 'grants_ride'
      AND item_ride.source_kind = 'item'
      AND item_ride.target_kind = 'ride'
      AND item_ride.target_id = resource.resource_id
)
"""

COMPANION_SCOPE_SQL = f"""
(
    resource.resource_kind = 'pet'
    OR (
        resource.resource_kind = 'ride'
        AND NOT ({COMPANION_HAS_PET_RELATION})
        AND NOT ({COMPANION_TEST_PREDICATE})
    )
)
"""

COMPANION_CATEGORY_SQL = f"""
CASE
    WHEN resource.resource_kind = 'pet'
      AND EXISTS (
          SELECT 1
          FROM resource_relation pet_ride
          WHERE pet_ride.relation_type = 'uses_ride'
            AND pet_ride.source_kind = 'pet'
            AND pet_ride.source_id = resource.resource_id
            AND pet_ride.target_kind = 'ride'
      )
    THEN 'spirit_mount'
    WHEN resource.resource_kind = 'pet'
    THEN 'servant_pet'
    WHEN {COMPANION_HAS_DIRECT_ITEM}
    THEN 'item_mount'
    WHEN {COMPANION_INTERACTION_PREDICATE}
    THEN 'interaction'
    WHEN {COMPANION_TURRET_PREDICATE}
    THEN 'turret'
    WHEN {COMPANION_SYSTEM_PREDICATE}
    THEN 'system_mount'
    ELSE 'unclassified'
END
"""

RELATION_LABELS = {
    "grants_pet": "使用后获得宠物",
    "grants_ride": "使用后获得骑乘配置",
    "grants_title": "使用后获得称号",
    "uses_ride": "使用骑乘配置",
}

ITEM_ACQUISITION_TYPE_LABELS = {
    1001: "坐骑道具",
    6000: "未鉴定宠物蛋",
    6001: "宠物蛋",
    6011: "侍宠蛋",
    6012: "原形宠物蛋",
    6013: "骑宠蛋",
    6014: "赠品宠物蛋",
    6015: "圣兽侍宠蛋",
}

COLOR_MARKUP_RE = re.compile(r"<c(?::[^>]*)?>", re.IGNORECASE)
GENERIC_EFFECT_NOTE_RE = re.compile(r"^通用(?:\d+|[一二三四五六七八九十]+)$")


def _clean_game_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = COLOR_MARKUP_RE.sub("", value)
    if len(cleaned) >= 2 and cleaned.startswith('"') and cleaned.endswith('"'):
        cleaned = cleaned[1:-1].replace('""', '"')
    return (
        cleaned
        .replace("\\r\\n", "\n")
        .replace("\\n", "\n")
        .replace("\\r", "\n")
        .replace("\\t", "\t")
    )


def _is_generic_effect_note(value: str | None) -> bool:
    return bool(value and GENERIC_EFFECT_NOTE_RE.fullmatch(value.strip()))


def _format_game_money(value: object) -> str | None:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        return None
    remainder = value
    parts: list[str] = []
    for unit_value, unit_name in (
        (1_000_000, "砖"),
        (10_000, "金"),
        (100, "银"),
        (1, "铜"),
    ):
        amount, remainder = divmod(remainder, unit_value)
        if amount:
            parts.append(f"{amount}{unit_name}")
    return "".join(parts)


def _format_item_price(value: object, *, tradable: bool) -> str:
    amount = _format_game_money(value)
    if amount is None:
        return "-"
    currency = "流通金" if tradable else "绑定金"
    return f"{currency}：{amount}"


def _format_title_attribute_value(value_kind: str, raw_value: int) -> str:
    if value_kind == "percentage":
        absolute = abs(raw_value)
        whole, decimal = divmod(absolute, 100)
        amount = (
            str(whole)
            if decimal == 0
            else f"{whole}.{decimal:02d}".rstrip("0")
        )
        sign = "+" if raw_value > 0 else ("-" if raw_value < 0 else "")
        return f"{sign}{amount}%"
    sign = "+" if raw_value > 0 else ""
    return f"{sign}{raw_value}"


def _use_effect(
    row: sqlite3.Row,
    resolved_targets: list[dict[str, Any]],
) -> dict[str, Any]:
    description = _clean_game_text(row["description"])
    parameters = json.loads(row["parameters_json"])
    return {
        **dict(row),
        "description": description,
        "display_description": (
            None if _is_generic_effect_note(description) else description
        ),
        "resolved_name": _clean_game_text(row["resolved_name"]),
        "resolved_description": _clean_game_text(row["resolved_description"]),
        "parameters": parameters,
        "type_description": describe_item_use_type(
            row["use_type_id"],
            parameters,
            description,
        ),
        "resolved_targets": resolved_targets,
    }


QUEST_RELATION_LABELS = {
    "reward": "任务奖励",
    "required": "任务要求",
    "objective": "任务目标",
    "accept_endpoint": "触发接取",
    "submit_endpoint": "提交对象",
    "title_reward": "称号奖励",
    "pet_reward": "宠物奖励",
}

METADATA_LABELS = {
    "item_type_id": "道具类型",
    "icon_key": "图标键",
    "model_id": "模型",
    "text_id": "说明文本",
    "quality": "品质",
    "buy_price": "购买价格",
    "sell_price": "出售价格",
    "level_requirement": "等级要求",
    "use_effect_raw": "使用效果引用",
    "stack_limit": "堆叠上限",
    "character_id": "角色外形",
    "pet_appearance_id": "宠物外形",
    "internal_name": "内部配置名",
    "player_names": "玩家名称",
    "pet_attributes": "四维属性",
    "ride_id": "骑乘配置",
    "note": "资料备注",
    "title_group_name": "称号分组",
    "description": "称号说明",
    "acquisition_hint": "获得条件",
}

TITLE_GROUP_FAMILY_LABELS = {
    1: "对抗与竞赛",
    2: "地域与阵营",
    3: "成长与生活",
    4: "劫境",
    5: "社交关系",
    6: "风物志与收集",
    7: "副本与挑战",
    8: "活动与荣誉",
    9: "剧情与支线",
    10: "其他",
}


@dataclass(frozen=True, slots=True)
class SearchResult:
    items: list[dict[str, Any]]
    total: int
    page: int
    page_count: int


class CatalogRepository:
    def __init__(self, database_path: Path):
        if not database_path.is_file():
            raise FileNotFoundError(
                f"资源数据库不存在：{database_path}；请先运行构建命令"
            )
        self.database_path = database_path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            f"file:{self.database_path.resolve()}?mode=ro",
            uri=True,
        )
        connection.row_factory = sqlite3.Row
        return connection

    def stats(self) -> dict[str, Any]:
        with self._connect() as connection:
            counts = {
                row["resource_kind"]: row["count"]
                for row in connection.execute(
                    """
                    SELECT resource_kind, COUNT(*) AS count
                    FROM resource
                    GROUP BY resource_kind
                    """
                )
            }
            relation_count = connection.execute(
                "SELECT COUNT(*) FROM resource_relation"
            ).fetchone()[0]
            quest_link_count = connection.execute(
                "SELECT COUNT(*) FROM quest_resource_link"
            ).fetchone()[0]
            companion_count = connection.execute(
                f"""
                SELECT COUNT(*)
                FROM resource
                WHERE {COMPANION_SCOPE_SQL}
                """
            ).fetchone()[0]
        return {
            "resource_count": sum(counts.values()),
            "counts": counts,
            "filter_counts": {
                "items": counts.get("item", 0) + counts.get("quest_item", 0),
                "companions": companion_count,
                "title": counts.get("title", 0),
            },
            "relation_count": relation_count,
            "quest_link_count": quest_link_count,
        }

    def title_group_options(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                WITH group_definitions AS (
                    SELECT DISTINCT
                        display_name AS group_name,
                        family_id AS group_family_id
                    FROM title_group

                    UNION

                    SELECT DISTINCT
                        json_extract(
                            metadata_json,
                            '$.title_group_name'
                        ) AS group_name,
                        json_extract(
                            metadata_json,
                            '$.title_group_family_id'
                        ) AS group_family_id
                    FROM resource
                    WHERE resource_kind = 'title'
                      AND json_extract(
                          metadata_json,
                          '$.title_group_name'
                      ) IS NOT NULL
                )
                SELECT
                    definition.group_name,
                    definition.group_family_id,
                    (
                        SELECT COUNT(*)
                        FROM resource
                        WHERE resource_kind = 'title'
                          AND json_extract(
                              metadata_json,
                              '$.title_group_name'
                          ) = definition.group_name
                          AND (
                              (
                                  definition.group_family_id IS NULL
                                  AND json_extract(
                                      metadata_json,
                                      '$.title_group_family_id'
                                  ) IS NULL
                              )
                              OR json_extract(
                                  metadata_json,
                                  '$.title_group_family_id'
                              ) = definition.group_family_id
                          )
                    ) AS title_count
                FROM group_definitions AS definition
                ORDER BY
                    CASE
                        WHEN group_name = '-'
                        THEN 1 ELSE 0
                    END,
                    group_family_id,
                    group_name COLLATE NOCASE
                """
            ).fetchall()
        families = []
        for family_id, family_label in TITLE_GROUP_FAMILY_LABELS.items():
            groups = [
                {
                    "value": f"group:{row['group_name']}",
                    "label": row["group_name"],
                    "title_count": row["title_count"],
                }
                for row in rows
                if row["group_family_id"] == family_id
                and row["group_name"] != "-"
            ]
            if groups:
                families.append(
                    {
                        "value": f"family:{family_id}",
                        "label": family_label,
                        "title_count": sum(
                            group["title_count"] for group in groups
                        ),
                        "groups": groups,
                    }
                )
        if any(row["group_name"] == "-" for row in rows):
            families.append(
                {
                    "value": "group:-",
                    "label": "未分组",
                    "title_count": next(
                        row["title_count"]
                        for row in rows
                        if row["group_name"] == "-"
                    ),
                    "groups": [],
                }
            )
        return families

    def title_group_filter_values(self) -> set[str]:
        return {
            option["value"]
            for family in self.title_group_options()
            for option in (family, *family["groups"])
        }

    def search(
        self,
        *,
        query: str = "",
        kind: str = "",
        category: str = "",
        page: int = 1,
        page_size: int = 15,
    ) -> SearchResult:
        if kind and kind not in {"items", "companions"}:
            ResourceKind(kind)
        if category:
            category_labels = (
                ITEM_CATEGORY_LABELS
                if kind == "items"
                else (
                    COMPANION_CATEGORY_LABELS
                    if kind == "companions"
                    else (
                        self.title_group_filter_values()
                        if kind == "title"
                        else set()
                    )
                )
            )
            if category not in category_labels:
                raise ValueError(f"未知筛选分类：{category}")
        page = max(1, page)
        clauses: list[str] = []
        parameters: list[Any] = []
        order_parameters: list[Any] = []
        # A bare integer in SQLite ORDER BY is a positional column reference.
        # Keep the no-query value as an expression so it remains a true constant.
        search_priority = "(2 + 0)"
        if kind == "items":
            if category:
                clauses.append("resource_kind = ?")
                parameters.append(category)
            else:
                clauses.append("resource_kind IN ('item', 'quest_item')")
        elif kind == "companions":
            clauses.append(COMPANION_SCOPE_SQL)
            if category:
                clauses.append(f"({COMPANION_CATEGORY_SQL}) = ?")
                parameters.append(category)
        elif kind == "title":
            clauses.append("resource_kind = 'title'")
            if category:
                filter_type, filter_value = category.split(":", 1)
                if filter_type == "family":
                    clauses.append(
                        """
                        json_extract(
                            metadata_json,
                            '$.title_group_family_id'
                        ) = ?
                        """
                    )
                    parameters.append(int(filter_value))
                else:
                    clauses.append(
                        "json_extract(metadata_json, '$.title_group_name') = ?"
                    )
                    parameters.append(filter_value)
        elif kind:
            clauses.append("resource_kind = ?")
            parameters.append(kind)
        normalized_query = query.strip()
        if normalized_query:
            clauses.append(
                """
                (
                    display_name LIKE ? ESCAPE '\\'
                    OR CAST(resource_id AS TEXT) = ?
                    OR COALESCE(json_extract(metadata_json, '$.description'), '')
                       LIKE ? ESCAPE '\\'
                    OR COALESCE(json_extract(metadata_json, '$.acquisition_hint'), '')
                       LIKE ? ESCAPE '\\'
                )
                """
            )
            escaped = (
                normalized_query
                .replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_")
            )
            like = f"%{escaped}%"
            parameters.extend([like, normalized_query, like, like])
            search_priority = """
                CASE
                    WHEN display_name = ? THEN 0
                    WHEN display_name LIKE ? ESCAPE '\\' THEN 1
                    ELSE 2
                END
            """
            order_parameters.extend([normalized_query, f"{escaped}%"])
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        with self._connect() as connection:
            total = connection.execute(
                f"SELECT COUNT(*) FROM resource {where}",
                parameters,
            ).fetchone()[0]
            page_count = max(1, (total + page_size - 1) // page_size)
            page = min(page, page_count)
            rows = connection.execute(
                f"""
                SELECT
                    resource_kind, resource_id, display_name, metadata_json,
                    {
                        COMPANION_CATEGORY_SQL
                        if kind == "companions"
                        else "NULL"
                    } AS companion_category,
                    (
                        SELECT COUNT(*) FROM resource_relation relation
                        WHERE relation.source_kind = resource.resource_kind
                          AND relation.source_id = resource.resource_id
                    ) AS relation_count,
                    (
                        SELECT COUNT(*) FROM quest_resource_link quest_link
                        WHERE quest_link.resource_kind = resource.resource_kind
                          AND quest_link.resource_id = resource.resource_id
                    ) AS quest_count
                FROM resource
                {where}
                ORDER BY
                    {search_priority},
                    CASE
                        WHEN display_name LIKE '*%'
                          OR display_name LIKE '%占位%'
                          OR display_name LIKE '(x)%'
                          OR display_name LIKE '（废）%'
                        THEN 1 ELSE 0
                    END,
                    CASE resource_kind
                        WHEN 'item' THEN 1
                        WHEN 'quest_item' THEN 2
                        WHEN 'pet' THEN 3
                        WHEN 'title' THEN 4
                        WHEN 'ride' THEN 5
                    END,
                    display_name COLLATE NOCASE,
                    resource_id
                LIMIT ? OFFSET ?
                """,
                [
                    *parameters,
                    *order_parameters,
                    page_size,
                    (page - 1) * page_size,
                ],
            ).fetchall()
        items = []
        for row in rows:
            metadata = json.loads(row["metadata_json"])
            metadata.pop("title_group_family_id", None)
            items.append(
                {
                    **dict(row),
                    "kind_label": KIND_LABELS[row["resource_kind"]],
                    "category_label": COMPANION_CATEGORY_LABELS.get(
                        row["companion_category"]
                    ),
                    "metadata": metadata,
                }
            )
        return SearchResult(items, total, page, page_count)

    def detail(self, kind: str, resource_id: int) -> dict[str, Any] | None:
        ResourceKind(kind)
        with self._connect() as connection:
            resource = connection.execute(
                f"""
                SELECT
                    resource.*,
                    ({COMPANION_CATEGORY_SQL}) AS companion_category
                FROM resource AS resource
                WHERE resource_kind = ? AND resource_id = ?
                """,
                (kind, resource_id),
            ).fetchone()
            if resource is None:
                return None
            outgoing = connection.execute(
                """
                SELECT
                    relation.*, target.display_name AS target_name
                FROM resource_relation relation
                JOIN resource target
                  ON target.resource_kind = relation.target_kind
                 AND target.resource_id = relation.target_id
                WHERE relation.source_kind = ? AND relation.source_id = ?
                ORDER BY relation.relation_type, target.display_name
                """,
                (kind, resource_id),
            ).fetchall()
            incoming = connection.execute(
                """
                SELECT
                    relation.*, source.display_name AS source_name
                FROM resource_relation relation
                JOIN resource source
                  ON source.resource_kind = relation.source_kind
                 AND source.resource_id = relation.source_id
                WHERE relation.target_kind = ? AND relation.target_id = ?
                ORDER BY relation.relation_type, source.display_name
                """,
                (kind, resource_id),
            ).fetchall()
            quest_links = connection.execute(
                """
                SELECT *
                FROM quest_resource_link
                WHERE resource_kind = ? AND resource_id = ?
                ORDER BY
                    CASE relation_type
                        WHEN 'reward' THEN 1
                        WHEN 'title_reward' THEN 1
                        WHEN 'required' THEN 2
                        WHEN 'objective' THEN 3
                        WHEN 'accept_endpoint' THEN 4
                        WHEN 'submit_endpoint' THEN 5
                        ELSE 6
                    END,
                    quest_name,
                    quest_id
                """,
                (kind, resource_id),
            ).fetchall()
            use_effects: list[sqlite3.Row] = []
            effect_targets: dict[int, list[dict[str, Any]]] = {}
            item_description: sqlite3.Row | None = None
            if kind == "item":
                use_effects = connection.execute(
                    """
                    SELECT
                        effect.*,
                        link.slot_no,
                        link.amount,
                        detail.detail_kind,
                        detail.display_name AS resolved_name,
                        detail.description AS resolved_description,
                        detail.source_file AS detail_source_file,
                        detail.source_row AS detail_source_row
                    FROM item_use_link link
                    JOIN item_use_effect effect USING (effect_id)
                    LEFT JOIN item_use_detail detail USING (effect_id)
                    WHERE link.item_id = ?
                    ORDER BY link.slot_no
                    """,
                    (resource_id,),
                ).fetchall()
                effect_target_rows = connection.execute(
                    """
                    SELECT
                        CAST(
                            json_extract(relation.path_json, '$[1].id')
                            AS INTEGER
                        ) AS effect_id,
                        relation.relation_type,
                        relation.target_kind,
                        relation.target_id,
                        target.display_name AS target_name
                    FROM resource_relation relation
                    JOIN resource target
                      ON target.resource_kind = relation.target_kind
                     AND target.resource_id = relation.target_id
                    WHERE relation.source_kind = 'item'
                      AND relation.source_id = ?
                      AND relation.relation_type IN (
                          'grants_pet', 'grants_ride', 'grants_title'
                      )
                      AND json_extract(
                          relation.path_json, '$[1].kind'
                      ) = 'item_use_effect'
                    ORDER BY
                        effect_id,
                        CASE relation.relation_type
                            WHEN 'grants_pet' THEN 1
                            WHEN 'grants_ride' THEN 2
                            WHEN 'grants_title' THEN 3
                            ELSE 4
                        END,
                        target.display_name,
                        target.resource_id
                    """,
                    (resource_id,),
                ).fetchall()
                for target in effect_target_rows:
                    effect_targets.setdefault(target["effect_id"], []).append(
                        {
                            **dict(target),
                            "relation_label": RELATION_LABELS[
                                target["relation_type"]
                            ],
                            "target_kind_label": KIND_LABELS[
                                target["target_kind"]
                            ],
                        }
                    )
                raw_item_metadata = json.loads(resource["metadata_json"])
                text_id = raw_item_metadata.get("text_id")
                if isinstance(text_id, int):
                    item_description = connection.execute(
                        """
                        SELECT
                            text_id, description, source_file, source_row
                        FROM item_text
                        WHERE text_id = ?
                        """,
                        (text_id,),
                    ).fetchone()
            raw_metadata = json.loads(resource["metadata_json"])
            title_attribute_rows: list[sqlite3.Row] = []
            title_attribute_issue_rows: list[sqlite3.Row] = []
            if kind == "title":
                title_attribute_rows = connection.execute(
                    """
                    SELECT
                        attribute_scope, slot_no, attribute_id,
                        attribute_name, value_kind, raw_value
                    FROM title_attribute
                    WHERE title_id = ?
                    ORDER BY
                        CASE attribute_scope
                            WHEN 'active' THEN 1
                            ELSE 2
                        END,
                        slot_no
                    """,
                    (resource_id,),
                ).fetchall()
                title_attribute_issue_rows = connection.execute(
                    """
                    SELECT issue.detail
                    FROM parse_issue issue
                    JOIN resource_source source
                      ON source.raw_record_id = issue.raw_record_id
                    WHERE source.resource_kind = 'title'
                      AND source.resource_id = ?
                      AND issue.issue_code = 'invalid_title_attribute'
                    ORDER BY issue.issue_id
                    """,
                    (resource_id,),
                ).fetchall()
            item_type_label: str | None = None
            pet_attribute_template: sqlite3.Row | None = None
            item_type_id = raw_metadata.get("item_type_id")
            if kind == "item" and isinstance(item_type_id, int):
                item_type = connection.execute(
                    """
                    SELECT display_name
                    FROM item_type
                    WHERE item_type_id = ?
                    """,
                    (item_type_id,),
                ).fetchone()
                if item_type is not None:
                    item_type_label = item_type["display_name"]
            attribute_template_id = raw_metadata.get(
                "attribute_template_id",
                raw_metadata.get("ability_id"),
            )
            if kind == "pet" and isinstance(attribute_template_id, int):
                pet_attribute_template = connection.execute(
                    """
                    SELECT
                        display_name, strength, physique, yuan_spirit, sinew
                    FROM pet_attribute_template
                    WHERE template_id = ?
                    """,
                    (attribute_template_id,),
                ).fetchone()
            skill_ride_id: int | None = None
            if kind == "ride":
                skill_ride_id = resource_id
            elif kind == "pet" and isinstance(raw_metadata.get("ride_id"), int):
                skill_ride_id = raw_metadata["ride_id"]

            ride_skills: list[sqlite3.Row] = []
            ride_skill_context: dict[str, Any] | None = None
            if skill_ride_id is not None:
                ride = connection.execute(
                    """
                    SELECT display_name
                    FROM resource
                    WHERE resource_kind = 'ride' AND resource_id = ?
                    """,
                    (skill_ride_id,),
                ).fetchone()
                ride_skill_context = {
                    "ride_id": skill_ride_id,
                    "ride_name": (
                        ride["display_name"] if ride is not None else "未收录骑乘配置"
                    ),
                    "inherited_from_ride": kind == "pet",
                }
                ride_skills = connection.execute(
                    """
                    SELECT
                        link.skill_id,
                        link.slot_no,
                        link.source_file AS link_source_file,
                        link.source_row AS link_source_row,
                        skill.display_name,
                        skill.description,
                        skill.internal_note,
                        skill.icon_key,
                        skill.definition_source_type,
                        skill.source_file AS definition_source_file,
                        skill.source_row AS definition_source_row,
                        skill.description_source_file,
                        skill.description_source_row
                    FROM ride_skill_link link
                    LEFT JOIN ride_skill skill USING (skill_id)
                    WHERE link.ride_id = ?
                    ORDER BY link.slot_no
                    """,
                    (skill_ride_id,),
                ).fetchall()

            acquisition_rows: list[sqlite3.Row] = []
            if kind == "pet":
                acquisition_rows = connection.execute(
                    """
                    SELECT
                        item.resource_id AS item_id,
                        item.display_name AS item_name,
                        item.metadata_json AS item_metadata_json,
                        effect.description AS effect_description,
                        'direct_pet' AS acquisition_route,
                        NULL AS via_pet_id,
                        NULL AS via_pet_name
                    FROM resource_relation relation
                    JOIN resource item
                      ON item.resource_kind = 'item'
                     AND item.resource_id = relation.source_id
                    LEFT JOIN item_use_effect effect
                      ON effect.effect_id = CAST(
                           json_extract(relation.path_json, '$[1].id')
                           AS INTEGER
                         )
                    WHERE relation.source_kind = 'item'
                      AND relation.target_kind = 'pet'
                      AND relation.target_id = ?
                      AND relation.relation_type = 'grants_pet'
                    ORDER BY item.display_name, item.resource_id
                    """,
                    (resource_id,),
                ).fetchall()
            elif kind == "ride":
                acquisition_rows = connection.execute(
                    """
                    SELECT
                        item.resource_id AS item_id,
                        item.display_name AS item_name,
                        item.metadata_json AS item_metadata_json,
                        effect.description AS effect_description,
                        'direct_ride' AS acquisition_route,
                        NULL AS via_pet_id,
                        NULL AS via_pet_name
                    FROM resource_relation direct_relation
                    JOIN resource item
                      ON item.resource_kind = 'item'
                     AND item.resource_id = direct_relation.source_id
                    LEFT JOIN item_use_effect effect
                      ON effect.effect_id = CAST(
                           json_extract(direct_relation.path_json, '$[1].id')
                           AS INTEGER
                         )
                    WHERE direct_relation.source_kind = 'item'
                      AND direct_relation.target_kind = 'ride'
                      AND direct_relation.target_id = ?
                      AND direct_relation.relation_type = 'grants_ride'

                    UNION ALL

                    SELECT
                        item.resource_id AS item_id,
                        item.display_name AS item_name,
                        item.metadata_json AS item_metadata_json,
                        effect.description AS effect_description,
                        'through_pet' AS acquisition_route,
                        pet.resource_id AS via_pet_id,
                        pet.display_name AS via_pet_name
                    FROM resource_relation item_pet
                    JOIN resource item
                      ON item.resource_kind = 'item'
                     AND item.resource_id = item_pet.source_id
                    LEFT JOIN item_use_effect effect
                      ON effect.effect_id = CAST(
                           json_extract(item_pet.path_json, '$[1].id')
                           AS INTEGER
                         )
                    JOIN resource pet
                      ON pet.resource_kind = 'pet'
                     AND pet.resource_id = item_pet.target_id
                    JOIN resource_relation pet_ride
                      ON pet_ride.source_kind = 'pet'
                     AND pet_ride.source_id = pet.resource_id
                     AND pet_ride.target_kind = 'ride'
                     AND pet_ride.target_id = ?
                     AND pet_ride.relation_type = 'uses_ride'
                    WHERE item_pet.source_kind = 'item'
                      AND item_pet.target_kind = 'pet'
                      AND item_pet.relation_type = 'grants_pet'
                    ORDER BY item_name, item_id, acquisition_route
                    """,
                    (resource_id, resource_id),
                ).fetchall()
            elif kind == "title":
                acquisition_rows = connection.execute(
                    """
                    SELECT
                        item.resource_id AS item_id,
                        item.display_name AS item_name,
                        item.metadata_json AS item_metadata_json,
                        effect.description AS effect_description,
                        'direct_title' AS acquisition_route,
                        NULL AS via_pet_id,
                        NULL AS via_pet_name
                    FROM resource_relation relation
                    JOIN resource item
                      ON item.resource_kind = 'item'
                     AND item.resource_id = relation.source_id
                    LEFT JOIN item_use_effect effect
                      ON effect.effect_id = CAST(
                           json_extract(relation.path_json, '$[1].id')
                           AS INTEGER
                         )
                    WHERE relation.source_kind = 'item'
                      AND relation.target_kind = 'title'
                      AND relation.target_id = ?
                      AND relation.relation_type = 'grants_title'
                    ORDER BY item.display_name, item.resource_id
                    """,
                    (resource_id,),
                ).fetchall()

        metadata = {
            key: _clean_game_text(value) if isinstance(value, str) else value
            for key, value in raw_metadata.items()
            if (
                key not in {
                    "ability_id",
                    "attribute_template_id",
                    "currency_is_tradable",
                    "ride_id",
                    "text_id",
                    "title_group_family_id",
                    "use_effect_raw",
                }
                and value is not None
                and value != ""
            )
        }
        if kind == "item":
            tradable = raw_metadata.get("currency_is_tradable") in (1, True)
            metadata.pop("buy_price", None)
            metadata.pop("sell_price", None)
            metadata["buy_price"] = _format_item_price(
                raw_metadata.get("buy_price"),
                tradable=tradable,
            )
            metadata["sell_price"] = _format_item_price(
                raw_metadata.get("sell_price"),
                tradable=tradable,
            )
        if kind == "pet" and "character_id" in metadata:
            metadata["pet_appearance_id"] = metadata.pop("character_id")
        if kind == "pet" and attribute_template_id is not None:
            if pet_attribute_template is None:
                metadata["pet_attributes"] = "配置尚未解析"
            else:
                attributes = (
                    ("力量", pet_attribute_template["strength"]),
                    ("体魄", pet_attribute_template["physique"]),
                    ("元神", pet_attribute_template["yuan_spirit"]),
                    ("筋骨", pet_attribute_template["sinew"]),
                )
                metadata["pet_attributes"] = "、".join(
                    f"{label} {value}"
                    for label, value in attributes
                    if value is not None
                ) or "配置尚未解析"
        if kind == "pet":
            metadata = {
                key: metadata[key]
                for key in (
                    "model_id",
                    "pet_appearance_id",
                    "note",
                    "pet_attributes",
                )
                if key in metadata
            }
        web_use_effects = [
            _use_effect(
                row,
                effect_targets.get(row["effect_id"], []),
            )
            for row in use_effects
        ]
        use_type_descriptions = list(
            dict.fromkeys(
                effect["type_description"] for effect in web_use_effects
            )
        )
        display_use_effects = [
            effect
            for effect in web_use_effects
            if (
                (
                    effect["display_description"]
                    and effect["display_description"] != resource["display_name"]
                )
                or effect["resolved_description"]
                or effect["resolved_targets"]
                or (
                    effect["amount"]
                    and not _is_generic_effect_note(effect["description"])
                )
            )
        ]
        title_attributes: dict[str, Any] = {
            "active": [],
            "passive": [],
            "active_unresolved": False,
            "passive_unresolved": False,
        }
        for row in title_attribute_rows:
            title_attributes[row["attribute_scope"]].append(
                {
                    **dict(row),
                    "display_value": _format_title_attribute_value(
                        row["value_kind"],
                        row["raw_value"],
                    ),
                }
            )
        for row in title_attribute_issue_rows:
            detail = row["detail"]
            if detail.startswith("active:"):
                title_attributes["active_unresolved"] = True
            elif detail.startswith("passive:"):
                title_attributes["passive_unresolved"] = True
        return {
            "resource_kind": kind,
            "resource_id": resource_id,
            "display_name": resource["display_name"],
            "kind_label": KIND_LABELS[kind],
            "category_label": (
                COMPANION_CATEGORY_LABELS.get(resource["companion_category"])
                if kind in {"pet", "ride"}
                else None
            ),
            "metadata": metadata,
            "source_file": resource["selected_source_file"],
            "source_row": resource["selected_source_row"],
            "outgoing": [self._relation(row, outgoing=True) for row in outgoing],
            "incoming": [self._relation(row, outgoing=False) for row in incoming],
            "quest_links": [
                {
                    **dict(row),
                    "relation_label": QUEST_RELATION_LABELS[row["relation_type"]],
                    "url": quest_url(row["quest_id"]),
                }
                for row in quest_links
            ],
            "use_effects": web_use_effects,
            "display_use_effects": display_use_effects,
            "use_type_descriptions": use_type_descriptions,
            "item_type_label": item_type_label,
            "item_description": (
                {
                    **dict(item_description),
                    "description": _clean_game_text(
                        item_description["description"]
                    ),
                }
                if item_description is not None
                else None
            ),
            "title_attributes": title_attributes,
            "ride_skill_context": ride_skill_context,
            "ride_skills": [
                {
                    **dict(row),
                    "description": _clean_game_text(row["description"]),
                    "internal_note": _clean_game_text(row["internal_note"]),
                    "is_resolved": row["display_name"] is not None,
                }
                for row in ride_skills
            ],
            "acquisition_items": self._acquisition_items(
                acquisition_rows,
                target_kind=kind,
            ),
        }

    @staticmethod
    def _relation(row: sqlite3.Row, *, outgoing: bool) -> dict[str, Any]:
        data = dict(row)
        data["relation_label"] = RELATION_LABELS.get(
            row["relation_type"], row["relation_type"]
        )
        data["path"] = json.loads(row["path_json"])
        if outgoing:
            data["linked_kind"] = row["target_kind"]
            data["linked_id"] = row["target_id"]
            data["linked_name"] = row["target_name"]
        else:
            data["linked_kind"] = row["source_kind"]
            data["linked_id"] = row["source_id"]
            data["linked_name"] = row["source_name"]
        data["linked_kind_label"] = KIND_LABELS[data["linked_kind"]]
        return data

    @staticmethod
    def _acquisition_items(
        rows: list[sqlite3.Row],
        *,
        target_kind: str,
    ) -> list[dict[str, Any]]:
        items: dict[int, dict[str, Any]] = {}
        for row in rows:
            item_id = row["item_id"]
            metadata = json.loads(row["item_metadata_json"])
            item_type_id = metadata.get("item_type_id")
            item = items.setdefault(
                item_id,
                {
                    "item_id": item_id,
                    "item_name": row["item_name"],
                    "item_type_id": item_type_id,
                    "effect_descriptions": [],
                    "routes": [],
                },
            )
            description = _clean_game_text(row["effect_description"])
            if (
                description
                and not _is_generic_effect_note(description)
                and description not in item["effect_descriptions"]
            ):
                item["effect_descriptions"].append(description)
            route = {
                "route": row["acquisition_route"],
                "via_pet_id": row["via_pet_id"],
                "via_pet_name": row["via_pet_name"],
            }
            if route not in item["routes"]:
                item["routes"].append(route)
        for item in items.values():
            evidence_text = " ".join(
                [item["item_name"], *item["effect_descriptions"]]
            )
            item_type_id = item["item_type_id"]
            if target_kind == "title":
                item["type_label"] = "称号获得道具"
            elif "骑宠蛋" in evidence_text:
                item["type_label"] = (
                    "赠品骑宠蛋"
                    if item_type_id == 6014 or "赠品" in item["item_name"]
                    else "骑宠蛋"
                )
            elif "圣兽侍宠蛋" in evidence_text or "神兽侍宠蛋" in evidence_text:
                item["type_label"] = "圣兽侍宠蛋"
            elif "侍宠蛋" in evidence_text:
                item["type_label"] = "侍宠蛋"
            elif (
                "原形宠物蛋" in evidence_text
                or "原形蛋" in evidence_text
            ):
                item["type_label"] = "原形宠物蛋"
            elif "宠物蛋" in evidence_text or "封妖笼" in evidence_text:
                item["type_label"] = "宠物蛋"
            elif item_type_id in ITEM_ACQUISITION_TYPE_LABELS:
                item["type_label"] = ITEM_ACQUISITION_TYPE_LABELS[item_type_id]
            elif any(
                route["route"] == "direct_ride" for route in item["routes"]
            ):
                item["type_label"] = "特殊坐骑道具"
            elif target_kind == "ride":
                item["type_label"] = "骑宠获得道具"
            else:
                item["type_label"] = "宠物获得道具"
        return list(items.values())
