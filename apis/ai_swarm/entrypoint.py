#!/usr/bin/env python
"""Entrypoint for the ai_swarm package."""

import sys
from pathlib import Path

package_dir = Path(__file__).resolve().parent
project_root = package_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from ai_swarm.app import app

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
