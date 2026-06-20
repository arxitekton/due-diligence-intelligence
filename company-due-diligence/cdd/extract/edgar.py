"""EDGAR filing access via edgartools (lazy import).

Network-bound; only guard behavior is unit-tested.
"""

from __future__ import annotations

from typing import Any

from cdd.extract import ExtractorUnavailable


def _get_edgar() -> Any:
    """Lazily import edgartools; raise ExtractorUnavailable if absent."""
    try:
        import edgar  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ExtractorUnavailable("edgartools not installed") from exc
    return edgar


def list_filings(
    identifier: str,
    forms: tuple[str, ...] = ("10-K", "10-Q", "20-F"),
) -> list[dict[str, object]]:
    """List SEC filings for a company.

    Args:
        identifier: Ticker symbol or CIK number.
        forms: Filing form types to filter on.

    Returns:
        List of filing metadata dicts.

    Raises:
        ExtractorUnavailable: If edgartools is not installed.
    """
    edgar: Any = _get_edgar()
    company: Any = edgar.Company(identifier)
    filings: Any = company.get_filings(form=list(forms))
    results: list[dict[str, object]] = []
    for filing in filings:
        results.append(
            {
                "accession": str(filing.accession_no),
                "form": str(filing.form),
                "filed": str(filing.filing_date),
                "description": str(getattr(filing, "description", "")),
            }
        )
    return results


def fetch_filing(accession: str) -> bytes:
    """Fetch the raw content of a filing by accession number.

    Args:
        accession: SEC accession number (e.g. "0000320193-23-000077").

    Returns:
        Raw filing content bytes.

    Raises:
        ExtractorUnavailable: If edgartools is not installed.
    """
    edgar: Any = _get_edgar()
    filing: Any = edgar.get_filing(accession_number=accession)
    if hasattr(filing, "html"):
        html_str: str = str(filing.html())
        return html_str.encode()
    return b""
