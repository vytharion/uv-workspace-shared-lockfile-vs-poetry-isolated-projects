#!/usr/bin/env python3
"""Compare two lockfile snapshots and report package-level and line-level churn.

The uv workspace and each Poetry project write TOML lockfiles with the
same top-level `[[package]] name / version` shape, so a single parser
handles both formats. Given `--before` and `--after` paths, the tool
prints how many packages were added, removed, or upgraded, plus the
raw line-diff volume between the two files.
"""
from __future__ import annotations

import argparse
import difflib
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

_PACKAGE_BLOCK = re.compile(
    r'\[\[package\]\]\s*\nname = "([^"]+)"\s*\nversion = "([^"]+)"'
)


@dataclass(frozen=True)
class PackageChurn:
    added: dict[str, str] = field(default_factory=dict)
    removed: dict[str, str] = field(default_factory=dict)
    upgraded: dict[str, tuple[str, str]] = field(default_factory=dict)

    @property
    def total_changed(self) -> int:
        return len(self.added) + len(self.removed) + len(self.upgraded)


def parse_pins(text: str) -> dict[str, str]:
    return {name: version for name, version in _PACKAGE_BLOCK.findall(text)}


def package_churn(before_text: str, after_text: str) -> PackageChurn:
    before = parse_pins(before_text)
    after = parse_pins(after_text)
    added = {name: ver for name, ver in after.items() if name not in before}
    removed = {name: ver for name, ver in before.items() if name not in after}
    shared = before.keys() & after.keys()
    upgraded = {
        name: (before[name], after[name])
        for name in shared
        if before[name] != after[name]
    }
    return PackageChurn(added=added, removed=removed, upgraded=upgraded)


def line_churn(before_text: str, after_text: str) -> tuple[int, int]:
    diff = difflib.unified_diff(
        before_text.splitlines(),
        after_text.splitlines(),
        lineterm="",
        n=0,
    )
    added = 0
    removed = 0
    for line in diff:
        if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
            continue
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1
    return added, removed


def format_report(label: str, before_text: str, after_text: str) -> str:
    churn = package_churn(before_text, after_text)
    added_lines, removed_lines = line_churn(before_text, after_text)
    lines = [
        f"{label}: +{added_lines} -{removed_lines} lines "
        f"({churn.total_changed} packages changed)",
        f"  added:    {sorted(churn.added.items())}",
        f"  removed:  {sorted(churn.removed.items())}",
        f"  upgraded: {sorted(churn.upgraded.items())}",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True, help="report row label")
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    args = parser.parse_args(argv)

    before_text = args.before.read_text(encoding="utf-8")
    after_text = args.after.read_text(encoding="utf-8")
    print(format_report(args.label, before_text, after_text))
    return 0


if __name__ == "__main__":
    sys.exit(main())
