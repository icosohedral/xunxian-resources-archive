import subprocess
from pathlib import Path

from xunxian_archive.validation import validate_project


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_original_data_is_ignored_by_git() -> None:
    result = subprocess.run(
        ["git", "check-ignore", "original_data/index_list.txt"],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0


def test_project_contract_and_boundaries_validate() -> None:
    messages = validate_project(PROJECT_ROOT)

    assert "编号空间配置有效" in messages
    assert "未发现复制的任务数据库" in messages

