"""Bounded, read-only 3MF structure inspection; no slicer or fabrication acceptance."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import posixpath
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
import zlib
from pathlib import Path
from urllib.parse import unquote, urlsplit

CORE = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
PRODUCTION = "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
RELATIONSHIPS = "http://schemas.openxmlformats.org/package/2006/relationships"
MODEL_RELATIONSHIP = "http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"
MODEL_CONTENT_TYPE = "application/vnd.ms-package.3dmanufacturing-3dmodel+xml"
CONTENT_TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"
MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
MAX_MEMBER_BYTES = 128 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024
MAX_MEMBERS = 512
MAX_ELEMENTS = 2_000_000
MAX_GEOMETRY = 500_000
MAX_INSTANCES = 10_000
MAX_REFERENCES = 10_000
IDENTITY = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]
UNITS = {"micron", "millimeter", "centimeter", "inch", "foot", "meter"}


def _safe_name(name: str) -> bool:
    return (
        bool(name)
        and len(name) <= 512
        and not name.startswith("/")
        and "\\" not in name
        and ":" not in name
        and "%" not in name
        and all(ord(c) >= 32 and ord(c) != 127 for c in name)
        and all(part not in {"", ".", ".."} for part in name.rstrip("/").split("/"))
    )


class ProjectArchive:
    """Shared bounded archive reader. Never extracts or emits arbitrary metadata."""

    def __init__(self, path: Path | bytes):
        if isinstance(path, bytes):
            payload = path
        else:
            with Path(path).open("rb") as source:
                payload = source.read(MAX_ARCHIVE_BYTES + 1)
        if not payload or len(payload) > MAX_ARCHIVE_BYTES:
            raise ValueError("project archive size outside bounded range")
        self.sha256 = hashlib.sha256(payload).hexdigest()
        self.size = len(payload)
        self._archive = zipfile.ZipFile(io.BytesIO(payload))
        try:
            infos = self._archive.infolist()
            names = [info.filename for info in infos]
            if (
                not infos
                or len(infos) > MAX_MEMBERS
                or len({name.casefold() for name in names}) != len(names)
                or sum(info.file_size for info in infos) > MAX_TOTAL_BYTES
            ):
                raise ValueError("project member count, collision or total size violation")
            for info in infos:
                if (
                    not _safe_name(info.filename)
                    or info.flag_bits & 1
                    or info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
                    or info.file_size > MAX_MEMBER_BYTES
                    or info.file_size > max(info.compress_size, 1) * 1000
                    or ((info.external_attr >> 16) & 0o170000) == 0o120000
                ):
                    raise ValueError("unsafe, encrypted, unsupported or oversized project member")
            self.names = tuple(names)
        except Exception:
            self._archive.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self._archive.close()

    def read(self, name: str, *, max_bytes: int = MAX_MEMBER_BYTES) -> bytes:
        if name not in self.names:
            raise ValueError("required project member is missing")
        if type(max_bytes) is not int or not 0 < max_bytes <= MAX_MEMBER_BYTES:
            raise ValueError("invalid member read bound")
        if self._archive.getinfo(name).file_size > max_bytes:
            raise ValueError("project member exceeds requested bound")
        with self._archive.open(name) as source:
            contents = source.read(max_bytes + 1)
        if len(contents) > max_bytes:
            raise ValueError("project member exceeds bound")
        return contents

    def safe_xml(self, name: str) -> ET.Element:
        payload = self.read(name)
        # Restrict to UTF-8, so alternate encodings cannot conceal a DTD/entity.
        text = payload.decode("utf-8-sig", errors="strict")
        if "\x00" in text or "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
            raise ValueError("DTD/entity or alternate-encoding XML is unsupported")
        declaration = re.match(r"\s*<\?xml\s+[^?]*encoding=['\"]([^'\"]+)", text)
        if declaration and declaration[1].lower() not in {"utf-8", "utf8"}:
            raise ValueError("only UTF-8 project XML is supported")
        # Count during parsing, before constructing an unbounded element tree.
        count = depth = 0
        parser = ET.XMLPullParser(events=("start", "end"))
        root = None
        for offset in range(0, len(payload), 65536):
            parser.feed(payload[offset : offset + 65536])
            for event, element in parser.read_events():
                if event == "start":
                    count += 1
                    depth += 1
                    if root is None:
                        root = element
                    if count > MAX_ELEMENTS or depth > 64:
                        raise ValueError("project XML node/depth bound exceeded")
                else:
                    depth -= 1
        parser.close()
        if root is None:
            raise ValueError("empty XML")
        return root


def _target(base: str, value: str) -> str:
    parsed = urlsplit(value)
    decoded = unquote(parsed.path)
    if (
        not value
        or "%" in value
        or parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
        or "\\" in decoded
        or any(part in {".", ".."} for part in decoded.split("/"))
    ):
        raise ValueError("external or ambiguous model reference")
    path = posixpath.normpath(
        decoded.lstrip("/") if decoded.startswith("/") else posixpath.join(base, decoded)
    )
    if not _safe_name(path) or path.endswith("/"):
        raise ValueError("unsafe model reference")
    return path


def _identifier(value: str | None) -> str:
    if value is None or not re.fullmatch(r"[1-9][0-9]{0,9}", value):
        raise ValueError("invalid positive object identifier")
    return value


def _number(value: str | None) -> float:
    if (
        value is None
        or len(value) > 128
        or not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", value)
    ):
        raise ValueError("invalid or oversized numeric token")
    mantissa, *exponent = value.lower().split("e")
    if exponent and abs(int(exponent[0])) > 324:
        raise ValueError("numeric exponent exceeds bound")
    result = float(value)
    if not math.isfinite(result) or abs(result) > 1e12:
        raise ValueError("nonfinite or out-of-range geometry/transform")
    if result == 0 and any(char in "123456789" for char in mantissa):
        raise ValueError("nonzero geometry/transform underflow")
    return result


def _transform(value: str | None) -> list[float]:
    if value is None:
        return IDENTITY.copy()
    tokens = value.split()
    if len(tokens) != 12:
        raise ValueError("transform must have twelve finite coefficients")
    result = [_number(token) for token in tokens]
    a, b, c, d, e, f, g, h, i = result[:9]
    determinant = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    if determinant == 0:
        raise ValueError("singular model transform")
    return result


def _transform_tokens(value: str | None) -> list[str]:
    return value.split() if value is not None else [str(int(value)) for value in IDENTITY]


def load_project(path: Path | bytes) -> dict:
    """Return numeric mesh graph for companion tools; no arbitrary metadata text.

    Instance transform_chain applies leaf-local component first, then each parent,
    then build transform, using 3MF row-vector twelve-coefficient convention.
    """
    with ProjectArchive(path) as archive:
        content_types = archive.safe_xml("[Content_Types].xml")
        if content_types.tag != f"{{{CONTENT_TYPES}}}Types":
            raise ValueError("invalid package content types")
        defaults, overrides = {}, {}
        for entry in content_types:
            if entry.tag == f"{{{CONTENT_TYPES}}}Default":
                key = entry.get("Extension", "").lower()
                destination = defaults
            elif entry.tag == f"{{{CONTENT_TYPES}}}Override":
                key = _target("", entry.get("PartName", ""))
                destination = overrides
            else:
                raise ValueError("unknown content type entry")
            if not key or key in destination or not entry.get("ContentType"):
                raise ValueError("missing or duplicate content type mapping")
            destination[key] = entry.get("ContentType")
        relationships = archive.safe_xml("_rels/.rels")
        if relationships.tag != f"{{{RELATIONSHIPS}}}Relationships":
            raise ValueError("invalid package relationships")
        starts = [row for row in relationships if row.get("Type") == MODEL_RELATIONSHIP]
        if len(starts) != 1 or starts[0].get("TargetMode") not in {None, "Internal"}:
            raise ValueError("missing, duplicate or external start model")
        root_path = _target("", starts[0].get("Target", ""))
        models = []
        pending = [root_path]
        seen = set()
        geometry_count = 0
        reference_count = 0
        while pending:
            model_path = pending.pop()
            if model_path in seen:
                continue
            seen.add(model_path)
            if (
                overrides.get(model_path, defaults.get(model_path.rsplit(".", 1)[-1].lower()))
                != MODEL_CONTENT_TYPE
            ):
                raise ValueError("referenced model has missing or incorrect content type")
            if len(seen) > 128:
                raise ValueError("model graph exceeds bounded part count")
            model = archive.safe_xml(model_path)
            if model.tag != f"{{{CORE}}}model" or model.get("unit", "millimeter") not in UNITS:
                raise ValueError("unsupported model namespace or unit")
            namespaces = {}
            for event, value in ET.iterparse(
                io.BytesIO(archive.read(model_path)), events=("start-ns", "start")
            ):
                if event == "start":
                    break
                namespaces[value[0]] = value[1]
            if any(
                namespaces.get(prefix) != PRODUCTION
                for prefix in model.get("requiredextensions", "").split()
            ):
                raise ValueError("unsupported required model extension")
            rows = []
            ids = set()
            resources = model.find(f"{{{CORE}}}resources")
            if (
                len(model.findall(f"{{{CORE}}}resources")) != 1
                or len(model.findall(f"{{{CORE}}}build")) != 1
            ):
                raise ValueError("model needs exactly one resources and build container")
            resource_ids = [_identifier(resource.get("id")) for resource in resources]
            if len(resource_ids) != len(set(resource_ids)):
                raise ValueError("duplicate resource identifier")
            for obj in model.findall(f"{{{CORE}}}resources/{{{CORE}}}object"):
                identifier = _identifier(obj.get("id"))
                if identifier in ids:
                    raise ValueError("duplicate object identifier")
                ids.add(identifier)
                reference_count += 1
                if reference_count > MAX_REFERENCES or obj.get("type", "model") != "model":
                    raise ValueError("unsupported object type or excessive resources")
                meshes = obj.findall(f"{{{CORE}}}mesh")
                groups = obj.findall(f"{{{CORE}}}components")
                if len(meshes) + len(groups) != 1:
                    raise ValueError("object must contain exactly one mesh or components group")
                vertices, triangles, tokens, components = [], [], [], []
                if meshes:
                    if (
                        len(meshes[0].findall(f"{{{CORE}}}vertices")) != 1
                        or len(meshes[0].findall(f"{{{CORE}}}triangles")) != 1
                    ):
                        raise ValueError("mesh needs exactly one vertices and triangles container")
                    for vertex in meshes[0].findall(f"{{{CORE}}}vertices/{{{CORE}}}vertex"):
                        raw = tuple(vertex.get(axis) for axis in ("x", "y", "z"))
                        tokens.append(raw)
                        vertices.append(tuple(_number(value) for value in raw))
                    for triangle in meshes[0].findall(f"{{{CORE}}}triangles/{{{CORE}}}triangle"):
                        indices = []
                        for key in ("v1", "v2", "v3"):
                            value = triangle.get(key, "")
                            if not re.fullmatch(r"[0-9]{1,10}", value):
                                raise ValueError("invalid triangle index")
                            indices.append(int(value))
                        if max(indices) >= len(vertices) or len(set(indices)) != 3:
                            raise ValueError("dangling or repeated triangle index")
                        triangles.append(tuple(indices))
                    if not vertices or not triangles:
                        raise ValueError("empty mesh")
                    geometry_count += len(vertices) + len(triangles)
                    if geometry_count > MAX_GEOMETRY:
                        raise ValueError("aggregate mesh complexity exceeds bound")
                else:
                    for component in groups[0].findall(f"{{{CORE}}}component"):
                        destination = component.get(f"{{{PRODUCTION}}}path")
                        if destination is not None and (
                            model_path != root_path or not destination.startswith("/")
                        ):
                            raise ValueError(
                                "production component paths require root-model absolute references"
                            )
                        target = (
                            _target(posixpath.dirname(model_path), destination)
                            if destination
                            else model_path
                        )
                        components.append(
                            {
                                "objectid": _identifier(component.get("objectid")),
                                "path": target,
                                "transform": _transform(component.get("transform")),
                                "transform_tokens": _transform_tokens(component.get("transform")),
                            }
                        )
                        pending.append(target)
                        reference_count += 1
                    if not components:
                        raise ValueError("empty components object")
                rows.append(
                    {
                        "id": identifier,
                        "vertices": vertices,
                        "vertex_tokens": tokens,
                        "triangles": triangles,
                        "components": components,
                    }
                )
            build = []
            for item in model.findall(f"{{{CORE}}}build/{{{CORE}}}item"):
                if model_path != root_path:
                    continue  # Production specifies only root build entries have meaning.
                printable = item.get("printable", "1")
                if printable not in {"0", "1", "true", "false"}:
                    raise ValueError("invalid build printable value")
                destination = item.get(f"{{{PRODUCTION}}}path")
                if destination is not None and not destination.startswith("/"):
                    raise ValueError("production build path must be absolute")
                target = (
                    _target(posixpath.dirname(model_path), destination)
                    if destination
                    else model_path
                )
                pending.append(target)
                reference_count += 1
                build.append(
                    {
                        "objectid": _identifier(item.get("objectid")),
                        "path": target,
                        "transform": _transform(item.get("transform")),
                        "transform_tokens": _transform_tokens(item.get("transform")),
                        "printable": printable in {"1", "true"},
                    }
                )
            models.append(
                {
                    "path": model_path,
                    "unit": model.get("unit", "millimeter"),
                    "objects": rows,
                    "build": build,
                }
            )
            if reference_count > MAX_REFERENCES:
                raise ValueError("project reference count exceeds bound")
        if len({model["unit"] for model in models}) != 1:
            raise ValueError("mixed linked-model units are unsupported")
        lookup = {(model["path"], obj["id"]): obj for model in models for obj in model["objects"]}
        # Validate every resource graph, including unused resources, before expanding builds.
        completed = {}

        def visit(key, ancestors):
            if key not in lookup:
                raise ValueError("dangling object reference")
            if key in ancestors or len(ancestors) >= 64:
                raise ValueError("cyclic or excessive-depth object graph")
            if key in completed:
                return completed[key]
            height = 1
            for component in lookup[key]["components"]:
                height = max(
                    height, 1 + visit((component["path"], component["objectid"]), ancestors | {key})
                )
            if height > 64:
                raise ValueError("object graph exceeds depth bound")
            completed[key] = height
            return height

        for key in lookup:
            visit(key, set())
        for model in models:
            for item in model["build"]:
                if (item["path"], item["objectid"]) not in lookup:
                    raise ValueError("dangling build object")
        root = next(model for model in models if model["path"] == root_path)
        instances = []

        def expand(key, chain, token_chain, build_index, printable):
            if len(chain) > 64:
                raise ValueError("mesh transform chain exceeds depth bound")
            obj = lookup[key]
            if obj["components"]:
                for component in obj["components"]:
                    expand(
                        (component["path"], component["objectid"]),
                        [component["transform"], *chain],
                        [component["transform_tokens"], *token_chain],
                        build_index,
                        printable,
                    )
            else:
                instances.append(
                    {
                        "model_path": key[0],
                        "objectid": key[1],
                        "build_index": build_index,
                        "transform_chain": chain,
                        "transform_tokens_chain": token_chain,
                        "printable": printable,
                    }
                )
                if len(instances) > MAX_INSTANCES:
                    raise ValueError("expanded mesh instance bound exceeded")

        for index, item in enumerate(root["build"]):
            key = (item["path"], item["objectid"])
            if key not in lookup:
                raise ValueError("dangling build object")
            expand(key, [item["transform"]], [item["transform_tokens"]], index, item["printable"])
        if not instances:
            raise ValueError("project has no mesh instances in root build")
        return {
            "sha256": archive.sha256,
            "size": archive.size,
            "member_count": len(archive.names),
            "root_model": root_path,
            "models": models,
            "instances": instances,
        }


def audit_project(path: Path | bytes) -> dict:
    graph = load_project(path)
    return {
        "schema": "raftel.anycubic_draft_project.v1",
        "evidence_class": "saved_package_structure_only",
        "project_sha256": graph["sha256"],
        "project_size_bytes": graph["size"],
        "member_count": graph["member_count"],
        "root_model": graph["root_model"],
        "models": [
            {
                "path": model["path"],
                "unit": model["unit"],
                "objects": [
                    {
                        "id": obj["id"],
                        "vertex_count": len(obj["vertices"]),
                        "triangle_count": len(obj["triangles"]),
                        "components": obj["components"],
                    }
                    for obj in model["objects"]
                ],
                "build": model["build"],
            }
            for model in graph["models"]
        ],
        "build_item_count": len(
            next(model for model in graph["models"] if model["path"] == graph["root_model"])[
                "build"
            ]
        ),
        "mesh_instance_count": len(graph["instances"]),
        "printable_mesh_instance_count": sum(row["printable"] for row in graph["instances"]),
        "instances": graph["instances"],
        "native_application_save_observed": None,
        "software_profile_observation": None,
        "geometry_source_equivalence": None,
        "slicing_or_gcode_generated": None,
        "physical_nozzle_material_confirmed": None,
        "manufacturing_release": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        report = audit_project(args.project)
        output = json.dumps(report, indent=2, allow_nan=False) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8", newline="\n") as target:
                target.write(output)
        else:
            print(output, end="")
    except (
        OSError,
        ValueError,
        KeyError,
        ET.ParseError,
        zipfile.BadZipFile,
        RuntimeError,
        zlib.error,
    ):
        print(
            "project audit failed: invalid, unsupported or unavailable input/output",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
