from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from harvester.headers import HeaderRotator


class RotatingSession(requests.Session):
    def __init__(self, rotator: HeaderRotator):
        super().__init__()
        self.rotator = rotator

    def prepare_request(self, request):
        prepared = super().prepare_request(request)
        rotated = self.rotator.next()
        for key, value in rotated.items():
            if key not in request.headers:
                prepared.headers[key] = value
        return prepared


def build_session(user_agent: str, *, rotate: bool = True, user_agents: list[str] | None = None) -> requests.Session:
    agents = list(user_agents or [])
    if user_agent and user_agent not in agents:
        agents = [user_agent, *agents]
    rotator = HeaderRotator(agents or None, enabled=rotate)
    session = RotatingSession(rotator)
    session.headers.update(rotator.next())
    retry = Retry(
        total=2,
        backoff_factor=0.5,
        status_forcelist=(502, 504),
        allowed_methods=("GET", "HEAD"),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=32, pool_maxsize=32)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session
