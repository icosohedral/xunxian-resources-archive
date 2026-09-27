from __future__ import annotations

import importlib.util
import json
import shutil
import sqlite3
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    PROJECT_ROOT
    / "apps"
    / "resource_viewer_cloudflare"
    / "scripts"
    / "build_web_database.py"
)
SPEC = importlib.util.spec_from_file_location(
    "cloudflare_build_web_database",
    SCRIPT_PATH,
)
assert SPEC is not None and SPEC.loader is not None
BUILD_SCRIPT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD_SCRIPT)

DEPLOY_SCRIPT_PATH = (
    PROJECT_ROOT
    / "apps"
    / "resource_viewer_cloudflare"
    / "scripts"
    / "deploy.py"
)
DEPLOY_SPEC = importlib.util.spec_from_file_location(
    "cloudflare_deploy",
    DEPLOY_SCRIPT_PATH,
)
assert DEPLOY_SPEC is not None and DEPLOY_SPEC.loader is not None
DEPLOY_SCRIPT = importlib.util.module_from_spec(DEPLOY_SPEC)
DEPLOY_SPEC.loader.exec_module(DEPLOY_SCRIPT)


def _database(
    path: Path,
    *,
    resources: list[tuple],
    details: list[tuple],
    resource_count: int,
) -> None:
    connection = BUILD_SCRIPT._create_output_database(path)
    connection.executemany(
        """
        INSERT INTO web_resource (
            resource_kind, resource_id, display_name, companion_category,
            title_group_name, title_group_family_id, search_text,
            placeholder_rank, summary_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        resources,
    )
    connection.executemany(
        """
        INSERT INTO web_resource_detail (
            resource_kind, resource_id, chunk_no, detail_chunk
        ) VALUES (?, ?, ?, ?)
        """,
        details,
    )
    connection.execute(
        "INSERT INTO web_metadata VALUES ('resource_count', ?)",
        (str(resource_count),),
    )
    connection.execute(
        "INSERT INTO web_metadata VALUES ('snapshot_id', ?)",
        (BUILD_SCRIPT._logical_snapshot_id(connection),),
    )
    connection.commit()
    connection.close()


def _rows(path: Path, table: str) -> list[tuple]:
    with sqlite3.connect(path) as connection:
        return connection.execute(
            f'SELECT * FROM "{table}" ORDER BY 1, 2'
        ).fetchall()


def test_first_build_uses_full_snapshot(tmp_path: Path) -> None:
    current = tmp_path / "current.db"
    sql_path = tmp_path / "deploy.sql"
    manifest_path = tmp_path / "deploy.json"
    _database(
        current,
        resources=[
            ("item", 1, "一", None, None, None, "", 0, '{"id":1}'),
        ],
        details=[("item", 1, 0, "detail-1")],
        resource_count=1,
    )

    manifest = BUILD_SCRIPT.write_deployment_sql(
        tmp_path / "missing.db",
        current,
        sql_path,
        manifest_path,
    )

    assert manifest["mode"] == "full"
    assert manifest["changed_resources"] == 1
    assert "DROP TABLE IF EXISTS web_resource;" in sql_path.read_text()
    assert json.loads(manifest_path.read_text())["mode"] == "full"


def test_unchanged_build_emits_noop(tmp_path: Path) -> None:
    previous = tmp_path / "previous.db"
    current = tmp_path / "current.db"
    sql_path = tmp_path / "deploy.sql"
    manifest_path = tmp_path / "deploy.json"
    rows = [("title", 1, "甲", None, "副本", 7, "", 0, '{"id":1}')]
    details = [("title", 1, 0, "same-detail")]
    _database(
        previous,
        resources=rows,
        details=details,
        resource_count=1,
    )
    _database(
        current,
        resources=rows,
        details=details,
        resource_count=1,
    )

    manifest = BUILD_SCRIPT.write_deployment_sql(
        previous,
        current,
        sql_path,
        manifest_path,
    )

    assert manifest["mode"] == "noop"
    assert manifest["changed_resources"] == 0
    assert manifest["changed_detail_resources"] == 0
    assert sql_path.read_text() == "SELECT 1;\n"


def test_incremental_sql_reproduces_new_database(tmp_path: Path) -> None:
    previous = tmp_path / "previous.db"
    current = tmp_path / "current.db"
    applied = tmp_path / "applied.db"
    sql_path = tmp_path / "deploy.sql"
    manifest_path = tmp_path / "deploy.json"
    _database(
        previous,
        resources=[
            ("item", 1, "旧名称", None, None, None, "", 0, '{"id":1}'),
            ("item", 2, "待删除", None, None, None, "", 0, '{"id":2}'),
        ],
        details=[
            ("item", 1, 0, "old-detail"),
            ("item", 2, 0, "removed-detail"),
        ],
        resource_count=2,
    )
    _database(
        current,
        resources=[
            ("item", 1, "新名称", None, None, None, "", 0, '{"id":1,"v":2}'),
            ("title", 3, "新增", None, "副本", 7, "", 0, '{"id":3}'),
        ],
        details=[
            ("item", 1, 0, "new-detail"),
            ("title", 3, 0, "new-title-detail"),
        ],
        resource_count=2,
    )

    manifest = BUILD_SCRIPT.write_deployment_sql(
        previous,
        current,
        sql_path,
        manifest_path,
    )

    assert manifest["mode"] == "incremental"
    assert manifest["changed_resources"] == 2
    assert manifest["removed_resources"] == 1
    assert manifest["changed_detail_resources"] == 3
    assert "DROP TABLE" not in sql_path.read_text()

    shutil.copy2(previous, applied)
    with sqlite3.connect(applied) as connection:
        connection.executescript(sql_path.read_text())
    for table in ("web_resource", "web_resource_detail", "web_metadata"):
        assert _rows(applied, table) == _rows(current, table)


def test_schema_change_falls_back_to_full_snapshot(tmp_path: Path) -> None:
    previous = tmp_path / "previous.db"
    current = tmp_path / "current.db"
    sql_path = tmp_path / "deploy.sql"
    manifest_path = tmp_path / "deploy.json"
    _database(
        previous,
        resources=[],
        details=[],
        resource_count=0,
    )
    _database(
        current,
        resources=[],
        details=[],
        resource_count=0,
    )
    with sqlite3.connect(current) as connection:
        connection.execute("ALTER TABLE web_metadata ADD COLUMN note TEXT")

    manifest = BUILD_SCRIPT.write_deployment_sql(
        previous,
        current,
        sql_path,
        manifest_path,
    )

    assert manifest["mode"] == "full"
    assert manifest["schema_changed"] is True
    assert "DROP TABLE IF EXISTS web_metadata;" in sql_path.read_text()


def test_index_only_schema_change_uses_incremental_migration(
    tmp_path: Path,
) -> None:
    previous = tmp_path / "previous.db"
    current = tmp_path / "current.db"
    applied = tmp_path / "applied.db"
    sql_path = tmp_path / "deploy.sql"
    manifest_path = tmp_path / "deploy.json"
    _database(
        previous,
        resources=[],
        details=[],
        resource_count=0,
    )
    _database(
        current,
        resources=[],
        details=[],
        resource_count=0,
    )
    with sqlite3.connect(current) as connection:
        connection.execute(
            """
            CREATE INDEX idx_test_listing
            ON web_resource(resource_kind, placeholder_rank)
            """
        )

    manifest = BUILD_SCRIPT.write_deployment_sql(
        previous,
        current,
        sql_path,
        manifest_path,
    )

    assert manifest["mode"] == "incremental"
    assert manifest["schema_changed"] is True
    assert manifest["index_migration_statements"] == 1
    assert "DROP TABLE" not in sql_path.read_text()
    assert "CREATE INDEX idx_test_listing" in sql_path.read_text()

    shutil.copy2(previous, applied)
    with sqlite3.connect(applied) as connection:
        connection.executescript(sql_path.read_text())
    with sqlite3.connect(applied) as applied_connection:
        with sqlite3.connect(current) as current_connection:
            assert BUILD_SCRIPT._schema_signature(
                applied_connection
            ) == BUILD_SCRIPT._schema_signature(current_connection)


def test_incremental_guard_rejects_an_unexpected_remote_baseline(
    tmp_path: Path,
) -> None:
    previous = tmp_path / "previous.db"
    current = tmp_path / "current.db"
    drifted = tmp_path / "drifted.db"
    sql_path = tmp_path / "deploy.sql"
    manifest_path = tmp_path / "deploy.json"
    _database(
        previous,
        resources=[
            ("item", 1, "旧名称", None, None, None, "", 0, '{"id":1}'),
        ],
        details=[("item", 1, 0, "old-detail")],
        resource_count=1,
    )
    _database(
        current,
        resources=[
            ("item", 1, "新名称", None, None, None, "", 0, '{"id":1}'),
        ],
        details=[("item", 1, 0, "new-detail")],
        resource_count=1,
    )
    BUILD_SCRIPT.write_deployment_sql(
        previous,
        current,
        sql_path,
        manifest_path,
    )
    shutil.copy2(previous, drifted)
    with sqlite3.connect(drifted) as connection:
        connection.execute(
            """
            UPDATE web_metadata
            SET metadata_value = 'unexpected'
            WHERE metadata_key = 'snapshot_id'
            """
        )

    with sqlite3.connect(drifted) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.executescript(sql_path.read_text())

    assert _rows(drifted, "web_resource") == _rows(previous, "web_resource")


def test_deploy_script_skips_d1_for_noop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = tmp_path / "data" / "resource_web.deploy.json"
    manifest.parent.mkdir()
    manifest.write_text(
        json.dumps(
            {
                "mode": "noop",
                "changed_resources": 0,
                "changed_detail_resources": 0,
                "removed_resources": 0,
                "sql_bytes": 10,
            }
        )
    )
    commands = []
    monkeypatch.setattr(DEPLOY_SCRIPT, "WORKER_ROOT", tmp_path)
    monkeypatch.setattr(DEPLOY_SCRIPT, "DEPLOY_MANIFEST", manifest)
    monkeypatch.setattr(
        DEPLOY_SCRIPT,
        "_run",
        lambda command, dry_run: commands.append(command),
    )

    DEPLOY_SCRIPT.deploy(
        remote=True,
        data_only=False,
        app_only=False,
        dry_run=True,
    )

    assert commands == [["uv", "run", "pywrangler", "deploy"]]


def test_deploy_script_runs_incremental_data_before_app(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_directory = tmp_path / "data"
    data_directory.mkdir()
    manifest = data_directory / "resource_web.deploy.json"
    sql_path = data_directory / "resource_web.sql"
    manifest.write_text(
        json.dumps(
            {
                "mode": "incremental",
                "changed_resources": 1,
                "changed_detail_resources": 1,
                "removed_resources": 0,
                "sql_bytes": 100,
            }
        )
    )
    sql_path.write_text("SELECT 1;\n")
    commands = []
    monkeypatch.setattr(DEPLOY_SCRIPT, "WORKER_ROOT", tmp_path)
    monkeypatch.setattr(DEPLOY_SCRIPT, "DEPLOY_MANIFEST", manifest)
    monkeypatch.setattr(DEPLOY_SCRIPT, "DEPLOY_SQL", sql_path)
    monkeypatch.setattr(
        DEPLOY_SCRIPT,
        "_run",
        lambda command, dry_run: commands.append(command),
    )

    DEPLOY_SCRIPT.deploy(
        remote=True,
        data_only=False,
        app_only=False,
        dry_run=True,
    )

    assert commands[0] == [
        "npx",
        "wrangler",
        "d1",
        "execute",
        "xunxian-resource-archive",
        "--remote",
        "--file=data/resource_web.sql",
        "--yes",
    ]
    assert commands[1] == ["uv", "run", "pywrangler", "deploy"]


def test_deploy_script_requires_remote_for_worker_publish(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="明确添加 --remote"):
        DEPLOY_SCRIPT.deploy(
            remote=False,
            data_only=False,
            app_only=False,
            dry_run=True,
        )


def test_category_counts_are_precomputed_for_bare_filters() -> None:
    counts = BUILD_SCRIPT._category_counts(
        [
            {
                "resource_kind": "item",
                "companion_category": None,
            },
            {
                "resource_kind": "quest_item",
                "companion_category": None,
            },
            {
                "resource_kind": "pet",
                "companion_category": "servant_pet",
            },
        ],
        [
            {
                "value": "family:7",
                "title_count": 4,
                "groups": [
                    {
                        "value": "group:车迟国剿匪",
                        "title_count": 3,
                    }
                ],
            }
        ],
    )

    assert counts == {
        "items": {"item": 1, "quest_item": 1},
        "companions": {"servant_pet": 1},
        "title": {
            "family:7": 4,
            "group:车迟国剿匪": 3,
        },
    }


def test_listing_queries_use_covering_order_indexes(tmp_path: Path) -> None:
    database = tmp_path / "listing.db"
    connection = BUILD_SCRIPT._create_output_database(database)
    plans = {
        "items": connection.execute(
            """
            EXPLAIN QUERY PLAN
            SELECT summary_json
            FROM web_resource
            WHERE resource_kind IN ('item', 'quest_item')
            ORDER BY
                resource_kind,
                placeholder_rank,
                display_name COLLATE NOCASE,
                resource_id
            LIMIT 15
            """
        ).fetchall(),
        "companions": connection.execute(
            """
            EXPLAIN QUERY PLAN
            SELECT summary_json
            FROM web_resource
            WHERE companion_category IS NOT NULL
            ORDER BY
                resource_kind,
                placeholder_rank,
                display_name COLLATE NOCASE,
                resource_id
            LIMIT 15
            """
        ).fetchall(),
        "title_family": connection.execute(
            """
            EXPLAIN QUERY PLAN
            SELECT summary_json
            FROM web_resource
            WHERE resource_kind = 'title'
              AND title_group_family_id = 7
            ORDER BY
                resource_kind,
                placeholder_rank,
                display_name COLLATE NOCASE,
                resource_id
            LIMIT 15
            """
        ).fetchall(),
    }
    connection.close()

    assert "idx_web_resource_kind_listing" in str(plans["items"])
    assert "idx_web_resource_companion_listing" in str(plans["companions"])
    assert "idx_web_resource_title_family_listing" in str(
        plans["title_family"]
    )


def test_unfiltered_item_listing_does_not_force_temporary_sort(
    tmp_path: Path,
) -> None:
    database = tmp_path / "listing.db"
    connection = BUILD_SCRIPT._create_output_database(database)
    plan = connection.execute(
        """
        EXPLAIN QUERY PLAN
        SELECT summary_json
        FROM web_resource INDEXED BY idx_web_resource_kind_listing
        WHERE 1 = 1
          AND resource_kind IN ('item', 'quest_item')
        ORDER BY
            resource_kind,
            placeholder_rank,
            display_name COLLATE NOCASE,
            resource_id
        LIMIT 15 OFFSET 0
        """
    ).fetchall()
    connection.close()

    plan_text = str(plan)
    assert "idx_web_resource_kind_listing" in plan_text
    assert "idx_web_resource_kind_name" not in plan_text
    assert "USE TEMP B-TREE FOR ORDER BY" not in plan_text


def test_numeric_search_uses_resource_primary_key(tmp_path: Path) -> None:
    database = tmp_path / "search.db"
    connection = BUILD_SCRIPT._create_output_database(database)
    plan = connection.execute(
        """
        EXPLAIN QUERY PLAN
        SELECT summary_json, COUNT(*) OVER () AS search_total
        FROM web_resource
        WHERE resource_kind IN ('item', 'quest_item')
          AND resource_id = 52947
        ORDER BY
            resource_kind,
            placeholder_rank,
            display_name COLLATE NOCASE,
            resource_id
        LIMIT 15 OFFSET 0
        """
    ).fetchall()
    connection.close()

    plan_text = str(plan)
    assert "sqlite_autoindex_web_resource_1" in plan_text
    assert "resource_kind=? AND resource_id=?" in plan_text


def test_search_window_returns_total_without_separate_count(
    tmp_path: Path,
) -> None:
    database = tmp_path / "search.db"
    connection = BUILD_SCRIPT._create_output_database(database)
    connection.executemany(
        """
        INSERT INTO web_resource (
            resource_kind, resource_id, display_name, search_text,
            placeholder_rank, summary_json
        ) VALUES ('title', ?, ?, '', 0, '{}')
        """,
        [(number, f"测试称号{number}") for number in range(20)],
    )
    rows = connection.execute(
        """
        SELECT summary_json, COUNT(*) OVER () AS search_total
        FROM web_resource
        WHERE resource_kind = 'title'
          AND display_name LIKE '%测试称号%'
        ORDER BY
            resource_kind,
            placeholder_rank,
            display_name COLLATE NOCASE,
            resource_id
        LIMIT 15 OFFSET 0
        """
    ).fetchall()
    connection.close()

    assert len(rows) == 15
    assert rows[0][1] == 20
