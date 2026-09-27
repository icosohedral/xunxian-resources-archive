"""对 original_data 进行只读、可重复的全量清点。"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from xunxian_archive.parsers.tabular import decode_bytes


PRIORITY_SOURCES = (
    "mb/item/item_list.txt",
    "mb/item/item_list2.txt",
    "mb/item/item_list3.txt",
    "mb/item/item_type.txt",
    "mb/item/item_use.txt",
    "mb/item/item_rand.txt",
    "mb/item/item_combin.txt",
    "mb/item/item_derive.txt",
    "mb/item/item_mcht.txt",
    "mb/item/item_pet.txt",
    "mb/item/item_award.txt",
    "mb/item/item_collect.txt",
    "mb/item/quest_shop_item.txt",
    "mb/quest/quest_item.txt",
    "mb/quest/quest_item_ex.txt",
    "mb/quest/quest_item_mapping.txt",
    "mb/pet/pet_list.txt",
    "mb/pet/pet_list_group.txt",
    "mb/pet/pet_text.txt",
    "mb/pet/pet_model.txt",
    "mb/pet/pet_ability.txt",
    "mb/pet/pet_newskill_list.txt",
    "mb/pet/pet_fetter.txt",
    "mb/pet/pet_catch.txt",
    "mb/pet/car_skill.txt",
    "mb/object/ride_list.txt",
    "mb/object/ride_connection.txt",
    "mb/object/cha_list.txt",
    "mb/object/cha_pic.txt",
    "mb/etc/title_list.txt",
    "mb/etc/title_group.txt",
    "mb/etc/title_share.txt",
    "mb/etc/itemaddtitle.txt",
    "mb/camp/camp_level_title.txt",
    "mb/compete/compete_title.txt",
    "mb/collection/col_list.txt",
    "mb/collection/col_text.txt",
    "mb/collection/col_reward.txt",
    "mb/collection/col_quest.txt",
    "mb/collection/col_type.txt",
)

HEADER_WORDS = {
    "id",
    "索引",
    "名称",
    "备注",
    "类型",
    "物品id",
    "物品名称",
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _line_endings(data: bytes) -> dict[str, int]:
    crlf = data.count(b"\r\n")
    return {
        "crlf": crlf,
        "lf": data.count(b"\n") - crlf,
        "cr": data.count(b"\r") - crlf,
    }


def _suspected_header(lines: list[str]) -> bool:
    if not lines:
        return False
    first = [value.strip().lower() for value in lines[0].split("\t")]
    return any(
        value in HEADER_WORDS
        or value.endswith("id")
        or value.endswith("名称")
        or value.endswith("索引")
        for value in first
    )


def _inspect_file(path: Path, root: Path) -> dict[str, Any]:
    data = path.read_bytes()
    item: dict[str, Any] = {
        "path": path.relative_to(root).as_posix(),
        "size_bytes": len(data),
        "sha256": _sha256(data),
        "status": "ok",
        "encoding": None,
        "line_endings": _line_endings(data),
        "line_count": len(data.splitlines()),
        "delimiter": None,
        "column_count_distribution": {},
        "suspected_header": False,
        "error": None,
    }
    if not data:
        item["status"] = "empty"
        return item
    if path.suffix.lower() != ".txt":
        item["status"] = "binary_or_non_text"
        return item
    try:
        text, encoding = decode_bytes(data)
    except UnicodeDecodeError as exc:
        item["status"] = "decode_failed"
        item["error"] = str(exc)
        return item
    item["encoding"] = encoding
    lines = text.splitlines()
    nonempty = [line for line in lines if line.strip()]
    if any("\t" in line for line in nonempty[:100]):
        item["delimiter"] = "tab"
        distribution = Counter(len(line.split("\t")) for line in nonempty)
    else:
        item["delimiter"] = "none_detected"
        distribution = Counter(1 for _ in nonempty)
    item["column_count_distribution"] = {
        str(count): frequency for count, frequency in sorted(distribution.items())
    }
    item["suspected_header"] = _suspected_header(nonempty)
    return item


def _indexed_references(index_path: Path) -> set[str]:
    if not index_path.exists():
        return set()
    text, _ = decode_bytes(index_path.read_bytes())
    rows = csv.reader(text.splitlines(), delimiter="\t")
    next(rows, None)
    references: set[str] = set()
    for row in rows:
        if len(row) < 3:
            continue
        for raw_reference in row[2].split("*"):
            reference = raw_reference.strip().replace("\\", "/").lstrip("/")
            while "//" in reference:
                reference = reference.replace("//", "/")
            if not reference:
                continue
            if not Path(reference).suffix:
                reference += ".txt"
            if not reference.startswith("mb/"):
                reference = f"mb/{reference}"
            references.add(reference)
    return references


def build_inventory(root: Path) -> dict[str, Any]:
    if not root.is_dir():
        raise FileNotFoundError(f"原始资料目录不存在：{root}")
    paths = sorted(path for path in root.rglob("*") if path.is_file())
    files = [_inspect_file(path, root) for path in paths]
    actual = {entry["path"] for entry in files}
    actual_text = {path for path in actual if path.endswith(".txt")}
    indexed = _indexed_references(root / "index_list.txt")
    missing_indexed = sorted(indexed - actual)
    unindexed_text = sorted(
        actual_text - indexed - {"index_list.txt"}
    )
    missing_priority = sorted(set(PRIORITY_SOURCES) - actual)
    empty_files = sorted(
        entry["path"] for entry in files if entry["status"] == "empty"
    )
    decode_failures = sorted(
        entry["path"] for entry in files if entry["status"] == "decode_failed"
    )
    by_hash: dict[str, list[str]] = defaultdict(list)
    for entry in files:
        by_hash[entry["sha256"]].append(entry["path"])
    duplicate_groups = sorted(
        (sorted(group) for group in by_hash.values() if len(group) > 1),
        key=lambda group: (group[0], len(group)),
    )
    reasons = []
    if missing_indexed:
        reasons.append("index_list_references_missing_files")
    if empty_files:
        reasons.append("empty_files_present")
    if decode_failures:
        reasons.append("text_decode_failures")
    if missing_priority:
        reasons.append("priority_sources_missing")
    aggregate = hashlib.sha256(
        "\n".join(
            f"{entry['path']}\t{entry['sha256']}" for entry in files
        ).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_root": "original_data",
        "summary": {
            "file_count": len(files),
            "text_file_count": len(actual_text),
            "total_size_bytes": sum(entry["size_bytes"] for entry in files),
            "indexed_reference_count": len(indexed),
            "missing_indexed_file_count": len(missing_indexed),
            "unindexed_text_file_count": len(unindexed_text),
            "empty_file_count": len(empty_files),
            "decode_failure_count": len(decode_failures),
            "duplicate_content_group_count": len(duplicate_groups),
            "priority_source_count": len(PRIORITY_SOURCES),
            "missing_priority_source_count": len(missing_priority),
            "completeness_status": "complete" if not reasons else "incomplete",
            "completeness_reasons": reasons,
            "aggregate_sha256": aggregate,
        },
        "index_check": {
            "missing_indexed_files": missing_indexed,
            "unindexed_text_files": unindexed_text,
        },
        "priority_check": {
            "missing_priority_sources": missing_priority,
        },
        "quality_findings": {
            "empty_files": empty_files,
            "decode_failures": decode_failures,
            "duplicate_content_groups": duplicate_groups,
        },
        "files": files,
    }


def write_inventory(root: Path, output: Path) -> dict[str, Any]:
    report = build_inventory(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def check_inventory(root: Path, output: Path) -> None:
    expected = json.loads(output.read_text(encoding="utf-8"))
    actual = build_inventory(root)
    stable_keys = ("summary", "index_check", "priority_check", "quality_findings", "files")
    differences = [
        key for key in stable_keys if actual.get(key) != expected.get(key)
    ]
    if differences:
        raise RuntimeError(
            "original_data 与资料清单不一致；变化部分：" + ", ".join(differences)
        )
