from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from xunxian_archive.builders.catalog import build_catalog
from xunxian_archive.relations.core import build_core_relations


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _write(root: Path, relative: str, rows: list[list[str]]) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join("\t".join(row) for row in rows) + "\n",
        encoding="utf-8",
    )


def _item_row(item_id: int, name: str, effect_id: int) -> list[str]:
    values = [""] * 35
    values[0] = str(item_id)
    values[1] = name
    values[30] = str(effect_id)
    return values


def test_core_relations_keep_paths_and_import_task_links(tmp_path: Path) -> None:
    original = tmp_path / "original_data"
    _write(
        original,
        "mb/item/item_list.txt",
        [
            ["物品ID", "物品名称"],
            _item_row(100, "合成宠物道具", 500),
            _item_row(101, "合成称号道具", 501),
            _item_row(102, "合成宠物蛋", 502),
            _item_row(103, "合成幻化宝珠", 503),
            _item_row(104, "合成状态道具", 504),
            _item_row(105, "合成图卷", 505),
            _item_row(106, "合成外观道具", 506),
            _item_row(107, "合成礼包", 507),
            _item_row(108, "合成经验丹", 508),
            _item_row(109, "合成恢复药", 509),
            _item_row(110, "合成状态数组道具", 510),
            _item_row(111, "合成猎魂礼包", 511),
            _item_row(112, "合成战灵符", 512),
        ],
    )
    _write(original, "mb/quest/quest_item.txt", [["合成任务道具", "100"]])
    pet = [""] * 9
    pet[0], pet[1], pet[6] = "合成宠物", "9", "7"
    _write(original, "mb/pet/pet_list.txt", [pet])
    title = [""] * 9
    title[0], title[1], title[7] = "合成称号", "11", "称号说明"
    _write(original, "mb/etc/title_list.txt", [title])
    ride = [""] * 22
    ride[0], ride[1], ride[16], ride[17], ride[18] = (
        "合成骑乘",
        "7",
        "6369",
        "7000",
        "9999",
    )
    _write(original, "mb/object/ride_list.txt", [ride])

    effect_ride = [""] * 21
    effect_ride[0], effect_ride[1], effect_ride[2], effect_ride[20] = (
        "500",
        "43",
        "7",
        "**获得合成骑乘",
    )
    effect_title = [""] * 21
    effect_title[0], effect_title[1], effect_title[2], effect_title[3] = (
        "501",
        "3",
        "353",
        "1",
    )
    effect_pet = [""] * 21
    effect_pet[0], effect_pet[1], effect_pet[2], effect_pet[20] = (
        "502",
        "28",
        "9",
        "**获得合成宠物",
    )
    effect_transform = [""] * 21
    (
        effect_transform[0],
        effect_transform[1],
        effect_transform[2],
        effect_transform[3],
        effect_transform[20],
    ) = ("503", "3", "1388", "16213", "**合成幻化宝珠")
    effect_state = [""] * 21
    (
        effect_state[0],
        effect_state[1],
        effect_state[2],
        effect_state[3],
        effect_state[20],
    ) = ("504", "1", "1", "16214", "**合成状态")
    effect_collection = [""] * 21
    (
        effect_collection[0],
        effect_collection[1],
        effect_collection[2],
        effect_collection[20],
    ) = ("505", "2", "222", "**合成图卷")
    effect_avatar = [""] * 21
    (
        effect_avatar[0],
        effect_avatar[1],
        effect_avatar[2],
        effect_avatar[20],
    ) = ("506", "176", "1365", "**合成外观")
    effect_loot = [""] * 21
    (
        effect_loot[0],
        effect_loot[1],
        effect_loot[2],
        effect_loot[20],
    ) = ("507", "9", "3407", "**合成礼包")
    effect_experience = [""] * 21
    (
        effect_experience[0],
        effect_experience[1],
        effect_experience[2],
        effect_experience[20],
    ) = ("508", "27", "3000000", "**合成经验丹")
    effect_recovery = [""] * 21
    (
        effect_recovery[0],
        effect_recovery[1],
        effect_recovery[2],
        effect_recovery[3],
        effect_recovery[4],
        effect_recovery[20],
    ) = ("509", "5", "17", "600", "800", "**合成恢复药")
    effect_state_array = [""] * 21
    (
        effect_state_array[0],
        effect_state_array[1],
        effect_state_array[2],
        effect_state_array[20],
    ) = ("510", "56", "2079", "**合成状态数组")
    effect_treasure = [""] * 21
    (
        effect_treasure[0],
        effect_treasure[1],
        effect_treasure[2],
        effect_treasure[20],
    ) = ("511", "141", "1", "**合成猎魂礼包")
    effect_common_skill = [""] * 21
    (
        effect_common_skill[0],
        effect_common_skill[1],
        effect_common_skill[2],
        effect_common_skill[20],
    ) = ("512", "145", "931", "**合成战灵符")
    _write(
        original,
        "mb/item/item_use.txt",
        [
            effect_ride,
            effect_title,
            effect_pet,
            effect_transform,
            effect_state,
            effect_collection,
            effect_avatar,
            effect_loot,
            effect_experience,
            effect_recovery,
            effect_state_array,
            effect_treasure,
            effect_common_skill,
        ],
    )
    _write(
        original,
        "mb/item/item_pet.txt",
        [["1", "100", "1", "", "合成宠物"]],
    )
    _write(
        original,
        "mb/etc/itemaddtitle.txt",
        [["合成称号说明", "1", "", "11"]],
    )
    _write(
        original,
        "mb/pet/car_skill.txt",
        [["冰箭", "6369", "1", "1", "合成冰箭说明"]],
    )
    _write(
        original,
        "mb/skill/skill_data_npc.txt",
        [
            ["冰箭", "6369", "", "jn6369", "向目标射出寒冰箭并降低移动速度。"],
            ["合成疾奔", "7000", "", "jn7000", "合成疾奔说明"],
        ],
    )
    _write(
        original,
        "mb/skill/state_group.txt",
        [
            ["合成变身", "16213", "使用后变身10分钟。"],
            ["合成增益", "16214", "使用后获得合成增益。"],
            ["合成数组状态一", "7001", "提高合成属性10点。"],
            ["合成数组状态二", "7002", "提高合成属性20点。"],
        ],
    )
    _write(
        original,
        "mb/etc/define_array.txt",
        [["2079", "7001*7002", "**合成神咒"]],
    )
    _write(
        original,
        "mb/collection/col_text.txt",
        [["合成风物志", "222", "222", "合成风物志的详细介绍。"]],
    )
    avatar = [""] * 17
    avatar[0], avatar[1], avatar[16] = (
        "合成外观",
        "1365",
        "使用后解锁合成外观。",
    )
    _write(
        original,
        "mb/avatar_cupboard/avatar_cupboard.txt",
        [avatar],
    )
    _write(
        original,
        "mb/item/item_rand.txt",
        [["合成礼包", "3407", "1", "1", "2", "102", "1000000"]],
    )
    _write(
        original,
        "mb/life/treasure_house/treasure_house_card.txt",
        [["合成妖魂", "80", "lh001", "4", "2", "增加合成经验。"]],
    )
    _write(
        original,
        "mb/life/treasure_house/treasure_house_randdata.txt",
        [["合成随机池", "1", "", "", "80*100000"]],
    )
    _write(
        original,
        "mb/life/treasure_house/treasure_house_randgroup.txt",
        [["合成猎魂礼包", "1", "1", "1000000*5"]],
    )
    _write(
        original,
        "mb/skill/skill_data_cmn.txt",
        [["合成陨石雷", "931", "", "jn931", "召唤陨石攻击目标。"]],
    )
    for relative_path in [
        "mb/skill/skill_data_npc_1.txt",
        "mb/skill/skill_data_npc_2.txt",
        "mb/skill/skill_data_npc_3.txt",
        "mb/skill/skill_data_npc_4.txt",
        "mb/skill/skill_data_npc_pet.txt",
        "mb/skill/skill_data_npc_pet1.txt",
    ]:
        _write(original, relative_path, [])

    config = tmp_path / "sources.toml"
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
    database = tmp_path / "catalog.db"
    build_catalog(
        original,
        database,
        config,
        schema_path=PROJECT_ROOT / "schemas/catalog.sql",
    )
    contract = tmp_path / "quest_resource_links.json"
    contract.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": "2026-07-28T00:00:00Z",
                "quest_site_base_url": "https://quests.xunxian.wiki",
                "links": [
                    {
                        "resource_kind": "item",
                        "resource_id": 100,
                        "quest_id": 800001,
                        "quest_name": "合成奖励任务",
                        "relation_type": "reward",
                        "amount": 1,
                        "source_file": "fixtures/quest.tsv",
                        "source_row": 2,
                        "quest_site_path": "/quests/800001",
                    },
                    {
                        "resource_kind": "quest_item",
                        "resource_id": 100,
                        "quest_id": 800002,
                        "quest_name": "合成目标任务",
                        "relation_type": "objective",
                        "amount": 2,
                        "source_file": "fixtures/quest.tsv",
                        "source_row": 3,
                        "quest_site_path": "/quests/800002",
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = build_core_relations(
        original_root=original,
        database_path=database,
        quest_contract_path=contract,
        quest_schema_path=PROJECT_ROOT
        / "schemas/quest_resource_links.schema.json",
    )

    assert report["foreign_key_error_count"] == 0
    assert report["findings"]["item_grants_ride"] == 1
    assert report["findings"]["ride_public_names_applied"] == 1
    assert report["findings"]["item_grants_pet"] == 2
    assert report["findings"]["item_grants_pet_from_use_effect"] == 1
    assert report["findings"]["item_use_effect_details"] == 10
    assert report["findings"]["item_use_effect_details:state_group"] == 2
    assert report["findings"]["item_use_effect_details:state_array"] == 1
    assert report["findings"]["item_use_effect_details:skill"] == 1
    assert report["findings"]["item_use_effect_details:collection"] == 1
    assert report["findings"]["item_use_effect_details:avatar"] == 1
    assert report["findings"]["item_use_effect_details:loot_table"] == 2
    assert report["findings"]["item_use_effect_details:parameter"] == 2
    assert report["findings"]["item_grants_title"] == 1
    assert report["findings"]["quest_links_imported"] == 2
    assert report["findings"]["ride_skill_references"] == 3
    assert report["findings"]["resolved_ride_skill_links"] == 2
    assert report["findings"]["unresolved_ride_skill_references"] == 1
    assert report["findings"]["ride_skills_with_detailed_description"] == 2
    assert (
        report["findings"]["ride_skills_enriched_with_detailed_description"]
        == 1
    )
    assert report["missing_targets"]["ride_skill"] == 1
    with sqlite3.connect(database) as connection:
        ride_name, ride_metadata_json = connection.execute(
            """
            SELECT display_name, metadata_json
            FROM resource
            WHERE resource_kind = 'ride' AND resource_id = 7
            """
        ).fetchone()
        assert ride_name == "合成宠物道具"
        assert json.loads(ride_metadata_json)["internal_name"] == "合成骑乘"
        assert {
            row
            for row in connection.execute(
                """
                SELECT source_kind, source_id, target_kind, target_id,
                       relation_type
                FROM resource_relation
                """
            )
        } >= {
            ("item", 100, "ride", 7, "grants_ride"),
            ("item", 100, "pet", 9, "grants_pet"),
            ("item", 102, "pet", 9, "grants_pet"),
            ("item", 101, "title", 11, "grants_title"),
            ("pet", 9, "ride", 7, "uses_ride"),
        }
        assert {
            row
            for row in connection.execute(
                """
                SELECT resource_kind, resource_id, quest_id, relation_type
                FROM quest_resource_link
                """
            )
        } == {
            ("item", 100, 800001, "reward"),
            ("quest_item", 100, 800002, "objective"),
        }
        path = json.loads(
            connection.execute(
                """
                SELECT path_json FROM resource_relation
                WHERE source_kind='item' AND source_id=101
                  AND relation_type='grants_title'
                """
            ).fetchone()[0]
        )
        assert [step["kind"] for step in path] == [
            "item",
            "item_use_effect",
            "item_title_mapping",
            "title",
        ]
        assert connection.execute(
            """
            SELECT skill_id, display_name, definition_source_type
            FROM ride_skill
            ORDER BY skill_id
            """
        ).fetchall() == [
            (6369, "冰箭", "car_skill"),
            (7000, "合成疾奔", "npc_skill"),
        ]
        assert connection.execute(
            """
            SELECT description, internal_note, icon_key,
                   description_source_file
            FROM ride_skill
            WHERE skill_id = 6369
            """
        ).fetchone() == (
            "向目标射出寒冰箭并降低移动速度。",
            "合成冰箭说明",
            "jn6369",
            "mb/skill/skill_data_npc.txt",
        )
        assert connection.execute(
            """
            SELECT detail_kind, display_name, description
            FROM item_use_detail
            WHERE effect_id = 503
            """
        ).fetchone() == (
            "state_group",
            "合成变身",
            "使用后变身10分钟。",
        )
        assert connection.execute(
            """
            SELECT effect_id, detail_kind, display_name, description
            FROM item_use_detail
            WHERE effect_id IN (504, 505, 506)
            ORDER BY effect_id
            """
        ).fetchall() == [
            (504, "state_group", "合成增益", "使用后获得合成增益。"),
            (
                505,
                "collection",
                "合成风物志",
                "合成风物志的详细介绍。",
            ),
            (
                506,
                "avatar",
                "合成外观",
                "使用后解锁合成外观。",
            ),
        ]
        assert connection.execute(
            """
            SELECT detail_kind, display_name, description
            FROM item_use_detail
            WHERE effect_id = 512
            """
        ).fetchone() == (
            "skill",
            "合成陨石雷",
            "召唤陨石攻击目标。",
        )
        assert connection.execute(
            """
            SELECT effect_id, detail_kind, display_name, description
            FROM item_use_detail
            WHERE effect_id IN (509, 510, 511)
            ORDER BY effect_id
            """
        ).fetchall() == [
            (
                509,
                "parameter",
                "恢复效果",
                "使用后恢复600 点生命和800 点法力。",
            ),
            (
                510,
                "state_array",
                "合成神咒",
                "使用时按配置档位应用下列状态之一：\n"
                "合成数组状态一：提高合成属性10点。\n"
                "合成数组状态二：提高合成属性20点。",
            ),
            (
                511,
                "loot_table",
                "合成猎魂礼包",
                "随机池「合成随机池」可能获得：合成妖魂\n固定数量：5",
            ),
        ]
        assert connection.execute(
            """
            SELECT effect_id, detail_kind, display_name, description
            FROM item_use_detail
            WHERE effect_id IN (507, 508)
            ORDER BY effect_id
            """
        ).fetchall() == [
            (
                507,
                "loot_table",
                "礼包内容",
                "合成礼包（掉落组 3407）：\n合成宠物蛋 ×2",
            ),
            (
                508,
                "parameter",
                "经验奖励",
                "使用后增加 3,000,000 点角色经验。",
            ),
        ]
        assert connection.execute(
            """
            SELECT skill_id, slot_no
            FROM ride_skill_link
            WHERE ride_id = 7
            ORDER BY slot_no
            """
        ).fetchall() == [(6369, 1), (7000, 2), (9999, 3)]
