from __future__ import annotations
from pathlib import Path

def part_path(dest: Path) -> Path:
    return dest.with_name(dest.name + ".part")

def existing_size(path: Path) -> int:
    return path.stat().st_size if path.exists() else 0

def atomic_replace(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    src.replace(dest)
