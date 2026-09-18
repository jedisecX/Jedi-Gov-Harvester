from __future__ import annotations
import json
from pathlib import Path
from harvester.database import Database
from harvester.export.csv import COLUMNS

def _rows(db: Database):
    rows = db.fetchall("""SELECT d.state, d.agency, a.agency_type, d.pdf_url, d.canonical_url, d.filename, d.domain, d.content_length, d.sha256, d.etag, d.last_modified, d.first_seen, d.last_seen, d.download_status, d.download_path, d.http_status FROM documents d LEFT JOIN agencies a ON a.agency_name = d.agency AND a.state = d.state ORDER BY d.id""")
    return [{k: row[k] if k in row.keys() else None for k in COLUMNS} for row in rows]

def export_json(db: Database, output: str | Path) -> int:
    data = _rows(db)
    Path(output).write_text(json.dumps(data, indent=2), encoding="utf-8")
    return len(data)

def export_jsonl(db: Database, output: str | Path) -> int:
    data = _rows(db)
    with Path(output).open("w", encoding="utf-8") as fh:
        for item in data:
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")
    return len(data)
