from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS agencies (
    id INTEGER PRIMARY KEY,
    state TEXT NOT NULL,
    agency_name TEXT NOT NULL,
    agency_type TEXT,
    official_url TEXT NOT NULL,
    domain TEXT NOT NULL,
    source TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    last_verified TEXT,
    UNIQUE(state, official_url)
);
CREATE TABLE IF NOT EXISTS urls (
    id INTEGER PRIMARY KEY,
    url TEXT NOT NULL,
    canonical_url TEXT NOT NULL UNIQUE,
    domain TEXT NOT NULL,
    url_type TEXT,
    source_url TEXT,
    depth INTEGER DEFAULT 0,
    discovered_at TEXT,
    status TEXT DEFAULT 'new',
    last_checked TEXT
);
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    url_id INTEGER,
    pdf_url TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    filename TEXT,
    domain TEXT,
    state TEXT,
    agency TEXT,
    content_length INTEGER,
    sha256 TEXT,
    etag TEXT,
    last_modified TEXT,
    first_seen TEXT,
    last_seen TEXT,
    download_status TEXT DEFAULT 'queued',
    download_path TEXT,
    http_status INTEGER,
    error TEXT,
    UNIQUE(canonical_url),
    FOREIGN KEY(url_id) REFERENCES urls(id)
);
CREATE INDEX IF NOT EXISTS idx_documents_sha256 ON documents(sha256);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(download_status);
CREATE TABLE IF NOT EXISTS searches (
    id INTEGER PRIMARY KEY,
    provider TEXT NOT NULL,
    query TEXT NOT NULL,
    page INTEGER NOT NULL,
    status TEXT DEFAULT 'pending',
    started_at TEXT,
    completed_at TEXT,
    result_count INTEGER DEFAULT 0,
    attempts INTEGER DEFAULT 0,
    error TEXT,
    next_attempt TEXT,
    UNIQUE(provider, query, page)
);
CREATE TABLE IF NOT EXISTS search_results (
    id INTEGER PRIMARY KEY,
    search_id INTEGER,
    provider TEXT NOT NULL,
    query TEXT NOT NULL,
    page INTEGER NOT NULL,
    url TEXT NOT NULL,
    title TEXT,
    snippet TEXT,
    seen_at TEXT,
    UNIQUE(provider, query, page, url)
);
CREATE INDEX IF NOT EXISTS idx_search_results_url ON search_results(url);
CREATE TABLE IF NOT EXISTS crawl_queue (
    id INTEGER PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    depth INTEGER DEFAULT 0,
    priority INTEGER DEFAULT 0,
    status TEXT DEFAULT 'queued',
    attempts INTEGER DEFAULT 0,
    next_attempt TEXT,
    locked_until TEXT,
    worker_id TEXT
);
CREATE TABLE IF NOT EXISTS download_queue (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL UNIQUE,
    status TEXT DEFAULT 'queued',
    attempts INTEGER DEFAULT 0,
    next_attempt TEXT,
    locked_until TEXT,
    worker_id TEXT,
    FOREIGN KEY(document_id) REFERENCES documents(id)
);
CREATE TABLE IF NOT EXISTS robots_cache (
    domain TEXT PRIMARY KEY,
    body TEXT,
    fetched_at TEXT,
    status INTEGER
);
"""

_SEARCH_COLS = {
    "attempts": "INTEGER DEFAULT 0",
    "error": "TEXT",
    "next_attempt": "TEXT",
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=30000")
            self._local.conn = conn
        return conn

    def _init(self) -> None:
        conn = sqlite3.connect(self.path)
        try:
            conn.executescript(SCHEMA)
            existing = {row[1] for row in conn.execute("PRAGMA table_info(searches)").fetchall()}
            for col, decl in _SEARCH_COLS.items():
                if col not in existing:
                    conn.execute(f"ALTER TABLE searches ADD COLUMN {col} {decl}")
            conn.commit()
        finally:
            conn.close()

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    def execute(self, sql: str, params: tuple | list = ()) -> sqlite3.Cursor:
        return self._connect().execute(sql, params)

    def executemany(self, sql: str, seq: list) -> sqlite3.Cursor:
        return self._connect().executemany(sql, seq)

    def fetchall(self, sql: str, params: tuple | list = ()) -> list[sqlite3.Row]:
        return self.execute(sql, params).fetchall()

    def fetchone(self, sql: str, params: tuple | list = ()) -> sqlite3.Row | None:
        return self.execute(sql, params).fetchone()

    def counts(self) -> dict[str, Any]:
        def n(table: str, where: str = "1=1") -> int:
            row = self.fetchone(f"SELECT COUNT(*) AS c FROM {table} WHERE {where}")
            return int(row["c"]) if row else 0
        return {
            "agencies": n("agencies"),
            "agencies_active": n("agencies", "active=1"),
            "urls": n("urls"),
            "searches": n("searches"),
            "searches_done": n("searches", "status='completed'"),
            "searches_pending": n("searches", "status IN ('pending','running','backoff')"),
            "searches_blocked": n("searches", "status='blocked'"),
            "search_results": n("search_results"),
            "crawl_queued": n("crawl_queue", "status='queued'"),
            "crawl_processing": n("crawl_queue", "status='processing'"),
            "crawl_done": n("crawl_queue", "status='completed'"),
            "crawl_failed": n("crawl_queue", "status='failed'"),
            "docs": n("documents"),
            "docs_unique_hash": n("documents", "sha256 IS NOT NULL"),
            "dl_queued": n("documents", "download_status='queued'"),
            "dl_active": n("documents", "download_status='downloading'"),
            "dl_done": n("documents", "download_status='complete'"),
            "dl_failed": n("documents", "download_status='failed'"),
        }
