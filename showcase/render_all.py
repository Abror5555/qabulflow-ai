"""Showcase rasmlarini bitta buyruq bilan qayta yaratish.

    python showcase/render_all.py --base-url http://127.0.0.1:8000 [--reseed]

1. (--reseed) demo ma'lumotlarni qayta yaratadi: backend/manage.py seed_demo (DEMO_MODE=true kerak)
2. capture_screenshots.py — ishlayotgan ilovadan asl ekranlar -> assets/screenshots/
3. render_showcase.py — 7 ta yakuniy PNG -> assets/showcase/ (o'lcham va yuklanish tekshiruvi bilan)

Ilova (DEMO_MODE=true) --base-url manzilida ishlab turgan bo'lishi kerak.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def run(cmd: list[str], cwd: Path) -> None:
    print("$", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--reseed", action="store_true", help="avval demo ma'lumotlarni qayta yaratish")
    args = parser.parse_args()
    py = sys.executable
    if args.reseed:
        run([py, "manage.py", "seed_demo"], cwd=ROOT / "backend")
    run([py, str(HERE / "capture_screenshots.py"), "--base-url", args.base_url], cwd=ROOT)
    run([py, str(HERE / "render_showcase.py")], cwd=ROOT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
