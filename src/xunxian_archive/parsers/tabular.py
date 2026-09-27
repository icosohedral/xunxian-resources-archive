"""保留原始值、实际行号和编码信息的制表符文本解析器。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


SUPPORTED_ENCODINGS = ("utf-8-sig", "gb18030")


def decode_bytes(data: bytes) -> tuple[str, str]:
    for encoding in SUPPORTED_ENCODINGS:
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError(
        "supported",
        data,
        0,
        min(len(data), 1),
        f"无法使用 {', '.join(SUPPORTED_ENCODINGS)} 解码",
    )


@dataclass(frozen=True, slots=True)
class RawRow:
    source_file: str
    source_row: int
    raw_value: str
    values: tuple[str, ...]
    encoding: str


def iter_tabular_rows(
    path: Path,
    *,
    source_root: Path,
    skip_blank: bool = True,
) -> Iterator[RawRow]:
    text, encoding = decode_bytes(path.read_bytes())
    source_file = path.relative_to(source_root).as_posix()
    for row_number, line in enumerate(text.splitlines(), start=1):
        if skip_blank and not line.strip():
            continue
        yield RawRow(
            source_file=source_file,
            source_row=row_number,
            raw_value=line,
            values=tuple(line.split("\t")),
            encoding=encoding,
        )

