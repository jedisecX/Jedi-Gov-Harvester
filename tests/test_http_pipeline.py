from __future__ import annotations
import hashlib
from pathlib import Path
from harvester.crawler.crawler import Crawler
from harvester.crawler.robots import RobotsCache
from harvester.discovery import Discovery
from harvester.downloader.hashing import sha256_file
from harvester.downloader.worker import DownloadWorker
from harvester.pdf.indexer import PdfIndexer
from harvester.search.base import SearchProvider, SearchResult
from harvester.search.yahoo import parse_yahoo_results, unwrap_yahoo_url
from tests.local_server import make_server, send

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n%%EOF\n"

def test_crawler_depth_and_pdf_index(tmp_env):
    def robots(h): send(h, 200, b"User-agent: *\nAllow: /\n", {"Content-Type": "text/plain"})
    def home(h): send(h, 200, b'<a href="/next">n</a><a href="/doc.pdf">p</a>', {"Content-Type": "text/html"})
    def nxt(h): send(h, 200, b'<a href="/deep">d</a>', {"Content-Type": "text/html"})
    def pdf(h): send(h, 200, PDF, {"Content-Type": "application/pdf"})
    srv = make_server({"/robots.txt": robots, "/": home, "/next": nxt, "/doc.pdf": pdf})
    try:
        tmp_env["policy"].allow_host("127.0.0.1")
        crawler = Crawler(tmp_env["db"], tmp_env["session"], tmp_env["policy"], tmp_env["limiter"], max_depth=1, timeout=5)
        crawler.enqueue(srv.base + "/", depth=0)
        crawler.run()
        docs = tmp_env["db"].fetchall("SELECT * FROM documents")
        assert any("doc.pdf" in r["canonical_url"] for r in docs)
    finally:
        srv.shutdown()

def test_robots_deny(tmp_env):
    srv = make_server({"/robots.txt": lambda h: send(h, 200, b"User-agent: *\nDisallow: /\n", {"Content-Type": "text/plain"})})
    try:
        cache = RobotsCache(tmp_env["db"], "GovernmentPDFHarvester-Test/1.0", tmp_env["session"].get)
        assert cache.allowed(srv.base + "/secret.pdf") is False
    finally:
        srv.shutdown()

def test_download_range_resume_and_hash(tmp_env):
    body = PDF * 50
    digest = hashlib.sha256(body).hexdigest()
    def big(h):
        rng = h.headers.get("Range")
        if rng and rng.startswith("bytes="):
            start = int(rng.split("=", 1)[1].split("-", 1)[0] or 0)
            send(h, 206, body[start:], {"Content-Type": "application/pdf", "Content-Range": f"bytes {start}-{len(body)-1}/{len(body)}"})
            return
        send(h, 200, body, {"Content-Type": "application/pdf"})
    srv = make_server({"/big.pdf": big})
    try:
        url = srv.base + "/big.pdf"
        doc_id = PdfIndexer(tmp_env["db"]).record(url, state="Test")
        worker = DownloadWorker(tmp_env["db"], tmp_env["session"], tmp_env["limiter"], tmp_env["root"], tmp_env["temp"], worker_id="t1")
        (tmp_env["temp"] / f"{doc_id}.pdf.part").write_bytes(body[:40])
        assert worker.process_one()
        row = tmp_env["db"].fetchone("SELECT * FROM documents WHERE id=?", (doc_id,))
        assert row["download_status"] == "complete"
        assert row["sha256"] == digest
        assert sha256_file(row["download_path"]) == digest
    finally:
        srv.shutdown()

def test_no_range_restart(tmp_env):
    body = PDF * 10
    srv = make_server({"/nr.pdf": lambda h: send(h, 200, body, {"Content-Type": "application/pdf"})})
    try:
        doc_id = PdfIndexer(tmp_env["db"]).record(srv.base + "/nr.pdf")
        (tmp_env["temp"] / f"{doc_id}.pdf.part").write_bytes(b"stale")
        worker = DownloadWorker(tmp_env["db"], tmp_env["session"], tmp_env["limiter"], tmp_env["root"], tmp_env["temp"])
        assert worker.process_one()
        row = tmp_env["db"].fetchone("SELECT * FROM documents WHERE id=?", (doc_id,))
        assert Path(row["download_path"]).read_bytes() == body
    finally:
        srv.shutdown()

def test_lease_expiration(tmp_env):
    PdfIndexer(tmp_env["db"]).record("https://example.gov/x.pdf")
    tmp_env["db"].execute("UPDATE download_queue SET status='processing', locked_until='2000-01-01T00:00:00+00:00'")
    tmp_env["db"].execute("UPDATE documents SET download_status='downloading'")
    from harvester.downloader.worker import DownloadWorker
    n = DownloadWorker(tmp_env["db"], tmp_env["session"], tmp_env["limiter"], tmp_env["root"], tmp_env["temp"]).release_expired()
    assert n >= 1
    assert tmp_env["db"].fetchone("SELECT status FROM download_queue")["status"] == "queued"

def test_http_429_backoff(tmp_env):
    srv = make_server({"/robots.txt": lambda h: send(h, 200, b"User-agent: *\nAllow: /\n", {"Content-Type": "text/plain"}), "/r": lambda h: send(h, 429, b"no", {"Retry-After": "1", "Content-Type": "text/plain"})})
    try:
        tmp_env["policy"].allow_host("127.0.0.1")
        crawler = Crawler(tmp_env["db"], tmp_env["session"], tmp_env["policy"], tmp_env["limiter"], timeout=5)
        crawler.enqueue(srv.base + "/r")
        crawler.process_one()
        row = tmp_env["db"].fetchone("SELECT status, next_attempt FROM crawl_queue")
        assert row["status"] == "queued" and row["next_attempt"]
    finally:
        srv.shutdown()

class FakeSearch(SearchProvider):
    name = "yahoo"
    def search(self, query, page):
        return [SearchResult("a", "https://example.gov/a.pdf" if page == 1 else "https://example.gov/b.pdf")]

def test_search_pagination_resume(tmp_env):
    tmp_env["policy"].allow_host("example.gov")
    disc = Discovery(tmp_env["db"], FakeSearch(), tmp_env["policy"], pages_per_query=2)
    tmp_env["db"].execute("INSERT INTO agencies (state, agency_name, agency_type, official_url, domain, source, active) VALUES (?,?,?,?,?,?,1)", ("Texas", "Portal", "portal", "https://example.gov", "example.gov", "t"))
    assert disc.plan(state="Texas") >= 2
    assert disc.run_one() and disc.run_one()
    assert len(tmp_env["db"].fetchall("SELECT canonical_url FROM documents")) == 2

def test_yahoo_parser_unwrap():
    dest = unwrap_yahoo_url("https://r.search.yahoo.com/path?RU=https%3A%2F%2Ftea.texas.gov%2Fx.pdf")
    assert dest.endswith("tea.texas.gov/x.pdf")
    parsed = parse_yahoo_results('<h3><a href="https://tea.texas.gov/budget.pdf">Budget</a></h3>')
    assert any("budget.pdf" in r.url for r in parsed)
