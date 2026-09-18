from __future__ import annotations
import csv
from pathlib import Path
from harvester.database import Database
COLUMNS = ["state","agency","agency_type","pdf_url","canonical_url","filename","domain","content_length","sha256","etag","last_modified","first_seen","last_seen","download_status","download_path","http_status"]

def export_csv(db: Database, output: str | Path) -> int:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = db.fetchall("""SELECT d.state, d.agency, a.agency_type, d.pdf_url, d.canonical_url, d.filename, d.domain, d.content_length, d.sha256, d.etag, d.last_modified, d.first_seen, d.last_seen, d.download_status, d.download_path, d.http_status FROM documents d LEFT JOIN agencies a ON a.agency_name = d.agency AND a.state = d.state ORDER BY d.id""")
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row[k] if k in row.keys() else None for k in COLUMNS})
    return len(rows)
