from __future__ import annotations
from dataclasses import dataclass


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ""


class SearchError(Exception):
    def __init__(self, message: str, *, status: int | None = None, retry_after: float | None = None, fatal: bool = False):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after
        self.fatal = fatal


class SearchProvider:
    name = "base"

    def search(self, query: str, page: int) -> list[SearchResult]:
        raise NotImplementedError
