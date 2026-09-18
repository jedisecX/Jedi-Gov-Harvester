from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from harvester.crawler.canonicalize import domain_of, normalize_url
from harvester.crawler.parser import extract_links
from harvester.crawler.robots import RobotsCache
from harvester.database import Database, utcnow
from harvester.domain_policy import DomainPolicy
from harvester.pdf.detector import classify_content_type, is_pdf, url_looks_like_pdf
from harvester.pdf.indexer import PdfIndexer
from harvester.rate_limit import DomainLimiter, backoff_seconds

log = logging.getLogger("crawl")


class Crawler:
    def __init__(self, db: Database, session, policy: DomainPolicy, limiter: DomainLimiter, *, max_depth: int = 5, max_pages_per_domain: int = 10000, max_pdf_per_domain: int = 100000, timeout: int = 30, user_agent: str = "GovernmentPDFHarvester/1.0"):
        self.db = db
        self.session = session
        self.policy = policy
        self.limiter = limiter
        self.max_depth = max_depth
        self.max_pages_per_domain = max_pages_per_domain
        self.max_pdf_per_domain = max_pdf_per_domain
        self.timeout = timeout
        self.indexer = PdfIndexer(db)
        self.robots = RobotsCache(db, user_agent, self._get)

    def enqueue(self, url: str, depth: int = 0, priority: int = 0) -> bool:
        canonical = normalize_url(url)
        if not canonical or not self.policy.is_allowed(canonical):
            return False
        self.db.execute("INSERT OR IGNORE INTO crawl_queue (url, depth, priority, status) VALUES (?, ?, ?, 'queued')", (canonical, depth, priority))
        return True

    def seed_from_agencies(self, state: str | None = None, agency: str | None = None) -> int:
        sql = "SELECT official_url FROM agencies WHERE active=1"
        params: list = []
        if state:
            sql += " AND LOWER(state)=LOWER(?)"
            params.append(state)
        if agency:
            sql += " AND LOWER(agency_name) LIKE LOWER(?)"
            params.append(f"%{agency}%")
        n = 0
        for row in self.db.fetchall(sql, params):
            if self.enqueue(row["official_url"], depth=0, priority=10):
                n += 1
        return n

    def release_expired_leases(self) -> int:
        cur = self.db.execute("UPDATE crawl_queue SET status='queued', worker_id=NULL, locked_until=NULL WHERE status='processing' AND locked_until IS NOT NULL AND locked_until < ?", (utcnow(),))
        return cur.rowcount

    def acquire(self, worker_id: str, lease_seconds: int = 300):
        until = (datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)).isoformat()
        with self.db.tx() as conn:
            row = conn.execute("SELECT id, url, depth, attempts FROM crawl_queue WHERE status='queued' AND (next_attempt IS NULL OR next_attempt <= ?) ORDER BY priority DESC, id ASC LIMIT 1", (utcnow(),)).fetchone()
            if not row:
                return None
            conn.execute("UPDATE crawl_queue SET status='processing', worker_id=?, locked_until=?, attempts=attempts+1 WHERE id=? AND status='queued'", (worker_id, until, row["id"]))
            return dict(row)

    def _get(self, url: str):
        return self.session.get(url, timeout=self.timeout, allow_redirects=True)

    def _domain_page_count(self, domain: str) -> int:
        row = self.db.fetchone("SELECT COUNT(*) AS c FROM urls WHERE domain=? AND url_type='html'", (domain,))
        return int(row["c"]) if row else 0

    def _domain_pdf_count(self, domain: str) -> int:
        row = self.db.fetchone("SELECT COUNT(*) AS c FROM documents WHERE domain=?", (domain,))
        return int(row["c"]) if row else 0

    def process_one(self, worker_id: str = "crawl-1") -> bool:
        job = self.acquire(worker_id)
        if not job:
            return False
        url = job["url"]
        depth = int(job["depth"] or 0)
        domain = domain_of(url)
        try:
            if not self.policy.is_allowed(url):
                self._finish(job["id"], "skipped")
                return True
            if not self.robots.allowed(url):
                log.info("robots deny %s", url)
                self._finish(job["id"], "robots")
                return True
            if self._domain_page_count(domain) >= self.max_pages_per_domain:
                self._finish(job["id"], "domain_limit")
                return True
            self.limiter.acquire(domain)
            try:
                resp = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            finally:
                self.limiter.release(domain)
            if resp.status_code in {429, 503, 403}:
                retry_after = resp.headers.get("Retry-After")
                wait = float(retry_after) if retry_after and retry_after.isdigit() else backoff_seconds(job["attempts"])
                nxt = (datetime.now(timezone.utc) + timedelta(seconds=wait)).isoformat()
                self.db.execute("UPDATE crawl_queue SET status='queued', next_attempt=?, worker_id=NULL, locked_until=NULL WHERE id=?", (nxt, job["id"]))
                return True
            body = resp.content or b""
            header = body[:16]
            ctype = resp.headers.get("Content-Type", "")
            final_url = normalize_url(str(resp.url)) or url
            kind = classify_content_type(ctype, final_url)
            if is_pdf(final_url, ctype, header):
                if self._domain_pdf_count(domain) < self.max_pdf_per_domain:
                    self.indexer.record(final_url, source_url=url, depth=depth)
                self._remember_url(final_url, url, "pdf", depth)
                self._finish(job["id"], "completed")
                return True
            if kind != "html":
                self._remember_url(final_url, url, kind, depth)
                self._finish(job["id"], "completed")
                return True
            html = body.decode(resp.encoding or "utf-8", errors="replace")
            self._remember_url(final_url, url, "html", depth)
            if depth < self.max_depth:
                for link in extract_links(html, final_url):
                    canon = normalize_url(link, final_url)
                    if not canon or not self.policy.is_allowed(canon):
                        continue
                    if url_looks_like_pdf(canon):
                        if self._domain_pdf_count(domain_of(canon)) < self.max_pdf_per_domain:
                            self.indexer.record(canon, source_url=final_url, depth=depth + 1)
                    else:
                        self.enqueue(canon, depth=depth + 1)
            self._finish(job["id"], "completed")
            return True
        except Exception:
            log.exception("crawl failed %s", url)
            self.db.execute("UPDATE crawl_queue SET status='failed', worker_id=NULL, locked_until=NULL WHERE id=?", (job["id"],))
            return True

    def _remember_url(self, url: str, source: str, url_type: str, depth: int) -> None:
        now = utcnow()
        self.db.execute("INSERT OR IGNORE INTO urls (url, canonical_url, domain, url_type, source_url, depth, discovered_at, status, last_checked) VALUES (?,?,?,?,?,?,?,?,?)", (url, url, domain_of(url), url_type, source, depth, now, "seen", now))

    def _finish(self, job_id: int, status: str) -> None:
        self.db.execute("UPDATE crawl_queue SET status=?, worker_id=NULL, locked_until=NULL WHERE id=?", (status, job_id))

    def run(self, max_jobs: int | None = None) -> int:
        self.release_expired_leases()
        done = 0
        while max_jobs is None or done < max_jobs:
            if not self.process_one():
                break
            done += 1
        return done
