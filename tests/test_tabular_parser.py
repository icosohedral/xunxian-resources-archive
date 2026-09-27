from pathlib import Path

from xunxian_archive.parsers.tabular import iter_tabular_rows


def test_parser_preserves_physical_source_row_and_raw_values(tmp_path: Path) -> None:
    root = tmp_path / "original_data"
    path = root / "mb/example/table.txt"
    path.parent.mkdir(parents=True)
    path.write_bytes("\r\n名称\t编号\r\n合成甲\t42\r\n".encode("utf-8"))

    rows = list(iter_tabular_rows(path, source_root=root))

    assert [row.source_row for row in rows] == [2, 3]
    assert rows[1].source_file == "mb/example/table.txt"
    assert rows[1].raw_value == "合成甲\t42"
    assert rows[1].values == ("合成甲", "42")

