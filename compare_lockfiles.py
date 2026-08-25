#!/usr/bin/env python3
"""Read every lockfile in the sample trees and print the pytest pin each resolver chose.

The uv workspace resolves once for both members, so exactly one pytest
version is expected. The Poetry projects resolve independently, so a
divergent pin between shared_lib and app is expected here.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
UV_LOCK = ROOT / "sample" / "uv.lock"
POETRY_LOCKS = {
    "shared_lib": ROOT / "poetry-sample" / "packages" / "shared_lib" / "poetry.lock",
    "app": ROOT / "poetry-sample" / "packages" / "app" / "poetry.lock",
}

PACKAGE_BLOCK = re.compile(
    r'\[\[package\]\]\s*\nname = "([^"]+)"\s*\nversion = "([^"]+)"'
)


def pinned_versions(lock_path: Path) -> dict[str, str]:
    text = lock_path.read_text(encoding="utf-8")
    return {name: version for name, version in PACKAGE_BLOCK.findall(text)}


def report_uv(pins: dict[str, str]) -> str:
    return f"uv workspace lock  → pytest {pins['pytest']}"


def report_poetry(project: str, pins: dict[str, str]) -> str:
    return f"poetry {project:<11} lock → pytest {pins['pytest']}"


def main() -> int:
    uv_pins = pinned_versions(UV_LOCK)
    poetry_pins = {name: pinned_versions(path) for name, path in POETRY_LOCKS.items()}

    print(report_uv(uv_pins))
    for project, pins in poetry_pins.items():
        print(report_poetry(project, pins))

    uv_pytest = uv_pins["pytest"]
    poetry_pytest = {p: pins["pytest"] for p, pins in poetry_pins.items()}
    diverged = len(set(poetry_pytest.values())) > 1

    print()
    print(f"uv unity:      1 pytest across the workspace ({uv_pytest})")
    print(f"poetry drift:  {'yes' if diverged else 'no'} — pins = {poetry_pytest}")

    return 0 if diverged else 1


if __name__ == "__main__":
    sys.exit(main())
