# Jedi Gov Harvester

Resumable harvester for publicly accessible PDF documents from U.S. state government agencies.

SQLite is the source of truth. The filesystem stores downloaded PDFs. CSV/JSON are export formats only.

## Pipeline

```
                 ┌──────────────────┐
                 │  Search Scheduler │
                 └────────┬─────────┘
                          │
                    one page/request
                          │
                 ┌────────▼─────────┐
                 │ Search Provider    │  (yahoo, replaceable)
                 └────────┬─────────┘
                          │
              ┌──────────▼───────────┐
              │ Persistent Search DB  │
              └──────────┬───────────┘
                          │
                 ┌────────▼─────────┐
                 │ Government URL/PDF │
                 └────────────────────┘
```

Search does **not** try to evade Yahoo anti-bot. It requests one page, persists state, caches results, honors 429/403/503 + Retry-After, then stops if Yahoo refuses automated access.

HTTP layer rotates `User-Agent` / `Accept` / `Accept-Language` on every request. Every UA still identifies as `GovernmentPDFHarvester`. Explicit headers such as `Range` are never overwritten.

CLI commands show tqdm bars for discover, crawl, download, and verify.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
python harvester.py seed
python harvester.py discover --state Louisiana
python harvester.py crawl --agency "Department of Transportation"
python harvester.py download --workers 16
python harvester.py export --format csv --output pdf_index.csv
python harvester.py resume
python harvester.py status
python harvester.py verify
```

Downloads write `*.part` files, send HTTP Range requests when possible, hash with SHA-256, and never overwrite a different existing file.

## Config

See `config.yaml`. Set `network.rotate_headers: false` to pin a single UA.

## Tests

```bash
pytest -q
```

## Respect

Honors robots.txt, HTTP 429/503 Retry-After, per-domain rate limits, and search-engine terms. Public documents only.
