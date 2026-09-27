import json
from pathlib import Path

import pytest

from xunxian_archive.parsers.inventory import (
    build_inventory,
    check_inventory,
    write_inventory,
)


def _make_inventory_fixture(tmp_path: Path) -> Path:
    root = tmp_path / "original_data"
    (root / "mb/item").mkdir(parents=True)
    (root / "index_list.txt").write_text(
        "备注\t索引\t文件名\n"
        "现有\t1\titem/present\n"
        "缺少\t2\titem/missing\n",
        encoding="utf-8",
        newline="",
    )
    (root / "mb/item/present.txt").write_bytes(
        "物品ID\t物品名称\r\n1\t合成道具\r\n".encode("utf-8")
    )
    (root / "mb/item/empty.txt").write_bytes(b"")
    return root


def test_inventory_explicitly_reports_incompleteness(tmp_path: Path) -> None:
    report = build_inventory(_make_inventory_fixture(tmp_path))

    assert report["summary"]["completeness_status"] == "incomplete"
    assert report["index_check"]["missing_indexed_files"] == [
        "mb/item/missing.txt"
    ]
    assert report["quality_findings"]["empty_files"] == [
        "mb/item/empty.txt"
    ]
    present = next(
        item
        for item in report["files"]
        if item["path"] == "mb/item/present.txt"
    )
    assert present["encoding"] == "utf-8-sig"
    assert present["delimiter"] == "tab"
    assert present["line_endings"]["crlf"] == 2
    assert present["suspected_header"] is True


def test_inventory_check_detects_source_change(tmp_path: Path) -> None:
    root = _make_inventory_fixture(tmp_path)
    output = tmp_path / "reports/inventory.json"
    write_inventory(root, output)
    check_inventory(root, output)

    (root / "mb/item/present.txt").write_text("已变化", encoding="utf-8")
    with pytest.raises(RuntimeError, match="不一致"):
        check_inventory(root, output)


def test_inventory_is_json_serializable(tmp_path: Path) -> None:
    report = build_inventory(_make_inventory_fixture(tmp_path))
    json.dumps(report, ensure_ascii=False)

