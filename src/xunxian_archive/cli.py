"""项目命令入口。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from xunxian_archive.builders.catalog import build_catalog
from xunxian_archive.parsers.inventory import check_inventory, write_inventory
from xunxian_archive.relations.core import build_core_relations
from xunxian_archive.validation import validate_project


def inventory_main() -> None:
    parser = argparse.ArgumentParser(description="清点只读 original_data")
    parser.add_argument("--root", type=Path, default=Path("original_data"))
    parser.add_argument("--output", type=Path, default=Path("reports/inventory.json"))
    parser.add_argument("--check", action="store_true", help="与已有清单比较，不写文件")
    args = parser.parse_args()
    if args.check:
        check_inventory(args.root, args.output)
        print("original_data 与资料清单一致")
    else:
        report = write_inventory(args.root, args.output)
        print(
            f"已清点 {report['summary']['file_count']} 个文件；"
            f"完整性状态：{report['summary']['completeness_status']}"
        )


def build_main() -> None:
    parser = argparse.ArgumentParser(description="构建资源目录数据库")
    parser.add_argument("--root", type=Path, default=Path("original_data"))
    parser.add_argument("--output", type=Path, default=Path("outputs/catalog.db"))
    parser.add_argument(
        "--config", type=Path, default=Path("config/source_routes.toml")
    )
    parser.add_argument(
        "--report", type=Path, default=Path("reports/build_summary.json")
    )
    parser.add_argument(
        "--quest-links",
        type=Path,
        default=Path("data_contracts/imported/quest_resource_links.json"),
    )
    parser.add_argument(
        "--quest-schema",
        type=Path,
        default=Path("schemas/quest_resource_links.schema.json"),
    )
    args = parser.parse_args()
    summary = build_catalog(args.root, args.output, args.config)
    relation_summary = build_core_relations(
        original_root=args.root,
        database_path=args.output,
        quest_contract_path=args.quest_links,
        quest_schema_path=args.quest_schema,
    )
    summary["relations"] = relation_summary
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"已构建 {summary['resource_count']} 个资源身份，"
        f"保留 {summary['raw_record_count']} 条来源记录；"
        f"{summary['parse_issue_count']} 条解析异常已写入报告"
    )


def validate_main() -> None:
    parser = argparse.ArgumentParser(description="校验项目配置与数据契约")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    messages = validate_project(args.project_root)
    for message in messages:
        print(message)
