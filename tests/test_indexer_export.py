from pathlib import Path
from harvester.export.csv import export_csv
from harvester.export.json import export_json, export_jsonl
from harvester.pdf.indexer import PdfIndexer

def test_duplicate_urls_single_document(tmp_env):
    idx = PdfIndexer(tmp_env["db"])
    a = idx.record("https://tea.texas.gov/a.pdf", state="Texas", agency="TEA")
    b = idx.record("https://tea.texas.gov/a.pdf?utm_source=x", state="Texas", agency="TEA")
    assert a == b
    assert len(tmp_env["db"].fetchall("SELECT * FROM documents")) == 1

def test_export_formats(tmp_env, tmp_path: Path):
    PdfIndexer(tmp_env["db"]).record("https://example.gov/report.pdf", state="Texas", agency="Portal")
    assert export_csv(tmp_env["db"], tmp_path / "i.csv") == 1
    assert "report.pdf" in (tmp_path / "i.csv").read_text()
    assert export_json(tmp_env["db"], tmp_path / "i.json") == 1
    assert export_jsonl(tmp_env["db"], tmp_path / "i.jsonl") == 1
