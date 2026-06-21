import pytest

from cdd.extract import capabilities

pytestmark = pytest.mark.skipif(not capabilities()["pdf"], reason="pdfplumber not installed")


def test_pdf_module_importable():
    from cdd.extract import pdf_tables  # noqa: F401
