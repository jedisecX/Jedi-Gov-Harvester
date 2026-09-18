"""Lightweight row helpers. SQLite schema is the source of truth."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Agency:
    state: str
    agency_name: str
    agency_type: str
    official_url: str
    domain: str
    source: str = "seed"
    active: bool = True
    last_verified: str | None = None


@dataclass
class Document:
    pdf_url: str
    canonical_url: str
    filename: str | None = None
    domain: str | None = None
    state: str | None = None
    agency: str | None = None
    sha256: str | None = None
    download_status: str = "queued"
