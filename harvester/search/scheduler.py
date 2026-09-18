from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from harvester.rate_limit import backoff_seconds
from harvester.search.base import SearchError, SearchProvider, SearchResult

log = logging.getLogger("search")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


class SearchScheduler:
    """One results page per request. Persist last successful page. Back off on 429/403/503."""

    def __init__(self, db, provider: SearchProvider):
        self.db = db
        self.provider = provider

    def due_row(self):
        now = _iso(_now())
        return self.db.fetchone(
            """SELECT * FROM searches
               WHERE provider=?
                 AND status IN ('pending','backoff')
                 AND (next_attempt IS NULL OR next_attempt<=?)
               ORDER BY query, page
               LIMIT 1""",
            (self.provider.name, now),
        )

    def cached_results(self, query: str, page: int) -> list[SearchResult] | None:
        rows = self.db.fetchall(
            """SELECT title, url, snippet FROM search_results
               WHERE provider=? AND query=? AND page=? ORDER BY id""",
            (self.provider.name, query, page),
        )
        if not rows:
            return None
        return [SearchResult(title=r["title"] or "", url=r["url"], snippet=r["snippet"] or "") for r in rows]

    def store_results(self, search_id: int, query: str, page: int, results: list[SearchResult]) -> None:
        self.db.execute("DELETE FROM search_results WHERE provider=? AND query=? AND page=?", (self.provider.name, query, page))
        self.db.executemany(
            """INSERT INTO search_results (search_id, provider, query, page, url, title, snippet, seen_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [(search_id, self.provider.name, query, page, r.url, r.title, r.snippet, _iso(_now())) for r in results],
        )

    def mark_ok(self, row_id: int, count: int) -> None:
        self.db.execute(
            """UPDATE searches SET status='completed', completed_at=?, result_count=?, error=NULL, next_attempt=NULL WHERE id=?""",
            (_iso(_now()), count, row_id),
        )

    def mark_backoff(self, row, exc: SearchError) -> None:
        attempts = int(row["attempts"] or 0) + 1
        wait = exc.retry_after if exc.retry_after is not None else backoff_seconds(attempts, base=8.0, cap=1800.0)
        status = "blocked" if exc.fatal else "backoff"
        nxt = _iso(_now() + timedelta(seconds=wait))
        log.info("search %s page %s -> %s wait=%.0fs", row["query"][:80], row["page"], status, wait)
        self.db.execute(
            """UPDATE searches SET status=?, attempts=?, error=?, next_attempt=?, started_at=COALESCE(started_at, ?) WHERE id=?""",
            (status, attempts, str(exc)[:400], nxt, _iso(_now()), row["id"]),
        )
        if exc.fatal:
            self.db.execute(
                """UPDATE searches SET status='blocked', next_attempt=? WHERE provider=? AND status IN ('pending','backoff')""",
                (nxt, self.provider.name),
            )

    def fetch_one_page(self) -> list[SearchResult] | None:
        row = self.due_row()
        if not row:
            return None
        cached = self.cached_results(row["query"], int(row["page"]))
        if cached is not None:
            self.mark_ok(row["id"], len(cached))
            return cached
        self.db.execute(
            "UPDATE searches SET status='running', started_at=COALESCE(started_at, ?), attempts=attempts+1 WHERE id=?",
            (_iso(_now()), row["id"]),
        )
        try:
            results = self.provider.search(row["query"], int(row["page"]))
        except SearchError as exc:
            self.mark_backoff(row, exc)
            return None
        except Exception as exc:
            self.mark_backoff(row, SearchError(str(exc), status=None, fatal=False))
            return None
        self.store_results(row["id"], row["query"], int(row["page"]), results)
        self.mark_ok(row["id"], len(results))
        return results
