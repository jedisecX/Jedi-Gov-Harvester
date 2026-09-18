from __future__ import annotations
from urllib.parse import urlparse

PDF_MAGIC = b"%PDF-"

def url_looks_like_pdf(url: str) -> bool:
    path = (urlparse(url).path or "").lower()
    return path.endswith(".pdf")

def content_type_is_pdf(content_type: str | None) -> bool:
    if not content_type:
        return False
    return "application/pdf" in content_type.lower()

def magic_is_pdf(header: bytes) -> bool:
    if not header:
        return False
    return header.lstrip().startswith(PDF_MAGIC)

def classify_content_type(content_type: str | None, url: str = "") -> str:
    ct = (content_type or "").lower()
    if "application/pdf" in ct or url_looks_like_pdf(url):
        return "pdf"
    if "text/html" in ct or ct.startswith("text/"):
        return "html"
    if ct.startswith("image/"):
        return "image"
    if any(x in ct for x in ("msword", "officedocument", "spreadsheet", "rtf")):
        return "document"
    if any(x in ct for x in ("zip", "gzip", "tar", "x-7z", "x-rar")):
        return "archive"
    if ct.startswith("application/octet-stream"):
        return "binary"
    if not ct:
        return "unknown"
    return "binary"

def is_pdf(url: str, content_type: str | None = None, header: bytes | None = None) -> bool:
    if header is not None and magic_is_pdf(header):
        return True
    if content_type_is_pdf(content_type):
        return True
    return url_looks_like_pdf(url)
