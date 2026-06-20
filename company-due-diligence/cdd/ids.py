"""Stable identity: company slug, run_id, and logical source_id."""

import hashlib
import re
import unicodedata
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from cdd.timeutil import compact_stamp

_LEGAL_SUFFIXES = {
    "inc", "incorporated", "corporation", "company", "co", "ltd",
    "limited", "llc", "llp", "plc", "sa", "ag", "gmbh", "nv", "bv", "spa",
    "pty", "kk", "oyj", "ab", "as",
}
# Exact param names dropped as tracking noise (short/ambiguous — never prefix-match
# these, or legitimate params like ``reference``/``referrer`` would be stripped and
# collapse distinct logical sources onto one source_id).
_TRACKING_EXACT = {"ref", "fbclid", "gclid"}
# Param-name prefixes that are unambiguously tracking families.
_TRACKING_PREFIXES = ("utm_", "mc_", "_ga")


def normalize_company_id(name: str) -> str:
    """Deterministic, stable slug for a company name."""
    decomposed = unicodedata.normalize("NFKD", name)
    ascii_name = decomposed.encode("ascii", "ignore").decode("ascii").lower()
    tokens = re.split(r"[^a-z0-9]+", ascii_name)
    # Drop empty strings, single-char tokens (abbreviation fragments like S. A.),
    # and known multi-char legal-entity suffixes.
    kept = [t for t in tokens if len(t) > 1 and t not in _LEGAL_SUFFIXES]
    slug = "-".join(kept)
    if not slug:
        raise ValueError(f"company name produced empty slug: {name!r}")
    return slug


def make_run_id(now: datetime, token: str) -> str:
    """run_id = {compact UTC stamp}-{short token}."""
    if not re.fullmatch(r"[0-9a-z]{4,12}", token):
        raise ValueError(f"token must be 4-12 lowercase alnum chars: {token!r}")
    return f"{compact_stamp(now)}-{token}"


def _normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower() or "https"
    netloc = parts.netloc.lower()
    path = parts.path.lower().rstrip("/") or "/"
    query_pairs = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in _TRACKING_EXACT and not k.lower().startswith(_TRACKING_PREFIXES)
    ]
    query = urlencode(sorted(query_pairs))
    return urlunsplit((scheme, netloc, path, query, ""))


def source_id_for(url: str, source_class: str) -> str:
    """Stable id for a logical source = normalized URL + source_class."""
    if not source_class:
        raise ValueError("source_class is required")
    basis = f"{source_class.lower()}|{_normalize_url(url)}"
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]
    return f"src_{digest}"
