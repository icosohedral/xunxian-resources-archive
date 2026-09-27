from pathlib import Path

import pytest

from xunxian_archive.parsers.inventory import check_inventory


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_DATA = PROJECT_ROOT / "original_data"
INVENTORY = PROJECT_ROOT / "reports/inventory.json"


@pytest.mark.skipif(
    not ORIGINAL_DATA.is_dir() or not INVENTORY.is_file(),
    reason="本地只读 original_data 或资料清单不可用",
)
def test_local_original_data_matches_inventory() -> None:
    check_inventory(ORIGINAL_DATA, INVENTORY)

