from harvester.database import Database
from harvester.pdf.indexer import PdfIndexer

def test_sqlite_survives_reconnect(tmp_path):
    path = tmp_path / "x.sqlite"
    idx = PdfIndexer(Database(path))
    idx.record("https://example.gov/a.pdf")
    assert len(Database(path).fetchall("SELECT * FROM documents")) == 1

def test_concurrent_same_document_unique(tmp_env):
    idx = PdfIndexer(tmp_env["db"])
    assert idx.record("https://example.gov/same.pdf") == idx.record("https://example.gov/same.pdf")
    assert len(tmp_env["db"].fetchall("SELECT * FROM download_queue")) == 1
