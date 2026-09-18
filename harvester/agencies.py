from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

from harvester.crawler.canonicalize import normalize_url
from harvester.database import Database, utcnow


def load_seed_file(path: str | Path) -> list[dict]:
    p = Path(path)
    with p.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict):
        data = data.get("agencies", [])
    return list(data)


def upsert_agencies(db: Database, records: list[dict]) -> int:
    now = utcnow()
    count = 0
    for rec in records:
        url = normalize_url(rec.get("official_url") or "")
        if not url:
            continue
        domain = (urlparse(url).hostname or "").lower()
        db.execute(
            """INSERT INTO agencies
            (state, agency_name, agency_type, official_url, domain, source, active, last_verified)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(state, official_url) DO UPDATE SET
              agency_name=excluded.agency_name,
              agency_type=excluded.agency_type,
              domain=excluded.domain,
              source=excluded.source,
              active=excluded.active,
              last_verified=excluded.last_verified
            """,
            (
                rec.get("state"),
                rec.get("agency_name"),
                rec.get("agency_type"),
                url,
                domain,
                rec.get("source", "seed"),
                1 if rec.get("active", True) else 0,
                rec.get("last_verified") or now,
            ),
        )
        count += 1
    return count


def list_agencies(db: Database, state: str | None = None, agency: str | None = None):
    sql = "SELECT * FROM agencies WHERE active=1"
    params: list = []
    if state:
        sql += " AND LOWER(state)=LOWER(?)"
        params.append(state)
    if agency:
        sql += " AND LOWER(agency_name) LIKE LOWER(?)"
        params.append(f"%{agency}%")
    sql += " ORDER BY state, agency_name"
    return db.fetchall(sql, params)


def search_queries_for(agency_row) -> list[str]:
    domain = agency_row["domain"]
    name = agency_row["agency_name"]
    queries = [
        f"site:{domain} filetype:pdf",
        f'site:{domain} filetype:pdf "annual report"',
        f'site:{domain} filetype:pdf "budget"',
        f'site:{domain} filetype:pdf "meeting minutes"',
        f'site:{domain} filetype:pdf "audit"',
    ]
    if name:
        queries.append(f'site:{domain} filetype:pdf "{name}"')
    return queries
