import json
from pathlib import Path

import pytest

from xunxian_archive.relations.quest_links import load_quest_resource_links
from xunxian_archive.web.links import quest_url


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = PROJECT_ROOT / "schemas/quest_resource_links.schema.json"


def test_imported_contract_is_valid() -> None:
    contract = load_quest_resource_links(
        PROJECT_ROOT / "data_contracts/imported/quest_resource_links.json",
        SCHEMA,
    )

    assert contract["schema_version"] == 1
    assert isinstance(contract["links"], list)
    assert all(
        link["quest_site_path"] == f"/quests/{link['quest_id']}"
        for link in contract["links"]
    )


def test_synthetic_example_is_valid_and_uses_task_id_link() -> None:
    contract = load_quest_resource_links(
        PROJECT_ROOT / "data_contracts/examples/quest_resource_links.example.json",
        SCHEMA,
    )
    link = contract["links"][0]

    assert quest_url(link["quest_id"]) == (
        "https://quests.xunxian.wiki/quests/800001"
    )


def test_path_must_match_quest_id(tmp_path: Path) -> None:
    contract = json.loads(
        (
            PROJECT_ROOT
            / "data_contracts/examples/quest_resource_links.example.json"
        ).read_text(encoding="utf-8")
    )
    contract["links"][0]["quest_site_path"] = "/quests/999999"
    path = tmp_path / "links.json"
    path.write_text(json.dumps(contract, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="不一致"):
        load_quest_resource_links(path, SCHEMA)


@pytest.mark.parametrize("invalid_id", [0, -1, True, "1"])
def test_invalid_quest_ids_do_not_create_links(invalid_id: object) -> None:
    with pytest.raises(ValueError):
        quest_url(invalid_id)  # type: ignore[arg-type]
