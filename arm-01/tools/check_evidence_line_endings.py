"""Read-only publication guard for LF text and exact-byte evidence bindings.

Git attributes normalize text at check-in; they do not rewrite newly generated
worktree files. A CRLF worktree input can therefore hash differently from the
published LF blob even when its parsed JSON is identical. This guard never
normalizes, stages or modifies files.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

TEXT_SUFFIXES = frozenset(
    {
        ".py",
        ".json",
        ".md",
        ".svg",
        ".yml",
        ".yaml",
        ".toml",
        ".lock",
        ".txt",
        ".ini",
        ".cfg",
        ".ps1",
        ".sh",
    }
)
TEXT_NAMES = frozenset({".gitattributes", ".gitignore", ".editorconfig"})


def inspect_paths(root: Path, paths: list[str]) -> dict:
    """Inspect known text types under root without reading excluded binary assets."""
    root = Path(root).resolve(strict=True)
    checked, missing, violations = [], [], []
    for relative in sorted(set(paths)):
        candidate = Path(relative)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError("line-ending guard paths must stay project-relative")
        path = (root / candidate).resolve()
        if not path.is_relative_to(root):
            raise ValueError("line-ending guard path resolves outside project root")
        if path.suffix.casefold() not in TEXT_SUFFIXES and path.name not in TEXT_NAMES:
            continue
        if not path.is_file():
            missing.append(candidate.as_posix())
            continue
        checked.append(candidate.as_posix())
        offset = 0
        with path.open("rb") as stream:
            while chunk := stream.read(1_048_576):
                index = chunk.find(b"\r")
                if index >= 0:
                    violations.append(
                        {
                            "path": candidate.as_posix(),
                            "first_carriage_return_byte": offset + index,
                            "reason": "CR_or_CRLF_bytes_would_change_under_LF_checkout_policy",
                        }
                    )
                    break
                offset += len(chunk)
    return {
        "schema_version": 1,
        "purpose": "read_only_publication_line_ending_guard",
        "checked_text_file_count": len(checked),
        "missing_worktree_paths": missing,
        "violations": violations,
        "files_changed": False,
        "exact_evidence_hashes_still_require_separate_validation": True,
    }


def repository_paths(root: Path, *, include_untracked: bool = False) -> list[str]:
    command = ["git", "ls-files", "-z", "--cached"]
    if include_untracked:
        command.extend(("--others", "--exclude-standard"))
    process = subprocess.run(command, cwd=root, capture_output=True, check=False)
    if process.returncode:
        raise ValueError("cannot list Git publication paths")
    return [path.decode("utf-8") for path in process.stdout.split(b"\0") if path]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument(
        "--include-untracked",
        action="store_true",
        help="Also inspect new nonignored files before staging",
    )
    args = parser.parse_args()
    try:
        report = inspect_paths(
            args.root, repository_paths(args.root, include_untracked=args.include_untracked)
        )
    except (ValueError, OSError, UnicodeError) as error:
        parser.error(str(error))
    print(json.dumps(report, indent=2))
    return 1 if report["violations"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
