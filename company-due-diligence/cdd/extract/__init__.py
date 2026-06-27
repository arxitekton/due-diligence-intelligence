"""Optional extraction tools (network/parse helpers). All heavy deps are lazy.

Absence of an optional library yields ExtractorUnavailable, never an ImportError
at package import time. The agent uses these for reliability on PDFs/EDGAR/HTML;
they are NOT used by the deterministic cdd bookkeeping path.
"""

import importlib.util


class ExtractorUnavailable(RuntimeError):
    """Raised when an optional extraction dependency is not installed."""


def _have(mod: str) -> bool:
    return importlib.util.find_spec(mod) is not None


def capabilities() -> dict[str, bool]:
    """Probe which optional extraction backends are importable. Never raises."""
    return {
        "html": _have("bs4") and _have("lxml"),
        "html_trafilatura": _have("trafilatura"),
        "pdf": _have("pdfplumber"),
        "pdf_pymupdf": _have("fitz"),
        "edgar": _have("edgar"),
        "fetch": _have("httpx"),
        "sanctions": _have("httpx"),
        "gleif": _have("httpx"),
        "companies_house": _have("httpx"),
        "gdelt": _have("httpx"),
        "econ": _have("httpx"),
        "sanctions_xml": _have("defusedxml"),
    }
