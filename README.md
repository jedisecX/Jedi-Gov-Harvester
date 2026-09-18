# Jedi Gov Harvester

Resumable harvester for publicly accessible PDF documents from U.S. state government agencies.

SQLite is the source of truth. The filesystem stores downloaded PDFs. CSV/JSON are export formats only.

## Pipeline

```
GOVERNMENT SEEDS → SEARCH/DISCOVERY → URL INDEX → DOMAIN FILTER
      → CRAWLER → PDF INDEX → CSV EXPORT → DOWNLOAD QUEUE
      → MULTITHREADED FETCH → RESUME + VERIFY → NO-CLOBBER → LOCAL ARCHIVE
```

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

Discovery uses Yahoo one results page at a time and stores page state so a crash on page 7 resumes on page 7.

Downloads write `*.part` files, send HTTP Range requests when possible, hash with SHA-256, and never overwrite a different existing file.

## Seeds

`seeds/agencies.json` covers all 50 states: official portals, governors, secretaries of state, legislatures, plus a set of documented agency homepages.

Rebuild:

```bash
python seeds/build_seeds.py
```

Do not invent agency URLs. Add verified official URLs only.

## Config

See `config.yaml` for domain allow/deny lists, crawl limits, rate limits, and storage layout (`content_addressed` or `flat`).

## Tests

```bash
pytest -q
```

Integration tests use a local HTTP server. They do not hit live government sites.

## Respect

Honors robots.txt, HTTP 429/503 Retry-After, per-domain rate limits, and search-engine terms. Public documents only.
