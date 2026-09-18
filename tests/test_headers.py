import requests
from harvester.headers import HeaderRotator
from harvester.http_client import build_session


def test_rotator_changes_ua():
    rot = HeaderRotator(enabled=True)
    seen = {rot.next()["User-Agent"] for _ in range(12)}
    assert len(seen) > 1
    assert all("GovernmentPDFHarvester" in ua for ua in seen)


def test_session_rotates_without_clobbering_range():
    session = build_session("GovernmentPDFHarvester-Test/1.0", rotate=True)
    prepared = session.prepare_request(
        requests.Request("GET", "https://example.gov/x.pdf", headers={"Range": "bytes=10-"})
    )
    assert prepared.headers.get("Range") == "bytes=10-"
    assert "User-Agent" in prepared.headers
    assert "GovernmentPDFHarvester" in prepared.headers.get("User-Agent", "")
