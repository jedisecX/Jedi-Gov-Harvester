from __future__ import annotations
from pathlib import Path
import click
from harvester import __version__
from harvester.agencies import load_seed_file, upsert_agencies
from harvester.config import Config
from harvester.crawler.crawler import Crawler
from harvester.database import Database
from harvester.discovery import Discovery
from harvester.domain_policy import DomainPolicy
from harvester.downloader.manager import DownloadManager
from harvester.export.csv import export_csv
from harvester.export.json import export_json, export_jsonl
from harvester.http_client import build_session
from harvester.logging_setup import setup_logging
from harvester.monitoring.dashboard import render_status
from harvester.rate_limit import DomainLimiter
from harvester.search import get_provider

def _boot(ctx):
    setup_logging()
    cfg = Config.load(ctx.obj.get("config"))
    db = Database(cfg.database_path)
    return cfg, db

def _policy(cfg, db):
    extras = [r["domain"] for r in db.fetchall("SELECT DISTINCT domain FROM agencies")]
    return DomainPolicy(cfg.allowed_domains, cfg.denied_domains, extras)

def _session(cfg):
    agents = cfg.get("network.user_agents") or []
    return build_session(
        cfg.user_agent,
        rotate=bool(cfg.get("network.rotate_headers", True)),
        user_agents=list(agents) if agents else None,
    )

def _limiter(cfg):
    return DomainLimiter(rps=float(cfg.get("rate_limit.requests_per_second", 2)), concurrent=int(cfg.get("rate_limit.concurrent_per_domain", 2)))

def _search_provider(cfg, session):
    return get_provider(
        str(cfg.get("search.provider", "yahoo")),
        session,
        delay=float(cfg.get("search.delay_seconds", 2)),
        timeout=int(cfg.get("network.timeout", 30)),
    )

@click.group()
@click.option("--config", default="config.yaml", show_default=True)
@click.version_option(__version__)
@click.pass_context
def main(ctx, config):
    ctx.ensure_object(dict)
    ctx.obj["config"] = config

@main.command()
@click.option("--file", "seed_file", default=None)
@click.pass_context
def seed(ctx, seed_file):
    cfg, db = _boot(ctx)
    path = seed_file or cfg.get("seeds.path", "seeds/agencies.json")
    n = upsert_agencies(db, load_seed_file(path))
    click.echo(f"seeded {n} agencies from {path}")

@main.command()
@click.option("--state", default=None)
@click.option("--agency", default=None)
@click.option("--max-pages", type=int, default=None)
@click.pass_context
def discover(ctx, state, agency, max_pages):
    cfg, db = _boot(ctx)
    session = _session(cfg)
    provider = _search_provider(cfg, session)
    disc = Discovery(db, provider, _policy(cfg, db), pages_per_query=int(cfg.get("search.pages_per_query", 10)))
    click.echo(f"planned {disc.plan(state=state, agency=agency)} search pages")
    click.echo(f"processed {disc.run(max_pages=max_pages)} search pages")

@main.command()
@click.option("--state", default=None)
@click.option("--agency", default=None)
@click.option("--max-jobs", type=int, default=None)
@click.pass_context
def crawl(ctx, state, agency, max_jobs):
    cfg, db = _boot(ctx)
    crawler = Crawler(db, _session(cfg), _policy(cfg, db), _limiter(cfg), max_depth=int(cfg.get("crawler.max_depth", 5)), max_pages_per_domain=int(cfg.get("crawler.max_pages_per_domain", 10000)), max_pdf_per_domain=int(cfg.get("crawler.max_pdf_count_per_domain", 100000)), timeout=int(cfg.get("network.timeout", 30)), user_agent=cfg.user_agent)
    click.echo(f"enqueued {crawler.seed_from_agencies(state=state, agency=agency)} agency URLs")
    click.echo(f"crawled {crawler.run(max_jobs=max_jobs)} pages")

@main.command("index")
@click.pass_context
def index_cmd(ctx):
    _, db = _boot(ctx)
    click.echo(render_status(db))

@main.command()
@click.option("--format", "fmt", type=click.Choice(["csv", "json", "jsonl"]), default="csv")
@click.option("--output", default=None)
@click.pass_context
def export(ctx, fmt, output):
    _, db = _boot(ctx)
    if output is None:
        output = {"csv": "pdf_index.csv", "json": "pdf_index.json", "jsonl": "pdf_index.jsonl"}[fmt]
    fn = {"csv": export_csv, "json": export_json, "jsonl": export_jsonl}[fmt]
    click.echo(f"exported {fn(db, output)} documents to {output}")

@main.command()
@click.option("--workers", type=int, default=None)
@click.pass_context
def download(ctx, workers):
    cfg, db = _boot(ctx)
    n = workers if workers is not None else int(cfg.get("download.workers", 16))
    mgr = DownloadManager(db, _session(cfg), _limiter(cfg), cfg.storage_root, cfg.storage_temp, workers=n, timeout=int(cfg.get("download.timeout", 60)), retries=int(cfg.get("download.retries", 5)), chunk_size=int(cfg.get("download.chunk_size", 1048576)), layout=str(cfg.get("storage.layout", "content_addressed")))
    click.echo(f"download workers={n}")
    mgr.run()

@main.command()
@click.pass_context
def resume(ctx):
    cfg, db = _boot(ctx)
    session = _session(cfg)
    policy = _policy(cfg, db)
    limiter = _limiter(cfg)
    crawler = Crawler(db, session, policy, limiter, user_agent=cfg.user_agent)
    from harvester.downloader.worker import DownloadWorker
    dw = DownloadWorker(db, session, limiter, cfg.storage_root, cfg.storage_temp)
    click.echo(f"released crawl={crawler.release_expired_leases()} download={dw.release_expired()}")
    disc = Discovery(db, _search_provider(cfg, session), policy, pages_per_query=int(cfg.get("search.pages_per_query", 10)))
    click.echo(f"resumed searches={disc.run()} crawl={crawler.run()}; start download separately if needed")

@main.command()
@click.pass_context
def status(ctx):
    cfg, db = _boot(ctx)
    click.echo(render_status(db, cfg.storage_root))

@main.command()
@click.pass_context
def verify(ctx):
    from harvester.downloader.hashing import sha256_file
    from harvester.progress import progress
    _, db = _boot(ctx)
    rows = db.fetchall("SELECT id, download_path, sha256 FROM documents WHERE download_status='complete'")
    ok = bad = missing = 0
    with progress(total=len(rows) or None, desc="verify", unit="file") as bar:
        for row in rows:
            path = Path(row["download_path"] or "")
            if not path.exists():
                missing += 1
            else:
                digest = sha256_file(path)
                if row["sha256"] and digest != row["sha256"]:
                    bad += 1
                else:
                    ok += 1
            bar.update(1)
    click.echo(f"verify ok={ok} mismatch={bad} missing={missing}")

if __name__ == "__main__":
    main()
