from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup


def extract_links(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html or "", "lxml")
    found: list[str] = []
    for tag in soup.find_all("a", href=True):
        href = tag.get("href", "").strip()
        if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
            continue
        found.append(urljoin(base_url, href))
    for tag in soup.find_all(["embed", "iframe", "object"], src=True):
        src = tag.get("src", "").strip()
        if src:
            found.append(urljoin(base_url, src))
    return found
