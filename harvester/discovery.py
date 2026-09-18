from __future__ import annotations

import logging

from harvester.agencies import list_agencies, search_queries_for
from harvester.crawler.canonicalize import normalize_url
from harvester.database import Database
from harvester.domain_policy import DomainPolicy
from harvester.pdf.detector import url_looks_like_pdf
from harvester.pdf.indexer import PdfIndexer
from harvester.progress import progress
from harvester.search.base import SearchProvider
from harvester.search.scheduler import SearchScheduler

log = logging.getLogger("search")


class Discovery:
    def __init__(self, db: Database, provider: SearchProvider, policy: DomainPolicy, *, pages_per_query: int = 10):
        self.db = db
        self.provider = provider
        self.policy = policy
        self.pages_per_query = pages_per_query
        self.indexer = PdfIndexer(db)
        self.scheduler = SearchScheduler(db, provider)

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

    def pending_count(self) -> int:
        row = self.db.fetchone(
            "SELECT COUNT(*) AS c FROM searches WHERE provider=? AND status IN ('pending','backoff')",
            (self.provider.name,),
        )
        return int(row["c"]) if row else 0

    def ingest(self, results) -> int:
        count = 0
        for item in results or []:
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
        return count

    def run_one(self) -> bool:
        results = self.scheduler.fetch_one_page()
        if results is None:
            return False
        self.ingest(results)
        return True

    def run(self, max_pages: int | None = None) -> int:
        remaining = self.pending_count()
        total = remaining if max_pages is None else min(remaining, max_pages)
        done = 0
        idle = 0
        with progress(total=total or None, desc="discover", unit="page") as bar:
            while max_pages is None or done < max_pages:
                results = self.scheduler.fetch_one_page()
                if results is None:
                    idle += 1
                    if not self.scheduler.due_row() or idle > 3:
                        break
                    continue
                ingested = self.ingest(results)
                done += 1
                idle = 0
                bar.update(1)
                bar.set_postfix(urls=ingested)
        return done
