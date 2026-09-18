from __future__ import annotations
import hashlib
from pathlib import Path

def sha256_file(path: str | Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        while True:
            block = fh.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()

def content_addressed_path(root: Path, digest: str) -> Path:
    return root / digest[:2] / digest[2:4] / f"{digest}.pdf"
