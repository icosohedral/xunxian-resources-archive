from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


WORKER_ROOT = Path(__file__).resolve().parents[1]
DEPLOY_SQL = WORKER_ROOT / "data" / "resource_web.sql"
DEPLOY_MANIFEST = WORKER_ROOT / "data" / "resource_web.deploy.json"
DATABASE_NAME = "xunxian-resource-archive"


def _run(command: list[str], *, dry_run: bool) -> None:
    print("$", " ".join(command), flush=True)
    if not dry_run:
        subprocess.run(command, cwd=WORKER_ROOT, check=True)


def deploy(
    *,
    remote: bool,
    data_only: bool,
    app_only: bool,
    dry_run: bool,
) -> None:
    if not remote and not data_only:
        raise ValueError(
            "本地模式只允许 --data-only；发布 Worker 请明确添加 --remote"
        )
    if not DEPLOY_MANIFEST.is_file():
        raise FileNotFoundError(
            "缺少部署清单；请先运行 scripts/build_web_database.py"
        )
    manifest = json.loads(DEPLOY_MANIFEST.read_text(encoding="utf-8"))
    mode = manifest.get("mode")
    if mode not in {"full", "incremental", "noop"}:
        raise ValueError(f"未知部署模式：{mode!r}")

    print(
        "数据模式："
        f"{mode}；资源变更 {manifest['changed_resources']}，"
        f"详情变更 {manifest['changed_detail_resources']}，"
        f"删除 {manifest['removed_resources']}，"
        f"SQL {manifest['sql_bytes']} bytes",
        flush=True,
    )

    if not app_only:
        if mode == "noop":
            print("数据没有变化，跳过 D1 导入。", flush=True)
        else:
            command = [
                "npx",
                "wrangler",
                "d1",
                "execute",
                DATABASE_NAME,
                "--remote" if remote else "--local",
                f"--file={DEPLOY_SQL.relative_to(WORKER_ROOT)}",
            ]
            if remote:
                command.append("--yes")
            _run(command, dry_run=dry_run)

    if not data_only:
        _run(["uv", "run", "pywrangler", "deploy"], dry_run=dry_run)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="按部署清单增量同步 D1，并发布 Cloudflare Worker。",
    )
    parser.add_argument(
        "--remote",
        action="store_true",
        help="同步远端 D1；省略时只操作 Wrangler 本地数据库",
    )
    parser.add_argument("--data-only", action="store_true")
    parser.add_argument("--app-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    arguments = parser.parse_args()
    if arguments.data_only and arguments.app_only:
        parser.error("--data-only 与 --app-only 不能同时使用")
    deploy(
        remote=arguments.remote,
        data_only=arguments.data_only,
        app_only=arguments.app_only,
        dry_run=arguments.dry_run,
    )


if __name__ == "__main__":
    main()
