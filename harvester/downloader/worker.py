from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from harvester.crawler.canonicalize import domain_of
from harvester.database import Database, utcnow
from harvester.downloader.hashing import content_addressed_path, sha256_file
from harvester.downloader.resume import atomic_replace, existing_size
from harvester.pdf.metadata import collision_name, filename_from_url
from harvester.rate_limit import DomainLimiter, backoff_seconds

log = logging.getLogger("download")
ProgressFn = Callable[[int], None]


class DownloadWorker:
    def __init__(self, db: Database, session, limiter: DomainLimiter, storage_root: Path, storage_temp: Path, *, timeout: int = 60, retries: int = 5, chunk_size: int = 1048576, layout: str = "content_addressed", worker_id: str = "dl-1", on_progress: ProgressFn | None = None):
        self.db = db
        self.session = session
        self.limiter = limiter
        self.root = Path(storage_root)
        self.temp = Path(storage_temp)
        self.timeout = timeout
        self.retries = retries
        self.chunk_size = chunk_size
        self.layout = layout
        self.worker_id = worker_id
        self.on_progress = on_progress
        self.root.mkdir(parents=True, exist_ok=True)
        self.temp.mkdir(parents=True, exist_ok=True)

    def acquire(self, lease_seconds: int = 600):
        until = (datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)).isoformat()
        with self.db.tx() as conn:
            row = conn.execute(
                """SELECT q.id AS qid, q.attempts, d.* FROM download_queue q JOIN documents d ON d.id = q.document_id
                   WHERE q.status='queued' AND (q.next_attempt IS NULL OR q.next_attempt <= ?) ORDER BY q.id ASC LIMIT 1""",
                (utcnow(),),
            ).fetchone()
            if not row:
                return None
            cur = conn.execute(
                """UPDATE download_queue SET status='processing', worker_id=?, locked_until=?, attempts=attempts+1 WHERE id=? AND status='queued'""",
                (self.worker_id, until, row["qid"]),
            )
            if cur.rowcount != 1:
                return None
            conn.execute("UPDATE documents SET download_status='downloading' WHERE id=?", (row["id"],))
            return dict(row)

    def release_expired(self) -> int:
        now = utcnow()
        self.db.execute(
            """UPDATE documents SET download_status='queued' WHERE download_status='downloading'
               AND id IN (SELECT document_id FROM download_queue WHERE status='processing' AND locked_until < ?)""",
            (now,),
        )
        cur = self.db.execute(
            """UPDATE download_queue SET status='queued', worker_id=NULL, locked_until=NULL
               WHERE status='processing' AND locked_until IS NOT NULL AND locked_until < ?""",
            (now,),
        )
        return cur.rowcount

    def process_one(self) -> bool:
        job = self.acquire()
        if not job:
            return False
        url = job["canonical_url"] or job["pdf_url"]
        domain = job["domain"] or domain_of(url)
        try:
            dest, digest, length, etag, last_mod, status = self._download(url, job, domain)
            self.db.execute(
                """UPDATE documents SET download_status='complete', download_path=?, sha256=?, content_length=?, etag=?, last_modified=?, http_status=?, error=NULL WHERE id=?""",
                (str(dest), digest, length, etag, last_mod, status, job["id"]),
            )
            self.db.execute("UPDATE download_queue SET status='completed', worker_id=NULL, locked_until=NULL WHERE document_id=?", (job["id"],))
            if self.on_progress:
                self.on_progress(1)
            return True
        except Exception as exc:
            log.info("download error %s %s", url, exc)
            attempts = int(job.get("attempts") or 1)
            if attempts >= self.retries:
                self.db.execute("UPDATE documents SET download_status='failed', error=?, http_status=? WHERE id=?", (str(exc)[:500], getattr(exc, "status_code", None), job["id"]))
                self.db.execute("UPDATE download_queue SET status='failed', worker_id=NULL, locked_until=NULL WHERE document_id=?", (job["id"],))
            else:
                wait = backoff_seconds(attempts)
                nxt = (datetime.now(timezone.utc) + timedelta(seconds=wait)).isoformat()
                self.db.execute("UPDATE documents SET download_status='queued', error=? WHERE id=?", (str(exc)[:500], job["id"]))
                self.db.execute("UPDATE download_queue SET status='queued', next_attempt=?, worker_id=NULL, locked_until=NULL WHERE document_id=?", (nxt, job["id"]))
            if self.on_progress:
                self.on_progress(1)
            return True

    def _download(self, url: str, job: dict, domain: str):
        tmp = self.temp / f"{job['id']}.pdf.part"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        offset = existing_size(tmp)
        headers = {}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        self.limiter.acquire(domain)
        try:
            resp = self.session.get(url, timeout=self.timeout, stream=True, headers=headers)
        finally:
            self.limiter.release(domain)
        if resp.status_code in {429, 503, 403}:
            err = RuntimeError(f"http {resp.status_code}")
            err.status_code = resp.status_code
            raise err
        if offset and resp.status_code == 200:
            offset = 0
            tmp.unlink(missing_ok=True)
        if offset and resp.status_code not in {206, 200}:
            offset = 0
            tmp.unlink(missing_ok=True)
            self.limiter.acquire(domain)
            try:
                resp = self.session.get(url, timeout=self.timeout, stream=True)
            finally:
                self.limiter.release(domain)
        resp.raise_for_status()
        mode = "ab" if offset and resp.status_code == 206 else "wb"
        first = True
        with tmp.open(mode) as fh:
            for chunk in resp.iter_content(self.chunk_size):
                if not chunk:
                    continue
                if first and mode == "wb" and chunk.lstrip()[:15].lower().startswith((b"<!doctype", b"<html")):
                    raise RuntimeError("response is html, not pdf")
                first = False
                fh.write(chunk)
        digest = sha256_file(tmp)
        length = tmp.stat().st_size
        dest = self._no_clobber(self._final_path(job, digest), digest)
        atomic_replace(tmp, dest)
        return dest, digest, length, resp.headers.get("ETag"), resp.headers.get("Last-Modified"), resp.status_code

    def _final_path(self, job: dict, digest: str) -> Path:
        if self.layout == "content_addressed":
            return content_addressed_path(self.root, digest)
        name = job.get("filename") or filename_from_url(job.get("canonical_url") or "")
        state = (job.get("state") or "unknown").replace(" ", "_")
        return self.root / state / name

    def _no_clobber(self, dest: Path, digest: str) -> Path:
        if not dest.exists():
            return dest
        try:
            existing = sha256_file(dest)
        except OSError:
            existing = ""
        if existing == digest:
            return dest
        idx = 2
        while True:
            alt = collision_name(dest, idx)
            if not alt.exists():
                return alt
            try:
                if sha256_file(alt) == digest:
                    return alt
            except OSError:
                pass
            idx += 1
