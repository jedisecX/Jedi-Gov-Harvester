from harvester.search.base import SearchError, SearchProvider, SearchResult
from harvester.search.yahoo import YahooSearchProvider

PROVIDERS = {"yahoo": YahooSearchProvider}


def get_provider(name: str, session, **kwargs) -> SearchProvider:
    cls = PROVIDERS.get((name or "yahoo").lower())
    if cls is None:
        raise ValueError(f"unknown search provider: {name}")
    return cls(session, **kwargs)


__all__ = ["SearchError", "SearchProvider", "SearchResult", "YahooSearchProvider", "get_provider"]
