from __future__ import annotations
from dataclasses import dataclass

@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ""

class SearchProvider:
    name = "base"
    def search(self, query: str, page: int) -> list[SearchResult]:
        raise NotImplementedError
