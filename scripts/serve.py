#!/usr/bin/env python3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import uvicorn


if __name__ == "__main__":
    uvicorn.run(
        "xunxian_archive.web.app:create_app",
        factory=True,
        host="127.0.0.1",
        port=8000,
        reload=False,
    )

