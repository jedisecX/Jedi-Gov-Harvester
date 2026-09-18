from __future__ import annotations

import logging
from harvester.agencies import list_agencies, search_queries_for
from harvester.crawler.canonicalize import normalize_url
from harvester.database import Database, utcnow
from harvester.domain_policy import DomainPolicy
from harvester.pdf.detector import url_looks_like_pdf
from harvester.pdf.indexer import PdfIndexer
from harvester.rate_limit import backoff_seconds
from harvester.search.base import SearchProvider

log = logging.getLogger("search")


class Discovery:
    def __init__(self, db: Database, provider: SearchProvider, policy: DomainPolicy, *, pages_per_query: int = 10):
        self.db = db
        self.provider = provider
        self.policy = policy
        self.pages_per_query = pages_per_query
        self.indexer = PdfIndexer(db)

    def plan(self, state: str | None = None, agency: str | None = None) -> int:
        created = 0
        for row in list_agencies(self.db, state=state, agency=agency):
            for query in search_queries_for(row):
                for page in range(1, self.pages_per_query + 1):
                    cur = self.db.execute(
                        """INSERT OR IGNORE INTO searches (provider, query, page, status) VALUES (?, ?, ?, 'pending')""",
                        (self.provider.name, query, page),
                    )
                    created += cur.rowcount
        return created

    def next_page(self):
        return self.db.fetchone(
            """SELECT * FROM searches WHERE status IN ('pending', 'running') ORDER BY query, page LIMIT 1"""
        )

    def run_one(self) -> bool:
        row = self.next_page()
        if not row:
            return False
        self.db.execute(
            "UPDATE searches SET status='running', started_at=COALESCE(started_at, ?) WHERE id=?",
            (utcnow(), row["id"]),
        )
        try:
            results = self.provider.search(row["query"], int(row["page"]))
        except Exception as exc:
            log.info("search failed %s page %s: %s", row["query"], row["page"], exc)
            self.db.execute("UPDATE searches SET status='pending' WHERE id=?", (row["id"],))
            raise
        count = 0
        for item in results:
            url = normalize_url(item.url)
            if not url or not self.policy.is_allowed(url):
                continue
            if url_looks_like_pdf(url):
                self.indexer.record(url, source_url=f"search:{self.provider.name}")
            else:
                self.db.execute(
                    """INSERT OR IGNORE INTO crawl_queue (url, depth, priority, status) VALUES (?, 0, 5, 'queued')""",
                    (url,),
                )
            count += 1
        self.db.execute(
            """UPDATE searches SET status='completed', completed_at=?, result_count=? WHERE id=?""",
            (utcnow(), count, row["id"]),
        )
        return True

    def run(self, max_pages: int | None = None) -> int:
        done = 0
        while max_pages is None or done < max_pages:
            if not self.run_one():
                break
            done += 1
        return done
