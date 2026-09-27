from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from xunxian_archive.web.app import create_app
from xunxian_archive.web.repository import CatalogRepository


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _database(tmp_path: Path) -> Path:
    path = tmp_path / "catalog.db"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            (PROJECT_ROOT / "schemas/catalog.sql").read_text(encoding="utf-8")
        )
        connection.execute(
            "INSERT INTO build_metadata VALUES (?, ?, ?)",
            ("a" * 64, "2026-07-28T00:00:00Z", 1),
        )
        connection.executemany(
            """
            INSERT INTO title_group (
                group_id, display_name, family_id, member_title_ids,
                source_file, source_row, build_id
            ) VALUES (?, ?, ?, ?, 'fixtures/title_group.tsv', ?, ?)
            """,
            [
                (34, "风物志·集", 6, "1515", 1, "a" * 64),
                (1206, "车迟国剿匪", 7, None, 2, "a" * 64),
            ],
        )
        connection.execute(
            """
            INSERT INTO pet_attribute_template (
                template_id, display_name, strength, physique, yuan_spirit,
                sinew, source_file, source_row, raw_value, raw_values_json,
                build_id
            ) VALUES (
                583, '侍宠4-15', 15, 15, 15, 15,
                'mb/pet/pet_model.txt', 283, 'fixture', '[]', ?
            )
            """,
            ("a" * 64,),
        )
        for kind, name, metadata in [
            ("item", "合成同号道具", {"quality": 5}),
            ("quest_item", "合成同号任务道具", {}),
            (
                "pet",
                "合成坐骑宠物",
                {
                    "character_id": 283,
                    "model_id": 1855,
                    "attribute_template_id": 583,
                    "ride_id": 1515,
                    "note": "合成宠物资料备注",
                },
            ),
            ("ride", "合成骑乘配置", {}),
            (
                "title",
                "合成称号",
                {
                    "title_group_name": "风物志·集",
                    "title_group_family_id": 6,
                    "description": "合成称号说明",
                },
            ),
        ]:
            connection.execute(
                """
                INSERT INTO resource (
                    resource_kind, resource_id, display_name, build_id,
                    selected_source_file, selected_source_row, metadata_json,
                    raw_values_json
                ) VALUES (?, 1515, ?, ?, 'fixtures/resources.tsv', 2, ?, '[]')
                """,
                (
                    kind,
                    name,
                    "a" * 64,
                    json.dumps(metadata, ensure_ascii=False),
                ),
            )
        connection.executemany(
            """
            INSERT INTO title_attribute (
                title_id, attribute_scope, slot_no, attribute_id,
                attribute_name, value_kind, raw_value,
                source_file, source_row, build_id
            ) VALUES (1515, ?, ?, ?, ?, ?, ?, 'fixtures/title.tsv', 2, ?)
            """,
            [
                ("active", 1, 0, "力量", "flat", 5, "a" * 64),
                (
                    "active",
                    2,
                    38,
                    "最终伤害和治疗输出",
                    "percentage",
                    200,
                    "a" * 64,
                ),
                ("passive", 1, 4, "生命值上限", "flat", 50, "a" * 64),
                (
                    "passive",
                    2,
                    68,
                    "会心伤害减免",
                    "percentage",
                    4000,
                    "a" * 64,
                ),
            ],
        )
        connection.execute(
            """
            INSERT INTO quest_resource_link (
                resource_kind, resource_id, quest_id, quest_name,
                relation_type, amount, quest_site_path, source_file,
                source_row, build_id
            ) VALUES (
                'item', 1515, 800001, '合成任务', 'reward', 1,
                '/quests/800001', 'fixtures/quest.tsv', 2, ?
            )
            """,
            ("a" * 64,),
        )
        connection.execute(
            """
            INSERT INTO item_use_effect (
                effect_id, use_type_id, parameters_json, description,
                source_file, source_row, raw_value, raw_values_json, build_id
            ) VALUES (
                7, 43, '["1515"]', '<c:FF00FF00>合成使用效果<c>',
                'fixtures/use.tsv', 2,
                '7', '[]', ?
            )
            """,
            ("a" * 64,),
        )
        connection.execute(
            """
            INSERT INTO item_text (
                text_id, description, source_file, source_row, raw_value,
                raw_values_json, build_id
            ) VALUES (
                77, '<c:FF00FF00>合成道具的玩家可读完整说明。\\n第二行<c>',
                'mb/etc/text.txt', 77, '77', '[]', ?
            )
            """,
            ("a" * 64,),
        )
        connection.execute(
            """
            INSERT INTO item_use_detail (
                effect_id, detail_kind, display_name, description,
                source_file, source_row, build_id
            ) VALUES (
                7, 'state_group', '合成详细效果',
                '"使用后产生已确认的合成效果。"',
                'mb/skill/state_group.txt', 88, ?
            )
            """,
            ("a" * 64,),
        )
        connection.execute(
            """
            UPDATE resource
            SET metadata_json = '{
                "quality": 5,
                "text_id": 77,
                "currency_is_tradable": true,
                "buy_price": 2000000,
                "sell_price": 2300
            }'
            WHERE resource_kind = 'item' AND resource_id = 1515
            """
        )
        connection.execute(
            """
            INSERT INTO item_use_link (
                item_id, effect_id, slot_no, amount, source_file,
                source_row, build_id
            ) VALUES (1515, 7, 1, 1, 'fixtures/resources.tsv', 2, ?)
            """,
            ("a" * 64,),
        )
        connection.execute(
            """
            INSERT INTO ride_skill (
                skill_id, display_name, description, internal_note, icon_key,
                definition_source_type, source_file, source_row,
                description_source_file, description_source_row,
                raw_values_json, build_id
            ) VALUES (
                6369, '冰箭', '向目标射出寒冰箭并降低移动速度。',
                '合成冰箭说明', 'jn6369', 'car_skill',
                'mb/pet/car_skill.txt', 2,
                'mb/skill/skill_data_npc.txt', 3, '[]', ?
            )
            """,
            ("a" * 64,),
        )
        connection.execute(
            """
            INSERT INTO ride_skill_link (
                ride_id, skill_id, slot_no, source_file, source_row,
                raw_value, build_id
            ) VALUES (
                1515, 6369, 1, 'mb/object/ride_list.txt', 2, '6369', ?
            )
            """,
            ("a" * 64,),
        )
        connection.execute(
            """
            INSERT INTO resource (
                resource_kind, resource_id, display_name, build_id,
                selected_source_file, selected_source_row, metadata_json,
                raw_values_json
            ) VALUES (
                'item', 1516, '合成骑宠蛋', ?,
                'fixtures/resources.tsv', 3, '{"item_type_id": 5}', '[]'
            )
            """,
            ("a" * 64,),
        )
        connection.execute(
            """
            INSERT INTO item_use_effect (
                effect_id, use_type_id, parameters_json, description,
                source_file, source_row, raw_value, raw_values_json, build_id
            ) VALUES (
                8, 28, '["1515"]', '骑宠蛋 合成骑宠',
                'fixtures/use.tsv', 3, '8', '[]', ?
            )
            """,
            ("a" * 64,),
        )
        connection.execute(
            """
            INSERT INTO item_use_link (
                item_id, effect_id, slot_no, amount, source_file,
                source_row, build_id
            ) VALUES (1516, 8, 1, 1, 'fixtures/resources.tsv', 3, ?)
            """,
            ("a" * 64,),
        )
        relation_values = [
            (
                "item", 1515, "ride", 1515, "grants_ride",
                '[{"kind":"item","id":1515},'
                '{"kind":"item_use_effect","id":7},'
                '{"kind":"ride","id":1515}]',
            ),
            (
                "item", 1516, "pet", 1515, "grants_pet",
                '[{"kind":"item","id":1516},'
                '{"kind":"item_use_effect","id":8},'
                '{"kind":"pet","id":1515}]',
            ),
            (
                "pet", 1515, "ride", 1515, "uses_ride",
                '[{"kind":"pet","id":1515},{"kind":"ride","id":1515}]',
            ),
            (
                "item", 1515, "title", 1515, "grants_title",
                '[{"kind":"item","id":1515},'
                '{"kind":"item_use_effect","id":7},'
                '{"kind":"title","id":1515}]',
            ),
        ]
        connection.executemany(
            """
            INSERT INTO resource_relation (
                source_kind, source_id, target_kind, target_id,
                relation_type, evidence_type, confidence, source_file,
                source_row, path_json, raw_values_json, build_id
            ) VALUES (?, ?, ?, ?, ?, 'mapped', 1.0, 'fixtures/resources.tsv',
                      3, ?, NULL, ?)
            """,
            [(*values, "a" * 64) for values in relation_values],
        )
    return path


def test_home_search_and_detail_render(tmp_path: Path) -> None:
    app = create_app(_database(tmp_path), PROJECT_ROOT / "public")
    client = TestClient(app)

    home = client.get("/")
    assert home.status_code == 200
    assert "一个称号因何而来，一段乐曲通向何处？" in home.text
    assert "一件称号从何而来" not in home.text
    assert "你的仙路从几时启程，又将在哪里落幕？" in home.text
    assert "一条隐藏许久的任务线" not in home.text
    assert "循着道具、宠物、称号、任务与乐曲留下的线索" in home.text
    assert "每一段有迹可循的仙途" in home.text
    assert "<b>资源概况</b>" not in home.text
    assert '<a class="brand" href="/" aria-label="寻仙资源存档首页">' in home.text
    assert "全部资料" not in home.text
    assert 'class="index-rail"' not in home.text
    assert 'class="search-form"' not in home.text
    assert 'class="resource-list"' not in home.text
    assert 'class="pagination"' not in home.text
    assert "从这里开始" not in home.text
    assert "从上方选择道具、宠物或称号" not in home.text
    assert "在左侧搜索" not in home.text
    assert "WORLD" not in home.text
    assert "东方神话世界" not in home.text
    assert "从凡人一步步踏上寻仙之路" not in home.text
    assert "这里收录道具、宠物、骑乘配置和称号" not in home.text
    assert "件资源" not in home.text
    assert "条关联" not in home.text
    assert "条任务线索" not in home.text
    assert "?kind=items" in home.text
    assert ">道具</b>" in home.text
    assert 'href="/?kind=items"' in home.text
    assert 'href="/?kind=companions"' in home.text
    assert 'href="/?kind=title"' in home.text
    assert 'href="/?kind=item&amp;q="' not in home.text
    assert 'href="/?kind=quest_item&amp;q="' not in home.text
    assert "?kind=companions" in home.text
    assert ">宠物</b>" in home.text
    assert 'href="/?kind=pet&amp;q="' not in home.text
    assert 'href="/?kind=ride&amp;q="' not in home.text
    assert 'href="https://quests.xunxian.wiki"' in home.text
    assert "<span>任</span><b>任务</b><small>8828</small>" in home.text
    assert 'href="https://music.xunxian.wiki"' in home.text
    assert "<span>乐</span><b>音乐</b><small>6414</small>" in home.text
    assert "<small>外链</small>" not in home.text
    assert 'target="_blank" rel="noopener noreferrer"' in home.text


def test_home_overview_does_not_query_the_resource_directory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def unexpected_search(*args, **kwargs):
        raise AssertionError("首页概况不应读取资源目录")

    monkeypatch.setattr(CatalogRepository, "search", unexpected_search)
    client = TestClient(create_app(_database(tmp_path), PROJECT_ROOT / "public"))

    response = client.get("/")

    assert response.status_code == 200
    assert "一个称号因何而来" in response.text


def test_direct_detail_infers_its_directory_kind(
    tmp_path: Path,
    monkeypatch,
) -> None:
    original_search = CatalogRepository.search
    seen_kinds = []

    def recording_search(self, **kwargs):
        seen_kinds.append(kwargs["kind"])
        return original_search(self, **kwargs)

    monkeypatch.setattr(CatalogRepository, "search", recording_search)
    client = TestClient(create_app(_database(tmp_path), PROJECT_ROOT / "public"))

    response = client.get("/resources/title/1515")

    assert response.status_code == 200
    assert seen_kinds == ["title"]


def test_resource_landing_pages_show_default_details(
    tmp_path: Path,
) -> None:
    database_path = _database(tmp_path)
    with sqlite3.connect(database_path) as connection:
        connection.executemany(
            """
            INSERT INTO resource (
                resource_kind, resource_id, display_name, build_id,
                selected_source_file, selected_source_row, metadata_json,
                raw_values_json
            ) VALUES (?, ?, ?, ?, 'fixtures/resources.tsv', ?, '{}', '[]')
            """,
            [
                ("item", 12029, "金签子", "a" * 64, 12029),
                ("pet", 1534, "吊睛斑斓虎王", "a" * 64, 1534),
                ("title", 401, "宁海杰出青年", "a" * 64, 401),
            ],
        )

    client = TestClient(create_app(database_path, PROJECT_ROOT / "public"))

    item_page = client.get("/?kind=items")
    companion_page = client.get("/?kind=companions")
    title_page = client.get("/?kind=title")

    assert item_page.status_code == 200
    assert "<h2>金签子</h2>" in item_page.text
    assert "item:<b>12029</b>" in item_page.text
    assert companion_page.status_code == 200
    assert "<h2>吊睛斑斓虎王</h2>" in companion_page.text
    assert "pet:<b>1534</b>" in companion_page.text
    assert title_page.status_code == 200
    assert "<h2>宁海杰出青年</h2>" in title_page.text
    assert "title:<b>401</b>" in title_page.text


def test_filtered_landing_page_selects_first_matching_result(
    tmp_path: Path,
) -> None:
    database_path = _database(tmp_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO resource (
                resource_kind, resource_id, display_name, build_id,
                selected_source_file, selected_source_row, metadata_json,
                raw_values_json
            ) VALUES (
                'pet', 1534, '吊睛斑斓虎王', ?,
                'fixtures/resources.tsv', 1534, '{}', '[]'
            )
            """,
            ("a" * 64,),
        )

    client = TestClient(create_app(database_path, PROJECT_ROOT / "public"))
    response = client.get("/?kind=companions&category=servant_pet")

    assert response.status_code == 200
    assert "<h2>吊睛斑斓虎王</h2>" in response.text
    assert "侍宠 DOSSIER" in response.text


def test_missing_default_detail_keeps_landing_page_available(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(_database(tmp_path), PROJECT_ROOT / "public"))

    response = client.get("/?kind=items")

    assert response.status_code == 200
    assert "<article class=\"dossier\">" not in response.text


def test_search_results_select_the_first_matching_detail(tmp_path: Path) -> None:
    database_path = _database(tmp_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO resource (
                resource_kind, resource_id, display_name, build_id,
                selected_source_file, selected_source_row, metadata_json,
                raw_values_json
            ) VALUES (
                'item', 12029, '金签子', ?,
                'fixtures/resources.tsv', 12029, '{}', '[]'
            )
            """,
            ("a" * 64,),
        )

    client = TestClient(create_app(database_path, PROJECT_ROOT / "public"))
    response = client.get("/?kind=items&q=金签")

    assert response.status_code == 200
    assert "<h2>金签子</h2>" in response.text
    assert "item:<b>12029</b>" in response.text
    assert 'class="is-current"' in response.text


def test_empty_search_shows_kind_specific_state(tmp_path: Path) -> None:
    client = TestClient(create_app(_database(tmp_path), PROJECT_ROOT / "public"))

    for kind, label in (
        ("items", "道具"),
        ("companions", "宠物"),
        ("title", "称号"),
    ):
        response = client.get(f"/?kind={kind}&q=绝对不存在的资料")
        assert response.status_code == 200
        assert f"<h2>未找到{label}</h2>" in response.text
        assert f"相符的{label}卷宗" in response.text
        assert '<article class="dossier">' not in response.text


def test_pet_dossier_uses_companion_category_label(tmp_path: Path) -> None:
    client = TestClient(create_app(_database(tmp_path), PROJECT_ROOT / "public"))

    response = client.get("/resources/pet/1515?kind=companions")

    assert response.status_code == 200
    assert "灵兽坐骑 DOSSIER" in response.text
    assert ">宠物 DOSSIER<" not in response.text


def test_site_version_and_daily_unique_visitors(tmp_path: Path) -> None:
    visits_database = tmp_path / "visits.db"
    client = TestClient(
        create_app(
            _database(tmp_path),
            PROJECT_ROOT / "public",
            visits_database,
        )
    )

    home = client.get("/")
    assert home.status_code == 200
    assert '<small class="brand-version">v1.0.4</small>' in home.text
    assert 'data-about-open>关于网站</button>' in home.text
    assert '<dialog class="about-dialog"' in home.text
    assert "寻仙资源资料库的整理、维护与网站开发。" in home.text
    assert "https://github.com/icosohedral/xunxian-resources-archive" in home.text
    assert "贴吧用户「耳目清净」" in home.text
    assert (
        '<strong id="today-visitors">0</strong>'
        in home.text
    )

    first = client.post(
        "/api/visit",
        json={"visitor_id": "visitor_0000000001"},
    )
    assert first.status_code == 200
    assert first.json()["count"] == 1
    assert first.json()["is_new"] is True

    repeated = client.post(
        "/api/visit",
        json={"visitor_id": "visitor_0000000001"},
    )
    assert repeated.status_code == 200
    assert repeated.json()["count"] == 1
    assert repeated.json()["is_new"] is False

    second = client.post(
        "/api/visit",
        json={"visitor_id": "visitor_0000000002"},
    )
    assert second.status_code == 200
    assert second.json()["count"] == 2
    assert second.json()["is_new"] is True

    refreshed = client.get("/")
    assert '<strong id="today-visitors">2</strong>' in refreshed.text
    assert client.post(
        "/api/visit",
        json={"visitor_id": "short"},
    ).status_code == 422


def test_home_search_and_detail_content(tmp_path: Path) -> None:
    app = create_app(_database(tmp_path), PROJECT_ROOT / "public")
    client = TestClient(app)

    item_search = client.get("/?kind=items&q=同号")
    assert item_search.status_code == 200
    assert "<h1>道具索引</h1>" in item_search.text
    assert 'placeholder="输入道具名称"' in item_search.text
    assert "合成同号道具" in item_search.text
    assert "合成同号任务道具" in item_search.text
    assert "道具分类" in item_search.text
    assert "普通道具" in item_search.text
    assert "任务道具" in item_search.text
    item_result = re.search(
        r'<a\s+href="/resources/item/1515\?[^"]+"[^>]*>(.*?)</a>',
        item_search.text,
        re.DOTALL,
    )
    assert item_result is not None
    assert "link-count" not in item_result.group(1)

    ordinary_item_search = client.get(
        "/?kind=items&category=item&q=同号"
    )
    assert ordinary_item_search.status_code == 200
    assert "合成同号道具" in ordinary_item_search.text
    assert "合成同号任务道具" not in ordinary_item_search.text
    assert '<option value="item" selected>普通道具</option>' in (
        ordinary_item_search.text
    )

    quest_item_search = client.get(
        "/?kind=items&category=quest_item&q=同号"
    )
    assert quest_item_search.status_code == 200
    assert "合成同号道具" not in quest_item_search.text
    assert "合成同号任务道具" in quest_item_search.text
    assert '<option value="quest_item" selected>任务道具</option>' in (
        quest_item_search.text
    )

    companion_search = client.get("/?kind=companions&q=合成")
    assert companion_search.status_code == 200
    assert "<h1>宠物索引</h1>" in companion_search.text
    assert 'placeholder="输入宠物名称"' in companion_search.text
    assert "合成坐骑宠物" in companion_search.text
    assert 'href="/resources/ride/1515?q=' not in companion_search.text
    assert "<h2>合成坐骑宠物</h2>" in companion_search.text
    assert "link-count" not in companion_search.text
    assert "宠物分类" in companion_search.text
    assert "灵兽坐骑" in companion_search.text
    assert 'value="unclassified"' in companion_search.text
    assert ">其他</option>" in companion_search.text
    assert ">待确认</option>" not in companion_search.text

    spirit_mount_search = client.get(
        "/?kind=companions&category=spirit_mount&q=合成"
    )
    assert spirit_mount_search.status_code == 200
    assert "合成坐骑宠物" in spirit_mount_search.text

    title_search = client.get("/?kind=title&q=合成")
    assert title_search.status_code == 200
    assert "<h1>称号索引</h1>" in title_search.text
    assert 'placeholder="输入称号名称"' in title_search.text
    assert "名称或编号" not in title_search.text
    assert "<kbd>" not in title_search.text
    assert "合成称号" in title_search.text
    assert 'href="/resources/item/1515?q=' not in title_search.text
    assert "<h2>合成称号</h2>" in title_search.text
    assert "称号分组" in title_search.text
    assert "全部称号分组" in title_search.text
    assert '<optgroup label="风物志与收集">' in title_search.text
    assert (
        '<option value="family:6">全部“风物志与收集”分组</option>'
        in title_search.text
    )
    assert (
        '<option value="group:风物志·集">风物志·集</option>'
        in title_search.text
    )
    assert "上级分类名称由资料库根据现有分组归纳" in title_search.text
    assert (
        '<option value="group:车迟国剿匪" disabled>'
        "车迟国剿匪（暂无称号）</option>"
    ) in title_search.text

    grouped_title_search = client.get(
        "/?kind=title&category=group:风物志·集"
    )
    assert grouped_title_search.status_code == 200
    assert "合成称号" in grouped_title_search.text
    assert '<option value="group:风物志·集" selected>风物志·集</option>' in (
        grouped_title_search.text
    )

    grouped_title_api = client.get(
        "/api/search?kind=title&category=group:风物志·集"
    )
    assert grouped_title_api.status_code == 200
    assert grouped_title_api.json()["total"] == 1
    assert grouped_title_api.json()["items"][0]["display_name"] == "合成称号"

    empty_grouped_title_search = client.get(
        "/?kind=title&category=group:风物志·集&q=不存在"
    )
    assert empty_grouped_title_search.status_code == 200
    assert "未找到称号" in empty_grouped_title_search.text

    family_title_api = client.get(
        "/api/search?kind=title&category=family:6"
    )
    assert family_title_api.status_code == 200
    assert family_title_api.json()["total"] == 1
    assert "title_group_family_id" not in (
        family_title_api.json()["items"][0]["metadata"]
    )

    search = client.get("/?q=同号")
    assert search.status_code == 200
    assert "合成同号道具" in search.text
    assert "合成同号任务道具" in search.text

    detail = client.get("/resources/item/1515")
    assert detail.status_code == 200
    assert "合成同号道具" in detail.text
    assert "合成道具的玩家可读完整说明。" in detail.text
    assert "合成道具的玩家可读完整说明。\n第二行" in detail.text
    assert r"\n第二行" not in detail.text
    assert "mb/etc/text.txt · 第 77 行" not in detail.text
    assert '<h3 id="item-description-title">道具说明</h3>' in detail.text
    assert "<dt>说明文本</dt>" not in detail.text
    assert "<dt>使用效果引用</dt>" not in detail.text
    assert '<h3 id="effect-title">使用效果</h3>' in detail.text
    assert '<h3 id="fact-title">概览</h3>' in detail.text
    assert "已确认资料" not in detail.text
    assert "购买价格" in detail.text
    assert "流通金：2砖" in detail.text
    assert "出售价格" in detail.text
    assert "流通金：23银" in detail.text
    assert detail.text.count("<span>叁</span>") == 1
    assert "<span>肆</span>" in detail.text
    assert "资源关系" not in detail.text
    assert "官方说明" not in detail.text
    assert "效果 7" not in detail.text
    assert "类型 43" not in detail.text
    assert detail.text.index("item-description-title") < detail.text.index(
        "effect-title"
    )
    assert "效果备注：合成使用效果" in detail.text
    assert "类型说明" not in detail.text
    assert "获得或激活骑乘配置。" in detail.text
    assert detail.text.index("获得或激活骑乘配置。") < detail.text.index(
        "effect-title"
    )
    item_type_cell = detail.text.split("<dt>道具类型</dt>", 1)[1].split(
        "</div>",
        1,
    )[0]
    assert 'class="item-type-cell"' in item_type_cell
    assert ">5<" not in item_type_cell
    assert "获得或激活骑乘配置。" in item_type_cell
    assert "effect-type-description" not in detail.text
    assert ">详细效果<" not in detail.text
    assert "合成详细效果" in detail.text
    assert "使用后产生已确认的合成效果。" in detail.text
    assert '"使用后产生已确认的合成效果。"' not in detail.text
    assert "mb/skill/state_group.txt · 第 88 行" not in detail.text
    assert "原始资料位置" not in detail.text
    assert "资料出处" not in detail.text
    assert "使用后获得骑乘配置" in detail.text
    assert 'href="/resources/ride/1515"' in detail.text
    assert "合成骑乘配置" in detail.text
    assert "&lt;c:FF00FF00&gt;" not in detail.text
    assert "&lt;c&gt;" not in detail.text

    detail_api = client.get("/api/resources/item/1515").json()
    assert detail_api["item_description"]["description"] == (
        "合成道具的玩家可读完整说明。\n第二行"
    )
    assert detail_api["use_effects"][0]["type_description"] == (
        "获得或激活骑乘配置。"
    )
    assert detail_api["use_effects"][0]["resolved_targets"] == [
        {
            "effect_id": 7,
            "relation_type": "grants_ride",
            "target_kind": "ride",
            "target_id": 1515,
            "target_name": "合成骑乘配置",
            "relation_label": "使用后获得骑乘配置",
            "target_kind_label": "骑乘配置",
        },
        {
            "effect_id": 7,
            "relation_type": "grants_title",
            "target_kind": "title",
            "target_id": 1515,
            "target_name": "合成称号",
            "relation_label": "使用后获得称号",
            "target_kind_label": "称号",
        },
    ]
    assert "合成使用效果" in detail.text
    assert "合成任务" in detail.text
    assert "https://quests.xunxian.wiki/quests/800001" in detail.text


def test_api_keeps_equal_ids_in_separate_namespaces(tmp_path: Path) -> None:
    client = TestClient(
        create_app(_database(tmp_path), PROJECT_ROOT / "public")
    )

    item = client.get("/api/resources/item/1515").json()
    quest_item = client.get("/api/resources/quest_item/1515").json()

    assert item["display_name"] == "合成同号道具"
    assert quest_item["display_name"] == "合成同号任务道具"
    assert item["resource_kind"] != quest_item["resource_kind"]


def test_search_limits_each_page_to_ten_resources(tmp_path: Path) -> None:
    database_path = _database(tmp_path)
    with sqlite3.connect(database_path) as connection:
        connection.executemany(
            """
            INSERT INTO resource (
                resource_kind, resource_id, display_name, build_id,
                selected_source_file, selected_source_row, metadata_json,
                raw_values_json
            ) VALUES (
                'item', ?, ?, ?, 'fixtures/resources.tsv', ?, '{}', '[]'
            )
            """,
            [
                (resource_id, f"分页道具{resource_id}", "a" * 64, resource_id)
                for resource_id in range(1600, 1620)
            ],
        )

    client = TestClient(create_app(database_path, PROJECT_ROOT / "public"))
    first_page = client.get("/api/search?kind=items").json()
    second_page = client.get("/api/search?kind=items&page=2").json()

    assert len(first_page["items"]) == 15
    assert len(second_page["items"]) > 0
    assert first_page["page_count"] >= 2


def test_companion_categories_distinguish_servant_and_item_mount(
    tmp_path: Path,
) -> None:
    database_path = _database(tmp_path)
    with sqlite3.connect(database_path) as connection:
        connection.executemany(
            """
            INSERT INTO resource (
                resource_kind, resource_id, display_name, build_id,
                selected_source_file, selected_source_row, metadata_json,
                raw_values_json
            ) VALUES (?, ?, ?, ?, 'fixtures/resources.tsv', ?, '{}', '[]')
            """,
            [
                ("pet", 1600, "独立侍宠", "a" * 64, 10),
                ("ride", 1600, "独立道具坐骑", "a" * 64, 11),
                ("item", 1600, "独立坐骑道具", "a" * 64, 12),
                ("ride", 1601, "独立防御炮台", "a" * 64, 13),
                ("ride", 1602, "独立场景渔船", "a" * 64, 14),
            ],
        )
        connection.execute(
            """
            INSERT INTO resource_relation (
                source_kind, source_id, target_kind, target_id,
                relation_type, evidence_type, confidence, source_file,
                source_row, path_json, raw_values_json, build_id
            ) VALUES (
                'item', 1600, 'ride', 1600, 'grants_ride',
                'mapped', 1.0, 'fixtures/resources.tsv', 12,
                '[{"kind":"item","id":1600},{"kind":"ride","id":1600}]',
                NULL, ?
            )
            """,
            ("a" * 64,),
        )

    client = TestClient(create_app(database_path, PROJECT_ROOT / "public"))
    servant = client.get(
        "/api/search?kind=companions&category=servant_pet&q=独立"
    ).json()
    item_mount = client.get(
        "/api/search?kind=companions&category=item_mount&q=独立"
    ).json()
    turret = client.get(
        "/api/search?kind=companions&category=turret&q=独立"
    ).json()
    system_mount = client.get(
        "/api/search?kind=companions&category=system_mount&q=独立"
    ).json()

    assert [item["display_name"] for item in servant["items"]] == ["独立侍宠"]
    assert servant["items"][0]["category_label"] == "侍宠"
    assert [item["display_name"] for item in item_mount["items"]] == [
        "独立道具坐骑"
    ]
    assert item_mount["items"][0]["category_label"] == "道具坐骑"
    assert [item["display_name"] for item in turret["items"]] == [
        "独立防御炮台"
    ]
    assert turret["items"][0]["category_label"] == "炮台"
    assert [item["display_name"] for item in system_mount["items"]] == [
        "独立场景渔船"
    ]
    assert system_mount["items"][0]["category_label"] == "系统／场景坐骑"


def test_pagination_uses_directory_only_refresh() -> None:
    script = (PROJECT_ROOT / "public/app.js").read_text(encoding="utf-8")

    assert 'event.target.closest(".pagination a")' in script
    assert "refreshDirectory(paginationLink.href, { preservedPosition })" in script
    assert 'selectors = [".result-caption", ".resource-list", ".pagination"]' in script
    assert "window.history.pushState" in script
    assert 'window.history.scrollRestoration = "manual"' in script
    assert 'root.style.scrollBehavior = "auto"' in script
    assert "preservedPosition = currentDirectoryPosition()" in script
    assert "currentNode.replaceChildren(...nextNode.childNodes)" in script
    assert "paginationLink.blur()" in script
    assert "window.setTimeout(restoreViewportPosition, 50)" in script


def test_missing_resource_returns_404(tmp_path: Path) -> None:
    client = TestClient(
        create_app(_database(tmp_path), PROJECT_ROOT / "public")
    )
    assert client.get("/resources/item/999999").status_code == 404
    assert client.get("/api/resources/not-a-kind/1").status_code == 404


def test_item_without_visible_use_effect_shows_empty_state(
    tmp_path: Path,
) -> None:
    database_path = _database(tmp_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO item_type (
                item_type_id, display_name, note, source_file, source_row,
                raw_value, raw_values_json, build_id
            ) VALUES (
                9, '神奇珍宝', '虚拟道具', 'mb/item/item_type.txt', 10,
                '9', '[]', ?
            )
            """,
            ("a" * 64,),
        )
        connection.execute(
            """
            INSERT INTO resource (
                resource_kind, resource_id, display_name, build_id,
                selected_source_file, selected_source_row, metadata_json,
                raw_values_json
            ) VALUES (
                'item', 1517, '无效果道具', ?,
                'fixtures/resources.tsv', 4, '{"item_type_id": 9}', '[]'
            )
            """,
            ("a" * 64,),
        )
        connection.execute(
            """
            INSERT INTO item_use_effect (
                effect_id, use_type_id, parameters_json, description,
                source_file, source_row, raw_value, raw_values_json, build_id
            ) VALUES (
                9, 3, '["537", "1098"]', '无效果道具',
                'fixtures/use.tsv', 4, '9', '[]', ?
            )
            """,
            ("a" * 64,),
        )
        connection.execute(
            """
            INSERT INTO item_use_link (
                item_id, effect_id, slot_no, amount, source_file,
                source_row, build_id
            ) VALUES (
                1517, 9, 1, NULL, 'fixtures/resources.tsv', 4, ?
            )
            """,
            ("a" * 64,),
        )

    client = TestClient(create_app(database_path, PROJECT_ROOT / "public"))
    detail = client.get("/resources/item/1517")

    assert detail.status_code == 200
    assert "神奇珍宝" in detail.text
    assert ">9<" not in detail.text
    buy_price_cell = detail.text.split("<dt>购买价格</dt>", 1)[1].split(
        "</div>",
        1,
    )[0]
    sell_price_cell = detail.text.split("<dt>出售价格</dt>", 1)[1].split(
        "</div>",
        1,
    )[0]
    assert "<dd>-</dd>" in buy_price_cell
    assert "<dd>-</dd>" in sell_price_cell
    assert (
        '<div class="section-empty">'
        "当前道具没有配置玩家可读的完整说明。</div>"
    ) in detail.text
    assert '<h3 id="effect-title">使用效果</h3>' in detail.text
    assert '<div class="section-empty">无使用效果</div>' in detail.text


def test_generic_numbered_effect_note_is_hidden(tmp_path: Path) -> None:
    database_path = _database(tmp_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE item_use_effect SET description = '通用1' WHERE effect_id = 7"
        )
        connection.execute(
            "DELETE FROM item_use_detail WHERE effect_id = 7"
        )
        connection.execute(
            "DELETE FROM resource_relation "
            "WHERE source_kind = 'item' AND source_id = 1515"
        )

    client = TestClient(create_app(database_path, PROJECT_ROOT / "public"))
    detail = client.get("/resources/item/1515")

    assert detail.status_code == 200
    assert "合成道具的玩家可读完整说明。" in detail.text
    assert "通用1" not in detail.text
    assert '<div class="section-empty">无使用效果</div>' in detail.text
    assert 'class="effect-entry"' not in detail.text


def test_ride_skills_render_for_ride_and_linked_pet(tmp_path: Path) -> None:
    client = TestClient(
        create_app(_database(tmp_path), PROJECT_ROOT / "public")
    )

    ride = client.get("/resources/ride/1515")
    assert ride.status_code == 200
    assert "坐骑技能" in ride.text
    assert "冰箭" in ride.text
    assert "向目标射出寒冰箭并降低移动速度。" in ride.text
    assert "内部备注" in ride.text
    assert "合成冰箭说明" in ride.text
    assert "按骑乘配置中的六个招式槽排列" not in ride.text
    assert "skill:6369" not in ride.text
    assert "技能效果" not in ride.text
    assert '<span class="skill-slot">一</span>' in ride.text
    assert "第 1 式" not in ride.text

    pet = client.get("/api/resources/pet/1515").json()
    assert pet["ride_skill_context"]["ride_id"] == 1515
    assert pet["ride_skill_context"]["inherited_from_ride"] is True
    assert pet["ride_skills"][0]["display_name"] == "冰箭"


def test_servant_pet_hides_ride_skills_and_empty_ride_uses_short_state(
    tmp_path: Path,
) -> None:
    database_path = _database(tmp_path)
    with sqlite3.connect(database_path) as connection:
        connection.executemany(
            """
            INSERT INTO resource (
                resource_kind, resource_id, display_name, build_id,
                selected_source_file, selected_source_row, metadata_json,
                raw_values_json
            ) VALUES (?, 1516, ?, ?, 'fixtures/resources.tsv', 4, '{}', '[]')
            """,
            [
                ("pet", "无坐骑技能宠物", "a" * 64),
                ("ride", "无技能骑乘配置", "a" * 64),
            ],
        )
    client = TestClient(create_app(database_path, PROJECT_ROOT / "public"))

    pet = client.get("/resources/pet/1516")
    ride = client.get("/resources/ride/1516")

    assert '<h3 id="ride-skill-title">坐骑技能</h3>' not in pet.text
    assert "坐骑技能为空" not in pet.text
    assert "<span>叁</span>" in pet.text
    assert "<span>肆</span>" not in pet.text
    assert '<div class="section-empty">坐骑技能为空</div>' in ride.text
    assert "该宠物未关联骑乘配置" not in pet.text
    assert "六个技能槽均为空" not in ride.text


def test_pet_and_ride_details_link_acquisition_items(tmp_path: Path) -> None:
    client = TestClient(
        create_app(_database(tmp_path), PROJECT_ROOT / "public")
    )

    pet = client.get("/resources/pet/1515")
    assert pet.status_code == 200
    assert 'class="fact-grid fact-grid--pet"' in pet.text
    assert "<dt>四维属性</dt>" in pet.text
    assert "力量 15、体魄 15、元神 15、筋骨 15" in pet.text
    assert "<dt>能力配置</dt>" not in pet.text
    assert "<dt>骑乘配置</dt>" not in pet.text
    assert "<dt>宠物外形</dt>" in pet.text
    assert "<dt>角色外形</dt>" not in pet.text
    assert (
        pet.text.index("<dt>模型</dt>")
        < pet.text.index("<dt>宠物外形</dt>")
        < pet.text.index("<dt>资料备注</dt>")
        < pet.text.index("<dt>四维属性</dt>")
    )
    assert "获得道具" in pet.text
    assert "合成骑宠蛋" in pet.text
    assert 'href="/resources/item/1516"' in pet.text
    assert "使用后获得此宠物" in pet.text

    ride = client.get("/resources/ride/1515")
    assert ride.status_code == 200
    assert "合成同号道具" in ride.text
    assert "直接获得此坐骑" in ride.text
    assert "合成骑宠蛋" in ride.text
    assert "通过骑宠" in ride.text
    assert 'href="/resources/pet/1515"' in ride.text

    ride_api = client.get("/api/resources/ride/1515").json()
    acquisition_names = {
        item["item_name"] for item in ride_api["acquisition_items"]
    }
    assert acquisition_names == {"合成同号道具", "合成骑宠蛋"}
    egg = next(
        item
        for item in ride_api["acquisition_items"]
        if item["item_id"] == 1516
    )
    assert egg["type_label"] == "骑宠蛋"
    assert egg["effect_descriptions"] == ["骑宠蛋 合成骑宠"]


def test_title_detail_links_acquisition_items_without_resource_section(
    tmp_path: Path,
) -> None:
    client = TestClient(
        create_app(_database(tmp_path), PROJECT_ROOT / "public")
    )

    title = client.get("/resources/title/1515")
    assert title.status_code == 200
    assert '<h3 id="title-attribute-title">属性加成</h3>' in title.text
    assert "<dt>称号分组</dt>" in title.text
    assert "<dd>风物志·集</dd>" in title.text
    assert ">34<" not in title.text
    assert "主动属性" in title.text
    assert "佩戴称号时生效" in title.text
    assert "力量" in title.text
    assert "+5" in title.text
    assert "最终伤害和治疗输出" in title.text
    assert "+2%" in title.text
    assert "被动属性" in title.text
    assert "获得称号后生效" in title.text
    assert "生命值上限" in title.text
    assert "+50" in title.text
    assert "会心伤害减免" in title.text
    assert "+40%" in title.text
    assert '<h3 id="acquisition-title">获得道具</h3>' in title.text
    assert "称号获得道具" in title.text
    assert "合成同号道具" in title.text
    assert 'href="/resources/item/1515"' in title.text
    assert "使用后获得此称号" in title.text
    assert "资源关系" not in title.text
    assert "<span>贰</span>" in title.text
    assert "<span>叁</span>" in title.text
    assert "<span>肆</span>" in title.text
    assert (
        title.text.index('id="fact-title"')
        < title.text.index('id="title-attribute-title"')
        < title.text.index('id="acquisition-title"')
    )
    title_api = client.get("/api/resources/title/1515").json()
    assert [row["display_value"] for row in title_api["title_attributes"]["active"]] == [
        "+5",
        "+2%",
    ]
    assert [
        row["display_value"] for row in title_api["title_attributes"]["passive"]
    ] == ["+50", "+40%"]


def test_item_index_prioritizes_normal_names_over_internal_placeholders(
    tmp_path: Path,
) -> None:
    database_path = _database(tmp_path)
    with sqlite3.connect(database_path) as connection:
        connection.executemany(
            """
            INSERT INTO resource (
                resource_kind, resource_id, display_name, build_id,
                selected_source_file, selected_source_row, metadata_json,
                raw_values_json
            ) VALUES ('item', ?, ?, ?, 'fixtures/resources.tsv', 3, '{}', '[]')
            """,
            [
                (1, "*占位道具", "a" * 64),
                (2, "正常道具", "a" * 64),
            ],
        )

    client = TestClient(create_app(database_path, PROJECT_ROOT / "public"))
    response = client.get("/?kind=items")

    assert response.status_code == 200
    assert response.text.index("正常道具") < response.text.index("*占位道具")
