"""Resolve pinned native sibling references without rewriting original CAD files.

On a case-sensitive filesystem create relative symlink aliases only inside a
separate working-copy freecad-src directory. Case-insensitive filesystems need
no aliases. The source files and their spelling remain unchanged.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def resolve_aliases(directory: Path, inventory: Path, *, apply: bool = False) -> dict:
    if not directory.is_dir():
        raise ValueError("working-copy directory must exist")
    data = json.loads(inventory.read_text())
    findings = data["reference_filename_case_mismatches"]
    created, resolved = [], []
    for alias, candidates in findings.items():
        if Path(alias).name != alias or alias in {".", ".."}:
            raise ValueError("only native sibling references are allowed")
        if len(candidates) != 1:
            raise ValueError(f"ambiguous reference: {alias}")
        target = candidates[0]
        if Path(target).name != target:
            raise ValueError("target must be a sibling filename")
        existing = directory / target
        link = directory / alias
        if not existing.is_file():
            raise ValueError(f"missing target: {target}")
        if link.exists():
            if not link.samefile(existing):
                raise ValueError(f"alias conflicts with an existing different file: {alias}")
            resolved.append(alias)
        elif link.is_symlink():
            raise ValueError(f"broken alias already exists: {alias}")
        elif apply:
            link.symlink_to(target)
            created.append(alias)
    return {
        "applied": apply,
        "reference_count": len(findings),
        "created_aliases": created,
        "already_resolved": resolved,
        "unresolved_without_apply": len(findings) - len(resolved) - len(created),
        "native_files_rewritten": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("working_copy", type=Path)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        result = resolve_aliases(args.working_copy, args.inventory, apply=args.apply)
    except (ValueError, OSError, KeyError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
