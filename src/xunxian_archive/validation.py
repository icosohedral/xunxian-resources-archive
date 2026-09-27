"""项目边界、配置与外部数据契约校验。"""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

from xunxian_archive.models import ResourceKind
from xunxian_archive.relations.quest_links import load_quest_resource_links


def validate_project(project_root: Path) -> list[str]:
    messages: list[str] = []
    config_path = project_root / "config/source_routes.toml"
    config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    kinds = {source["resource_kind"] for source in config["source"]}
    required_kinds = {
        ResourceKind.ITEM.value,
        ResourceKind.QUEST_ITEM.value,
        ResourceKind.PET.value,
        ResourceKind.TITLE.value,
    }
    missing_kinds = required_kinds - kinds
    if missing_kinds:
        raise ValueError(f"缺少独立编号空间：{sorted(missing_kinds)}")
    messages.append("编号空间配置有效")

    contract = load_quest_resource_links(
        project_root / "data_contracts/imported/quest_resource_links.json",
        project_root / "schemas/quest_resource_links.schema.json",
    )
    messages.append(f"任务交换契约有效（{len(contract['links'])} 条关系）")

    git_check = subprocess.run(
        ["git", "check-ignore", "-q", "original_data/index_list.txt"],
        cwd=project_root,
        check=False,
    )
    if git_check.returncode != 0:
        raise RuntimeError("original_data 未被 Git 忽略")
    messages.append("original_data 已受 Git 忽略规则保护")

    tracked_databases = list(project_root.glob("data_contracts/**/*.db"))
    if tracked_databases:
        raise RuntimeError(f"data_contracts 中不得复制任务数据库：{tracked_databases}")
    messages.append("未发现复制的任务数据库")
    return messages

