from __future__ import annotations

import itertools
import logging
import threading
from datetime import datetime, timezone

import requests

from harvester.proxy import parse_proxy_list, proxy_map

log = logging.getLogger("proxy")

DEFAULT_LISTS = [
    "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks5.txt",
    "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProxyPool:
    def __init__(self, db, list_urls: list[str] | None = None, *, scheme_default: str = "socks5h"):
        self.db = db
        self.list_urls = [u for u in (list_urls or []) if u]
        self.scheme_default = scheme_default
        self._lock = threading.Lock()
        self._cycle = None

    def refresh(self, session: requests.Session | None = None, timeout: int = 20) -> int:
        sess = session or requests.Session()
        added = 0
        sources = self.list_urls or DEFAULT_LISTS
        for url in sources:
            try:
                resp = sess.get(url, timeout=timeout)
                resp.raise_for_status()
            except Exception as exc:
                log.info("proxy list fetch failed %s: %s", url, exc)
                continue
            for proxy in parse_proxy_list(resp.text):
                cur = self.db.execute(
                    """INSERT OR IGNORE INTO proxies (url, host_port, source, status, first_seen, last_seen)
                       VALUES (?, ?, ?, 'fresh', ?, ?)""",
                    (proxy, proxy.rsplit("@", 1)[-1], url, _now(), _now()),
                )
                added += cur.rowcount
        self._rebuild()
        log.info("proxy pool added=%s live=%s", added, self.live_count())
        return added

    def live(self) -> list[str]:
        rows = self.db.fetchall("SELECT url FROM proxies WHERE status IN ('fresh','ok') ORDER BY id")
        return [r["url"] for r in rows]

    def live_count(self) -> int:
        row = self.db.fetchone("SELECT COUNT(*) AS c FROM proxies WHERE status IN ('fresh','ok')")
        return int(row["c"]) if row else 0

    def _rebuild(self) -> None:
        urls = self.live()
        self._cycle = itertools.cycle(urls) if urls else None

    def next_url(self) -> str | None:
        with self._lock:
            if self._cycle is None:
                self._rebuild()
            if self._cycle is None:
                return None
            return next(self._cycle)

    def next_map(self) -> dict[str, str] | None:
        url = self.next_url()
        return proxy_map(url) if url else None

    def mark(self, url: str, ok: bool, error: str | None = None) -> None:
        status = "ok" if ok else "dead"
        self.db.execute(
            "UPDATE proxies SET status=?, last_seen=?, last_error=?, fail_count=fail_count+? WHERE url=?",
            (status, _now(), (error or "")[:300], 0 if ok else 1, url),
        )
        if not ok:
            self._rebuild()
