"""建立道具使用、宠物／骑乘、称号和任务关系。"""

from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from xunxian_archive.parsers.tabular import RawRow, iter_tabular_rows
from xunxian_archive.relations.quest_links import load_quest_resource_links


ITEM_USE = "mb/item/item_use.txt"
ITEM_PET = "mb/item/item_pet.txt"
ITEM_ADD_TITLE = "mb/etc/itemaddtitle.txt"
STATE_GROUP = "mb/skill/state_group.txt"
DEFINE_ARRAY = "mb/etc/define_array.txt"
COLLECTION_TEXT = "mb/collection/col_text.txt"
AVATAR_CUPBOARD = "mb/avatar_cupboard/avatar_cupboard.txt"
ITEM_RAND = "mb/item/item_rand.txt"
TREASURE_CARD = "mb/life/treasure_house/treasure_house_card.txt"
TREASURE_RAND_DATA = "mb/life/treasure_house/treasure_house_randdata.txt"
TREASURE_RAND_GROUP = "mb/life/treasure_house/treasure_house_randgroup.txt"
COMMON_SKILL = "mb/skill/skill_data_cmn.txt"
RIDE_SKILL_SOURCES = (
    ("mb/pet/car_skill.txt", "car_skill"),
    ("mb/skill/skill_data_npc.txt", "npc_skill"),
    ("mb/skill/skill_data_npc_1.txt", "npc_skill"),
    ("mb/skill/skill_data_npc_2.txt", "npc_skill"),
    ("mb/skill/skill_data_npc_3.txt", "npc_skill"),
    ("mb/skill/skill_data_npc_4.txt", "npc_skill"),
    ("mb/skill/skill_data_npc_pet.txt", "npc_skill"),
    ("mb/skill/skill_data_npc_pet1.txt", "npc_skill"),
)
RIDE_SKILL_COLUMNS = range(16, 22)
RIDE_ITEM_NAME_SUFFIX_RE = re.compile(
    r"[（(](?:\d+天(?:试用|绑定)?|试用|赠品|绑定|限时)[）)]$"
)


def _integer(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    try:
        return int(value.strip())
    except ValueError:
        return None


def _at(values: tuple[str, ...], index: int) -> str | None:
    if index >= len(values):
        return None
    return values[index]


def _rows(path: Path, root: Path) -> Iterable[RawRow]:
    return iter_tabular_rows(path, source_root=root)


def _effect_references(raw_value: str | None) -> list[tuple[int, int | None]]:
    if not raw_value:
        return []
    values = [_integer(part) for part in raw_value.split("*")]
    references: list[tuple[int, int | None]] = []
    for offset in range(0, len(values), 2):
        effect_id = values[offset]
        if effect_id is None:
            continue
        amount = values[offset + 1] if offset + 1 < len(values) else None
        references.append((effect_id, amount))
    return references


def _ride_item_name(display_name: str) -> str | None:
    if "占位" in display_name or "···" in display_name:
        return None
    cleaned = display_name.strip()
    while True:
        without_suffix = RIDE_ITEM_NAME_SUFFIX_RE.sub("", cleaned).strip()
        if without_suffix == cleaned:
            return cleaned or None
        cleaned = without_suffix


def _apply_ride_display_names(
    connection: sqlite3.Connection,
    findings: Counter[str],
) -> None:
    candidates: dict[int, dict[str, Any]] = {}
    for row in connection.execute(
        """
        SELECT
            relation.target_id AS ride_id,
            ride.display_name AS internal_name,
            ride.metadata_json,
            item.resource_id AS item_id,
            item.display_name AS item_name
        FROM resource_relation relation
        JOIN resource ride
          ON ride.resource_kind = 'ride'
         AND ride.resource_id = relation.target_id
        JOIN resource item
          ON item.resource_kind = 'item'
         AND item.resource_id = relation.source_id
        WHERE relation.relation_type = 'grants_ride'
        ORDER BY relation.target_id, item.resource_id
        """
    ):
        candidate = candidates.setdefault(
            row["ride_id"],
            {
                "internal_name": row["internal_name"],
                "metadata_json": row["metadata_json"],
                "names": [],
            },
        )
        item_name = _ride_item_name(row["item_name"])
        if item_name and item_name not in candidate["names"]:
            candidate["names"].append(item_name)

    for ride_id, candidate in candidates.items():
        names = candidate["names"]
        if not names:
            findings["ride_public_names_without_candidate"] += 1
            continue
        metadata = json.loads(candidate["metadata_json"])
        internal_name = candidate["internal_name"]
        if len(names) == 1:
            public_name = names[0]
            if public_name != internal_name:
                metadata["internal_name"] = internal_name
                connection.execute(
                    """
                    UPDATE resource
                    SET display_name = ?, metadata_json = ?
                    WHERE resource_kind = 'ride' AND resource_id = ?
                    """,
                    (
                        public_name,
                        json.dumps(metadata, ensure_ascii=False),
                        ride_id,
                    ),
                )
                findings["ride_public_names_applied"] += 1
            else:
                findings["ride_public_names_already_match"] += 1
        else:
            metadata["player_names"] = "、".join(names)
            connection.execute(
                """
                UPDATE resource
                SET metadata_json = ?
                WHERE resource_kind = 'ride' AND resource_id = ?
                """,
                (json.dumps(metadata, ensure_ascii=False), ride_id),
            )
            findings["ride_public_name_conflicts"] += 1


def _insert_relation(
    connection: sqlite3.Connection,
    *,
    source_kind: str,
    source_id: int,
    target_kind: str,
    target_id: int,
    relation_type: str,
    evidence_type: str,
    source_file: str,
    source_row: int,
    path: list[dict[str, Any]],
    build_id: str,
) -> int:
    return connection.execute(
        """
        INSERT OR IGNORE INTO resource_relation (
            source_kind, source_id, target_kind, target_id, relation_type,
            evidence_type, confidence, source_file, source_row, path_json,
            raw_values_json, build_id
        ) VALUES (?, ?, ?, ?, ?, ?, 1.0, ?, ?, ?, NULL, ?)
        """,
        (
            source_kind,
            source_id,
            target_kind,
            target_id,
            relation_type,
            evidence_type,
            source_file,
            source_row,
            json.dumps(path, ensure_ascii=False),
            build_id,
        ),
    ).rowcount


def build_core_relations(
    *,
    original_root: Path,
    database_path: Path,
    quest_contract_path: Path,
    quest_schema_path: Path,
) -> dict[str, Any]:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    build_id = connection.execute(
        "SELECT build_id FROM build_metadata"
    ).fetchone()[0]
    resources = {
        (row["resource_kind"], row["resource_id"]): row
        for row in connection.execute(
            """
            SELECT resource_kind, resource_id, display_name, metadata_json,
                   selected_source_file, selected_source_row, raw_values_json
            FROM resource
            """
        )
    }
    findings: Counter[str] = Counter()
    missing_targets: Counter[str] = Counter()
    missing_examples: dict[str, list[int]] = defaultdict(list)

    effect_rows: dict[int, RawRow] = {}
    effect_values: dict[int, tuple[str, ...]] = {}
    for row in _rows(original_root / ITEM_USE, original_root):
        effect_id = _integer(_at(row.values, 0))
        if effect_id is None:
            findings["invalid_item_use_rows"] += 1
            continue
        if effect_id in effect_rows:
            findings["duplicate_item_use_ids"] += 1
            continue
        effect_rows[effect_id] = row
        effect_values[effect_id] = row.values

    item_pet_sources: dict[int, RawRow] = {}
    for row in _rows(original_root / ITEM_PET, original_root):
        item_id = _integer(_at(row.values, 1))
        if item_id is not None:
            item_pet_sources.setdefault(item_id, row)

    title_mappings: dict[int, tuple[int, RawRow]] = {}
    for row in _rows(original_root / ITEM_ADD_TITLE, original_root):
        mapping_id = _integer(_at(row.values, 1))
        title_id = _integer(_at(row.values, 3))
        if mapping_id is not None and title_id is not None:
            title_mappings.setdefault(mapping_id, (title_id, row))

    state_groups: dict[int, dict[str, Any]] = {}
    state_group_path = original_root / STATE_GROUP
    if state_group_path.is_file():
        for row in _rows(state_group_path, original_root):
            state_id = _integer(_at(row.values, 1))
            description = (_at(row.values, 2) or "").strip()
            if state_id is None or not description:
                continue
            state_groups.setdefault(
                state_id,
                {
                    "display_name": (_at(row.values, 0) or "").strip() or None,
                    "description": description,
                    "source_file": row.source_file,
                    "source_row": row.source_row,
                },
            )

    state_arrays: dict[int, dict[str, Any]] = {}
    define_array_path = original_root / DEFINE_ARRAY
    if define_array_path.is_file():
        for row in _rows(define_array_path, original_root):
            array_id = _integer(_at(row.values, 0))
            if array_id is None:
                continue
            state_ids = [
                state_id
                for state_id in (
                    _integer(part)
                    for part in (_at(row.values, 1) or "").split("*")
                )
                if state_id is not None
            ]
            states = [
                state_groups[state_id]
                for state_id in dict.fromkeys(state_ids)
                if state_id in state_groups
            ]
            if not states:
                continue
            array_name = (
                (_at(row.values, 2) or "").lstrip("*").strip()
                or f"状态数组 {array_id}"
            )
            state_arrays.setdefault(
                array_id,
                {
                    "display_name": array_name,
                    "description": (
                        "使用时按配置档位应用下列状态之一：\n"
                        + "\n".join(
                            (
                                f"{state['display_name']}："
                                f"{state['description']}"
                            )
                            for state in states
                        )
                    ),
                    "source_file": row.source_file,
                    "source_row": row.source_row,
                },
            )

    collection_texts: dict[int, dict[str, Any]] = {}
    collection_text_path = original_root / COLLECTION_TEXT
    if collection_text_path.is_file():
        for row in _rows(collection_text_path, original_root):
            collection_id = _integer(_at(row.values, 1))
            display_name = (_at(row.values, 0) or "").strip()
            if collection_id is None or not display_name:
                continue
            description = (_at(row.values, 3) or "").strip()
            collection_texts.setdefault(
                collection_id,
                {
                    "display_name": display_name,
                    "description": (
                        description or f"使用后收录风物志：{display_name}"
                    ),
                    "source_file": row.source_file,
                    "source_row": row.source_row,
                },
            )

    avatar_entries: dict[int, dict[str, Any]] = {}
    avatar_path = original_root / AVATAR_CUPBOARD
    if avatar_path.is_file():
        for row in _rows(avatar_path, original_root):
            avatar_id = _integer(_at(row.values, 1))
            display_name = (_at(row.values, 0) or "").strip()
            if avatar_id is None or not display_name:
                continue
            description = (_at(row.values, 16) or "").strip()
            avatar_entries.setdefault(
                avatar_id,
                {
                    "display_name": display_name,
                    "description": (
                        description or f"使用后解锁外观：{display_name}"
                    ),
                    "source_file": row.source_file,
                    "source_row": row.source_row,
                },
            )

    loot_groups: dict[int, dict[str, Any]] = {}
    item_rand_path = original_root / ITEM_RAND
    if item_rand_path.is_file():
        for row in _rows(item_rand_path, original_root):
            group_id = _integer(_at(row.values, 1))
            group_name = (_at(row.values, 0) or "").strip()
            if group_id is None or not group_name:
                continue
            entries: list[str] = []
            for column in range(4, len(row.values), 3):
                amount = _integer(_at(row.values, column))
                item_id = _integer(_at(row.values, column + 1))
                if amount is None or item_id is None:
                    continue
                item = resources.get(("item", item_id))
                item_name = (
                    item["display_name"]
                    if item is not None
                    else f"未收录道具 {item_id}"
                )
                entries.append(f"{item_name} ×{amount}")
            description = f"{group_name}（掉落组 {group_id}）"
            if entries:
                description += "：\n" + "、".join(entries)
            loot_groups.setdefault(
                group_id,
                {
                    "display_name": group_name,
                    "description": description,
                    "source_file": row.source_file,
                    "source_row": row.source_row,
                },
            )

    treasure_cards: dict[int, dict[str, Any]] = {}
    treasure_card_path = original_root / TREASURE_CARD
    if treasure_card_path.is_file():
        for row in _rows(treasure_card_path, original_root):
            card_id = _integer(_at(row.values, 1))
            card_name = (_at(row.values, 0) or "").strip()
            if card_id is None or not card_name:
                continue
            treasure_cards.setdefault(
                card_id,
                {
                    "display_name": card_name,
                    "description": (_at(row.values, 5) or "").strip() or None,
                },
            )

    treasure_pools: dict[int, dict[str, Any]] = {}
    treasure_pool_path = original_root / TREASURE_RAND_DATA
    if treasure_pool_path.is_file():
        for row in _rows(treasure_pool_path, original_root):
            pool_id = _integer(_at(row.values, 1))
            pool_name = (_at(row.values, 0) or "").strip()
            if pool_id is None or not pool_name:
                continue
            candidate_ids: list[int] = []
            for raw_candidate in row.values[4:]:
                card_id = _integer(raw_candidate.split("*", 1)[0])
                if card_id is not None:
                    candidate_ids.append(card_id)
            candidates = [
                treasure_cards[card_id]
                for card_id in dict.fromkeys(candidate_ids)
                if card_id in treasure_cards
            ]
            treasure_pools.setdefault(
                pool_id,
                {
                    "display_name": pool_name,
                    "candidates": candidates,
                },
            )

    treasure_groups: dict[int, dict[str, Any]] = {}
    treasure_group_path = original_root / TREASURE_RAND_GROUP
    if treasure_group_path.is_file():
        for row in _rows(treasure_group_path, original_root):
            group_id = _integer(_at(row.values, 1))
            group_name = (_at(row.values, 0) or "").strip()
            if group_id is None or not group_name:
                continue
            pool_ids = [
                pool_id
                for pool_id in (
                    _integer(part)
                    for part in (_at(row.values, 2) or "").split("*")
                )
                if pool_id is not None
            ]
            pools = [
                treasure_pools[pool_id]
                for pool_id in dict.fromkeys(pool_ids)
                if pool_id in treasure_pools
            ]
            sections: list[str] = []
            for pool in pools:
                candidate_names = list(
                    dict.fromkeys(
                        candidate["display_name"]
                        for candidate in pool["candidates"]
                    )
                )
                if candidate_names:
                    sections.append(
                        f"随机池「{pool['display_name']}」可能获得："
                        + "、".join(candidate_names)
                        + (
                            f"（源表共 {len(pool['candidates'])} 个候选项）"
                            if len(pool["candidates"]) != len(candidate_names)
                            else ""
                        )
                    )
                else:
                    sections.append(f"随机池：{pool['display_name']}")
            fixed_quantities = [
                quantity
                for quantity in (
                    _integer(raw_value.split("*", 1)[1])
                    if raw_value.startswith("1000000*")
                    and "*" in raw_value
                    else None
                    for raw_value in row.values[3:]
                )
                if quantity is not None
            ]
            if fixed_quantities:
                sections.append(
                    "固定数量："
                    + "、".join(f"{quantity:,}" for quantity in fixed_quantities)
                )
            if not sections:
                sections.append(f"使用后获得：{group_name}")
            treasure_groups.setdefault(
                group_id,
                {
                    "display_name": group_name,
                    "description": "\n".join(sections),
                    "source_file": row.source_file,
                    "source_row": row.source_row,
                },
            )

    common_skills: dict[int, dict[str, Any]] = {}
    common_skill_path = original_root / COMMON_SKILL
    if common_skill_path.is_file():
        for row in _rows(common_skill_path, original_root):
            skill_id = _integer(_at(row.values, 1))
            skill_name = (_at(row.values, 0) or "").strip()
            skill_description = (_at(row.values, 4) or "").strip()
            if skill_id is None or not skill_name or not skill_description:
                continue
            common_skills.setdefault(
                skill_id,
                {
                    "display_name": skill_name,
                    "description": skill_description,
                    "source_file": row.source_file,
                    "source_row": row.source_row,
                },
            )

    ride_skill_definitions: dict[int, dict[str, Any]] = {}
    for relative_path, source_type in RIDE_SKILL_SOURCES:
        for row in _rows(original_root / relative_path, original_root):
            if not any(value.strip() for value in row.values):
                continue
            skill_id = _integer(_at(row.values, 1))
            display_name = (_at(row.values, 0) or "").strip()
            if skill_id is None or not display_name:
                findings["invalid_ride_skill_rows"] += 1
                continue
            source_text = (_at(row.values, 4) or "").strip() or None
            if skill_id in ride_skill_definitions:
                definition = ride_skill_definitions[skill_id]
                if (
                    source_type == "npc_skill"
                    and definition["description"] is None
                    and source_text is not None
                ):
                    definition["description"] = source_text
                    definition["description_source_file"] = row.source_file
                    definition["description_source_row"] = row.source_row
                    definition["icon_key"] = (
                        (_at(row.values, 3) or "").strip() or None
                    )
                    findings["enriched_ride_skill_definition_candidates"] += 1
                    continue
                findings["shadowed_ride_skill_definition_candidates"] += 1
                continue
            ride_skill_definitions[skill_id] = {
                "skill_id": skill_id,
                "display_name": display_name,
                "description": (
                    source_text if source_type == "npc_skill" else None
                ),
                "internal_note": (
                    source_text if source_type == "car_skill" else None
                ),
                "icon_key": (
                    (_at(row.values, 3) or "").strip() or None
                    if source_type == "npc_skill"
                    else None
                ),
                "definition_source_type": source_type,
                "source_file": row.source_file,
                "source_row": row.source_row,
                "description_source_file": (
                    row.source_file if source_type == "npc_skill" else None
                ),
                "description_source_row": (
                    row.source_row if source_type == "npc_skill" else None
                ),
                "raw_values_json": json.dumps(row.values, ensure_ascii=False),
            }

    pets_by_ride: dict[int, list[sqlite3.Row]] = defaultdict(list)
    for key, resource in resources.items():
        if key[0] != "pet":
            continue
        metadata = json.loads(resource["metadata_json"])
        ride_id = metadata.get("ride_id")
        if isinstance(ride_id, int):
            pets_by_ride[ride_id].append(resource)

    with connection:
        referenced_ride_skill_ids: set[int] = set()
        for (kind, ride_id), resource in resources.items():
            if kind != "ride":
                continue
            values = tuple(json.loads(resource["raw_values_json"]))
            ride_has_skill_reference = False
            for slot_no, column in enumerate(RIDE_SKILL_COLUMNS, start=1):
                raw_value = (_at(values, column) or "").strip()
                if not raw_value:
                    continue
                skill_id = _integer(raw_value)
                if skill_id is None:
                    findings["invalid_ride_skill_references"] += 1
                    continue
                ride_has_skill_reference = True
                findings["ride_skill_references"] += 1
                connection.execute(
                    """
                    INSERT INTO ride_skill_link (
                        ride_id, skill_id, slot_no, source_file, source_row,
                        raw_value, build_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ride_id,
                        skill_id,
                        slot_no,
                        resource["selected_source_file"],
                        resource["selected_source_row"],
                        raw_value,
                        build_id,
                    ),
                )
                definition = ride_skill_definitions.get(skill_id)
                if definition is None:
                    findings["unresolved_ride_skill_references"] += 1
                    missing_targets["ride_skill"] += 1
                    if len(missing_examples["ride_skill"]) < 20:
                        missing_examples["ride_skill"].append(skill_id)
                    continue
                referenced_ride_skill_ids.add(skill_id)
                findings["resolved_ride_skill_links"] += 1
            if ride_has_skill_reference:
                findings["rides_with_skill_references"] += 1

        for skill_id in sorted(referenced_ride_skill_ids):
            definition = ride_skill_definitions[skill_id]
            connection.execute(
                """
                INSERT INTO ride_skill (
                    skill_id, display_name, description, internal_note,
                    icon_key, definition_source_type, source_file, source_row,
                    description_source_file, description_source_row,
                    raw_values_json, build_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    definition["skill_id"],
                    definition["display_name"],
                    definition["description"],
                    definition["internal_note"],
                    definition["icon_key"],
                    definition["definition_source_type"],
                    definition["source_file"],
                    definition["source_row"],
                    definition["description_source_file"],
                    definition["description_source_row"],
                    definition["raw_values_json"],
                    build_id,
                ),
            )
            findings["ride_skill_definitions"] += 1
            if definition["description"] is not None:
                findings["ride_skills_with_detailed_description"] += 1
            if definition["internal_note"] is not None:
                findings["ride_skills_with_internal_note"] += 1
            if (
                definition["description"] is not None
                and definition["internal_note"] is not None
            ):
                findings["ride_skills_enriched_with_detailed_description"] += 1

        for effect_id, row in effect_rows.items():
            values = effect_values[effect_id]
            use_type_id = _integer(_at(values, 1))
            connection.execute(
                """
                INSERT INTO item_use_effect (
                    effect_id, use_type_id, parameters_json, description,
                    source_file, source_row, raw_value, raw_values_json, build_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    effect_id,
                    use_type_id,
                    json.dumps(values[2:20], ensure_ascii=False),
                    (_at(values, 20) or "").lstrip("*") or None,
                    row.source_file,
                    row.source_row,
                    row.raw_value,
                    json.dumps(values, ensure_ascii=False),
                    build_id,
                ),
            )
            detail_kind: str | None = None
            detail_id: int | None = None
            detail: dict[str, Any] | None = None
            # Type 1 consistently applies the state-group ID in parameter 2.
            if use_type_id == 1:
                detail_kind = "state_group"
                detail_id = _integer(_at(values, 3))
                detail = state_groups.get(detail_id or -1)
            # Type 3 is a broad scripted-use family. Subtype 1388 is
            # confirmed to apply the state-group ID in parameter 2.
            elif use_type_id == 3 and _integer(_at(values, 2)) == 1388:
                detail_kind = "state_group"
                detail_id = _integer(_at(values, 3))
                detail = state_groups.get(detail_id or -1)
            # Type 2 consumes a collection scroll and references col_text.
            elif use_type_id == 2:
                detail_kind = "collection"
                detail_id = _integer(_at(values, 2))
                detail = collection_texts.get(detail_id or -1)
            # Type 176 unlocks an appearance in avatar_cupboard.
            elif use_type_id == 176:
                detail_kind = "avatar"
                detail_id = _integer(_at(values, 2))
                detail = avatar_entries.get(detail_id or -1)
            # Type 9 opens one or more item_rand loot groups.
            elif use_type_id == 9:
                detail_kind = "loot_table"
                group_ids = [
                    group_id
                    for group_id in (
                        _integer(_at(values, column))
                        for column in range(2, 7)
                    )
                    if group_id is not None
                ]
                groups = [
                    loot_groups[group_id]
                    for group_id in dict.fromkeys(group_ids)
                    if group_id in loot_groups
                ]
                if groups:
                    detail = {
                        "display_name": "礼包内容",
                        "description": "\n".join(
                            group["description"] for group in groups
                        ),
                        "source_file": groups[0]["source_file"],
                        "source_row": groups[0]["source_row"],
                    }
                else:
                    detail_id = group_ids[0] if group_ids else None
            # Type 56 references define_array, whose entries are state groups.
            elif use_type_id == 56:
                detail_kind = "state_array"
                detail_id = _integer(_at(values, 2))
                detail = state_arrays.get(detail_id or -1)
            # Type 141 opens a treasure-house random group.
            elif use_type_id == 141:
                detail_kind = "loot_table"
                detail_id = _integer(_at(values, 2))
                detail = treasure_groups.get(detail_id or -1)
            # Type 145 teaches/activates the referenced common combat skill.
            elif use_type_id == 145:
                detail_kind = "skill"
                detail_id = _integer(_at(values, 2))
                detail = common_skills.get(detail_id or -1)
            # Type 5 modes 16/17 are the confirmed instant recovery modes.
            elif use_type_id == 5 and _integer(_at(values, 2)) in (16, 17):
                health = _integer(_at(values, 3))
                mana = _integer(_at(values, 4))
                recoveries = []
                if health is not None and health > 0:
                    recoveries.append(f"{health:,} 点生命")
                if mana is not None and mana > 0:
                    recoveries.append(f"{mana:,} 点法力")
                if recoveries:
                    detail_kind = "parameter"
                    detail = {
                        "display_name": "恢复效果",
                        "description": (
                            "使用后恢复" + "和".join(recoveries) + "。"
                        ),
                        "source_file": row.source_file,
                        "source_row": row.source_row,
                    }
            # Type 27 grants character experience in parameter 1.
            elif use_type_id == 27:
                experience = _integer(_at(values, 2))
                if experience is not None and experience > 0:
                    detail_kind = "parameter"
                    detail = {
                        "display_name": "经验奖励",
                        "description": (
                            f"使用后增加 {experience:,} 点角色经验。"
                        ),
                        "source_file": row.source_file,
                        "source_row": row.source_row,
                    }

            if detail_kind is not None:
                if detail is not None:
                    connection.execute(
                        """
                        INSERT INTO item_use_detail (
                            effect_id, detail_kind, display_name, description,
                            source_file, source_row, build_id
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            effect_id,
                            detail_kind,
                            detail["display_name"],
                            detail["description"],
                            detail["source_file"],
                            detail["source_row"],
                            build_id,
                        ),
                    )
                    findings["item_use_effect_details"] += 1
                    findings[
                        f"item_use_effect_details:{detail_kind}"
                    ] += 1
                else:
                    findings[f"missing_item_use_details:{detail_kind}"] += 1
                    if detail_id is not None and len(
                        missing_examples[detail_kind]
                    ) < 20:
                        missing_examples[detail_kind].append(detail_id)

        for (kind, item_id), resource in resources.items():
            if kind != "item":
                continue
            metadata = json.loads(resource["metadata_json"])
            references = _effect_references(metadata.get("use_effect_raw"))
            for slot_no, (effect_id, amount) in enumerate(references, start=1):
                effect_row = effect_rows.get(effect_id)
                if effect_row is None:
                    findings["missing_item_use_effects"] += 1
                    continue
                connection.execute(
                    """
                    INSERT INTO item_use_link (
                        item_id, effect_id, slot_no, amount, source_file,
                        source_row, build_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item_id,
                        effect_id,
                        slot_no,
                        amount,
                        resource["selected_source_file"],
                        resource["selected_source_row"],
                        build_id,
                    ),
                )
                findings["item_use_links"] += 1
                values = effect_values[effect_id]
                use_type = _integer(_at(values, 1))

                if use_type == 28:
                    pet_id = _integer(_at(values, 2))
                    if pet_id is None:
                        findings["pet_effects_without_pet_id"] += 1
                    elif ("pet", pet_id) in resources:
                        path = [
                            {
                                "kind": "item",
                                "id": item_id,
                                "source_file": resource["selected_source_file"],
                                "source_row": resource["selected_source_row"],
                            },
                            {
                                "kind": "item_use_effect",
                                "id": effect_id,
                                "source_file": effect_row.source_file,
                                "source_row": effect_row.source_row,
                            },
                            {"kind": "pet", "id": pet_id},
                        ]
                        inserted = _insert_relation(
                            connection,
                            source_kind="item",
                            source_id=item_id,
                            target_kind="pet",
                            target_id=pet_id,
                            relation_type="grants_pet",
                            evidence_type="mapped",
                            source_file=resource["selected_source_file"],
                            source_row=resource["selected_source_row"],
                            path=path,
                            build_id=build_id,
                        )
                        findings["item_grants_pet"] += inserted
                        findings["item_grants_pet_from_use_effect"] += inserted
                    else:
                        missing_targets["pet"] += 1
                        if len(missing_examples["pet"]) < 20:
                            missing_examples["pet"].append(pet_id)

                if use_type == 43:
                    ride_id = _integer(_at(values, 2))
                    if ride_id is None:
                        findings["ride_effects_without_ride_id"] += 1
                        continue
                    ride = resources.get(("ride", ride_id))
                    path = [
                        {
                            "kind": "item",
                            "id": item_id,
                            "source_file": resource["selected_source_file"],
                            "source_row": resource["selected_source_row"],
                        },
                        {
                            "kind": "item_use_effect",
                            "id": effect_id,
                            "source_file": effect_row.source_file,
                            "source_row": effect_row.source_row,
                        },
                        {"kind": "ride", "id": ride_id},
                    ]
                    if ride is not None:
                        findings["item_grants_ride"] += _insert_relation(
                            connection,
                            source_kind="item",
                            source_id=item_id,
                            target_kind="ride",
                            target_id=ride_id,
                            relation_type="grants_ride",
                            evidence_type="mapped",
                            source_file=resource["selected_source_file"],
                            source_row=resource["selected_source_row"],
                            path=path,
                            build_id=build_id,
                        )
                    else:
                        missing_targets["ride"] += 1
                        if len(missing_examples["ride"]) < 20:
                            missing_examples["ride"].append(ride_id)

                    if item_id in item_pet_sources:
                        for pet in pets_by_ride.get(ride_id, []):
                            pet_path = path + [
                                {
                                    "kind": "pet",
                                    "id": pet["resource_id"],
                                    "source_file": pet["selected_source_file"],
                                    "source_row": pet["selected_source_row"],
                                }
                            ]
                            findings["item_grants_pet"] += _insert_relation(
                                connection,
                                source_kind="item",
                                source_id=item_id,
                                target_kind="pet",
                                target_id=pet["resource_id"],
                                relation_type="grants_pet",
                                evidence_type="mapped",
                                source_file=item_pet_sources[item_id].source_file,
                                source_row=item_pet_sources[item_id].source_row,
                                path=pet_path,
                                build_id=build_id,
                            )
                        if not pets_by_ride.get(ride_id):
                            findings["item_pet_without_pet_match"] += 1

                if (
                    use_type == 3
                    and _integer(_at(values, 2)) == 353
                ):
                    mapping_id = _integer(_at(values, 3))
                    mapped = title_mappings.get(mapping_id or -1)
                    if mapped is None:
                        findings["title_effect_without_mapping"] += 1
                        continue
                    title_id, mapping_row = mapped
                    if ("title", title_id) not in resources:
                        missing_targets["title"] += 1
                        if len(missing_examples["title"]) < 20:
                            missing_examples["title"].append(title_id)
                        continue
                    path = [
                        {
                            "kind": "item",
                            "id": item_id,
                            "source_file": resource["selected_source_file"],
                            "source_row": resource["selected_source_row"],
                        },
                        {
                            "kind": "item_use_effect",
                            "id": effect_id,
                            "source_file": effect_row.source_file,
                            "source_row": effect_row.source_row,
                        },
                        {
                            "kind": "item_title_mapping",
                            "id": mapping_id,
                            "source_file": mapping_row.source_file,
                            "source_row": mapping_row.source_row,
                        },
                        {"kind": "title", "id": title_id},
                    ]
                    findings["item_grants_title"] += _insert_relation(
                        connection,
                        source_kind="item",
                        source_id=item_id,
                        target_kind="title",
                        target_id=title_id,
                        relation_type="grants_title",
                        evidence_type="mapped",
                        source_file=resource["selected_source_file"],
                        source_row=resource["selected_source_row"],
                        path=path,
                        build_id=build_id,
                    )

        for ride_id, pets in pets_by_ride.items():
            if ("ride", ride_id) not in resources:
                continue
            for pet in pets:
                findings["pet_ride_links"] += _insert_relation(
                    connection,
                    source_kind="pet",
                    source_id=pet["resource_id"],
                    target_kind="ride",
                    target_id=ride_id,
                    relation_type="uses_ride",
                    evidence_type="source",
                    source_file=pet["selected_source_file"],
                    source_row=pet["selected_source_row"],
                    path=[
                        {
                            "kind": "pet",
                            "id": pet["resource_id"],
                            "source_file": pet["selected_source_file"],
                            "source_row": pet["selected_source_row"],
                        },
                        {"kind": "ride", "id": ride_id},
                    ],
                    build_id=build_id,
                )

        _apply_ride_display_names(connection, findings)

        contract = load_quest_resource_links(
            quest_contract_path,
            quest_schema_path,
        )
        for link in contract["links"]:
            key = (link["resource_kind"], link["resource_id"])
            if key not in resources:
                missing_targets[f"quest:{link['resource_kind']}"] += 1
                examples = missing_examples[f"quest:{link['resource_kind']}"]
                if len(examples) < 20:
                    examples.append(link["resource_id"])
                continue
            connection.execute(
                """
                INSERT INTO quest_resource_link (
                    resource_kind, resource_id, quest_id, quest_name,
                    relation_type, amount, quest_site_path, source_file,
                    source_row, build_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    link["resource_kind"],
                    link["resource_id"],
                    link["quest_id"],
                    link["quest_name"],
                    link["relation_type"],
                    link.get("amount"),
                    link["quest_site_path"],
                    link["source_file"],
                    link["source_row"],
                    build_id,
                ),
            )
            findings["quest_links_imported"] += 1

    foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
    relation_count = connection.execute(
        "SELECT COUNT(*) FROM resource_relation"
    ).fetchone()[0]
    connection.close()
    return {
        "build_id": build_id,
        "findings": dict(sorted(findings.items())),
        "resource_relation_count": relation_count,
        "missing_targets": dict(sorted(missing_targets.items())),
        "missing_target_examples": {
            key: sorted(set(values))
            for key, values in sorted(missing_examples.items())
        },
        "foreign_key_error_count": len(foreign_key_errors),
    }
