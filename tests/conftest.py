from __future__ import annotations
from pathlib import Path
import pytest, yaml
from harvester.database import Database
from harvester.domain_policy import DomainPolicy
from harvester.http_client import build_session
from harvester.rate_limit import DomainLimiter

@pytest.fixture()
def tmp_env(tmp_path: Path):
    db = Database(tmp_path / "h.sqlite")
    root = tmp_path / "pdfs"
    temp = tmp_path / "partials"
    root.mkdir(); temp.mkdir()
    policy = DomainPolicy(["*.gov", "*.example.local", "localhost", "127.0.0.1"], ["*.facebook.com"])
    return {"db": db, "root": root, "temp": temp, "policy": policy, "session": build_session("GovernmentPDFHarvester-Test/1.0"), "limiter": DomainLimiter(rps=100, concurrent=4), "path": tmp_path}
