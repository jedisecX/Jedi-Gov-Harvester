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
                 ┌────────▼─────────┐
                 │ Result Normalizer │
                 └────────┬─────────┘
                          │
              ┌──────────▼───────────┐
              │ Persistent Search DB  │
              └──────────┬───────────┘
                          │
                 ┌────────▼─────────┐
                 │ Government URL     │
                 │ PDF Discovery      │
                 └────────────────────┘
```

Search does **not** try to evade Yahoo anti-bot. It:

- requests exactly one results page
- persists query/page state in SQLite
- caches seen results
- honors 429 / 403 / 503 and `Retry-After`
- exponential backoff, then stops (`blocked`) if Yahoo refuses automated access
- is provider-replaceable via `search.provider` in `config.yaml`

If page 1 succeeds and page 2 rate-limits, page 1 stays `completed` and page 2 waits.

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

## Seeds

`seeds/agencies.json` covers all 50 states: official portals, governors, secretaries of state, legislatures, plus documented agency homepages.

Do not invent agency URLs. Add verified official URLs only.

## Config

See `config.yaml`.

## Tests

```bash
pytest -q
```

## Respect

Honors robots.txt, HTTP 429/503 Retry-After, per-domain rate limits, and search-engine terms. Public documents only.
