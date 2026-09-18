from __future__ import annotations
import logging, signal, threading
from pathlib import Path
from harvester.database import Database
from harvester.downloader.worker import DownloadWorker
from harvester.rate_limit import DomainLimiter
log = logging.getLogger("download")

class DownloadManager:
    def __init__(self, db: Database, session, limiter: DomainLimiter, storage_root: Path, storage_temp: Path, *, workers: int = 16, timeout: int = 60, retries: int = 5, chunk_size: int = 1048576, layout: str = "content_addressed"):
        self.db = db
        self.session = session
        self.limiter = limiter
        self.storage_root = Path(storage_root)
        self.storage_temp = Path(storage_temp)
        self.workers_n = max(1, int(workers))
        self.timeout = timeout
        self.retries = retries
        self.chunk_size = chunk_size
        self.layout = layout
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        DownloadWorker(self.db, self.session, self.limiter, self.storage_root, self.storage_temp, timeout=self.timeout, retries=self.retries, chunk_size=self.chunk_size, layout=self.layout, worker_id="dl-main").release_expired()
        threads = []
        def loop(wid: str) -> None:
            w = DownloadWorker(self.db, self.session, self.limiter, self.storage_root, self.storage_temp, timeout=self.timeout, retries=self.retries, chunk_size=self.chunk_size, layout=self.layout, worker_id=wid)
            while not self._stop.is_set():
                if not w.process_one():
                    break
        def handle_stop(*_args) -> None:
            self.stop()
        signal.signal(signal.SIGINT, handle_stop)
        signal.signal(signal.SIGTERM, handle_stop)
        for i in range(self.workers_n):
            t = threading.Thread(target=loop, args=(f"dl-{i}",), daemon=True)
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
