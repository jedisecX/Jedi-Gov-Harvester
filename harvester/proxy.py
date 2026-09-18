from __future__ import annotations

from urllib.parse import quote, urlparse


def proxy_url(raw: str | dict | None) -> str | None:
    if not raw:
        return None
    if isinstance(raw, str):
        raw = raw.strip()
        return raw or None
    scheme = str(raw.get("scheme") or raw.get("type") or "socks5h").lower()
    if scheme in {"socks", "socks5"}:
        scheme = "socks5h"
    elif scheme == "socks4":
        scheme = "socks4a"
    host = raw.get("host") or raw.get("addr")
    if not host:
        return None
    port = raw.get("port") or 1080
    user = raw.get("username") or raw.get("user")
    password = raw.get("password") or raw.get("pass") or ""
    auth = ""
    if user:
        auth = f"{quote(str(user), safe='')}:{quote(str(password), safe='')}@"
    return f"{scheme}://{auth}{host}:{int(port)}"


def proxy_map(raw: str | dict | None) -> dict[str, str] | None:
    url = proxy_url(raw)
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https", "socks4", "socks4a", "socks5", "socks5h"}:
        raise ValueError(f"unsupported proxy scheme: {parsed.scheme}")
    return {"http": url, "https": url}
