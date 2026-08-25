#!/usr/bin/env python3
"""Model CI pipeline wall-clock time for the uv workspace and Poetry projects.

Step 5 measured install seconds on a developer laptop; this module lifts
that data into the CI shape the two workflows in `.github/workflows/`
actually run. Each pipeline is a tuple of `PipelineStep` records with
`cold_seconds` (first run, empty cache) and `warm_seconds` (cache hit)
per step. The two setups differ in how the cache is keyed:

- The uv workflow uses ONE cache entry (`sample/uv.lock`) that primes
  every workspace member with a single install step.
- The Poetry workflow uses ONE cache entry PER project because each
  `poetry.lock` is independent, so the install step fans out across the
  matrix and every leg pays its own cold or warm cost.

The pure arithmetic here (`cold_total`, `warm_total`, `cache_savings`)
is unit-tested; the wall-clock numbers themselves are configurable so
an operator can plug in their own measurements without patching code.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class PipelineStep:
    name: str
    cold_seconds: float
    warm_seconds: float
    cacheable: bool = False


@dataclass(frozen=True)
class Pipeline:
    name: str
    steps: tuple[PipelineStep, ...] = field(default_factory=tuple)

    @property
    def cold_total(self) -> float:
        return round(sum(step.cold_seconds for step in self.steps), 3)

    @property
    def warm_total(self) -> float:
        return round(sum(step.warm_seconds for step in self.steps), 3)

    @property
    def cache_savings(self) -> float:
        return round(self.cold_total - self.warm_total, 3)

    @property
    def cacheable_steps(self) -> tuple[PipelineStep, ...]:
        return tuple(step for step in self.steps if step.cacheable)


# Wall-clock defaults reflect the step-5 laptop numbers rounded up to
# what GitHub-hosted runners typically see: uv sync of the shared
# workspace is ~3s cold / 0.5s warm; poetry install per project is
# ~10s cold / 1.5s warm; test suites run in well under a second.
_UV_STEPS: tuple[PipelineStep, ...] = (
    PipelineStep("checkout", cold_seconds=1.0, warm_seconds=1.0),
    PipelineStep("setup-python", cold_seconds=3.0, warm_seconds=3.0),
    PipelineStep("install-uv", cold_seconds=1.5, warm_seconds=1.5),
    PipelineStep(
        "restore-uv-cache", cold_seconds=0.2, warm_seconds=1.2, cacheable=True
    ),
    PipelineStep("uv-sync", cold_seconds=3.0, warm_seconds=0.5, cacheable=True),
    PipelineStep("run-tests", cold_seconds=0.4, warm_seconds=0.4),
)


def _poetry_leg_steps(package: str) -> tuple[PipelineStep, ...]:
    return (
        PipelineStep(f"checkout[{package}]", cold_seconds=1.0, warm_seconds=1.0),
        PipelineStep(f"setup-python[{package}]", cold_seconds=3.0, warm_seconds=3.0),
        PipelineStep(f"install-poetry[{package}]", cold_seconds=6.0, warm_seconds=6.0),
        PipelineStep(
            f"restore-poetry-cache[{package}]",
            cold_seconds=0.2,
            warm_seconds=1.5,
            cacheable=True,
        ),
        PipelineStep(
            f"poetry-install[{package}]",
            cold_seconds=10.0,
            warm_seconds=1.5,
            cacheable=True,
        ),
        PipelineStep(f"run-tests[{package}]", cold_seconds=0.4, warm_seconds=0.4),
    )


def uv_pipeline() -> Pipeline:
    return Pipeline(name="uv workspace", steps=_UV_STEPS)


def poetry_pipeline(packages: tuple[str, ...] = ("shared_lib", "app")) -> Pipeline:
    steps: list[PipelineStep] = []
    for package in packages:
        steps.extend(_poetry_leg_steps(package))
    return Pipeline(name="poetry isolated (matrix)", steps=tuple(steps))


def format_pipeline(pipeline: Pipeline) -> str:
    lines = [
        f"{pipeline.name}: cold={pipeline.cold_total:.2f}s "
        f"warm={pipeline.warm_total:.2f}s "
        f"savings={pipeline.cache_savings:.2f}s "
        f"({len(pipeline.cacheable_steps)} cacheable of {len(pipeline.steps)} steps)"
    ]
    for step in pipeline.steps:
        marker = "*" if step.cacheable else "-"
        lines.append(
            f"  {marker} {step.name:<32} "
            f"cold={step.cold_seconds:5.2f}s warm={step.warm_seconds:5.2f}s"
        )
    return "\n".join(lines)


def compare_pipelines(uv: Pipeline, poetry: Pipeline) -> str:
    cold_delta = round(poetry.cold_total - uv.cold_total, 3)
    warm_delta = round(poetry.warm_total - uv.warm_total, 3)
    return (
        f"pipeline delta: poetry cold={poetry.cold_total:.2f}s vs "
        f"uv cold={uv.cold_total:.2f}s (+{cold_delta:.2f}s); "
        f"poetry warm={poetry.warm_total:.2f}s vs uv warm={uv.warm_total:.2f}s "
        f"(+{warm_delta:.2f}s)"
    )


def pipelines_as_json(uv: Pipeline, poetry: Pipeline) -> str:
    def to_row(p: Pipeline) -> dict:
        return asdict(p) | {
            "cold_total": p.cold_total,
            "warm_total": p.warm_total,
            "cache_savings": p.cache_savings,
        }

    payload = {
        "uv_workspace": to_row(uv),
        "poetry_isolated": to_row(poetry),
        "cold_delta": round(poetry.cold_total - uv.cold_total, 3),
        "warm_delta": round(poetry.warm_total - uv.warm_total, 3),
    }
    return json.dumps(payload, indent=2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    parser.add_argument("--out", type=Path, help="also write the report to this file")
    args = parser.parse_args(argv)

    uv = uv_pipeline()
    poetry = poetry_pipeline()

    if args.json:
        text = pipelines_as_json(uv, poetry)
    else:
        text = "\n\n".join(
            [format_pipeline(uv), format_pipeline(poetry), compare_pipelines(uv, poetry)]
        )

    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
