"""HTTP fetch helper using httpx (lazy import), hardened against SSRF.

The agent supplies arbitrary URLs to fetch, so every destination (and every
redirect hop) is validated before dispatch: scheme must be http/https and the
resolved host must not be a private/loopback/link-local/reserved/multicast
address (which would let a crafted URL reach cloud metadata or internal
services). Validation is factored into pure helpers with an injectable
resolver so it is fully unit-testable without httpx or real DNS.
"""

from __future__ import annotations

import ipaddress
import os
import socket
from collections.abc import Callable
from typing import Any
from urllib.parse import urljoin, urlsplit

from cdd.extract import ExtractorUnavailable

# Cloud metadata endpoints worth blocking explicitly (covered by link-local too,
# but called out for clarity / defense in depth).
_BLOCKED_HOSTS = {"169.254.169.254", "metadata.google.internal"}
_MAX_REDIRECTS = 5
_MAX_BYTES = 50 * 1024 * 1024  # 50 MiB cap

# Some primary sources (notably SEC EDGAR) reject requests without a descriptive
# User-Agent that includes a contact. SEC's fair-access policy asks for a UA like
# "Company Name contact@example.com". This default satisfies that shape; override
# with a real contact via the CDD_HTTP_USER_AGENT env var or the user_agent= arg.
_DEFAULT_USER_AGENT = (
    "company-due-diligence/0.1 (due-diligence-intelligence; contact: due-diligence@example.com)"
)

Resolver = Callable[[str], list[str]]


def resolve_user_agent(user_agent: str | None = None) -> str:
    """Pick the User-Agent: explicit arg > CDD_HTTP_USER_AGENT env > default.

    Set CDD_HTTP_USER_AGENT to a real contact (e.g. "Acme DD admin@acme.com") so
    contact-requiring sources like SEC EDGAR accept the request.
    """
    return user_agent or os.environ.get("CDD_HTTP_USER_AGENT") or _DEFAULT_USER_AGENT


class UnsafeURLError(ValueError):
    """Raised when a URL fails SSRF / scheme validation."""


def _get_httpx() -> Any:
    """Lazily import httpx; raise ExtractorUnavailable if absent."""
    try:
        import httpx  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ExtractorUnavailable("httpx not installed") from exc
    return httpx


def _is_blocked_ip(ip_str: str) -> bool:
    """True if the address must not be fetched (anything not globally routable).

    Uses ``not is_global`` as the primary gate (rejects CGNAT 100.64.0.0/10 and
    any future-reserved range automatically) plus explicit special-range flags.
    """
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True
    return (
        not ip.is_global
        or ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _default_resolver(host: str) -> list[str]:
    infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    return [str(info[4][0]) for info in infos]


def assert_public_url(url: str, *, resolver: Resolver = _default_resolver) -> None:
    """Raise UnsafeURLError unless url is http(s) and resolves to public addrs."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise UnsafeURLError(f"unsupported scheme: {parts.scheme!r}")
    host = parts.hostname
    if not host:
        raise UnsafeURLError("missing host")
    if host.lower() in _BLOCKED_HOSTS:
        raise UnsafeURLError(f"blocked host: {host}")
    try:
        addrs = resolver(host)
    except OSError as exc:
        raise UnsafeURLError(f"cannot resolve host: {host}") from exc
    if not addrs:
        raise UnsafeURLError(f"no addresses for host: {host}")
    for addr in addrs:
        if addr in _BLOCKED_HOSTS or _is_blocked_ip(addr):
            raise UnsafeURLError(f"blocked address {addr} for host {host}")


def get(
    url: str,
    *,
    user_agent: str | None = None,
    timeout: float = 30.0,
    resolver: Resolver = _default_resolver,
    client: Any = None,
) -> tuple[bytes, dict[str, object]]:
    """Fetch a URL and return content bytes plus metadata.

    The initial URL and every redirect hop are validated against
    ``assert_public_url`` before each request (redirects are followed manually
    with httpx ``follow_redirects=False`` so each hop is re-checked). Response
    size is capped at ``_MAX_BYTES``.

    KNOWN LIMITATION (DNS rebinding / TOCTOU): validation resolves the host, but
    httpx resolves it again independently when connecting, so a hostile
    authoritative DNS could return a public address to validation and a private
    one to the connection. This pre-flight guard blocks the common cases
    (literal private/metadata IPs, private-resolving hostnames, unsafe schemes,
    private redirect targets) but is NOT a complete defence against an attacker
    who controls a domain's DNS. For untrusted-input contexts, pin the
    connection to the validated address via a custom transport. The agent here
    fetches URLs it selects from discovered sources, not arbitrary attacker input.

    Args:
        client: optional pre-built httpx-like client (for testing / connection
            pinning); when None a default ``httpx.Client`` is created.

    Returns:
        (content_bytes, metadata) with keys status, content_type, final_url
        (the post-redirect target), retrieved_at_hint (None — caller stamps time).

    Raises:
        ExtractorUnavailable: httpx not installed (and no client injected).
        UnsafeURLError: the URL or a redirect target is not a safe public http(s) URL.
    """
    headers = {"User-Agent": resolve_user_agent(user_agent)}
    owns_client = client is None
    if owns_client:
        httpx: Any = _get_httpx()
        client = httpx.Client(follow_redirects=False, timeout=timeout, headers=headers)
    try:
        current = url
        for _ in range(_MAX_REDIRECTS + 1):
            assert_public_url(current, resolver=resolver)
            response: Any = client.get(current)
            status = int(response.status_code)
            location = response.headers.get("location")
            if status in (301, 302, 303, 307, 308) and location:
                current = urljoin(current, str(location))
                continue
            break
        else:
            raise UnsafeURLError(f"too many redirects (>{_MAX_REDIRECTS})")

        content: bytes = bytes(response.content)
        if len(content) > _MAX_BYTES:
            raise UnsafeURLError(f"response exceeds {_MAX_BYTES} bytes")
        metadata: dict[str, object] = {
            "status": status,
            "content_type": response.headers.get("content-type"),
            "final_url": str(response.url),
            "retrieved_at_hint": None,
        }
    finally:
        if owns_client:
            client.close()
    return content, metadata
