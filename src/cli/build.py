"""Build the Vue frontend."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = PROJECT_ROOT / "web"


def main() -> int:
    """Run the frontend production build."""
    npm = shutil.which("npm")
    if npm is None:
        print("npm not found on PATH; install Node.js to build the frontend.")
        return 1
    return subprocess.run([npm, "run", "build"], cwd=WEB_ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
