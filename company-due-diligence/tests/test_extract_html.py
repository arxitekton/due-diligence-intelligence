import pytest

from cdd.extract import capabilities, html_clean

pytestmark = pytest.mark.skipif(not capabilities()["html"], reason="bs4/lxml not installed")

_HTML = (
    b"<html><body><script>x=1</script><h1>Acme</h1>"
    b"<table><tr><td>a</td><td>b</td></tr></table></body></html>"
)


def test_extract_main_text():
    text = html_clean.extract_main_text(_HTML)
    assert "Acme" in text and "x=1" not in text


def test_extract_tables():
    tables = html_clean.extract_tables(_HTML)
    assert tables and tables[0][0] == ["a", "b"]
