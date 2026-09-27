"""从只读来源构建可追溯的 SQLite 原始层与核心实体层。"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from xunxian_archive.models import ResourceKind
from xunxian_archive.parsers.tabular import iter_tabular_rows


ITEM_TEXT = "mb/etc/text.txt"
ITEM_TYPE = "mb/item/item_type.txt"
PET_ATTRIBUTE_TEMPLATE = "mb/pet/pet_model.txt"
TITLE_ATTRIBUTE_DEFINITION = "mb/etc/atb_fight.txt"
TITLE_GROUP = "mb/etc/title_group.txt"


def _build_id(config_bytes: bytes, source_paths: list[Path]) -> str:
    digest = hashlib.sha256(config_bytes)
    for path in source_paths:
        digest.update(path.as_posix().encode("utf-8"))
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def _value(values: tuple[str, ...], index: int) -> str | None:
    if index >= len(values):
        return None
    value = values[index].strip()
    return value or None


def _integer(values: tuple[str, ...], index: int) -> int | None:
    value = _value(values, index)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _metadata_for(
    resource_kind: str,
    values: tuple[str, ...],
    *,
    title_group_defaults: dict[int, tuple[dict[str, Any], ...]] | None = None,
    title_group_members: dict[tuple[int, int], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if resource_kind == ResourceKind.ITEM.value:
        return {
            "item_type_id": _integer(values, 2),
            "icon_key": _value(values, 4),
            "model_id": _integer(values, 5),
            "text_id": _integer(values, 6),
            "quality": _integer(values, 7),
            "currency_is_tradable": _integer(values, 15) == 1,
            "buy_price": _integer(values, 16),
            "sell_price": _integer(values, 17),
            "level_requirement": _integer(values, 11),
            "use_effect_raw": _value(values, 30),
            "stack_limit": _integer(values, 34),
        }
    if resource_kind == ResourceKind.PET.value:
        return {
            "character_id": _integer(values, 2),
            "model_id": _integer(values, 4),
            "attribute_template_id": _integer(values, 5),
            "ride_id": _integer(values, 6),
            "note": _value(values, 8),
        }
    if resource_kind == ResourceKind.TITLE.value:
        group_id = _integer(values, 2)
        title_id = _integer(values, 1)
        group_name = None
        group_family_id = None
        if group_id is not None:
            group = (title_group_members or {}).get((group_id, title_id))
            if group is not None:
                group_name = group["group_name"]
                group_family_id = group["group_family_id"]
            else:
                groups = (title_group_defaults or {}).get(group_id, ())
                group_name = "／".join(
                    group["group_name"] for group in groups
                ) or None
                group_family_id = (
                    groups[0]["group_family_id"] if groups else None
                )
        return {
            "title_group_name": group_name or "-",
            "title_group_family_id": group_family_id,
            "description": _value(values, 7),
            "acquisition_hint": _value(values, 8),
        }
    if resource_kind == ResourceKind.RIDE.value:
        return {
            "character_id": _integer(values, 2),
        }
    return {}


def _load_sources(config_path: Path, original_root: Path) -> tuple[bytes, list[dict[str, Any]]]:
    config_bytes = config_path.read_bytes()
    config = tomllib.loads(config_bytes.decode("utf-8"))
    sources = config.get("source", [])
    if not sources:
        raise ValueError("config/source_routes.toml 中没有 [[source]]")
    for source in sources:
        ResourceKind(source["resource_kind"])
        source["absolute_path"] = original_root / source["path"]
        if not source["absolute_path"].is_file():
            raise FileNotFoundError(f"重点来源不存在：{source['path']}")
    return config_bytes, sources


def _load_item_texts(original_root: Path) -> dict[int, dict[str, Any]]:
    path = original_root / ITEM_TEXT
    if not path.is_file():
        return {}
    texts: dict[int, dict[str, Any]] = {}
    for row in iter_tabular_rows(path, source_root=original_root):
        if len(row.values) < 2:
            continue
        try:
            text_id = int(row.values[0].strip())
        except ValueError:
            continue
        description = row.values[1].strip()
        if not description:
            continue
        texts.setdefault(
            text_id,
            {
                "text_id": text_id,
                "description": description,
                "source_file": row.source_file,
                "source_row": row.source_row,
                "raw_value": row.raw_value,
                "raw_values_json": json.dumps(
                    row.values,
                    ensure_ascii=False,
                ),
            },
        )
    return texts


def _load_item_types(original_root: Path) -> dict[int, dict[str, Any]]:
    path = original_root / ITEM_TYPE
    if not path.is_file():
        return {}
    item_types: dict[int, dict[str, Any]] = {}
    for row in iter_tabular_rows(path, source_root=original_root):
        if len(row.values) < 2:
            continue
        try:
            item_type_id = int(row.values[0].strip())
        except ValueError:
            continue
        display_name = row.values[1].strip()
        if not display_name:
            continue
        note = row.values[8].strip() if len(row.values) > 8 else ""
        item_types.setdefault(
            item_type_id,
            {
                "item_type_id": item_type_id,
                "display_name": display_name,
                "note": note or None,
                "source_file": row.source_file,
                "source_row": row.source_row,
                "raw_value": row.raw_value,
                "raw_values_json": json.dumps(row.values, ensure_ascii=False),
            },
        )
    return item_types


def _load_pet_attribute_templates(
    original_root: Path,
) -> dict[int, dict[str, Any]]:
    path = original_root / PET_ATTRIBUTE_TEMPLATE
    if not path.is_file():
        return {}
    templates: dict[int, dict[str, Any]] = {}
    for row in iter_tabular_rows(path, source_root=original_root):
        if len(row.values) < 7:
            continue
        template_id = _integer(row.values, 1)
        display_name = _value(row.values, 0)
        if template_id is None or display_name is None:
            continue
        templates.setdefault(
            template_id,
            {
                "template_id": template_id,
                "display_name": display_name,
                "strength": _integer(row.values, 3),
                "physique": _integer(row.values, 4),
                "yuan_spirit": _integer(row.values, 5),
                "sinew": _integer(row.values, 6),
                "source_file": row.source_file,
                "source_row": row.source_row,
                "raw_value": row.raw_value,
                "raw_values_json": json.dumps(row.values, ensure_ascii=False),
            },
        )
    return templates


def _load_title_attribute_definitions(
    original_root: Path,
) -> dict[int, dict[str, Any]]:
    path = original_root / TITLE_ATTRIBUTE_DEFINITION
    if not path.is_file():
        return {}
    definitions: dict[int, dict[str, Any]] = {}
    for row in iter_tabular_rows(path, source_root=original_root):
        attribute_id = _integer(row.values, 1)
        display_name = _value(row.values, 0)
        if attribute_id is None or display_name is None:
            continue
        definitions.setdefault(
            attribute_id,
            {
                "attribute_id": attribute_id,
                "display_name": display_name,
                "source_file": row.source_file,
                "source_row": row.source_row,
            },
        )
    return definitions


def _load_title_groups(
    original_root: Path,
) -> tuple[
    dict[int, tuple[dict[str, Any], ...]],
    dict[tuple[int, int], dict[str, Any]],
    list[dict[str, Any]],
]:
    path = original_root / TITLE_GROUP
    if not path.is_file():
        return {}, {}, []
    groups: dict[int, list[dict[str, Any]]] = {}
    members: dict[tuple[int, int], dict[str, Any]] = {}
    records: list[dict[str, Any]] = []
    for row in iter_tabular_rows(path, source_root=original_root):
        group_name = _value(row.values, 0)
        group_id = _integer(row.values, 1)
        group_family_id = _integer(row.values, 2)
        if (
            group_name is None
            or group_id is None
            or group_family_id is None
        ):
            continue
        group = {
            "group_name": group_name,
            "group_family_id": group_family_id,
        }
        records.append(
            {
                "group_id": group_id,
                "display_name": group_name,
                "family_id": group_family_id,
                "member_title_ids": _value(row.values, 6),
                "source_file": row.source_file,
                "source_row": row.source_row,
            }
        )
        group_entries = groups.setdefault(group_id, [])
        if group not in group_entries:
            group_entries.append(group)
        raw_members = _value(row.values, 6)
        if raw_members is None:
            continue
        for raw_title_id in raw_members.split("*"):
            try:
                title_id = int(raw_title_id)
            except ValueError:
                continue
            members.setdefault((group_id, title_id), group)
    return (
        {
            group_id: tuple(group_entries)
            for group_id, group_entries in groups.items()
        },
        members,
        records,
    )


def _parse_title_attributes(
    raw_value: str | None,
    definitions: dict[int, dict[str, Any]],
) -> tuple[list[dict[str, Any]], str | None]:
    if raw_value is None:
        return [], None
    parts = raw_value.split("*")
    if len(parts) % 3:
        return [], "属性配置不是完整的三元组"
    try:
        values = [int(part) for part in parts]
    except ValueError:
        return [], "属性配置中存在非数字参数"
    attributes: list[dict[str, Any]] = []
    for offset in range(0, len(values), 3):
        attribute_id, value_mode, raw_amount = values[offset : offset + 3]
        definition = definitions.get(attribute_id)
        if definition is None:
            return [], f"没有找到属性编号 {attribute_id} 的定义"
        if value_mode not in {0, 1}:
            return [], f"属性编号 {attribute_id} 使用未知数值形式 {value_mode}"
        attributes.append(
            {
                "slot_no": offset // 3 + 1,
                "attribute_id": attribute_id,
                "attribute_name": definition["display_name"],
                "value_kind": "percentage" if value_mode == 1 else "flat",
                "raw_value": raw_amount,
            }
        )
    return attributes, None


def build_catalog(
    original_root: Path,
    output_path: Path,
    config_path: Path,
    *,
    schema_path: Path = Path("schemas/catalog.sql"),
) -> dict[str, Any]:
    config_bytes, sources = _load_sources(config_path, original_root)
    source_paths = [source["absolute_path"] for source in sources]
    item_text_path = original_root / ITEM_TEXT
    if item_text_path.is_file():
        source_paths.append(item_text_path)
    item_type_path = original_root / ITEM_TYPE
    if item_type_path.is_file():
        source_paths.append(item_type_path)
    pet_attribute_path = original_root / PET_ATTRIBUTE_TEMPLATE
    if pet_attribute_path.is_file():
        source_paths.append(pet_attribute_path)
    title_attribute_path = original_root / TITLE_ATTRIBUTE_DEFINITION
    if title_attribute_path.is_file():
        source_paths.append(title_attribute_path)
    title_group_path = original_root / TITLE_GROUP
    if title_group_path.is_file():
        source_paths.append(title_group_path)
    build_id = _build_id(config_bytes, source_paths)
    item_texts = _load_item_texts(original_root)
    item_types = _load_item_types(original_root)
    pet_attribute_templates = _load_pet_attribute_templates(original_root)
    title_attribute_definitions = _load_title_attribute_definitions(original_root)
    (
        title_group_defaults,
        title_group_members,
        title_group_records,
    ) = _load_title_groups(original_root)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary_path.unlink(missing_ok=True)
    connection = sqlite3.connect(temporary_path)
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        connection.executescript(schema_path.read_text(encoding="utf-8"))
        connection.execute(
            """
            INSERT INTO build_metadata (build_id, generated_at, source_count)
            VALUES (?, ?, ?)
            """,
            (build_id, datetime.now(timezone.utc).isoformat(), len(sources)),
        )
        connection.executemany(
            """
            INSERT INTO title_group (
                group_id, display_name, family_id, member_title_ids,
                source_file, source_row, build_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    group["group_id"],
                    group["display_name"],
                    group["family_id"],
                    group["member_title_ids"],
                    group["source_file"],
                    group["source_row"],
                    build_id,
                )
                for group in title_group_records
            ],
        )
        connection.executemany(
            """
            INSERT INTO item_text (
                text_id, description, source_file, source_row, raw_value,
                raw_values_json, build_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    text["text_id"],
                    text["description"],
                    text["source_file"],
                    text["source_row"],
                    text["raw_value"],
                    text["raw_values_json"],
                    build_id,
                )
                for text in item_texts.values()
            ],
        )
        connection.executemany(
            """
            INSERT INTO item_type (
                item_type_id, display_name, note, source_file, source_row,
                raw_value, raw_values_json, build_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item_type["item_type_id"],
                    item_type["display_name"],
                    item_type["note"],
                    item_type["source_file"],
                    item_type["source_row"],
                    item_type["raw_value"],
                    item_type["raw_values_json"],
                    build_id,
                )
                for item_type in item_types.values()
            ],
        )
        connection.executemany(
            """
            INSERT INTO pet_attribute_template (
                template_id, display_name, strength, physique, yuan_spirit,
                sinew, source_file, source_row, raw_value, raw_values_json,
                build_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    template["template_id"],
                    template["display_name"],
                    template["strength"],
                    template["physique"],
                    template["yuan_spirit"],
                    template["sinew"],
                    template["source_file"],
                    template["source_row"],
                    template["raw_value"],
                    template["raw_values_json"],
                    build_id,
                )
                for template in pet_attribute_templates.values()
            ],
        )
        for source in sources:
            rows = iter_tabular_rows(
                source["absolute_path"],
                source_root=original_root,
            )
            first_nonblank = True
            for row in rows:
                if source.get("has_header", False) and first_nonblank:
                    first_nonblank = False
                    continue
                first_nonblank = False
                values_json = json.dumps(row.values, ensure_ascii=False)
                cursor = connection.execute(
                    """
                    INSERT INTO raw_record (
                        build_id, resource_kind, source_file, source_row,
                        raw_value, raw_values_json
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        build_id,
                        source["resource_kind"],
                        row.source_file,
                        row.source_row,
                        row.raw_value,
                        values_json,
                    ),
                )
                raw_record_id = cursor.lastrowid
                id_column = int(source["id_column"])
                name_column = int(source["name_column"])
                try:
                    raw_id = row.values[id_column].strip()
                    name = row.values[name_column].strip()
                    resource_id = int(raw_id)
                    if resource_id < 0:
                        raise ValueError("ID 为负数")
                    if not name:
                        raise ValueError("名称为空")
                except (IndexError, ValueError) as exc:
                    connection.execute(
                        """
                        INSERT INTO parse_issue (
                            build_id, raw_record_id, issue_code, detail
                        ) VALUES (?, ?, ?, ?)
                        """,
                        (build_id, raw_record_id, "invalid_core_identity", str(exc)),
                    )
                    continue
                inserted = connection.execute(
                    """
                    INSERT OR IGNORE INTO resource (
                        resource_kind, resource_id, display_name, build_id,
                        selected_source_file, selected_source_row, metadata_json,
                        raw_values_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source["resource_kind"],
                        resource_id,
                        name,
                        build_id,
                        row.source_file,
                        row.source_row,
                        json.dumps(
                            _metadata_for(
                                source["resource_kind"],
                                row.values,
                                title_group_defaults=title_group_defaults,
                                title_group_members=title_group_members,
                            ),
                            ensure_ascii=False,
                        ),
                        values_json,
                    ),
                ).rowcount
                connection.execute(
                    """
                    INSERT INTO resource_source (
                        resource_kind, resource_id, raw_record_id, is_selected
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (
                        source["resource_kind"],
                        resource_id,
                        raw_record_id,
                        1 if inserted else 0,
                    ),
                )
                if inserted and source["resource_kind"] == ResourceKind.TITLE.value:
                    for attribute_scope, column_index in (
                        ("active", 5),
                        ("passive", 10),
                    ):
                        raw_attributes = _value(row.values, column_index)
                        attributes, attribute_error = _parse_title_attributes(
                            raw_attributes,
                            title_attribute_definitions,
                        )
                        if attribute_error is not None:
                            connection.execute(
                                """
                                INSERT INTO parse_issue (
                                    build_id, raw_record_id, issue_code, detail
                                ) VALUES (?, ?, ?, ?)
                                """,
                                (
                                    build_id,
                                    raw_record_id,
                                    "invalid_title_attribute",
                                    f"{attribute_scope}: {attribute_error}",
                                ),
                            )
                            continue
                        connection.executemany(
                            """
                            INSERT INTO title_attribute (
                                title_id, attribute_scope, slot_no,
                                attribute_id, attribute_name, value_kind,
                                raw_value, source_file, source_row, build_id
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            [
                                (
                                    resource_id,
                                    attribute_scope,
                                    attribute["slot_no"],
                                    attribute["attribute_id"],
                                    attribute["attribute_name"],
                                    attribute["value_kind"],
                                    attribute["raw_value"],
                                    row.source_file,
                                    row.source_row,
                                    build_id,
                                )
                                for attribute in attributes
                            ],
                        )
        connection.commit()
        foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_key_errors:
            raise RuntimeError(f"数据库外键检查失败：{foreign_key_errors[:5]}")
        summary = {
            "build_id": build_id,
            "source_count": len(sources),
            "raw_record_count": connection.execute(
                "SELECT COUNT(*) FROM raw_record"
            ).fetchone()[0],
            "resource_count": connection.execute(
                "SELECT COUNT(*) FROM resource"
            ).fetchone()[0],
            "parse_issue_count": connection.execute(
                "SELECT COUNT(*) FROM parse_issue"
            ).fetchone()[0],
            "item_text_count": connection.execute(
                "SELECT COUNT(*) FROM item_text"
            ).fetchone()[0],
            "item_type_count": connection.execute(
                "SELECT COUNT(*) FROM item_type"
            ).fetchone()[0],
            "pet_attribute_template_count": connection.execute(
                "SELECT COUNT(*) FROM pet_attribute_template"
            ).fetchone()[0],
            "title_attribute_count": connection.execute(
                "SELECT COUNT(*) FROM title_attribute"
            ).fetchone()[0],
            "title_group_count": connection.execute(
                "SELECT COUNT(*) FROM title_group"
            ).fetchone()[0],
            "parse_issues": [
                {
                    "source_file": source_file,
                    "source_row": source_row,
                    "issue_code": issue_code,
                    "detail": detail,
                }
                for source_file, source_row, issue_code, detail in connection.execute(
                    """
                    SELECT
                        raw_record.source_file,
                        raw_record.source_row,
                        parse_issue.issue_code,
                        parse_issue.detail
                    FROM parse_issue
                    JOIN raw_record USING (raw_record_id)
                    ORDER BY raw_record.source_file, raw_record.source_row
                    """
                )
            ],
        }
    except Exception:
        connection.close()
        temporary_path.unlink(missing_ok=True)
        raise
    else:
        connection.close()
        temporary_path.replace(output_path)
        return summary
