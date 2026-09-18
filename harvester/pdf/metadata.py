from __future__ import annotations
from pathlib import Path
from urllib.parse import unquote, urlparse

def filename_from_url(url: str, default: str = "document.pdf") -> str:
    path = unquote(urlparse(url).path or "")
    name = Path(path).name
    if not name or name in {".", "/"}:
        return default
    if "." not in name:
        name = f"{name}.pdf"
    safe = "".join(c if c.isalnum() or c in "._- " else "_" for c in name)
    return safe[:180] or default

def collision_name(path: Path, index: int) -> Path:
    stem = path.stem
    suffix = path.suffix or ".pdf"
    return path.with_name(f"{stem}__{index}{suffix}")
