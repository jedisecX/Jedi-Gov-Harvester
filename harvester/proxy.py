from __future__ import annotations

import re
from urllib.parse import quote, urlparse

LINE_RE = re.compile(
    r"(?:(?P<scheme>socks5h?|socks4a?|https?)://)?(?:(?P<user>[^:@\s]+):(?P<pw>[^@\s]*)@)?(?P<host>[A-Za-z0-9._:-]+):(?P<port>\d{2,5})"
)


def proxy_url(raw: str | dict | None) -> str | None:
    if not raw:
        return None
    if isinstance(raw, str):
        raw = raw.strip()
        if not raw:
            return None
        parsed = parse_proxy_line(raw)
        return parsed or raw
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


def parse_proxy_line(line: str) -> str | None:
    text = (line or "").strip()
    if not text or text.startswith("#"):
        return None
    if "," in text and "//" not in text:
        parts = [p.strip() for p in text.split(",")]
        if len(parts) >= 2 and parts[1].isdigit():
            text = f"{parts[0]}:{parts[1]}"
    match = LINE_RE.search(text)
    if not match:
        return None
    scheme = (match.group("scheme") or "socks5h").lower()
    if scheme in {"socks5", "socks"}:
        scheme = "socks5h"
    elif scheme == "socks4":
        scheme = "socks4a"
    host = match.group("host")
    port = int(match.group("port"))
    if port < 1 or port > 65535:
        return None
    user, pw = match.group("user"), match.group("pw") or ""
    auth = f"{quote(user, safe='')}:{quote(pw, safe='')}@" if user else ""
    return f"{scheme}://{auth}{host}:{port}"


def parse_proxy_list(body: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for line in (body or "").splitlines():
        url = parse_proxy_line(line)
        if url and url not in seen:
            seen.add(url)
            out.append(url)
    return out


def proxy_map(raw: str | dict | None) -> dict[str, str] | None:
    url = proxy_url(raw)
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https", "socks4", "socks4a", "socks5", "socks5h"}:
        raise ValueError(f"unsupported proxy scheme: {parsed.scheme}")
    return {"http": url, "https": url}
