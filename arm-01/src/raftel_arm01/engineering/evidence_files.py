"""Small shared writer for new evidence artifacts; existing files are preserved."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path


def write_new_evidence(
    outputs: Sequence[tuple[Path, str]], *, protected_inputs: Iterable[Path] = ()
) -> None:
    """Preflight every destination, then exclusively create UTF-8/LF files.

    Path resolution catches relative/absolute and symlink-parent aliases.
    Exclusive creation also rejects a file created after preflight. An I/O race
    or failure can leave partial *new* outputs; existing evidence is never
    truncated or automatically deleted. Callers must use a fresh run directory
    and treat a nonzero exit as an incomplete run.
    """
    paths = [Path(path) for path, _ in outputs]
    resolved = [path.resolve() for path in paths]
    if len(resolved) != len(set(resolved)):
        raise ValueError("evidence output paths must be distinct after resolution")
    protected = {Path(path).resolve() for path in protected_inputs}
    for path, target in zip(paths, resolved, strict=True):
        if target in protected:
            raise ValueError(f"evidence output cannot replace an input: {path}")
        if path.exists() or path.is_symlink():
            raise ValueError(f"evidence output already exists; use a new path: {path}")
    for path, content in outputs:
        with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
