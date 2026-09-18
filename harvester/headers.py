from __future__ import annotations

import itertools
import random
import threading
from typing import Iterable

DEFAULT_USER_AGENTS = [
    "GovernmentPDFHarvester/1.0 (+https://github.com/jedisecX/Jedi-Gov-Harvester)",
    "GovernmentPDFHarvester/1.0 (research; +https://github.com/jedisecX/Jedi-Gov-Harvester)",
    "Mozilla/5.0 (compatible; GovernmentPDFHarvester/1.0; +https://github.com/jedisecX/Jedi-Gov-Harvester)",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 GovernmentPDFHarvester/1.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 GovernmentPDFHarvester/1.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15 GovernmentPDFHarvester/1.0",
]

ACCEPTS = [
    "text/html,application/xhtml+xml,application/pdf,*/*;q=0.8",
    "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf;q=0.8,*/*;q=0.7",
    "application/pdf,text/html;q=0.9,*/*;q=0.8",
]

LANGUAGES = [
    "en-US,en;q=0.9",
    "en-US,en;q=0.8",
    "en;q=0.9,en-US;q=0.8",
]


class HeaderRotator:
    """Round-robin + jittered Accept/UA sets. Every UA still names this harvester."""

    def __init__(self, user_agents: Iterable[str] | None = None, enabled: bool = True):
        agents = [a.strip() for a in (user_agents or DEFAULT_USER_AGENTS) if a and str(a).strip()]
        self.agents = agents or list(DEFAULT_USER_AGENTS)
        self.enabled = enabled
        self._lock = threading.Lock()
        self._cycle = itertools.cycle(self.agents)

    def next(self) -> dict[str, str]:
        if not self.enabled:
            return {
                "User-Agent": self.agents[0],
                "Accept": ACCEPTS[0],
                "Accept-Language": LANGUAGES[0],
            }
        with self._lock:
            ua = next(self._cycle)
        return {
            "User-Agent": ua,
            "Accept": random.choice(ACCEPTS),
            "Accept-Language": random.choice(LANGUAGES),
            "Cache-Control": random.choice(["no-cache", "max-age=0"]),
            "DNT": "1",
        }
