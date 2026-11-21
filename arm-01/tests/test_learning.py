import json

import pytest

from raftel_arm01.learning import (
    ScreeningExample,
    fit_screening_policy,
    main,
    run_screening_experiment,
)


def test_fitted_policy_uses_a_label_majority_and_copies_training_data():
    query = (0.1, 0.1, 0.05)
    examples = [
        ScreeningExample(query, "defer"),
        ScreeningExample((0.11, 0.1, 0.05), "consider"),
        ScreeningExample((0.12, 0.1, 0.05), "consider"),
        ScreeningExample((0.5, 0.3, 0.12), "defer"),
    ]
    fitted = fit_screening_policy(examples)
    examples[1] = ScreeningExample(examples[1].observation, "defer")
    refitted = fit_screening_policy(examples)

    assert fitted(query) == "consider"
    assert refitted(query) == "defer"


def test_equal_distances_retain_training_order():
    query = (0.1, 0.1, 0.05)
    examples = [
        ScreeningExample(query, "consider"),
        ScreeningExample(query, "consider"),
        ScreeningExample(query, "defer"),
        ScreeningExample(query, "defer"),
    ]

    assert fit_screening_policy(examples)(query) == "consider"
    assert fit_screening_policy(examples[::-1])(query) == "defer"


def test_training_rejects_fewer_examples_than_neighbors():
    with pytest.raises(ValueError, match="training examples"):
        fit_screening_policy([])


def test_default_holdout_reproduces_screening_metrics_and_baselines():
    report = run_screening_experiment()
    assert report == run_screening_experiment()
    assert report["train"]["layout_seeds"] == list(range(42, 72))
    assert report["evaluation"]["layout_seeds"] == list(range(1000, 1010))
    assert report["train"]["examples"] == 300
    assert report["train"]["planner_consider"] == 114
    assert report["evaluation"]["examples"] == 100
    assert report["evaluation"]["planner_consider"] == 33
    scores = report["metrics"]
    assert scores["imitation"] == {
        "true_consider": 31,
        "true_defer": 63,
        "false_consider": 4,
        "false_defer": 2,
        "accuracy": 0.94,
        "false_consider_rate": pytest.approx(4 / 67),
        "false_defer_rate": pytest.approx(2 / 33),
    }
    assert scores["always_consider"]["accuracy"] == 0.33
    assert scores["always_consider"]["false_consider_rate"] == 1.0
    assert scores["always_defer"]["accuracy"] == 0.67
    assert scores["always_defer"]["false_defer_rate"] == 1.0
    assert scores["planner_oracle"]["accuracy"] == 1.0


def test_changing_evaluation_seeds_leaves_training_inputs_frozen():
    first = run_screening_experiment(train_layouts=2, eval_layouts=2)
    second = run_screening_experiment(train_layouts=2, eval_seed=2500, eval_layouts=2)
    assert first["train"] == second["train"]
    assert (
        first["evaluation"]["examples_canonical_sha256"]
        != second["evaluation"]["examples_canonical_sha256"]
    )


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"train_seed": 1000}, "overlap"),
        ({"eval_seed": 71}, "overlap"),
        ({"train_seed": -1}, "signed 64-bit"),
        ({"eval_seed": 2**63 - 1, "eval_layouts": 2}, "signed 64-bit"),
        ({"eval_seed": True}, "signed 64-bit"),
        ({"train_layouts": 0}, "1..100 layouts"),
        ({"eval_layouts": 101}, "1..100 layouts"),
    ],
)
def test_rejects_invalid_or_overlapping_splits(options, message):
    with pytest.raises(ValueError, match=message):
        run_screening_experiment(**options)


def test_cli_prints_json_and_reports_bad_splits(capsys):
    assert main(["--train-layouts", "1", "--eval-layouts", "1"]) == 0
    assert json.loads(capsys.readouterr().out)["evidence_class"] == "synthetic_logical_screening"
    with pytest.raises(SystemExit) as exc:
        main(["--eval-seed", "42"])
    assert exc.value.code == 2
    output = capsys.readouterr()
    assert not output.out
    assert "training and evaluation layout seeds overlap" in output.err
