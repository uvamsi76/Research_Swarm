#!/usr/bin/env python
"""Entrypoint for the tool_service package."""

import sys
from pathlib import Path

package_dir = Path(__file__).resolve().parent
project_root = package_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from tool_service.app import app

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=3000)
