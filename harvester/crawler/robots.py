from __future__ import annotations

from io import StringIO
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from harvester.database import Database, utcnow


class RobotsCache:
    def __init__(self, db: Database, user_agent: str, fetcher):
        self.db = db
        self.user_agent = user_agent
        self.fetcher = fetcher
        self._parsers: dict[str, RobotFileParser] = {}

    def allowed(self, url: str) -> bool:
        host = (urlparse(url).hostname or "").lower()
        if not host:
            return False
        parser = self._load(host, url)
        try:
            return parser.can_fetch(self.user_agent, url)
        except Exception:
            return True

    def _load(self, host: str, sample_url: str) -> RobotFileParser:
        if host in self._parsers:
            return self._parsers[host]
        row = self.db.fetchone("SELECT body, status FROM robots_cache WHERE domain=?", (host,))
        body = row["body"] if row else None
        if row is None:
            parsed = urlparse(sample_url)
            scheme = parsed.scheme or "https"
            netloc = parsed.netloc or host
            robots_url = f"{scheme}://{netloc}/robots.txt"
            try:
                resp = self.fetcher(robots_url)
                status = getattr(resp, "status_code", 0)
                text = resp.text if status == 200 else ""
            except Exception:
                status = 0
                text = ""
            self.db.execute(
                "INSERT OR REPLACE INTO robots_cache (domain, body, fetched_at, status) VALUES (?,?,?,?)",
                (host, text, utcnow(), status),
            )
            body = text
        rp = RobotFileParser()
        rp.parse(StringIO(body or "").read().splitlines())
        self._parsers[host] = rp
        return rp
