"""Topshirish arxivi: QabulFlow_AI.zip (maxfiy fayllar, virtualenv, node_modules va build keshlarisiz).

    python scripts/make_zip.py [--out ../QabulFlow_AI.zip]

Arxivga kiritishdan oldin fayllar maxfiy kalit naqshlariga tekshiriladi; topilsa arxiv yaratilmaydi.
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "dist",
    "var",
    "artifacts",  # e2e/artifacts
    "build",  # showcase/build
}
EXCLUDE_FILES = ["*.pyc", "*.zip", "*.tsbuildinfo", "dump.rdb", ".env", ".env.*", "*.log", "celerybeat-schedule*", ".DS_Store"]
ALLOW_FILES = {".env.example"}

SECRET_PATTERNS = [
    re.compile(rb"sk-ant-[A-Za-z0-9_-]{20,}"),
    re.compile(rb"sk-(proj-)?[A-Za-z0-9]{32,}"),
    re.compile(rb"\b\d{8,10}:AA[A-Za-z0-9_-]{30,}\b"),  # Telegram bot token
    re.compile(rb"AKIA[0-9A-Z]{16}"),
    re.compile(rb"-----BEGIN (RSA |EC )?PRIVATE KEY-----"),
]


def included(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if any(part in EXCLUDE_DIRS for part in rel.parts[:-1]):
        return False
    name = rel.name
    if name in ALLOW_FILES:
        return True
    return not any(fnmatch.fnmatch(name, pat) for pat in EXCLUDE_FILES)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(ROOT / "QabulFlow_AI.zip"))
    args = parser.parse_args()
    out = Path(args.out).resolve()
    files = sorted(p for p in ROOT.rglob("*") if p.is_file() and included(p) and p.resolve() != out)
    leaks = []
    for f in files:
        data = f.read_bytes()
        for pat in SECRET_PATTERNS:
            if pat.search(data):
                leaks.append(f"{f.relative_to(ROOT)} ({pat.pattern[:24]!r})")
    if leaks:
        print("Maxfiy kalitga o'xshash qiymat topildi — arxiv yaratilmadi:", *leaks, sep="\n  ")
        return 1
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for f in files:
            zf.write(f, Path("QabulFlow_AI") / f.relative_to(ROOT))
    size = out.stat().st_size / 1024 / 1024
    print(f"{out} — {len(files)} fayl, {size:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
