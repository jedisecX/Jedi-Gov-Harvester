from harvester.http_client import build_session
from harvester.proxy import parse_proxy_list, proxy_map, proxy_url
from harvester.proxy_pool import ProxyPool


def test_socks_url_defaults_to_remote_dns():
    assert proxy_url({"scheme": "socks5", "host": "127.0.0.1", "port": 9050}) == "socks5h://127.0.0.1:9050"
    assert proxy_url("socks5h://127.0.0.1:1080") == "socks5h://127.0.0.1:1080"


def test_parse_host_port_list():
    body = "1.2.3.4:1080\nsocks5://5.6.7.8:9050\n# comment\nbad\n9.9.9.9,1080"
    got = parse_proxy_list(body)
    assert "socks5h://1.2.3.4:1080" in got
    assert "socks5h://5.6.7.8:9050" in got
    assert "socks5h://9.9.9.9:1080" in got


def test_session_gets_proxy_map():
    session = build_session("GovernmentPDFHarvester-Test/1.0", rotate=False, proxy="socks5h://127.0.0.1:9050")
    assert session.proxies["https"] == "socks5h://127.0.0.1:9050"
    assert proxy_map(None) is None


def test_pool_round_robin(tmp_env):
    pool = ProxyPool(tmp_env["db"], list_urls=[])
    tmp_env["db"].execute(
        "INSERT INTO proxies (url, host_port, source, status) VALUES (?,?,?,?)",
        ("socks5h://1.1.1.1:1080", "1.1.1.1:1080", "t", "fresh"),
    )
    tmp_env["db"].execute(
        "INSERT INTO proxies (url, host_port, source, status) VALUES (?,?,?,?)",
        ("socks5h://2.2.2.2:1080", "2.2.2.2:1080", "t", "fresh"),
    )
    seen = {pool.next_url() for _ in range(4)}
    assert seen == {"socks5h://1.1.1.1:1080", "socks5h://2.2.2.2:1080"}
