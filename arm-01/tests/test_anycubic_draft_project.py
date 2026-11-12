"""Synthetic structure/hostile-input checks; actual desktop saves are separate evidence."""

import importlib.util
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "audit_anycubic_draft_project",
    Path(__file__).parents[1] / "tools/audit_anycubic_draft_project.py",
)
audit = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = audit
SPEC.loader.exec_module(audit)

MESH = (
    '<object id="1"><mesh><vertices><vertex x="0" y="0" z="0"/>'
    '<vertex x="1" y="0" z="0"/><vertex x="0" y="1" z="0"/></vertices>'
    '<triangles><triangle v1="0" v2="1" v3="2"/></triangles></mesh></object>'
)


def model(objects=MESH, build='<item objectid="1"/>', unit="millimeter"):
    return (
        f'<model xmlns="{audit.CORE}" xmlns:p="{audit.PRODUCTION}" unit="{unit}">'
        '<metadata name="Designer">PRIVATE@example.invalid</metadata>'
        f"<resources>{objects}</resources><build>{build}</build></model>"
    ).encode()


def package(main=None, extras=None, target="/3D/3dmodel.model", mode=""):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="model" '
            'ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>',
        )
        archive.writestr(
            "_rels/.rels",
            f'<Relationships xmlns="{audit.RELATIONSHIPS}"><Relationship Id="rel1" '
            f'Type="{audit.MODEL_RELATIONSHIP}" Target="{target}" {mode}/></Relationships>',
        )
        archive.writestr("3D/3dmodel.model", main or model())
        for name, payload in (extras or {}).items():
            archive.writestr(name, payload)
    return buffer.getvalue()


def test_counts_privacy_hash_and_unknowns():
    payload = package(model(build='<item objectid="1"/><item objectid="1" printable="0"/>'))
    result = audit.audit_project(payload)
    assert result["mesh_instance_count"] == result["build_item_count"] == 2
    assert result["printable_mesh_instance_count"] == 1
    assert result["models"][0]["objects"][0]["triangle_count"] == 1
    assert "PRIVATE" not in json.dumps(result)
    assert result["geometry_source_equivalence"] is None
    assert not result["manufacturing_release"]


def test_cross_part_components_and_transform_order():
    objects = (
        '<object id="2"><components><component objectid="1" '
        'p:path="/3D/Objects/one.model" transform="1 0 0 0 1 0 0 0 1 0 2 0"/>'
        "</components></object>"
    )
    payload = package(
        model(objects, '<item objectid="2" transform="1 0 0 0 1 0 0 0 1 3 0 0"/>'),
        {"3D/Objects/one.model": model()},
    )
    graph = audit.load_project(payload)
    leaf = graph["instances"][0]
    assert leaf["model_path"] == "3D/Objects/one.model"
    assert [row[9:] for row in leaf["transform_chain"]] == [[0, 2, 0], [3, 0, 0]]
    assert leaf["transform_tokens_chain"][0][10] == "2"


@pytest.mark.parametrize(
    "change",
    [
        lambda: package(extras={"../escape": b"x"}),
        lambda: package(extras={"3d/3DMODEL.model": model()}),
        lambda: package(target="https://example.invalid/model"),
        lambda: package(target="%2f3D/3dmodel.model"),
        lambda: package(mode='TargetMode="External"'),
        lambda: package(model(MESH + MESH)),
        lambda: package(model(build='<item objectid="99"/>')),
        lambda: package(
            model('<object id="1"><components><component objectid="1"/></components></object>')
        ),
        lambda: package(model().replace(b'x="1"', b'x="NaN"')),
        lambda: package(model().replace(b'x="1"', b'x="1e-99999999"')),
        lambda: package(model().replace(b'x="1"', b'x="0e99999999"')),
        lambda: package(model().replace(b'x="1"', b'x="1e-324"')),
        lambda: package(model().replace(b'x="1"', b'x="1_0"')),
        lambda: package(model().replace(b'v3="2"', b'v3="3"')),
        lambda: package(model().replace(b"</vertices>", b"</vertices><vertices/>")),
        lambda: package(model().replace(b"</build>", b"</build><build/>")),
        lambda: package(b'<!DOCTYPE model [<!ENTITY x "xx">]>' + model()),
        lambda: package(model().decode().encode("utf-16")),
        lambda: package(model(unit="parsec")),
        lambda: package(model(build='<item objectid="1" transform="0 0 0 0 0 0 0 0 0 0 0 0"/>')),
    ],
)
def test_malformed_or_unsafe_rejected(change):
    with pytest.raises((ValueError, UnicodeError)):
        audit.load_project(change())


def test_mixed_linked_units_rejected():
    objects = (
        '<object id="2"><components><component objectid="1" '
        'p:path="/3D/other.model"/></components></object>'
    )
    with pytest.raises(ValueError, match="mixed"):
        audit.load_project(
            package(model(objects, '<item objectid="2"/>'), {"3D/other.model": model(unit="inch")})
        )


def test_expansion_and_archive_bounds(monkeypatch):
    monkeypatch.setattr(audit, "MAX_INSTANCES", 1)
    with pytest.raises(ValueError, match="instance bound"):
        audit.load_project(package(model(build='<item objectid="1"/><item objectid="1"/>')))
    monkeypatch.setattr(audit, "MAX_ARCHIVE_BYTES", 10)
    with pytest.raises(ValueError, match="size"):
        audit.load_project(package())


def test_deep_reused_resource_graph_rejected():
    objects = MESH + "".join(
        f'<object id="{i}"><components><component objectid="{i - 1}"/></components></object>'
        for i in range(2, 81)
    )
    with pytest.raises(ValueError, match="depth"):
        audit.load_project(package(model(objects, '<item objectid="80"/>')))


def test_root_extension_namespace_cannot_be_shadowed():
    contents = (
        model()
        .replace(b"<model ", b'<model xmlns:e="urn:unsupported" requiredextensions="e" ')
        .replace(b'<vertex x="0"', f'<vertex xmlns:e="{audit.PRODUCTION}" x="0"'.encode(), 1)
    )
    with pytest.raises(ValueError, match="required model extension"):
        audit.load_project(package(contents))


def test_member_read_caller_bound():
    with audit.ProjectArchive(package(extras={"Metadata/test": b"12345"})) as archive:
        with pytest.raises(ValueError, match="requested bound"):
            archive.read("Metadata/test", max_bytes=4)
        assert archive.read("Metadata/test", max_bytes=5) == b"12345"
        with pytest.raises(ValueError, match="invalid member"):
            archive.read("Metadata/test", max_bytes=True)


def test_child_builds_ignored_and_nonroot_crossparts_rejected():
    objects = (
        '<object id="2"><components><component objectid="1" '
        'p:path="/3D/other.model"/></components></object>'
    )
    payload = package(
        model(objects, '<item objectid="2"/>'),
        {"3D/other.model": model(build='<item objectid="999"/>')},
    )
    assert len(audit.load_project(payload)["instances"]) == 1
    child = model(
        '<object id="1"><components><component objectid="1" '
        'p:path="/3D/3dmodel.model"/></components></object>'
    )
    with pytest.raises(ValueError, match="root-model absolute"):
        audit.load_project(
            package(model(objects, '<item objectid="2"/>'), {"3D/other.model": child})
        )


def test_cli_exclusive_output_preserves_project(tmp_path):
    source = tmp_path / "DRAFT.3mf"
    payload = package()
    source.write_bytes(payload)
    output = tmp_path / "audit.json"
    assert audit.main([str(source), "--output", str(output)]) == 0
    assert b"\r" not in output.read_bytes()
    original = output.read_bytes()
    assert audit.main([str(source), "--output", str(output)]) == 2
    assert output.read_bytes() == original
    assert audit.main([str(source), "--output", str(source)]) == 2
    assert source.read_bytes() == payload
