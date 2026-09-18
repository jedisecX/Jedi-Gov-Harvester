from __future__ import annotations
import logging, time
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
import requests
from bs4 import BeautifulSoup
from harvester.search.base import SearchProvider, SearchResult
log = logging.getLogger("search")
YAHOO_SEARCH = "https://search.yahoo.com/search"

class YahooSearchProvider(SearchProvider):
    name = "yahoo"
    def __init__(self, session: requests.Session, delay: float = 2.0, timeout: int = 30):
        self.session = session
        self.delay = delay
        self.timeout = timeout
    def search(self, query: str, page: int) -> list[SearchResult]:
        offset = 1 + max(0, page - 1) * 10
        url = f"{YAHOO_SEARCH}?p={quote_plus(query)}&b={offset}&pz=10"
        log.info("yahoo search page=%s query=%s", page, query[:120])
        resp = self.session.get(url, timeout=self.timeout)
        if resp.status_code in {429, 503, 403}:
            raise RuntimeError(f"yahoo http {resp.status_code}")
        resp.raise_for_status()
        if self.delay:
            time.sleep(self.delay)
        return parse_yahoo_results(resp.text)

def unwrap_yahoo_url(href: str) -> str:
    if not href:
        return ""
    parsed = urlparse(href)
    qs = parse_qs(parsed.query)
    for key in ("RU", "u", "url"):
        if key in qs and qs[key]:
            return unquote(qs[key][0])
    path = parsed.path or ""
    if "/RU=" in path:
        return unquote(path.split("/RU=", 1)[1].split("/RK=", 1)[0])
    return href

def parse_yahoo_results(html: str) -> list[SearchResult]:
    soup = BeautifulSoup(html or "", "lxml")
    results = []
    seen = set()
    anchors = soup.select("h3 a, .algo-sr h3 a, #web a[href], ol.searchCenterMiddle a") or soup.find_all("a", href=True)
    for a in anchors:
        href = a.get("href") or ""
        if "yahoo.com" in urlparse(href).netloc and "/search" in href:
            continue
        dest = unwrap_yahoo_url(href)
        if not dest.startswith("http"):
            continue
        host = urlparse(dest).hostname or ""
        if host.endswith("yahoo.com") or host.endswith("yimg.com"):
            continue
        if dest in seen:
            continue
        seen.add(dest)
        results.append(SearchResult(title=a.get_text(" ", strip=True)[:300], url=dest))
    return results
