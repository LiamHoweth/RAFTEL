"""Guard native audit inputs without requiring a FreeCAD installation."""

import runpy
from pathlib import Path

import pytest

TOOLS = runpy.run_path(str(Path(__file__).parents[1] / "tools" / "audit_freecad_assembly.py"))


def test_actual_native_paths_must_stay_inside_requested_isolation_root(tmp_path):
    from types import SimpleNamespace

    root = tmp_path / "task"
    values = {
        key: str(root / key)
        for key in (
            "UserParameter",
            "SystemParameter",
            "UserHomePath",
            "UserAppData",
            "AppTempPath",
        )
    }
    app = SimpleNamespace(ConfigGet=values.__getitem__, listDocuments=lambda: {})
    result = TOOLS["_runtime_isolation"](app, root)
    assert result["verified"] and result["actual_paths"] == values
    values["UserAppData"] = str(tmp_path / "task-other")
    with pytest.raises(ValueError, match="escaped"):
        TOOLS["_runtime_isolation"](app, root)
    values["UserAppData"] = str(root / "data")
    app.listDocuments = lambda: {"Unrelated": object()}
    with pytest.raises(ValueError, match="fresh process"):
        TOOLS["_runtime_isolation"](app, root)
    assert TOOLS["_runtime_isolation"](app, None) == {"requested": False, "verified": False}


def test_final_state_inventory_catches_later_recompute_touching_an_inspected_parent(
    tmp_path, monkeypatch
):
    import sys
    from types import SimpleNamespace

    source = tmp_path / "Assembly.FCStd"
    source.write_bytes(b"native fixture")
    a = SimpleNamespace(Name="BodyA", Label="A", TypeId="Part::Feature", State=["Up-to-date"])
    b = SimpleNamespace(Name="BodyB", Label="B", TypeId="Part::Feature", State=["Up-to-date"])
    documents = {}

    class Document:
        def __init__(self, name, obj):
            self.Name = name
            self.Objects = [obj]

        def recompute(self, objects, force):
            if self.Name == "B":
                a.State = ["Touched"]
            return 1

    def open_document(*args):
        documents.update(A=Document("A", a), B=Document("B", b))
        return documents["A"]

    app = SimpleNamespace(
        Version=lambda: ["fixture"],
        listDocuments=lambda: documents,
        openDocument=open_document,
        closeDocument=documents.pop,
    )
    monkeypatch.setitem(sys.modules, "FreeCAD", app)
    result = TOOLS["audit"](source, recompute="changed", shape_scope="none")
    assert result["documents"][0]["objects"][0]["state"] == ["Up-to-date"]
    assert result["final_loaded_object_states"] == {
        "object_count": 2,
        "state_token_counts": {"Touched": 1, "Up-to-date": 1},
        "not_up_to_date": [{"object": "A::BodyA", "state": ["Touched"]}],
        "scope": "all newly loaded documents after every requested recompute",
    }
    assert not documents


def test_missing_native_source_rejected_before_importing_freecad(tmp_path):
    with pytest.raises(ValueError, match="existing native"):
        TOOLS["audit"](tmp_path / "missing.FCStd")


def test_existing_report_is_never_overwritten(tmp_path, monkeypatch):
    output = tmp_path / "report.json"
    output.write_text("retained evidence")
    monkeypatch.setenv("RAFTEL_FREECAD_ASSEMBLY", str(tmp_path / "source.FCStd"))
    monkeypatch.setenv("RAFTEL_FREECAD_REPORT", str(output))
    with pytest.raises(ValueError, match="never overwritten"):
        TOOLS["main"]()
    assert output.read_text() == "retained evidence"


def test_report_cannot_overwrite_a_cad_file(tmp_path, monkeypatch):
    source = tmp_path / "source.FCStd"
    source.write_bytes(b"protected native data")
    monkeypatch.setenv("RAFTEL_FREECAD_ASSEMBLY", str(source))
    monkeypatch.setenv("RAFTEL_FREECAD_REPORT", str(source))
    with pytest.raises(ValueError, match="new .json"):
        TOOLS["main"]()
    assert source.read_bytes() == b"protected native data"


def test_report_writer_replaces_only_its_owned_file(tmp_path):
    import json

    output = tmp_path / "progress.json"
    writer = TOOLS["ReportWriter"](output)
    writer({"stage": "opening"})
    assert json.loads(output.read_text()) == {"stage": "opening"}
    writer({"stage": "recomputing", "document": "Part"})
    assert json.loads(output.read_text())["document"] == "Part"
    # A different actor replaces this filename. It is no longer our report.
    replacement = tmp_path / "other.json"
    replacement.write_text("other evidence")
    replacement.replace(output)
    with pytest.raises(RuntimeError, match="ownership"):
        writer({"stage": "finished"})
    assert output.read_text() == "other evidence"
    assert not list(tmp_path.glob("*.tmp"))


def test_atomic_checkpoint_does_not_truncate_previous_evidence_on_invalid_json(tmp_path):
    import json

    output = tmp_path / "progress.json"
    writer = TOOLS["ReportWriter"](output)
    writer({"stage": "opening"})
    with pytest.raises(ValueError):
        writer({"bad": float("nan")})
    assert json.loads(output.read_text()) == {"stage": "opening"}
    assert not list(tmp_path.glob("*.tmp"))


def fake_native(monkeypatch, tmp_path, *, fail_recompute=False):
    import sys
    from types import SimpleNamespace

    source = tmp_path / "part.FCStd"
    source.write_bytes(b"native fixture")
    obj = SimpleNamespace(
        Name="Body", Label="Body", TypeId="PartDesign::Body", State=["Up-to-date"]
    )

    class Document:
        Name = "Part"
        Objects = [obj]

        def recompute(self, objects, force):
            calls.append(("recompute", force))
            if fail_recompute:
                raise RuntimeError("native feature failed")
            return 1

    calls = []
    documents = {"Existing": SimpleNamespace(Name="Existing")}

    def open_document(filename, hidden):
        assert filename == str(source) and hidden is True
        documents["Part"] = Document()
        return documents["Part"]

    def close_document(name):
        calls.append(("close", name))
        del documents[name]

    app = SimpleNamespace(
        Version=lambda: ["1", "1", "4"],
        listDocuments=lambda: documents.copy(),
        openDocument=open_document,
        closeDocument=close_document,
    )
    monkeypatch.setitem(sys.modules, "FreeCAD", app)
    return source, calls, documents


def test_cached_audit_never_requests_recompute_and_preserves_existing_documents(
    tmp_path, monkeypatch
):
    import copy

    source, calls, documents = fake_native(monkeypatch, tmp_path)
    checkpoints = []
    report = TOOLS["audit"](source, checkpoint=lambda item: checkpoints.append(copy.deepcopy(item)))
    assert report["restore_completed"] and report["status"] == "complete"
    assert report["audit_mode"] == "none"
    assert report["documents"][0]["objects"][0]["state"] == ["Up-to-date"]
    assert calls == [("close", "Part")]
    assert set(documents) == {"Existing"}
    assert checkpoints[0]["stage"] == "opening"
    assert checkpoints[0]["restore_completed"] is False
    assert any(item["stage"] == "document_complete" for item in checkpoints)
    assert source.read_bytes() == b"native fixture"


def test_forced_recompute_is_checkpointed_before_native_call(tmp_path, monkeypatch):
    import copy

    source, calls, _ = fake_native(monkeypatch, tmp_path, fail_recompute=True)
    checkpoints = []
    report = TOOLS["audit"](
        source, recompute="force", checkpoint=lambda r: checkpoints.append(copy.deepcopy(r))
    )
    assert ("recompute", True) in calls
    assert report["documents"][0]["recompute_error"] == "native feature failed"
    before = next(item for item in checkpoints if item["stage"] == "recomputing")
    assert before["current_document"] == "Part"
    assert "recompute_error" not in before["documents"][0]
    assert calls[-1] == ("close", "Part")


def test_document_filter_does_not_leave_unselected_new_documents_open(tmp_path, monkeypatch):
    source, calls, documents = fake_native(monkeypatch, tmp_path)
    report = TOOLS["audit"](source, document_names=("Other",))
    assert report["documents"] == []
    assert calls == [("close", "Part")]
    assert set(documents) == {"Existing"}


@pytest.mark.parametrize("options", [{"recompute": "anything"}, {"shape_scope": "unknown"}])
def test_invalid_modes_rejected_before_native_import(tmp_path, options):
    source = tmp_path / "part.FCStd"
    source.touch()
    with pytest.raises(ValueError):
        TOOLS["audit"](source, **options)


def test_generic_shape_com_fallback_preserves_bounds_and_volume():
    from types import SimpleNamespace

    bounds = SimpleNamespace(XMin=0, XMax=4, YMin=0, YMax=2, ZMin=0, ZMax=2)
    one = SimpleNamespace(Volume=1, CenterOfMass=SimpleNamespace(x=0, y=1, z=2))
    three = SimpleNamespace(Volume=3, CenterOfMass=SimpleNamespace(x=4, y=1, z=2))
    shape = SimpleNamespace(isNull=lambda: False, BoundBox=bounds, Volume=4, Solids=[one, three])
    item = {}
    TOOLS["_shape_metadata"](SimpleNamespace(Shape=shape), item, False)
    assert item["volume_mm3"] == 4
    assert item["bounds_mm"]["xmax"] == 4
    assert item["shape_center_of_mass_mm"] == [3, 1, 2]
    assert item["center_of_mass_source"] == "volume-weighted solid centroids"
    assert "shape_valid" not in item


def test_optional_com_failure_does_not_remove_available_geometry():
    from types import SimpleNamespace

    class BadSolid:
        Volume = 2

        @property
        def CenterOfMass(self):
            raise RuntimeError("centroid unavailable")

    bounds = SimpleNamespace(XMin=0, XMax=1, YMin=0, YMax=1, ZMin=0, ZMax=1)
    shape = SimpleNamespace(isNull=lambda: False, BoundBox=bounds, Volume=2, Solids=[BadSolid()])
    item = {}
    TOOLS["_shape_metadata"](SimpleNamespace(Shape=shape), item, False)
    assert item["volume_mm3"] == 2 and item["solid_count"] == 1
    assert "centroid unavailable" in item["shape_errors"][0]


def test_checkpoint_failure_still_closes_only_new_documents(tmp_path, monkeypatch):
    source, calls, documents = fake_native(monkeypatch, tmp_path)

    def failed_checkpoint(report):
        if report["stage"] in {"document_start", "closing"}:
            raise RuntimeError("checkpoint storage unavailable")

    with pytest.raises(RuntimeError, match="checkpoint"):
        TOOLS["audit"](source, checkpoint=failed_checkpoint)
    assert calls == [("close", "Part")]
    assert set(documents) == {"Existing"}


def test_terminal_scope_skips_assembly_compounds_but_keeps_leaf_links_and_bodies():
    from types import SimpleNamespace

    group = SimpleNamespace(TypeId="App::Part")
    body = SimpleNamespace(TypeId="PartDesign::Body")
    assembly_link = SimpleNamespace(TypeId="App::Link", getLinkedObject=lambda recursive: group)
    leaf_link = SimpleNamespace(TypeId="App::Link", getLinkedObject=lambda recursive: body)
    assert TOOLS["_is_terminal"](body)
    assert TOOLS["_is_terminal"](leaf_link)
    assert not TOOLS["_is_terminal"](assembly_link)


def test_invalid_mode_does_not_leave_a_misleading_starting_report(tmp_path, monkeypatch):
    source = tmp_path / "source.FCStd"
    source.touch()
    output = tmp_path / "report.json"
    monkeypatch.setenv("RAFTEL_FREECAD_ASSEMBLY", str(source))
    monkeypatch.setenv("RAFTEL_FREECAD_REPORT", str(output))
    monkeypatch.setenv("RAFTEL_FREECAD_RECOMPUTE", "invalid")
    with pytest.raises(ValueError, match="recompute"):
        TOOLS["main"]()
    assert not output.exists()


def test_object_checkpoint_throttling_retains_final_observations(tmp_path, monkeypatch):
    import copy
    import sys
    from types import SimpleNamespace

    source, _, _ = fake_native(monkeypatch, tmp_path)
    app = sys.modules["FreeCAD"]
    original_open = app.openDocument

    def many_objects(filename, hidden):
        document = original_open(filename, hidden)
        document.Objects = [
            SimpleNamespace(Name=f"Body{i}", Label=f"Part{i}", TypeId="PartDesign::Body", State=[])
            for i in range(1000)
        ]
        return document

    app.openDocument = many_objects
    checkpoints = []
    report = TOOLS["audit"](
        source,
        recompute="force",
        checkpoint_interval_s=10000,
        checkpoint=lambda r: checkpoints.append(copy.deepcopy(r)),
    )
    assert len(report["documents"][0]["objects"]) == 1000
    object_events = [
        r
        for r in checkpoints
        if r["stage"] in {"inspecting_shape", "shape_finished", "inspecting_metadata"}
    ]
    assert len(object_events) == 1
    assert object_events[0]["current_object"] == "Body0"
    stages = {r["stage"] for r in checkpoints}
    assert {
        "opening",
        "restored",
        "document_start",
        "recomputing",
        "recompute_finished",
        "document_complete",
        "closing",
        "finished",
    } <= stages
    assert checkpoints[-1]["documents"][0]["object_count"] == 1000


@pytest.mark.parametrize("interval", [-1, float("nan"), float("inf")])
def test_invalid_checkpoint_interval_rejected_before_native_import(tmp_path, interval):
    source = tmp_path / "source.FCStd"
    source.touch()
    with pytest.raises(ValueError, match="checkpoint interval"):
        TOOLS["audit"](source, checkpoint_interval_s=interval)


def test_terminal_imported_part_is_not_consumed_by_datum_references():
    import json
    from types import SimpleNamespace

    evidence = json.loads(
        (Path(__file__).with_name("fixtures") / "freecad_datum_inheritance_native.json").read_text()
    )
    for native in evidence:
        datum = SimpleNamespace(
            TypeId=native["type"],
            isDerivedFrom=lambda name, row=native: row["derived"].get(name, False),
        )
        motor = SimpleNamespace(
            TypeId="Part::Feature",
            InList=[datum],
            isDerivedFrom=lambda name: name == "Part::Feature",
        )
        assert datum.isDerivedFrom("Part::Feature") and datum.isDerivedFrom("Part::Datum")
        assert TOOLS["_is_terminal"](motor)
    true_consumer = SimpleNamespace(
        TypeId="Part::Cut", isDerivedFrom=lambda name: name == "Part::Feature"
    )
    motor.InList.append(true_consumer)
    assert not TOOLS["_is_terminal"](motor)
    motor.InList = [SimpleNamespace(TypeId="PartDesign::Body")]
    assert not TOOLS["_is_terminal"](motor)
