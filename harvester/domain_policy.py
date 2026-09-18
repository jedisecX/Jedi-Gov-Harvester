from __future__ import annotations

import fnmatch
from urllib.parse import urlparse


def _host(value: str) -> str:
    raw = (value or "").strip().lower()
    if "://" in raw:
        raw = urlparse(raw).hostname or ""
    return raw.rstrip(".")


def _match(host: str, pattern: str) -> bool:
    pat = pattern.strip().lower()
    if pat.startswith("*."):
        suffix = pat[1:]
        if host.endswith(suffix):
            return True
        return fnmatch.fnmatch(host, pat)
    if "*" in pat:
        return fnmatch.fnmatch(host, pat)
    return host == pat or host.endswith("." + pat)


class DomainPolicy:
    def __init__(self, allowed=None, denied=None, extra_allowed_hosts=None):
        self.allowed = allowed or ["*.gov"]
        self.denied = denied or []
        self.extra = {_host(h) for h in (extra_allowed_hosts or []) if h}

    def allow_host(self, host: str) -> None:
        h = _host(host)
        if h:
            self.extra.add(h)

    def is_allowed(self, url_or_host: str) -> bool:
        host = _host(url_or_host)
        if not host:
            return False
        if any(_match(host, p) for p in self.denied):
            return False
        if host in self.extra or any(host.endswith("." + e) for e in self.extra):
            return True
        return any(_match(host, p) for p in self.allowed)
