"""HTML text and table extraction using BeautifulSoup4 + lxml (lazy imports)."""

from __future__ import annotations

import re
from typing import Any, cast

from cdd.extract import ExtractorUnavailable


def _get_bs4() -> Any:
    """Lazily import BeautifulSoup; raise ExtractorUnavailable if absent."""
    try:
        from bs4 import BeautifulSoup  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ExtractorUnavailable("beautifulsoup4/lxml not installed") from exc
    return cast(Any, BeautifulSoup)


def extract_main_text(html: bytes) -> str:
    """Return whitespace-normalized visible text, stripping script/style tags.

    Args:
        html: Raw HTML bytes.

    Returns:
        Visible text content with normalized whitespace.

    Raises:
        ExtractorUnavailable: If bs4/lxml are not installed.
    """
    BeautifulSoup: Any = _get_bs4()
    soup: Any = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style"]):
        tag.decompose()
    raw: Any = soup.get_text(separator=" ")
    text: str = str(raw)
    return re.sub(r"\s+", " ", text).strip()


def extract_tables(html: bytes) -> list[list[list[str]]]:
    """Parse all <table> elements into a nested list structure.

    Returns:
        List of tables; each table is a list of rows; each row is a list of
        stripped cell text strings.

    Raises:
        ExtractorUnavailable: If bs4/lxml are not installed.
    """
    BeautifulSoup: Any = _get_bs4()
    soup: Any = BeautifulSoup(html, "lxml")
    result: list[list[list[str]]] = []
    for table in soup.find_all("table"):
        rows: list[list[str]] = []
        for tr in table.find_all("tr"):
            cells: list[str] = [
                str(td.get_text(strip=True)) for td in tr.find_all(["td", "th"])
            ]
            if cells:
                rows.append(cells)
        if rows:
            result.append(rows)
    return result
