"""Inspect FreeCAD source containers without importing or executing CAD code."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile


def inspect_reference(source: Path) -> dict:
    """Read native files; compare reference names using case-sensitive semantics."""
    if not source.is_dir():
        raise ValueError(f"Not a source directory: {source}")
    native = sorted(p for p in source.iterdir() if p.suffix.casefold() == ".fcstd")
    if not native:
        raise ValueError("No FreeCAD source files found")
    names = {p.name for p in native}
    files = []
    errors = []
    mismatches = {}
    missing = set()
    assemblies = {}
    for path in native:
        try:
            data = path.read_bytes()
            with zipfile.ZipFile(path) as archive:
                document = ET.fromstring(archive.read("Document.xml"))
            references = sorted(
                {node.attrib["file"] for node in document.findall(".//XLink") if node.get("file")}
            )
            for reference in references:
                if reference in names:
                    continue
                matches = sorted(name for name in names if name.casefold() == reference.casefold())
                if matches:
                    mismatches[reference] = matches
                else:
                    missing.add(reference)
            files.append(
                {
                    "path": path.name,
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "document_program_version": document.get("ProgramVersion"),
                    "external_file_references": references,
                }
            )
            if path.name.startswith("Assembly"):
                assemblies[path.name] = references
        except (OSError, ValueError, KeyError, zipfile.BadZipFile, ET.ParseError) as error:
            errors.append({"path": path.name, "error": str(error)})
    return {
        "schema_version": 1,
        "validation_level": "ZIP/XML source inspection only; no CAD import or recompute",
        "source_file_count": len(native),
        "parsed_file_count": len(files),
        "source_bytes": sum(p.stat().st_size for p in native),
        "assembly_dependencies": assemblies,
        "reference_filename_case_mismatches": dict(sorted(mismatches.items())),
        "missing_reference_files": sorted(missing),
        "errors": errors,
        "files": files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Upstream freecad-src directory (read only)")
    parser.add_argument("--strict", action="store_true", help="Exit 1 for parse or reference issues")
    args = parser.parse_args()
    try:
        result = inspect_reference(args.source)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2))
    issues = result["errors"] or result["missing_reference_files"] or result["reference_filename_case_mismatches"]
    return int(bool(args.strict and issues))


if __name__ == "__main__":
    raise SystemExit(main())
