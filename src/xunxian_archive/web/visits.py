"""按中国时区统计每日匿名访客。"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


CHINA_TIMEZONE = timezone(timedelta(hours=8))

VISIT_SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_visit (
    visit_day TEXT PRIMARY KEY,
    visitor_count INTEGER NOT NULL CHECK (visitor_count >= 0)
);

CREATE TABLE IF NOT EXISTS daily_visitor (
    visit_day TEXT NOT NULL,
    visitor_id TEXT NOT NULL,
    PRIMARY KEY (visit_day, visitor_id)
);
"""


class VisitorStore:
    """将访问统计写入与资源目录分离的 SQLite 数据库。"""

    def __init__(self, database_path: Path):
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(VISIT_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path, timeout=10)

    @staticmethod
    def _today() -> str:
        return datetime.now(CHINA_TIMEZONE).date().isoformat()

    def count_today(self) -> int:
        today = self._today()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT visitor_count
                FROM daily_visit
                WHERE visit_day = ?
                """,
                (today,),
            ).fetchone()
        return int(row[0]) if row is not None else 0

    def record(self, visitor_id: str) -> tuple[int, str, bool]:
        today = self._today()
        with self._connect() as connection:
            inserted = connection.execute(
                """
                INSERT OR IGNORE INTO daily_visitor (visit_day, visitor_id)
                VALUES (?, ?)
                """,
                (today, visitor_id),
            )
            is_new = inserted.rowcount == 1
            if is_new:
                connection.execute(
                    """
                    INSERT INTO daily_visit (visit_day, visitor_count)
                    VALUES (?, 1)
                    ON CONFLICT(visit_day) DO UPDATE
                    SET visitor_count = visitor_count + 1
                    """,
                    (today,),
                )
            row = connection.execute(
                """
                SELECT visitor_count
                FROM daily_visit
                WHERE visit_day = ?
                """,
                (today,),
            ).fetchone()
        return (int(row[0]) if row is not None else 0), today, is_new
