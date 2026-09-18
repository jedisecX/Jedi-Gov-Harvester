from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from harvester.headers import HeaderRotator
from harvester.proxy import proxy_map


class RotatingSession(requests.Session):
    def __init__(self, rotator: HeaderRotator, pool=None):
        super().__init__()
        self.rotator = rotator
        self.pool = pool

    def prepare_request(self, request):
        prepared = super().prepare_request(request)
        rotated = self.rotator.next()
        for key, value in rotated.items():
            if key not in request.headers:
                prepared.headers[key] = value
        return prepared

    def send(self, request, **kwargs):
        if self.pool is not None:
            chosen = self.pool.next_map()
            if chosen:
                kwargs["proxies"] = chosen
                request.headers["X-Harvester-Proxy"] = next(iter(chosen.values()))
        try:
            resp = super().send(request, **kwargs)
        except Exception as exc:
            if self.pool is not None:
                used = (kwargs.get("proxies") or {}).get("https") or (kwargs.get("proxies") or {}).get("http")
                if used:
                    self.pool.mark(used, False, str(exc))
            raise
        if self.pool is not None:
            used = (kwargs.get("proxies") or {}).get("https") or (kwargs.get("proxies") or {}).get("http")
            if used:
                self.pool.mark(used, resp.status_code < 500, f"http {resp.status_code}")
        return resp


def build_session(
    user_agent: str,
    *,
    rotate: bool = True,
    user_agents: list[str] | None = None,
    proxy: str | dict | None = None,
    pool=None,
) -> requests.Session:
    agents = list(user_agents or [])
    if user_agent and user_agent not in agents:
        agents = [user_agent, *agents]
    rotator = HeaderRotator(agents or None, enabled=rotate)
    session = RotatingSession(rotator, pool=pool)
    session.headers.update(rotator.next())
    proxies = proxy_map(proxy)
    if proxies and pool is None:
        session.proxies.update(proxies)
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
