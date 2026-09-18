from __future__ import annotations
from pathlib import Path
from harvester.database import Database

def storage_stats(root: Path):
    if not root.exists():
        return 0, 0
    n = size = 0
    for p in root.rglob("*.pdf"):
        if p.name.endswith(".part"):
            continue
        n += 1
        try:
            size += p.stat().st_size
        except OSError:
            pass
    return n, size

def render_status(db: Database, storage_root: Path | None = None) -> str:
    c = db.counts()
    pdfs, nbytes = storage_stats(Path(storage_root or "data/pdfs"))
    return f"""AGENCIES\n  discovered: {c['agencies']}\n  active:     {c['agencies_active']}\n\nSEARCH\n  queries:          {c['searches']}\n  pages processed:  {c['searches_done']}\n  pages remaining:  {c['searches_pending']}\n\nCRAWLER\n  queued:     {c['crawl_queued']}\n  processing: {c['crawl_processing']}\n  completed:  {c['crawl_done']}\n  failed:     {c['crawl_failed']}\n\nPDF INDEX\n  discovered: {c['docs']}\n  unique:     {c['docs_unique_hash']}\n  duplicates: {max(0, c['docs'] - c['docs_unique_hash'])}\n\nDOWNLOADS\n  queued:    {c['dl_queued']}\n  active:    {c['dl_active']}\n  completed: {c['dl_done']}\n  failed:    {c['dl_failed']}\n\nSTORAGE\n  PDFs:  {pdfs}\n  bytes: {nbytes}""".strip()
