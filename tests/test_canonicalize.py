from harvester.crawler.canonicalize import domain_of, normalize_url

def test_strips_fragment_and_default_port():
    assert normalize_url("https://example.gov:443/a/b/#frag") == "https://example.gov/a/b"

def test_drops_tracking_keeps_doc_query():
    assert normalize_url("https://example.gov/getfile?id=9&utm_source=x") == "https://example.gov/getfile?id=9"

def test_trailing_slash():
    assert normalize_url("https://example.gov/docs/") == "https://example.gov/docs"

def test_relative_join():
    assert normalize_url("/x.pdf", "https://dot.texas.gov/a") == "https://dot.texas.gov/x.pdf"

def test_domain_of():
    assert domain_of("https://WWW.TXDOT.GOV/a") == "www.txdot.gov"
