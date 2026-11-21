"""Fit and evaluate a one-step imitation baseline for logical waypoint screening."""

import argparse
import json
import random
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from math import hypot
from typing import Literal

from raftel_arm01.config import Config, load_config
from raftel_arm01.evaluation.benchmark import canonical_sha256
from raftel_arm01.models import ObjectPose, Position
from raftel_arm01.planning.sorting import plan

Action = Literal["consider", "defer"]
Observation = tuple[float, float, float]
Policy = Callable[[Observation], Action]

NEIGHBORS = 3
OBJECTS_PER_LAYOUT = 10
# Bounds define the experiment's sampling distribution and the feature scales.
# They do not define the planner's acceptance thresholds.
X_MM = (-300, 300)
Y_MM = (-50, 450)
Z_MM = (-20, 340)
MASS_G = (10, 140)
FEATURE_SCALES = (0.6, 0.4, 0.15)


@dataclass(frozen=True)
class ScreeningExample:
    observation: Observation
    planner_action: Action


def _layout(seed: int, config: Config) -> tuple[ScreeningExample, ...]:
    rng = random.Random(seed)
    examples: list[ScreeningExample] = []
    for index in range(OBJECTS_PER_LAYOUT):
        x, y, z = (
            rng.randint(*X_MM) / 1000,
            rng.randint(*Y_MM) / 1000,
            rng.randint(*Z_MM) / 1000,
        )
        mass = rng.randint(*MASS_G) / 1000
        obj = ObjectPose(
            f"candidate-{index:02d}",
            config.bins[index % len(config.bins)].category,
            Position(x, y, z),
            mass,
        )
        try:
            plan(obj, config)
        except ValueError:
            action: Action = "defer"
        else:
            action = "consider"
        examples.append(ScreeningExample((hypot(x, y), z, mass), action))
    return tuple(examples)


def fit_screening_policy(examples: Sequence[ScreeningExample]) -> Policy:
    """Fit a fixed 3-nearest-neighbor policy by retaining labeled examples."""
    if len(examples) < NEIGHBORS:
        raise ValueError(f"need at least {NEIGHBORS} training examples")
    training = tuple(examples)

    def predict(observation: Observation) -> Action:
        def squared_distance(example: ScreeningExample) -> float:
            return sum(
                ((seen - query) / scale) ** 2
                for seen, query, scale in zip(
                    example.observation, observation, FEATURE_SCALES, strict=True
                )
            )

        # Stable sorting breaks distance ties in dataset order. Three votes
        # give a strict majority even when multiple examples have the same location.
        closest = sorted(training, key=squared_distance)[:NEIGHBORS]
        consider_votes = sum(example.planner_action == "consider" for example in closest)
        return "consider" if consider_votes > NEIGHBORS // 2 else "defer"

    return predict


def _score(examples: Sequence[ScreeningExample], decisions: Sequence[Action]) -> dict:
    true_consider = true_defer = false_consider = false_defer = 0
    for example, decision in zip(examples, decisions, strict=True):
        if decision == "consider":
            if example.planner_action == "consider":
                true_consider += 1
            else:
                false_consider += 1
        elif example.planner_action == "defer":
            true_defer += 1
        else:
            false_defer += 1
    planner_deferred = true_defer + false_consider
    planner_considered = true_consider + false_defer
    return {
        "true_consider": true_consider,
        "true_defer": true_defer,
        "false_consider": false_consider,
        "false_defer": false_defer,
        "accuracy": (true_consider + true_defer) / len(examples),
        "false_consider_rate": false_consider / planner_deferred if planner_deferred else None,
        "false_defer_rate": false_defer / planner_considered if planner_considered else None,
    }


def _layout_seeds(first_seed: int, layouts: int) -> range:
    if type(layouts) is not int or not 1 <= layouts <= 100:
        raise ValueError("each split must have 1..100 layouts")
    if type(first_seed) is not int or not 0 <= first_seed <= (2**63 - layouts):
        raise ValueError("seeds must be nonnegative signed 64-bit integers")
    return range(first_seed, first_seed + layouts)


def _describe_split(
    layouts: dict[int, tuple[ScreeningExample, ...]], examples: Sequence[ScreeningExample]
) -> dict:
    return {
        "layout_seeds": list(layouts),
        "examples": len(examples),
        "planner_consider": sum(example.planner_action == "consider" for example in examples),
        "examples_canonical_sha256": canonical_sha256(
            {seed: [asdict(example) for example in rows] for seed, rows in layouts.items()}
        ),
    }


def run_screening_experiment(
    *,
    train_seed: int = 42,
    train_layouts: int = 30,
    eval_seed: int = 1000,
    eval_layouts: int = 10,
) -> dict:
    """Train once and compare fixed policies against labels on unseen layout seeds."""
    training_seeds = _layout_seeds(train_seed, train_layouts)
    evaluation_seeds = _layout_seeds(eval_seed, eval_layouts)
    if max(training_seeds.start, evaluation_seeds.start) < min(
        training_seeds.stop, evaluation_seeds.stop
    ):
        raise ValueError("training and evaluation layout seeds overlap")

    config = load_config()
    training_layouts = {seed: _layout(seed, config) for seed in training_seeds}
    training = [example for layout in training_layouts.values() for example in layout]
    policy = fit_screening_policy(training)
    evaluation_layouts = {seed: _layout(seed, config) for seed in evaluation_seeds}
    evaluation = [example for layout in evaluation_layouts.values() for example in layout]
    return {
        "schema_version": 1,
        "evidence_class": "synthetic_logical_screening",
        "planner_config_canonical_sha256": canonical_sha256(asdict(config)),
        "experiment": {
            "objects_per_layout": OBJECTS_PER_LAYOUT,
            "sampling_bounds_inclusive": {
                "x_mm": X_MM,
                "y_mm": Y_MM,
                "z_mm": Z_MM,
                "mass_g": MASS_G,
            },
            "observation": ["horizontal_radius_m", "height_m", "mass_kg"],
            "actions": ["consider", "defer"],
            "decision_horizon": 1,
            "objective": "match the deterministic waypoint planner's accept or reject action",
            "learner": "3-nearest neighbors",
            "neighbors": NEIGHBORS,
            "feature_scales": FEATURE_SCALES,
        },
        "train": _describe_split(training_layouts, training),
        "evaluation": _describe_split(evaluation_layouts, evaluation),
        "metrics": {
            "imitation": _score(evaluation, [policy(row.observation) for row in evaluation]),
            "always_consider": _score(evaluation, ["consider"] * len(evaluation)),
            "always_defer": _score(evaluation, ["defer"] * len(evaluation)),
            "planner_oracle": _score(evaluation, [row.planner_action for row in evaluation]),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-seed", type=int, default=42, help="first training layout seed")
    parser.add_argument("--train-layouts", type=int, default=30, help="number of training layouts")
    parser.add_argument("--eval-seed", type=int, default=1000, help="first evaluation layout seed")
    parser.add_argument("--eval-layouts", type=int, default=10, help="number of evaluation layouts")
    args = parser.parse_args(argv)
    try:
        report = run_screening_experiment(**vars(args))
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(report, allow_nan=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
