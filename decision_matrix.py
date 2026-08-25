#!/usr/bin/env python3
"""Score uv workspaces against Poetry isolated projects on nine weighted criteria.

Steps 1-7 produced the raw evidence: a two-package sample under each
setup, a forced resolver conflict, laptop bench numbers, a refactor
propagation plan, and a CI pipeline model. Step 8 collapses those
findings into a decision matrix so a reader can plug in their own
scenario and get a defensible recommendation instead of a vibes call.

The matrix is deliberately small (nine criteria) and every verdict is
backed by a specific earlier step. Weights are integers in `[1, 3]`
so the scoring stays auditable: nothing here is a black-box regression.
Scenario helpers (`monorepo_scenario`, `multi_team_scenario`,
`hybrid_scenario`) reweight the same criteria for the situations we
saw in the earlier steps — they do not invent new evidence.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path


class Verdict(str, Enum):
    UV_WINS = "uv-wins"
    POETRY_WINS = "poetry-wins"
    TIE = "tie"


class Recommendation(str, Enum):
    USE_UV_WORKSPACE = "use-uv-workspace"
    USE_POETRY_ISOLATED = "use-poetry-isolated"
    EITHER_WORKS = "either-works"


@dataclass(frozen=True)
class Criterion:
    name: str
    weight: int
    verdict: Verdict
    rationale: str
    evidence_step: int

    def __post_init__(self) -> None:
        if self.weight < 1 or self.weight > 3:
            raise ValueError(f"weight must be in [1, 3], got {self.weight}")
        if self.evidence_step < 1 or self.evidence_step > 8:
            raise ValueError(
                f"evidence_step must be in [1, 8], got {self.evidence_step}"
            )


@dataclass(frozen=True)
class DecisionMatrix:
    name: str
    criteria: tuple[Criterion, ...] = field(default_factory=tuple)

    @property
    def uv_score(self) -> int:
        return sum(c.weight for c in self.criteria if c.verdict is Verdict.UV_WINS)

    @property
    def poetry_score(self) -> int:
        return sum(
            c.weight for c in self.criteria if c.verdict is Verdict.POETRY_WINS
        )

    @property
    def tie_weight(self) -> int:
        return sum(c.weight for c in self.criteria if c.verdict is Verdict.TIE)

    @property
    def total_weight(self) -> int:
        return sum(c.weight for c in self.criteria)

    def criteria_for(self, verdict: Verdict) -> tuple[Criterion, ...]:
        return tuple(c for c in self.criteria if c.verdict is verdict)


@dataclass(frozen=True)
class RecommendationResult:
    matrix_name: str
    recommendation: Recommendation
    uv_score: int
    poetry_score: int
    tie_weight: int
    total_weight: int
    margin_ratio: float
    rationale: str


_CRITERIA: tuple[Criterion, ...] = (
    Criterion(
        name="shared-lockfile churn",
        weight=3,
        verdict=Verdict.UV_WINS,
        rationale=(
            "one uv.lock re-resolves both packages in one command; "
            "per-project poetry.lock files churn independently"
        ),
        evidence_step=5,
    ),
    Criterion(
        name="cross-package refactor cost",
        weight=3,
        verdict=Verdict.UV_WINS,
        rationale=(
            "step-6 planner: uv touches 2 files + 1 command + 1 lockfile; "
            "poetry touches 4 files + 4 commands + 2 lockfiles + a version bump"
        ),
        evidence_step=6,
    ),
    Criterion(
        name="CI pipeline wall-clock",
        weight=2,
        verdict=Verdict.UV_WINS,
        rationale=(
            "step-7 model: shared cache primes both packages once, "
            "the poetry matrix pays install-poetry and setup-python per leg"
        ),
        evidence_step=7,
    ),
    Criterion(
        name="cold install time on a fresh machine",
        weight=1,
        verdict=Verdict.UV_WINS,
        rationale="step-5 bench: uv sync is single-digit seconds where poetry install stacks per project",
        evidence_step=5,
    ),
    Criterion(
        name="transitive conflict clarity",
        weight=2,
        verdict=Verdict.TIE,
        rationale=(
            "step-4 forced a conflict: both resolvers reject the incompatibility fast; "
            "poetry's message is per-project, uv's is workspace-wide"
        ),
        evidence_step=4,
    ),
    Criterion(
        name="independent release cadence per package",
        weight=3,
        verdict=Verdict.POETRY_WINS,
        rationale=(
            "poetry projects publish and version on their own timeline; "
            "the uv workspace pins all members through one lockfile snapshot"
        ),
        evidence_step=3,
    ),
    Criterion(
        name="multi-team ownership boundary",
        weight=3,
        verdict=Verdict.POETRY_WINS,
        rationale=(
            "isolated pyproject.toml + poetry.lock per project gives each team "
            "its own review surface; uv workspaces share the lockfile globally"
        ),
        evidence_step=3,
    ),
    Criterion(
        name="ecosystem maturity and plugin surface",
        weight=2,
        verdict=Verdict.POETRY_WINS,
        rationale=(
            "poetry ships publish, dynamic-versioning, and shell plugins today; "
            "uv is younger and covers fewer publishing workflows"
        ),
        evidence_step=1,
    ),
    Criterion(
        name="onboarding a new package to the monorepo",
        weight=2,
        verdict=Verdict.UV_WINS,
        rationale=(
            "adding packages/foo under uv is a `members` glob + one sync; "
            "poetry needs a new pyproject.toml, its own lockfile, and consumer path deps"
        ),
        evidence_step=2,
    ),
)


def default_matrix() -> DecisionMatrix:
    return DecisionMatrix(name="default", criteria=_CRITERIA)


def _reweight(overrides: dict[str, int]) -> tuple[Criterion, ...]:
    rebuilt: list[Criterion] = []
    for criterion in _CRITERIA:
        new_weight = overrides.get(criterion.name, criterion.weight)
        rebuilt.append(
            Criterion(
                name=criterion.name,
                weight=new_weight,
                verdict=criterion.verdict,
                rationale=criterion.rationale,
                evidence_step=criterion.evidence_step,
            )
        )
    return tuple(rebuilt)


def monorepo_scenario() -> DecisionMatrix:
    overrides = {
        "shared-lockfile churn": 3,
        "cross-package refactor cost": 3,
        "onboarding a new package to the monorepo": 3,
        "independent release cadence per package": 1,
        "multi-team ownership boundary": 1,
    }
    return DecisionMatrix(name="monorepo", criteria=_reweight(overrides))


def multi_team_scenario() -> DecisionMatrix:
    overrides = {
        "independent release cadence per package": 3,
        "multi-team ownership boundary": 3,
        "ecosystem maturity and plugin surface": 3,
        "shared-lockfile churn": 1,
        "cross-package refactor cost": 1,
    }
    return DecisionMatrix(name="multi-team", criteria=_reweight(overrides))


def hybrid_scenario() -> DecisionMatrix:
    overrides = {
        "shared-lockfile churn": 1,
        "cross-package refactor cost": 1,
        "CI pipeline wall-clock": 1,
        "onboarding a new package to the monorepo": 1,
        "transitive conflict clarity": 1,
        "independent release cadence per package": 2,
        "multi-team ownership boundary": 2,
    }
    return DecisionMatrix(name="hybrid", criteria=_reweight(overrides))


def _pick_recommendation(uv: int, poetry: int, margin_ratio: float) -> Recommendation:
    if margin_ratio < 0.10:
        return Recommendation.EITHER_WORKS
    if uv > poetry:
        return Recommendation.USE_UV_WORKSPACE
    return Recommendation.USE_POETRY_ISOLATED


def _rationale_for(pick: Recommendation, matrix: DecisionMatrix) -> str:
    if pick is Recommendation.USE_UV_WORKSPACE:
        return (
            f"{matrix.name}: uv wins {matrix.uv_score} vs poetry {matrix.poetry_score} — "
            "shared lockfile, cheaper refactors, faster CI"
        )
    if pick is Recommendation.USE_POETRY_ISOLATED:
        return (
            f"{matrix.name}: poetry wins {matrix.poetry_score} vs uv {matrix.uv_score} — "
            "independent release cadence and per-project ownership dominate"
        )
    return (
        f"{matrix.name}: scores within 10% ({matrix.uv_score} vs {matrix.poetry_score}); "
        "either setup is defensible"
    )


def recommend(matrix: DecisionMatrix) -> RecommendationResult:
    uv = matrix.uv_score
    poetry = matrix.poetry_score
    scored = uv + poetry
    margin_ratio = 0.0 if scored == 0 else abs(uv - poetry) / scored
    pick = _pick_recommendation(uv, poetry, margin_ratio)
    return RecommendationResult(
        matrix_name=matrix.name,
        recommendation=pick,
        uv_score=uv,
        poetry_score=poetry,
        tie_weight=matrix.tie_weight,
        total_weight=matrix.total_weight,
        margin_ratio=round(margin_ratio, 3),
        rationale=_rationale_for(pick, matrix),
    )


_VERDICT_MARKER: dict[Verdict, str] = {
    Verdict.UV_WINS: "U",
    Verdict.POETRY_WINS: "P",
    Verdict.TIE: "=",
}


def format_matrix(matrix: DecisionMatrix) -> str:
    header = (
        f"{matrix.name}: uv={matrix.uv_score} poetry={matrix.poetry_score} "
        f"tie={matrix.tie_weight} total={matrix.total_weight}"
    )
    lines = [header]
    for criterion in matrix.criteria:
        marker = _VERDICT_MARKER[criterion.verdict]
        lines.append(
            f"  [{marker}] w={criterion.weight} step{criterion.evidence_step} "
            f"{criterion.name}: {criterion.rationale}"
        )
    return "\n".join(lines)


def format_recommendation(result: RecommendationResult) -> str:
    return (
        f"recommendation: {result.recommendation.value} "
        f"(uv={result.uv_score} poetry={result.poetry_score} "
        f"tie={result.tie_weight} margin={result.margin_ratio:.2f}) — "
        f"{result.rationale}"
    )


def _criterion_row(criterion: Criterion) -> dict:
    return asdict(criterion) | {"verdict": criterion.verdict.value}


def matrix_as_json(matrix: DecisionMatrix) -> str:
    result = recommend(matrix)
    payload = {
        "name": matrix.name,
        "criteria": [_criterion_row(c) for c in matrix.criteria],
        "uv_score": matrix.uv_score,
        "poetry_score": matrix.poetry_score,
        "tie_weight": matrix.tie_weight,
        "total_weight": matrix.total_weight,
        "recommendation": {
            "pick": result.recommendation.value,
            "margin_ratio": result.margin_ratio,
            "rationale": result.rationale,
        },
    }
    return json.dumps(payload, indent=2)


_SCENARIOS: dict[str, "callable"] = {
    "default": default_matrix,
    "monorepo": monorepo_scenario,
    "multi-team": multi_team_scenario,
    "hybrid": hybrid_scenario,
}


def scenario_by_name(name: str) -> DecisionMatrix:
    if name not in _SCENARIOS:
        raise KeyError(f"unknown scenario {name!r}; choose from {sorted(_SCENARIOS)}")
    return _SCENARIOS[name]()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenario",
        default="default",
        choices=sorted(_SCENARIOS),
        help="which weighting profile to score",
    )
    parser.add_argument(
        "--json", action="store_true", help="emit JSON instead of text"
    )
    parser.add_argument(
        "--out", type=Path, help="also write the report to this file"
    )
    args = parser.parse_args(argv)

    matrix = scenario_by_name(args.scenario)
    result = recommend(matrix)

    if args.json:
        text = matrix_as_json(matrix)
    else:
        text = "\n\n".join([format_matrix(matrix), format_recommendation(result)])

    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
