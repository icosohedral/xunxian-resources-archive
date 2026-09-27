"""任务资源轻量交换文件读取与语义校验。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from xunxian_archive.web.links import quest_url


def load_quest_resource_links(
    contract_path: Path,
    schema_path: Path,
) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema).iter_errors(contract),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        details = "; ".join(
            f"{'/'.join(map(str, error.absolute_path)) or '<root>'}: {error.message}"
            for error in errors[:10]
        )
        raise ValueError(f"任务资源交换文件不符合 Schema：{details}")

    seen: set[tuple[str, int, int, str]] = set()
    base_url = contract["quest_site_base_url"]
    for link in contract["links"]:
        expected_path = f"/quests/{link['quest_id']}"
        if link["quest_site_path"] != expected_path:
            raise ValueError(
                f"quest_site_path 与 quest_id 不一致：{link['quest_site_path']}"
            )
        quest_url(link["quest_id"], base_url=base_url)
        identity = (
            link["resource_kind"],
            link["resource_id"],
            link["quest_id"],
            link["relation_type"],
        )
        if identity in seen:
            raise ValueError(f"任务资源关系重复：{identity}")
        seen.add(identity)
    return contract

