"""Coordinate/step replay is source-level synthetic evidence only."""

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from raftel_arm01.control.thor_protocol_replay import (
    DiagnosticReplay,
    scalar_steps,
    source_decimal,
)


def test_scalar_half_steps_round_away_from_zero_and_use_float32():
    assert scalar_steps(0.5, 1) == 1
    assert scalar_steps(-0.5, 1) == -1
    assert scalar_steps(0.499999999, 1) == 1  # converts to float32 before rounding
    assert scalar_steps(-0.499999999, 1) == -1
    assert scalar_steps(1, 44.5) == 45


def test_source_decimal_drops_after_eight_digits_including_leading_zeros():
    assert source_decimal("123456789") == 123456784.0
    assert source_decimal("0.000000001") == 0
    assert source_decimal("-0.000000001") == 0
    assert source_decimal("000000001") == 0
    # Decimal accumulation differs from correctly rounded float32(strtod()).
    assert source_decimal("0.123456789") == 0.1234566941857338
    with pytest.raises(ValueError, match="bounded"):
        source_decimal("1" * 65)


def test_host_cpp_float32_reference_fixtures():
    path = Path(__file__).parent / "fixtures/thor-controller-decimal.json"
    fixture = json.loads(path.read_text())
    for case in fixture["cases"]:
        assert source_decimal(case["decimal"]) == case["avr_float32"]


def test_replay_uses_source_decimal_not_python_decimal_parser():
    replay = DiagnosticReplay(steps_per_degree=(1,) * 7)
    assert replay.submit("G0 A0.000000001").parser_target_deg[0] == 0


def test_accepted_planned_acknowledged_completed_are_distinct():
    model = DiagnosticReplay()
    receipt = model.submit("G0 A1 B-2 C-2 D3 X4 Y5 Z6\r\n")
    assert receipt.acknowledged and not receipt.completed_in_simulation
    assert receipt.planned_steps == (45, -540, -540, 795, 80, 1250, 1500)
    assert model.completed_steps == (0,) * 7
    assert model.status(0).pending_commands == 1
    assert model.complete_next().completed_in_simulation
    assert model.completed_steps == receipt.planned_steps
    assert model.status(1).evidence_class == "synthetic_protocol_replay_not_measured_pose"


def test_per_axis_g90_g91_and_no_elbow_carrier_mix():
    model = DiagnosticReplay()
    model.submit("G0 B10 C10 D20")
    shoulder_only = model.submit("G0 B20 C20")
    assert shoulder_only.parser_target_deg[3] == 20
    incremental = model.submit("G91 G0 B5 C5 D-2")
    assert incremental.parser_target_deg[1:4] == (25, 25, 18)
    absolute = model.submit("G90 D7")
    assert absolute.parser_target_deg[1:4] == (25, 25, 7)


def test_work_and_g92_offsets_apply_only_in_absolute_mode_and_omitted_axes_hold():
    model = DiagnosticReplay(work_offset_deg=(10, 0, 0, 0, 0, 0, 0))
    assert model.submit("G0 A5").parser_target_deg[0] == 15
    assert model.submit("G92 A1").parser_target_deg[0] == 15
    assert model.g92_offset_deg[0] == 4
    assert model.submit("G0 A2").parser_target_deg[0] == 16
    assert model.submit("G91 A2").parser_target_deg[0] == 18
    model.submit("G92.1")
    assert model.submit("G90 A2").parser_target_deg[0] == 12


def test_incremental_parser_state_is_not_rounded_completed_step_state():
    model = DiagnosticReplay(steps_per_degree=(1,) * 7)
    first = model.submit("G91 A0.4")
    second = model.submit("A0.4")
    assert first.planned_steps[0] == 0
    assert second.planned_steps[0] == 1
    assert model.completed_steps[0] == 0


def test_lost_ack_is_ambiguous_retry_duplicates_incremental_move():
    model = DiagnosticReplay()
    first = model.submit("G91 A1", acknowledgment_received=False)
    second = model.submit("A1", acknowledgment_received=False)
    assert first.parser_target_deg[0] == 1
    assert second.parser_target_deg[0] == 2
    assert not first.acknowledged and not second.acknowledged
    model.complete_next()
    assert not model.receipts[0].acknowledged
    assert model.receipts[0].completed_in_simulation
    with pytest.raises(ValueError, match="order"):
        model.acknowledge(1)
    assert model.acknowledge(0).acknowledged
    assert model.acknowledge(1).acknowledged
    with pytest.raises(ValueError, match="duplicate"):
        model.acknowledge(1)


def test_reset_invalidates_pending_and_latches_without_claiming_origin():
    model = DiagnosticReplay()
    model.submit("G0 A10")
    model.reset()
    assert model.receipts[0].invalidated_by_reset
    assert not model.receipts[0].completed_in_simulation
    assert model.completed_steps == (0,) * 7
    for action in (lambda: model.submit("G90"), model.complete_next, lambda: model.status(0)):
        with pytest.raises(ValueError, match="latched"):
            action()
    model.reset()  # idempotent invalidation, no recovery
    assert model.fault is not None


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"completed_steps": (0,) * 6}, "partial"),
        ({"completed_steps": (0, 270, 0, 0, 0, 0, 0)}, "shoulder"),
        ({"timestamp_s": 100}, "future"),
        ({"timestamp_s": -1}, "stale"),
        ({"timestamp_s": float("nan")}, "timestamp"),
        ({"evidence_class": "physical"}, "non_synthetic"),
        ({"sequence": True}, "malformed"),
    ],
)
def test_malformed_and_stale_status_latches_fault(change, reason):
    model = DiagnosticReplay()
    status = replace(model.status(1), **change)
    with pytest.raises(ValueError, match=reason):
        model.observe_status(status, now_s=2, max_age_s=2)
    with pytest.raises(ValueError, match="latched"):
        model.submit("G0 A1")


def test_stale_and_out_of_order_status_rejected_even_after_good_state():
    model = DiagnosticReplay()
    first, second = model.status(1), model.status(2)
    model.observe_status(second, now_s=2, max_age_s=1)
    with pytest.raises(ValueError, match="order"):
        model.observe_status(first, now_s=2, max_age_s=1)
    stale = DiagnosticReplay()
    with pytest.raises(ValueError, match="stale"):
        stale.observe_status(stale.status(0), now_s=2, max_age_s=1)


def test_unequal_step_scales_compare_shoulder_coordinates_not_raw_counts():
    model = DiagnosticReplay(steps_per_degree=(1, 10, 20, 1, 1, 1, 1))
    model.submit("G0 B1 C1")
    model.complete_next()
    model.observe_status(model.status(0), now_s=0, max_age_s=1)
    assert model.fault is None


@pytest.mark.parametrize(
    "line",
    [
        "",
        "G0 A1 A2",
        "G90 G91 A1",
        "G1 A1",
        "G0 F100 A1",
        "G0 A1e3",
        "G0 Ainf",
        "G0 A1\nG0 A2",
        "G0 A1;comment",
        "g0 a1",
        "G92",
        "G92.1 A1",
        "G0 G92 A1",
        "G0 A9999999999999999999999999999999999999999999999999999999",
    ],
)
def test_invalid_line_does_not_partially_mutate_state(line):
    model = DiagnosticReplay()
    with pytest.raises(ValueError):
        model.submit(line)
    assert model.receipts == []
    assert model.parser_target_deg == (0,) * 7
    assert model.absolute


def test_replay_capacity_is_bounded_and_parameters_finite():
    model = DiagnosticReplay(max_commands=2, max_pending=1)
    model.submit("G90")
    with pytest.raises(ValueError, match="capacity"):
        model.submit("G0 A1")
    model.complete_next()
    model.submit("G0 A1")
    model.complete_next()
    with pytest.raises(ValueError, match="capacity"):
        model.submit("G0 A1")
    for kwargs in ({"max_pending": True}, {"max_commands": 0}, {"steps_per_degree": (0,) * 7}):
        with pytest.raises(ValueError):
            DiagnosticReplay(**kwargs)


@pytest.mark.parametrize("target,scale", [(1e308, 1), (1, 0), (True, 1), (1, float("nan"))])
def test_scalar_invalid_and_overflow_rejected(target, scale):
    with pytest.raises(ValueError):
        scalar_steps(target, scale)


def test_installed_python_cli_separates_pending_and_completed_and_validates_template():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools/thor_controller_replay.py"),
            "--calibration",
            str(root / "config/thor-calibration-template.json"),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    report = json.loads(result.stdout)
    assert not report["hardware_connection"]
    assert not report["firmware_executed"]
    assert not report["commissioned"]
    assert not report["calibration"]["analysis_inputs_complete"]
    before = report["events"][3]["result"]
    after = report["events"][6]["result"]
    assert before["completed_steps"] == [0] * 7
    assert before["pending_commands"] == 2
    assert after["completed_steps"][1:4] == [2700, 2700, 5300]
    assert after["pending_commands"] == 0


def test_cli_script_replay_is_deterministic_and_preserves_existing_reports(tmp_path):
    root = Path(__file__).resolve().parents[1]
    command = [
        sys.executable,
        str(root / "tools/thor_controller_replay.py"),
        "--script",
        str(root / "tests/fixtures/thor-controller-replay.json"),
    ]
    first = subprocess.run(command, capture_output=True, text=True, check=True)
    second = subprocess.run(command, capture_output=True, text=True, check=True)
    assert first.stdout == second.stdout
    report = json.loads(first.stdout)
    assert report["final_fault"].startswith("reset_invalidates")
    assert report["receipts"][-1]["invalidated_by_reset"]
    output = tmp_path / "existing.json"
    output.write_text("original evidence")
    failed = subprocess.run(command + ["--output", str(output)], capture_output=True, text=True)
    assert failed.returncode == 2
    assert output.read_text() == "original evidence"


@pytest.mark.parametrize(
    "document",
    [
        {"schema_version": True, "events": []},
        {"schema_version": 1, "events": [{"action": "send_to_port", "port": "not-opened"}]},
        {"schema_version": 1, "events": [{"action": "submit", "line": "G0 A1"}]},
        {
            "schema_version": 1,
            "events": [{"action": "source_write", "board": [], "joints_rad": []}],
        },
        {"schema_version": 1, "events": [{"action": "reset", "recover": True}]},
    ],
)
def test_cli_negative_schema_and_unknown_actions_fail_without_report(tmp_path, document):
    root = Path(__file__).resolve().parents[1]
    script = tmp_path / "bad.json"
    output = tmp_path / "should-not-exist.json"
    script.write_text(json.dumps(document))
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools/thor_controller_replay.py"),
            "--script",
            str(script),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "controller replay:" in result.stderr
    assert not output.exists()


@pytest.mark.parametrize(
    "raw", ['{"schema_version":1,"schema_version":1,"events":[]}', '{"events":[NaN]}']
)
def test_cli_rejects_ambiguous_or_nonfinite_json_before_replay(tmp_path, raw):
    root = Path(__file__).resolve().parents[1]
    script = tmp_path / "ambiguous.json"
    script.write_text(raw)
    result = subprocess.run(
        [sys.executable, str(root / "tools/thor_controller_replay.py"), "--script", str(script)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert not result.stdout
