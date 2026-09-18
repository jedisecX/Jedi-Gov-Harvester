from harvester.pdf.detector import classify_content_type, is_pdf, magic_is_pdf, url_looks_like_pdf

def test_extension_and_magic():
    assert url_looks_like_pdf("https://x.gov/a/b.PDF")
    assert magic_is_pdf(b"%PDF-1.7\n")
    assert is_pdf("https://x.gov/getfile?id=1", "application/pdf", b"%PDF-")
    assert not is_pdf("https://x.gov/page", "text/html", b"<!doctype html>")

def test_classify():
    assert classify_content_type("application/pdf") == "pdf"
    assert classify_content_type("text/html") == "html"
    assert classify_content_type("image/png") == "image"
