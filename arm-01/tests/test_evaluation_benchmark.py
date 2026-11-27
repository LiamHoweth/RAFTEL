"""Existing-sorter adaptation, pooled denominators and layout uncertainty."""

import copy
import json
from dataclasses import replace
from pathlib import Path

import pytest

from raftel_arm01.config import load_config
from raftel_arm01.evaluation.benchmark import canonical_sha256, logical_layout, summarize_runs
from raftel_arm01.evaluation.cli import main
from raftel_arm01.evaluation.replay import read_jsonl, read_manifest, score_replay, wilson_interval
from raftel_arm01.models import Position
from raftel_arm01.tasks import sorter


def test_seeded_adapter_preserves_original_results_and_provenance():
    one = logical_layout(42, unreachable=True, failed_grasp_ids=("object-00",))
    assert one == logical_layout(42, unreachable=True, failed_grasp_ids=("object-00",))
    manifest, events, metadata = one
    report = score_replay(manifest, events)
    assert report["counts"]["presented"] == 11
    assert report["counts"]["eligible"] == 10
    assert report["counts"]["correct"] == metadata["original_summary"]["sorted"] == 9
    assert report["counts"]["failed"] == metadata["original_summary"]["failed"] == 1
    assert report["counts"]["excluded"] == metadata["original_summary"]["skipped"] == 1
    assert report["counts"]["failed_attempts"] == 2
    assert report["counts"]["unresolved"] == 0
    assert metadata["input_canonical_sha256"] == canonical_sha256(metadata["inputs"])
    assert metadata["manifest_canonical_sha256"] == canonical_sha256(manifest)
    assert metadata["events_canonical_sha256"] == canonical_sha256(events)
    assert "tasks/sorter.py" in metadata["inputs"]["implementation"]["installed_file_sha256"]
    assert logical_layout(43)[2]["input_canonical_sha256"] != metadata["input_canonical_sha256"]


@pytest.mark.parametrize("in_declared_bin", [True, False])
def test_replay_uses_backend_placement_instead_of_expected_category(monkeypatch, in_declared_bin):
    config = load_config()
    alternate = config.bins[1]
    placement = alternate.position if in_declared_bin else Position(0, 0.27, 0.02)
    correct_planner = sorter.plan

    def misroute(obj, config):
        above = placement.above(config.clearance_m)
        return replace(
            correct_planner(obj, config), transit=above, placement=placement, retreat=above
        )

    monkeypatch.setattr(sorter, "plan", misroute)
    manifest, events, metadata = logical_layout(42, count=1, config=config)
    report = score_replay(manifest, events)
    assert metadata["original_summary"]["sorted"] == 1
    assert report["counts"]["correct"] == 0
    assert report["counts"]["failed_attempts"] == 1
    if in_declared_bin:
        assert report["counts"]["misroutes"] == 1
        assert events[-1]["observed_bin"] == alternate.category
    else:
        assert events[-1]["event"] == "failed"
        assert "observed_bin" not in events[-1]


def test_layout_summary_pools_counts_and_bootstraps_whole_layouts():
    good = logical_layout(10, count=10)[:2]
    bad = logical_layout(11, count=1, failed_grasp_ids=("object-00",))[:2]
    summary = summarize_runs([good, bad], bootstrap_resamples=1000)
    assert summary["totals"]["correct"] == 10
    assert summary["totals"]["attempted"] == 11
    assert summary["rates"]["after_retry_cycle_success"]["pooled_observed_proportion"] == 10 / 11
    assert summary["rates"]["after_retry_cycle_success"]["layout_bootstrap_percentile_95"] == [0, 1]
    assert summary == summarize_runs([good, bad], bootstrap_resamples=1000)
    single = summarize_runs([good], bootstrap_resamples=100)
    assert single["rates"]["after_retry_cycle_success"]["layout_bootstrap_percentile_95"] is None


def test_zero_denominator_resamples_are_explicit_and_not_conditioned_away():
    good = logical_layout(10, count=1)[:2]
    manifest, _ = logical_layout(11, count=1)[:2]
    manifest["objects"][0]["eligible"] = False
    summary = summarize_runs([good, (manifest, [])], bootstrap_resamples=1000)
    rate = summary["rates"]["after_retry_cycle_success"]
    assert rate["undefined_resamples"] > 0
    assert rate["layout_bootstrap_percentile_95"] is None
    assert rate["pooled_observed_proportion"] == 1
    assert summary["totals"]["presented"] == 2


def test_duplicate_layouts_mixed_evidence_and_invalid_resampling_reject():
    first = logical_layout(42, count=1)[:2]
    for runs in ([], [first, first]):
        with pytest.raises(ValueError):
            summarize_runs(runs)
    second = copy.deepcopy(logical_layout(43, count=1)[:2])
    second[0]["evidence_class"] = "physical"
    with pytest.raises(ValueError, match="evidence classes"):
        summarize_runs([first, second])
    for value in (True, 0, 20_001):
        with pytest.raises(ValueError):
            summarize_runs([first], bootstrap_resamples=value)


def test_large_aggregate_wilson_counts_do_not_use_per_run_event_limit():
    interval = wilson_interval(1_800_000, 2_000_000)
    assert interval[0] < 0.9 < interval[1]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"seed": True},
        {"count": True},
        {"unreachable": 1},
        {"failed_grasp_ids": "object-00"},
        {"failed_grasp_ids": ("missing",)},
    ],
)
def test_invalid_logical_layout_inputs_fail(kwargs):
    parameters = {"seed": 42, **kwargs}
    with pytest.raises(ValueError):
        logical_layout(**parameters)


def test_score_cli_distinguishes_settled_bounced_out_and_unobserved(tmp_path, capsys):
    fixtures = Path(__file__).with_name("fixtures")
    manifest = fixtures / "benchsort-placement-manifest-v1.json"
    events = fixtures / "benchsort-placement-events-v1.jsonl"
    output = tmp_path / "report.json"
    args = [
        "score",
        "--manifest",
        str(manifest),
        "--events",
        str(events),
        "--output",
        str(output),
    ]
    assert main(args) == 1
    original = output.read_bytes()
    report = json.loads(original)
    assert report["evidence_class"] == "logical_only"
    counts = report["counts"]
    assert counts["presented"] == counts["eligible"] == counts["attempted"] == 3
    assert counts["correct"] == counts["failed"] == counts["unresolved"] == 1
    assert counts["misroutes"] == 0
    assert report["metrics"]["eligible_end_to_end_completion"] == pytest.approx(1 / 3)

    objects = {row["id"]: row for row in report["objects"]}
    assert objects["settled"]["first_attempt_correct"]
    assert not objects["bounced-out"]["autonomous_correct"]
    assert objects["bounced-out"]["failed"]
    assert not objects["bounced-out"]["unresolved"]
    assert not objects["unobserved"]["autonomous_correct"]
    assert objects["unobserved"]["unresolved"]
    assert not objects["unobserved"]["failed"]
    assert objects["unobserved"]["failed_attempts"] == 0
    assert report["input_provenance"]["events_canonical_sha256"] == canonical_sha256(
        read_jsonl(events)
    )
    assert main(args) == 2
    assert output.read_bytes() == original
    assert "error" in capsys.readouterr().err


def test_manifest_duplicate_keys_nonfinite_and_unknown_fields_rejected(tmp_path):
    path = tmp_path / "manifest.json"
    for text in ('{"schema_version":1,"schema_version":1}', '{"x":1e309}', '{"x":NaN}'):
        path.write_text(text, encoding="utf-8")
        with pytest.raises(ValueError):
            read_manifest(path)


def test_benchmark_cli_success_failure_and_bounds(tmp_path):
    good, bad = tmp_path / "good.json", tmp_path / "bad.json"
    common = ["benchmark", "--layouts", "2", "--count", "3", "--bootstrap-resamples", "100"]
    assert main(common + ["--output", str(good)]) == 0
    assert main(common + ["--fail-grasp", "object-00", "--output", str(bad)]) == 1
    assert json.loads(good.read_text())["totals"]["correct"] == 6
    assert json.loads(bad.read_text())["totals"]["correct"] == 4
    assert main(["benchmark", "--layouts", "1000", "--count", "1000"]) == 2
    assert main(["benchmark", "--layouts", "0"]) == 2
