#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from xunxian_archive.cli import inventory_main


if __name__ == "__main__":
    inventory_main()
