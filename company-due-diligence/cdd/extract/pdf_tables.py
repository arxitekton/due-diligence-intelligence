"""PDF text and table extraction using pdfplumber (lazy import)."""

from __future__ import annotations

import io
from typing import Any

from cdd.extract import ExtractorUnavailable


def _get_pdfplumber() -> Any:
    """Lazily import pdfplumber; raise ExtractorUnavailable if absent."""
    try:
        import pdfplumber  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ExtractorUnavailable("pdfplumber not installed") from exc
    return pdfplumber


def extract_text(pdf: bytes) -> str:
    """Concatenate text from all pages of a PDF.

    Args:
        pdf: Raw PDF bytes.

    Returns:
        Concatenated text from all pages, separated by newlines.

    Raises:
        ExtractorUnavailable: If pdfplumber is not installed.
    """
    pdfplumber: Any = _get_pdfplumber()
    pages: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        for page in doc.pages:
            raw: Any = page.extract_text()
            page_text: str = str(raw) if raw is not None else ""
            pages.append(page_text)
    return "\n".join(pages)


def extract_tables(pdf: bytes) -> list[list[list[str]]]:
    """Extract all tables from all pages of a PDF.

    Returns:
        List of tables across all pages; each table is a list of rows; each
        row is a list of stripped cell text strings (None cells become "").

    Raises:
        ExtractorUnavailable: If pdfplumber is not installed.
    """
    pdfplumber: Any = _get_pdfplumber()
    result: list[list[list[str]]] = []
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        for page in doc.pages:
            raw_tables: Any = page.extract_tables() or []
            for raw_table in raw_tables:
                rows: list[list[str]] = [
                    [str(cell).strip() if cell is not None else "" for cell in row]
                    for row in raw_table
                    if row
                ]
                if rows:
                    result.append(rows)
    return result
