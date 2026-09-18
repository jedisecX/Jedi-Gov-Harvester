from __future__ import annotations
from harvester.crawler.canonicalize import domain_of, normalize_url
from harvester.database import Database, utcnow
from harvester.pdf.metadata import filename_from_url

class PdfIndexer:
    def __init__(self, db: Database):
        self.db = db

    def record(self, url: str, *, source_url: str | None = None, state: str | None = None, agency: str | None = None, depth: int = 0) -> int | None:
        canonical = normalize_url(url)
        if not canonical:
            return None
        domain = domain_of(canonical)
        now = utcnow()
        with self.db.tx() as conn:
            existing = conn.execute("SELECT id FROM urls WHERE canonical_url=?", (canonical,)).fetchone()
            if existing:
                url_id = existing["id"]
                conn.execute("UPDATE urls SET last_checked=?, status='indexed' WHERE id=?", (now, url_id))
            else:
                cur = conn.execute(
                    """INSERT INTO urls (url, canonical_url, domain, url_type, source_url, depth, discovered_at, status, last_checked)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (url, canonical, domain, "pdf", source_url, depth, now, "indexed", now),
                )
                url_id = cur.lastrowid
            doc = conn.execute("SELECT id FROM documents WHERE canonical_url=?", (canonical,)).fetchone()
            if doc:
                conn.execute("UPDATE documents SET last_seen=? WHERE id=?", (now, doc["id"]))
                return doc["id"]
            cur = conn.execute(
                """INSERT INTO documents (url_id, pdf_url, canonical_url, filename, domain, state, agency, first_seen, last_seen, download_status)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (url_id, url, canonical, filename_from_url(canonical), domain, state, agency, now, now, "queued"),
            )
            doc_id = cur.lastrowid
            conn.execute("INSERT OR IGNORE INTO download_queue (document_id, status) VALUES (?, 'queued')", (doc_id,))
            return doc_id
