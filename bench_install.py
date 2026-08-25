#!/usr/bin/env python3
"""Measure cold and warm install times for the uv workspace and both Poetry projects.

"Cold" wipes the local `.venv` and the tool's cache directory before
running; "warm" runs the same install a second time against the now
populated cache. Each scenario runs N times (default 3) and the report
prints the median so a single hiccup does not dominate the number.

Results also land in `benchmarks/results.json` for the article to link
against. Pure formatting + aggregation helpers live at module scope
so they are unit-testable without shelling out to `uv` or `poetry`.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

CODEBASE_ROOT = Path(__file__).resolve().parent
SAMPLE_ROOT = CODEBASE_ROOT / "sample"
POETRY_PACKAGES = CODEBASE_ROOT / "poetry-sample" / "packages"
DEFAULT_RUNS = 3


@dataclass
class Measurement:
    scenario: str
    tool: str
    kind: str
    seconds: list[float] = field(default_factory=list)

    @property
    def median(self) -> float:
        return statistics.median(self.seconds) if self.seconds else 0.0


def format_row(m: Measurement) -> str:
    return (
        f"{m.scenario:<24} {m.tool:<7} {m.kind:<5} "
        f"median={m.median:6.2f}s  runs={len(m.seconds)}"
    )


def summarize(measurements: list[Measurement]) -> dict[str, dict[str, float]]:
    grouped: dict[str, dict[str, float]] = {}
    for m in measurements:
        grouped.setdefault(m.scenario, {})[m.kind] = round(m.median, 3)
    return grouped


def total_by_kind(measurements: list[Measurement], tool: str, kind: str) -> float:
    return round(sum(m.median for m in measurements if m.tool == tool and m.kind == kind), 3)


def _remove_tree(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def _timed(cmd: list[str], cwd: Path, env: dict[str, str] | None = None) -> float:
    merged_env = {**os.environ, **(env or {})}
    start = time.perf_counter()
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, env=merged_env)
    return time.perf_counter() - start


def measure_uv(runs: int, uv_cache: Path) -> list[Measurement]:
    cold = Measurement("uv-workspace", "uv", "cold")
    warm = Measurement("uv-workspace", "uv", "warm")
    cmd = ["uv", "sync", "--all-packages", "--cache-dir", str(uv_cache)]
    for _ in range(runs):
        _remove_tree(SAMPLE_ROOT / ".venv")
        _remove_tree(uv_cache)
        cold.seconds.append(_timed(cmd, SAMPLE_ROOT))
        warm.seconds.append(_timed(cmd, SAMPLE_ROOT))
    return [cold, warm]


def measure_poetry(project: str, runs: int, poetry_cache: Path) -> list[Measurement]:
    project_dir = POETRY_PACKAGES / project
    cold = Measurement(f"poetry-{project}", "poetry", "cold")
    warm = Measurement(f"poetry-{project}", "poetry", "warm")
    env = {"POETRY_CACHE_DIR": str(poetry_cache)}
    cmd = ["poetry", "install", "--no-interaction"]
    for _ in range(runs):
        _remove_tree(project_dir / ".venv")
        _remove_tree(poetry_cache)
        cold.seconds.append(_timed(cmd, project_dir, env))
        warm.seconds.append(_timed(cmd, project_dir, env))
    return [cold, warm]


def write_json(path: Path, measurements: list[Measurement]) -> None:
    payload = [asdict(m) | {"median_seconds": round(m.median, 3)} for m in measurements]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS)
    parser.add_argument(
        "--out",
        type=Path,
        default=CODEBASE_ROOT / "benchmarks" / "results.json",
    )
    parser.add_argument(
        "--uv-cache",
        type=Path,
        default=CODEBASE_ROOT / ".bench-cache" / "uv",
    )
    parser.add_argument(
        "--poetry-cache",
        type=Path,
        default=CODEBASE_ROOT / ".bench-cache" / "poetry",
    )
    args = parser.parse_args(argv)

    measurements: list[Measurement] = []
    measurements.extend(measure_uv(args.runs, args.uv_cache))
    for project in ("shared_lib", "app"):
        measurements.extend(measure_poetry(project, args.runs, args.poetry_cache))

    for m in measurements:
        print(format_row(m))

    poetry_cold_sum = total_by_kind(measurements, "poetry", "cold")
    poetry_warm_sum = total_by_kind(measurements, "poetry", "warm")
    print()
    print(f"poetry cold total (both projects): {poetry_cold_sum:.2f}s")
    print(f"poetry warm total (both projects): {poetry_warm_sum:.2f}s")

    write_json(args.out, measurements)
    print(f"\nwrote {args.out.relative_to(CODEBASE_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
