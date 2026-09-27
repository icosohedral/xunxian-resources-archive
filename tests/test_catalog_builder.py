import sqlite3
from pathlib import Path

from xunxian_archive.builders.catalog import build_catalog


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _write_source(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="")


def test_catalog_keeps_equal_ids_in_separate_namespaces(tmp_path: Path) -> None:
    original = tmp_path / "original_data"
    _write_source(
        original,
        "mb/item/item_list.txt",
        "物品ID\t物品名称\n1515\t合成普通道具\t\t\t\t\t77\n",
    )
    _write_source(
        original,
        "mb/etc/text.txt",
        "77\t合成普通道具的完整说明。\n",
    )
    _write_source(
        original,
        "mb/item/item_type.txt",
        "9\t神奇珍宝\te_zw001_%d\t1\t1\t6009\t1\t4\t虚拟道具\n",
    )
    _write_source(
        original,
        "mb/quest/quest_item.txt",
        "\n合成任务道具\t1515\n",
    )
    _write_source(
        original,
        "mb/pet/pet_list.txt",
        "\n合成宠物\t1515\t283\t1800\t1855\t583\n",
    )
    _write_source(
        original,
        "mb/pet/pet_model.txt",
        "侍宠4-15\t583\t10000*0\t15\t15\t15\t15\t\t5000\n",
    )
    _write_source(
        original,
        "mb/etc/title_list.txt",
        "\n合成称号\t1515\t34\n无分组称号\t1516\n季度称号\t2249\t1043\n",
    )
    _write_source(
        original,
        "mb/etc/title_group.txt",
        (
            "风物志·集\t34\t6\t1\t1\t0\t\n"
            "天平斗神一季度称号\t1043\t10\t0\t1\t1\t2248\n"
            "天平斗神二季度称号\t1043\t10\t0\t1\t1\t2249\n"
        ),
    )
    _write_source(original, "mb/object/ride_list.txt", "\n合成骑乘\t1515\n")
    config = tmp_path / "source_routes.toml"
    config.write_text(
        """
[[source]]
path = "mb/item/item_list.txt"
resource_kind = "item"
id_column = 0
name_column = 1
has_header = true

[[source]]
path = "mb/quest/quest_item.txt"
resource_kind = "quest_item"
id_column = 1
name_column = 0
has_header = false

[[source]]
path = "mb/pet/pet_list.txt"
resource_kind = "pet"
id_column = 1
name_column = 0
has_header = false

[[source]]
path = "mb/etc/title_list.txt"
resource_kind = "title"
id_column = 1
name_column = 0
has_header = false

[[source]]
path = "mb/object/ride_list.txt"
resource_kind = "ride"
id_column = 1
name_column = 0
has_header = false
""",
        encoding="utf-8",
    )
    output = tmp_path / "outputs/catalog.db"

    summary = build_catalog(
        original,
        output,
        config,
        schema_path=PROJECT_ROOT / "schemas/catalog.sql",
    )

    assert summary["resource_count"] == 7
    assert summary["raw_record_count"] == 7
    assert summary["parse_issue_count"] == 0
    assert summary["title_group_count"] == 3
    with sqlite3.connect(output) as connection:
        rows = connection.execute(
            """
            SELECT resource_kind, resource_id, selected_source_row
            FROM resource
            ORDER BY resource_kind
            """
        ).fetchall()
        assert {row[:2] for row in rows} == {
            ("item", 1515),
            ("quest_item", 1515),
            ("pet", 1515),
            ("title", 1515),
            ("title", 1516),
            ("title", 2249),
            ("ride", 1515),
        }
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute(
            "SELECT description FROM item_text WHERE text_id = 77"
        ).fetchone() == ("合成普通道具的完整说明。",)
        assert connection.execute(
            "SELECT display_name FROM item_type WHERE item_type_id = 9"
        ).fetchone() == ("神奇珍宝",)
        assert connection.execute(
            """
            SELECT display_name, strength, physique, yuan_spirit, sinew
            FROM pet_attribute_template
            WHERE template_id = 583
            """
        ).fetchone() == ("侍宠4-15", 15, 15, 15, 15)
        pet_metadata = connection.execute(
            """
            SELECT metadata_json
            FROM resource
            WHERE resource_kind = 'pet' AND resource_id = 1515
            """
        ).fetchone()[0]
        assert '"attribute_template_id": 583' in pet_metadata
        title_groups = dict(
            connection.execute(
                """
                SELECT resource_id,
                       json_extract(metadata_json, '$.title_group_name')
                FROM resource
                WHERE resource_kind = 'title'
                ORDER BY resource_id
                """
            )
        )
        assert title_groups == {
            1515: "风物志·集",
            1516: "-",
            2249: "天平斗神二季度称号",
        }
        assert connection.execute(
            """
            SELECT json_extract(metadata_json, '$.title_group_family_id')
            FROM resource
            WHERE resource_kind = 'title' AND resource_id = 1515
            """
        ).fetchone() == (6,)
        assert connection.execute(
            """
            SELECT display_name, family_id
            FROM title_group
            ORDER BY source_row
            """
        ).fetchall() == [
            ("风物志·集", 6),
            ("天平斗神一季度称号", 10),
            ("天平斗神二季度称号", 10),
        ]


def test_duplicate_source_versions_are_retained(tmp_path: Path) -> None:
    original = tmp_path / "original_data"
    _write_source(
        original,
        "mb/item/a.txt",
        "物品ID\t物品名称\n1\t第一版本\n1\t第二版本\n",
    )
    config = tmp_path / "source_routes.toml"
    config.write_text(
        """
[[source]]
path = "mb/item/a.txt"
resource_kind = "item"
id_column = 0
name_column = 1
has_header = true
""",
        encoding="utf-8",
    )
    output = tmp_path / "catalog.db"

    summary = build_catalog(
        original,
        output,
        config,
        schema_path=PROJECT_ROOT / "schemas/catalog.sql",
    )

    assert summary["resource_count"] == 1
    assert summary["raw_record_count"] == 2
    with sqlite3.connect(output) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM resource_source"
        ).fetchone()[0] == 2
        assert connection.execute(
            "SELECT SUM(is_selected) FROM resource_source"
        ).fetchone()[0] == 1


def test_catalog_parses_title_active_and_passive_attributes(
    tmp_path: Path,
) -> None:
    original = tmp_path / "original_data"
    title_values = [
        "初探形神",
        "231",
        "30",
        "1",
        "15",
        "9*0*5*10*0*5*11*0*5*12*0*5",
        "",
        "初探形神竞技。",
        "活动兑换获得",
        "1",
        "15*0*4*29*0*1*4*0*50",
        "",
        "",
        "10",
        "12826",
        "",
        "",
        "",
        "",
    ]
    _write_source(
        original,
        "mb/etc/title_list.txt",
        f"\n{'\t'.join(title_values)}\n",
    )
    _write_source(
        original,
        "mb/etc/atb_fight.txt",
        "\n".join(
            [
                "",
                "生命值上限\t4",
                "抗定身\t9",
                "抗迷惑\t10",
                "抗流失\t11",
                "抗削弱\t12",
                "防御\t15",
                "法术抗性\t29",
            ]
        )
        + "\n",
    )
    config = tmp_path / "source_routes.toml"
    config.write_text(
        """
[[source]]
path = "mb/etc/title_list.txt"
resource_kind = "title"
id_column = 1
name_column = 0
has_header = false
""",
        encoding="utf-8",
    )
    output = tmp_path / "catalog.db"

    summary = build_catalog(
        original,
        output,
        config,
        schema_path=PROJECT_ROOT / "schemas/catalog.sql",
    )

    assert summary["title_attribute_count"] == 7
    assert summary["parse_issue_count"] == 0
    with sqlite3.connect(output) as connection:
        rows = connection.execute(
            """
            SELECT
                attribute_scope, slot_no, attribute_name,
                value_kind, raw_value
            FROM title_attribute
            WHERE title_id = 231
            ORDER BY
                CASE attribute_scope WHEN 'active' THEN 1 ELSE 2 END,
                slot_no
            """
        ).fetchall()
    assert rows == [
        ("active", 1, "抗定身", "flat", 5),
        ("active", 2, "抗迷惑", "flat", 5),
        ("active", 3, "抗流失", "flat", 5),
        ("active", 4, "抗削弱", "flat", 5),
        ("passive", 1, "防御", "flat", 4),
        ("passive", 2, "法术抗性", "flat", 1),
        ("passive", 3, "生命值上限", "flat", 50),
    ]
