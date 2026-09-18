from harvester.http_client import build_session
from harvester.proxy import proxy_map, proxy_url


def test_socks_url_defaults_to_remote_dns():
    assert proxy_url({"scheme": "socks5", "host": "127.0.0.1", "port": 9050}) == "socks5h://127.0.0.1:9050"
    assert proxy_url("socks5h://127.0.0.1:1080") == "socks5h://127.0.0.1:1080"


def test_session_gets_proxy_map():
    session = build_session("GovernmentPDFHarvester-Test/1.0", rotate=False, proxy="socks5h://127.0.0.1:9050")
    assert session.proxies["https"] == "socks5h://127.0.0.1:9050"
    assert proxy_map(None) is None
