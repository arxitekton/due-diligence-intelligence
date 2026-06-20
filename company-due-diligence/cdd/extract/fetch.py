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

Resolver = Callable[[str], list[str]]


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
    """True if the address must not be fetched (non-public ranges)."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True
    return (
        ip.is_private
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
    user_agent: str = "company-due-diligence/0.1",
    timeout: float = 30.0,
    resolver: Resolver = _default_resolver,
) -> tuple[bytes, dict[str, object]]:
    """Fetch a URL and return content bytes plus metadata.

    SSRF-safe: the initial URL and every redirect hop are validated against
    ``assert_public_url`` before the request is sent. Redirects are followed
    manually (httpx ``follow_redirects=False``) so each hop is re-checked.

    Returns:
        (content_bytes, metadata) with keys status, content_type, final_url,
        retrieved_at_hint (None — caller stamps real time).

    Raises:
        ExtractorUnavailable: httpx not installed.
        UnsafeURLError: the URL or a redirect target is not a safe public http(s) URL.
    """
    httpx: Any = _get_httpx()
    headers = {"User-Agent": user_agent}
    current = url
    with httpx.Client(follow_redirects=False, timeout=timeout, headers=headers) as client:
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
            "status": int(response.status_code),
            "content_type": response.headers.get("content-type"),
            "final_url": str(response.url),
            "retrieved_at_hint": None,
        }
    return content, metadata
