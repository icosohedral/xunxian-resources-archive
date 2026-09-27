from __future__ import annotations

import argparse
import base64
import hashlib
import json
import multiprocessing
import shutil
import sqlite3
import sys
import time
import zlib
from pathlib import Path
from typing import Any
from datetime import datetime, timezone


PROJECT_ROOT = Path(__file__).resolve().parents[3]
WORKER_ROOT = PROJECT_ROOT / "apps" / "resource_viewer_cloudflare"
SOURCE_DATABASE = PROJECT_ROOT / "outputs" / "catalog.db"
OUTPUT_DIRECTORY = WORKER_ROOT / "data"
OUTPUT_DATABASE = OUTPUT_DIRECTORY / "resource_web.db"
OUTPUT_SQL = OUTPUT_DIRECTORY / "resource_web.sql"
DEPLOY_MANIFEST = OUTPUT_DIRECTORY / "resource_web.deploy.json"
GENERATED_TEMPLATE = WORKER_ROOT / "src" / "generated_template.py"
GENERATED_CONFIG = WORKER_ROOT / "src" / "generated_config.py"
DETAIL_CHUNK_SIZE = 60_000

sys.path.insert(0, str(PROJECT_ROOT / "src"))

from xunxian_archive.web.app import (  # noqa: E402
    DEFAULT_FILTER_DETAILS,
    EXTERNAL_COLLECTION_COUNTS,
    SITE_VERSION,
)
from xunxian_archive.web.repository import (  # noqa: E402
    COMPANION_CATEGORY_LABELS,
    COMPANION_CATEGORY_SQL,
    COMPANION_SCOPE_SQL,
    FILTER_KIND_LABELS,
    ITEM_CATEGORY_LABELS,
    KIND_LABELS,
    METADATA_LABELS,
    CatalogRepository,
)


_repository: CatalogRepository | None = None


def _encode_detail(detail: dict[str, Any]) -> str:
    raw = json.dumps(
        detail,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.b64encode(zlib.compress(raw, level=9)).decode("ascii")


def _build_detail(
    identity: tuple[str, int],
) -> tuple[str, int, list[str]]:
    global _repository
    if _repository is None:
        _repository = CatalogRepository(SOURCE_DATABASE)
    resource_kind, resource_id = identity
    detail = _repository.detail(resource_kind, resource_id)
    if detail is None:
        raise RuntimeError(f"资源不存在：{resource_kind}:{resource_id}")
    encoded = _encode_detail(detail)
    chunks = [
        encoded[index : index + DETAIL_CHUNK_SIZE]
        for index in range(0, len(encoded), DETAIL_CHUNK_SIZE)
    ]
    return resource_kind, resource_id, chunks


def _resource_summaries() -> list[dict[str, Any]]:
    with sqlite3.connect(SOURCE_DATABASE) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT
                resource.resource_kind,
                resource.resource_id,
                resource.display_name,
                resource.metadata_json,
                json_extract(
                    resource.metadata_json,
                    '$.title_group_name'
                ) AS title_group_name,
                json_extract(
                    resource.metadata_json,
                    '$.title_group_family_id'
                ) AS title_group_family_id,
                CASE
                    WHEN {COMPANION_SCOPE_SQL}
                    THEN {COMPANION_CATEGORY_SQL}
                    ELSE NULL
                END AS companion_category
            FROM resource
            ORDER BY resource.resource_kind, resource.resource_id
            """
        ).fetchall()
    summaries: list[dict[str, Any]] = []
    for row in rows:
        metadata = json.loads(row["metadata_json"])
        metadata.pop("title_group_family_id", None)
        search_text = " ".join(
            str(metadata.get(key, ""))
            for key in ("description", "acquisition_hint")
            if metadata.get(key)
        )
        summaries.append(
            {
                "resource_kind": row["resource_kind"],
                "resource_id": row["resource_id"],
                "display_name": row["display_name"],
                "companion_category": row["companion_category"],
                "title_group_name": (
                    row["title_group_name"]
                    if row["resource_kind"] == "title"
                    else None
                ),
                "title_group_family_id": (
                    row["title_group_family_id"]
                    if row["resource_kind"] == "title"
                    else None
                ),
                "search_text": search_text,
                "kind_label": KIND_LABELS[row["resource_kind"]],
                "category_label": COMPANION_CATEGORY_LABELS.get(
                    row["companion_category"]
                ),
                "metadata": metadata,
                "quest_count": 0,
                "relation_count": 0,
            }
        )
    return summaries


RESOURCE_COLUMNS = (
    "resource_kind",
    "resource_id",
    "display_name",
    "companion_category",
    "title_group_name",
    "title_group_family_id",
    "search_text",
    "placeholder_rank",
    "summary_json",
)


def _create_output_database(database_path: Path) -> sqlite3.Connection:
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    database_path.unlink(missing_ok=True)
    connection = sqlite3.connect(database_path)
    connection.executescript(
        """
        PRAGMA journal_mode=OFF;
        PRAGMA synchronous=OFF;

        CREATE TABLE web_resource (
            resource_kind TEXT NOT NULL,
            resource_id INTEGER NOT NULL,
            display_name TEXT NOT NULL,
            companion_category TEXT,
            title_group_name TEXT,
            title_group_family_id INTEGER,
            search_text TEXT NOT NULL DEFAULT '',
            placeholder_rank INTEGER NOT NULL DEFAULT 0,
            summary_json TEXT NOT NULL,
            PRIMARY KEY (resource_kind, resource_id)
        );

        CREATE INDEX idx_web_resource_kind_name
            ON web_resource(
                resource_kind,
                display_name COLLATE NOCASE,
                resource_id
            );
        CREATE INDEX idx_web_resource_kind_listing
            ON web_resource(
                resource_kind,
                placeholder_rank,
                display_name COLLATE NOCASE,
                resource_id
            );
        CREATE INDEX idx_web_resource_companion
            ON web_resource(
                companion_category,
                display_name COLLATE NOCASE,
                resource_id
            );
        CREATE INDEX idx_web_resource_companion_listing
            ON web_resource(
                resource_kind,
                placeholder_rank,
                display_name COLLATE NOCASE,
                resource_id
            )
            WHERE companion_category IS NOT NULL;
        CREATE INDEX idx_web_resource_companion_category_listing
            ON web_resource(
                companion_category,
                resource_kind,
                placeholder_rank,
                display_name COLLATE NOCASE,
                resource_id
            );
        CREATE INDEX idx_web_resource_title_group
            ON web_resource(
                title_group_name,
                display_name COLLATE NOCASE,
                resource_id
            );
        CREATE INDEX idx_web_resource_title_group_listing
            ON web_resource(
                title_group_name,
                placeholder_rank,
                display_name COLLATE NOCASE,
                resource_id
            );
        CREATE INDEX idx_web_resource_title_family
            ON web_resource(
                title_group_family_id,
                display_name COLLATE NOCASE,
                resource_id
            );
        CREATE INDEX idx_web_resource_title_family_listing
            ON web_resource(
                title_group_family_id,
                placeholder_rank,
                display_name COLLATE NOCASE,
                resource_id
            );

        CREATE TABLE web_resource_detail (
            resource_kind TEXT NOT NULL,
            resource_id INTEGER NOT NULL,
            chunk_no INTEGER NOT NULL,
            detail_chunk TEXT NOT NULL,
            PRIMARY KEY (resource_kind, resource_id, chunk_no)
        );

        CREATE TABLE web_metadata (
            metadata_key TEXT PRIMARY KEY,
            metadata_value TEXT NOT NULL
        );
        """
    )
    return connection


def _sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def _insert_statement(table: str, columns: tuple[str, ...], row: sqlite3.Row) -> str:
    column_names = ",".join(f'"{column}"' for column in columns)
    values = ",".join(_sql_literal(row[column]) for column in columns)
    return (
        f'INSERT OR REPLACE INTO "{table}"({column_names}) '
        f"VALUES({values});"
    )


def _schema_signature(connection: sqlite3.Connection) -> list[tuple[str, str, str]]:
    return [
        tuple(row)
        for row in connection.execute(
            """
            SELECT type, name, sql
            FROM sqlite_master
            WHERE name NOT LIKE 'sqlite_%'
              AND sql IS NOT NULL
            ORDER BY type, name
            """
        ).fetchall()
    ]


def _schema_by_type(
    connection: sqlite3.Connection,
    object_type: str,
) -> dict[str, str]:
    return {
        row[0]: row[1]
        for row in connection.execute(
            """
            SELECT name, sql
            FROM sqlite_master
            WHERE type = ?
              AND name NOT LIKE 'sqlite_%'
              AND sql IS NOT NULL
            ORDER BY name
            """,
            (object_type,),
        ).fetchall()
    }


def _index_migration_statements(
    previous: sqlite3.Connection,
    current: sqlite3.Connection,
) -> list[str]:
    previous_indexes = _schema_by_type(previous, "index")
    current_indexes = _schema_by_type(current, "index")
    changed_names = {
        name
        for name in previous_indexes.keys() | current_indexes.keys()
        if previous_indexes.get(name) != current_indexes.get(name)
    }
    statements = [
        f'DROP INDEX IF EXISTS "{name}";'
        for name in sorted(changed_names & previous_indexes.keys())
    ]
    statements.extend(
        current_indexes[name].rstrip(";") + ";"
        for name in sorted(changed_names & current_indexes.keys())
    )
    return statements


def _logical_snapshot_id(connection: sqlite3.Connection) -> str:
    digest = hashlib.sha256()
    table_queries = (
        (
            "web_resource",
            """
            SELECT *
            FROM web_resource
            ORDER BY resource_kind, resource_id
            """,
        ),
        (
            "web_resource_detail",
            """
            SELECT *
            FROM web_resource_detail
            ORDER BY resource_kind, resource_id, chunk_no
            """,
        ),
    )
    for table_name, query in table_queries:
        digest.update(table_name.encode("utf-8"))
        for row in connection.execute(query):
            digest.update(
                json.dumps(
                    tuple(row),
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8")
            )
            digest.update(b"\n")
    return digest.hexdigest()


def _full_dump_statements(connection: sqlite3.Connection) -> list[str]:
    return [
        "DROP TABLE IF EXISTS web_resource_detail;",
        "DROP TABLE IF EXISTS web_resource;",
        "DROP TABLE IF EXISTS web_metadata;",
        *[
            statement
            for statement in connection.iterdump()
            if statement not in {"BEGIN TRANSACTION;", "COMMIT;"}
        ],
    ]


def _changed_resource_rows(
    current: sqlite3.Connection,
) -> tuple[list[sqlite3.Row], list[tuple[str, int]]]:
    comparisons = " OR ".join(
        f"current.{column} IS NOT previous.{column}"
        for column in RESOURCE_COLUMNS[2:]
    )
    changed = current.execute(
        f"""
        SELECT current.*
        FROM web_resource AS current
        LEFT JOIN previous.web_resource AS previous
          USING (resource_kind, resource_id)
        WHERE previous.resource_kind IS NULL
           OR {comparisons}
        ORDER BY current.resource_kind, current.resource_id
        """
    ).fetchall()
    removed = current.execute(
        """
        SELECT previous.resource_kind, previous.resource_id
        FROM previous.web_resource AS previous
        LEFT JOIN web_resource AS current
          USING (resource_kind, resource_id)
        WHERE current.resource_kind IS NULL
        ORDER BY previous.resource_kind, previous.resource_id
        """
    ).fetchall()
    return changed, [(row[0], row[1]) for row in removed]


def _changed_detail_identities(
    current: sqlite3.Connection,
) -> list[tuple[str, int]]:
    rows = current.execute(
        """
        WITH current_only AS (
            SELECT resource_kind, resource_id, chunk_no, detail_chunk
            FROM web_resource_detail
            EXCEPT
            SELECT resource_kind, resource_id, chunk_no, detail_chunk
            FROM previous.web_resource_detail
        ),
        previous_only AS (
            SELECT resource_kind, resource_id, chunk_no, detail_chunk
            FROM previous.web_resource_detail
            EXCEPT
            SELECT resource_kind, resource_id, chunk_no, detail_chunk
            FROM web_resource_detail
        )
        SELECT DISTINCT resource_kind, resource_id
        FROM (
            SELECT resource_kind, resource_id FROM current_only
            UNION ALL
            SELECT resource_kind, resource_id FROM previous_only
        )
        ORDER BY resource_kind, resource_id
        """
    ).fetchall()
    return [(row[0], row[1]) for row in rows]


def _changed_metadata(
    current: sqlite3.Connection,
) -> tuple[list[sqlite3.Row], list[str]]:
    changed = current.execute(
        """
        SELECT current.*
        FROM web_metadata AS current
        LEFT JOIN previous.web_metadata AS previous
          USING (metadata_key)
        WHERE previous.metadata_key IS NULL
           OR current.metadata_value IS NOT previous.metadata_value
        ORDER BY current.metadata_key
        """
    ).fetchall()
    removed = current.execute(
        """
        SELECT previous.metadata_key
        FROM previous.web_metadata AS previous
        LEFT JOIN web_metadata AS current
          USING (metadata_key)
        WHERE current.metadata_key IS NULL
        ORDER BY previous.metadata_key
        """
    ).fetchall()
    return changed, [row[0] for row in removed]


def write_deployment_sql(
    previous_database: Path,
    current_database: Path,
    output_sql: Path,
    manifest_path: Path,
    *,
    force_full: bool = False,
) -> dict[str, Any]:
    output_sql.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(current_database) as current:
        current.row_factory = sqlite3.Row
        previous_exists = previous_database.is_file()
        schema_changed = True
        requires_full_schema = True
        index_migrations: list[str] = []
        if previous_exists and not force_full:
            with sqlite3.connect(previous_database) as previous:
                schema_changed = (
                    _schema_signature(previous) != _schema_signature(current)
                )
                requires_full_schema = (
                    _schema_by_type(previous, "table")
                    != _schema_by_type(current, "table")
                )
                if not requires_full_schema:
                    index_migrations = _index_migration_statements(
                        previous,
                        current,
                    )
        if force_full or not previous_exists or requires_full_schema:
            statements = _full_dump_statements(current)
            mode = "full"
            changed_resources = current.execute(
                "SELECT COUNT(*) FROM web_resource"
            ).fetchone()[0]
            changed_details = current.execute(
                """
                SELECT COUNT(DISTINCT resource_kind || ':' || resource_id)
                FROM web_resource_detail
                """
            ).fetchone()[0]
            removed_resources = 0
            changed_metadata = current.execute(
                "SELECT COUNT(*) FROM web_metadata"
            ).fetchone()[0]
        else:
            current.execute(
                "ATTACH DATABASE ? AS previous",
                (str(previous_database),),
            )
            stored_snapshot = current.execute(
                """
                SELECT metadata_value
                FROM previous.web_metadata
                WHERE metadata_key = 'snapshot_id'
                """
            ).fetchone()
            with sqlite3.connect(previous_database) as previous_connection:
                base_snapshot_id = _logical_snapshot_id(previous_connection)
            current_snapshot_row = current.execute(
                """
                SELECT metadata_value
                FROM web_metadata
                WHERE metadata_key = 'snapshot_id'
                """
            ).fetchone()
            current_snapshot_id = (
                current_snapshot_row[0]
                if current_snapshot_row is not None
                else _logical_snapshot_id(current)
            )
            base_resource_count = current.execute(
                "SELECT COUNT(*) FROM previous.web_resource"
            ).fetchone()[0]
            base_detail_count = current.execute(
                "SELECT COUNT(*) FROM previous.web_resource_detail"
            ).fetchone()[0]
            resource_rows, removed = _changed_resource_rows(current)
            detail_identities = _changed_detail_identities(current)
            metadata_rows, removed_metadata = _changed_metadata(current)
            if stored_snapshot is not None:
                guard_condition = (
                    "NOT EXISTS ("
                    "SELECT 1 FROM web_metadata "
                    "WHERE metadata_key='snapshot_id' "
                    f"AND metadata_value={_sql_literal(stored_snapshot[0])}"
                    ")"
                )
            else:
                guard_condition = (
                    f"(SELECT COUNT(*) FROM web_resource) != {base_resource_count} "
                    "OR "
                    "(SELECT COUNT(*) FROM web_resource_detail) "
                    f"!= {base_detail_count}"
                )
            statements = [
                "INSERT INTO web_metadata(metadata_key, metadata_value) "
                "SELECT NULL, NULL "
                f"WHERE {guard_condition};"
            ]
            for resource_kind, resource_id in detail_identities:
                statements.append(
                    "DELETE FROM web_resource_detail "
                    f"WHERE resource_kind={_sql_literal(resource_kind)} "
                    f"AND resource_id={resource_id};"
                )
            for resource_kind, resource_id in removed:
                statements.append(
                    "DELETE FROM web_resource "
                    f"WHERE resource_kind={_sql_literal(resource_kind)} "
                    f"AND resource_id={resource_id};"
                )
            statements.extend(
                _insert_statement("web_resource", RESOURCE_COLUMNS, row)
                for row in resource_rows
            )
            for resource_kind, resource_id in detail_identities:
                detail_rows = current.execute(
                    """
                    SELECT resource_kind, resource_id, chunk_no, detail_chunk
                    FROM web_resource_detail
                    WHERE resource_kind = ? AND resource_id = ?
                    ORDER BY chunk_no
                    """,
                    (resource_kind, resource_id),
                ).fetchall()
                statements.extend(
                    _insert_statement(
                        "web_resource_detail",
                        (
                            "resource_kind",
                            "resource_id",
                            "chunk_no",
                            "detail_chunk",
                        ),
                        row,
                    )
                    for row in detail_rows
                )
            statements.extend(
                "DELETE FROM web_metadata "
                f"WHERE metadata_key={_sql_literal(key)};"
                for key in removed_metadata
            )
            statements.extend(
                _insert_statement(
                    "web_metadata",
                    ("metadata_key", "metadata_value"),
                    row,
                )
                for row in metadata_rows
            )
            statements.extend(index_migrations)
            data_statement_count = len(statements) - 1
            mode = "incremental" if data_statement_count else "noop"
            if mode == "noop":
                statements = ["SELECT 1;"]
            changed_resources = len(resource_rows)
            changed_details = len(detail_identities)
            removed_resources = len(removed)
            changed_metadata = len(metadata_rows) + len(removed_metadata)
            current.execute("DETACH DATABASE previous")
        if mode == "full":
            base_snapshot_id = None
            current_snapshot_row = current.execute(
                """
                SELECT metadata_value
                FROM web_metadata
                WHERE metadata_key = 'snapshot_id'
                """
            ).fetchone()
            current_snapshot_id = (
                current_snapshot_row[0] if current_snapshot_row else None
            )

    statements = [
        statement
        for statement in statements
        if statement.strip()
    ]
    longest = max(map(len, statements), default=0)
    if longest > 100_000:
        raise RuntimeError(f"D1 单条 SQL 超过 100KB：{longest} bytes")
    output_sql.write_text("\n".join(statements) + "\n", encoding="utf-8")
    with sqlite3.connect(current_database) as count_connection:
        current_resource_count = count_connection.execute(
            "SELECT COUNT(*) FROM web_resource"
        ).fetchone()[0]
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "schema_changed": schema_changed,
        "index_migration_statements": len(index_migrations),
        "base_snapshot_id": base_snapshot_id,
        "current_snapshot_id": current_snapshot_id,
        "changed_resources": changed_resources,
        "removed_resources": removed_resources,
        "changed_detail_resources": changed_details,
        "changed_metadata": changed_metadata,
        "statement_count": len(statements),
        "sql_bytes": output_sql.stat().st_size,
        "current_resource_count": current_resource_count,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def _category_counts(
    summaries: list[dict[str, Any]],
    title_group_options: list[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {
        "items": {},
        "companions": {},
        "title": {},
    }
    for summary in summaries:
        if summary["resource_kind"] in {"item", "quest_item"}:
            key = summary["resource_kind"]
            counts["items"][key] = counts["items"].get(key, 0) + 1
        companion_category = summary["companion_category"]
        if companion_category:
            counts["companions"][companion_category] = (
                counts["companions"].get(companion_category, 0) + 1
            )
    for family in title_group_options:
        counts["title"][family["value"]] = family["title_count"]
        for group in family["groups"]:
            counts["title"][group["value"]] = group["title_count"]
    return counts


def _write_generated_modules(
    stats: dict[str, Any],
    summaries: list[dict[str, Any]],
) -> None:
    template_source = (
        PROJECT_ROOT
        / "src"
        / "xunxian_archive"
        / "web"
        / "templates"
        / "index.html"
    ).read_text(encoding="utf-8")
    GENERATED_TEMPLATE.parent.mkdir(parents=True, exist_ok=True)
    GENERATED_TEMPLATE.write_text(
        "TEMPLATE_SOURCE = " + repr(template_source) + "\n",
        encoding="utf-8",
    )
    title_group_options = CatalogRepository(
        SOURCE_DATABASE
    ).title_group_options()
    config = {
        "site_version": SITE_VERSION,
        "default_filter_details": DEFAULT_FILTER_DETAILS,
        "external_collection_counts": EXTERNAL_COLLECTION_COUNTS,
        "filter_kind_labels": FILTER_KIND_LABELS,
        "item_category_labels": ITEM_CATEGORY_LABELS,
        "companion_category_labels": COMPANION_CATEGORY_LABELS,
        "title_group_options": title_group_options,
        "category_counts": _category_counts(
            summaries,
            title_group_options,
        ),
        "metadata_labels": METADATA_LABELS,
        "stats": stats,
    }
    GENERATED_CONFIG.write_text(
        "CONFIG = " + repr(config) + "\n",
        encoding="utf-8",
    )
    static_directory = WORKER_ROOT / "public" / "static"
    if static_directory.exists():
        shutil.rmtree(static_directory)
    shutil.copytree(PROJECT_ROOT / "public", static_directory)


def build(limit: int | None, processes: int) -> None:
    started = time.monotonic()
    summaries = _resource_summaries()
    if limit:
        summaries = summaries[:limit]
    identities = [
        (summary["resource_kind"], summary["resource_id"])
        for summary in summaries
    ]
    temporary_database = OUTPUT_DATABASE.with_suffix(".next.db")
    connection = _create_output_database(temporary_database)
    connection.executemany(
        """
        INSERT INTO web_resource (
            resource_kind, resource_id, display_name, companion_category,
            title_group_name, title_group_family_id, search_text,
            placeholder_rank, summary_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                summary["resource_kind"],
                summary["resource_id"],
                summary["display_name"],
                summary["companion_category"],
                summary["title_group_name"],
                summary["title_group_family_id"],
                summary["search_text"],
                int(
                    summary["display_name"].startswith("*")
                    or "占位" in summary["display_name"]
                    or summary["display_name"].startswith("(x)")
                    or summary["display_name"].startswith("（废）")
                ),
                json.dumps(
                    summary,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            )
            for summary in summaries
        ],
    )
    connection.commit()

    if processes == 1:
        results = map(_build_detail, identities)
        pool = None
    else:
        pool = multiprocessing.Pool(processes=processes)
        results = pool.imap_unordered(_build_detail, identities, chunksize=20)
    try:
        for completed, (kind, resource_id, chunks) in enumerate(
            results, start=1
        ):
            connection.executemany(
                """
                INSERT INTO web_resource_detail (
                    resource_kind, resource_id, chunk_no, detail_chunk
                ) VALUES (?, ?, ?, ?)
                """,
                [
                    (kind, resource_id, chunk_no, chunk)
                    for chunk_no, chunk in enumerate(chunks)
                ],
            )
            if completed % 500 == 0 or completed == len(identities):
                connection.commit()
                print(
                    f"{completed}/{len(identities)} "
                    f"({time.monotonic() - started:.1f}s)",
                    flush=True,
                )
    finally:
        if pool is not None:
            pool.close()
            pool.join()

    repository = CatalogRepository(SOURCE_DATABASE)
    stats = repository.stats()
    snapshot_id = _logical_snapshot_id(connection)
    connection.executemany(
        """
        INSERT INTO web_metadata (metadata_key, metadata_value)
        VALUES (?, ?)
        """,
        [
            ("resource_count", str(len(identities))),
            ("snapshot_id", snapshot_id),
        ],
    )
    connection.commit()
    connection.execute("VACUUM")
    connection.close()
    manifest = write_deployment_sql(
        OUTPUT_DATABASE,
        temporary_database,
        OUTPUT_SQL,
        DEPLOY_MANIFEST,
        force_full=limit is not None,
    )
    temporary_database.replace(OUTPUT_DATABASE)
    _write_generated_modules(stats, summaries)
    print(f"数据库：{OUTPUT_DATABASE} ({OUTPUT_DATABASE.stat().st_size} bytes)")
    print(
        f"D1 SQL：{OUTPUT_SQL} ({OUTPUT_SQL.stat().st_size} bytes，"
        f"{manifest['mode']})"
    )
    print(f"部署清单：{DEPLOY_MANIFEST}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--processes",
        type=int,
        default=min(8, multiprocessing.cpu_count()),
    )
    arguments = parser.parse_args()
    build(arguments.limit, max(1, arguments.processes))


if __name__ == "__main__":
    main()
