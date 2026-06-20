"""HTTP fetch helper using httpx (lazy import)."""

from __future__ import annotations

from typing import Any

from cdd.extract import ExtractorUnavailable


def _get_httpx() -> Any:
    """Lazily import httpx; raise ExtractorUnavailable if absent."""
    try:
        import httpx  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ExtractorUnavailable("httpx not installed") from exc
    return httpx


def get(
    url: str,
    *,
    user_agent: str = "company-due-diligence/0.1",
    timeout: float = 30.0,
) -> tuple[bytes, dict[str, object]]:
    """Fetch a URL and return content bytes plus metadata.

    Args:
        url: The URL to fetch.
        user_agent: User-Agent header value.
        timeout: Request timeout in seconds.

    Returns:
        Tuple of (content_bytes, metadata) where metadata contains:
        - status: HTTP status code (int)
        - content_type: Content-Type header value (str or None)
        - final_url: URL after redirects (str)
        - retrieved_at_hint: None (caller stamps real time)

    Raises:
        ExtractorUnavailable: If httpx is not installed.
    """
    httpx: Any = _get_httpx()
    headers = {"User-Agent": user_agent}
    with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
        response: Any = client.get(url)
        content: bytes = bytes(response.content)
        metadata: dict[str, object] = {
            "status": int(response.status_code),
            "content_type": response.headers.get("content-type"),
            "final_url": str(response.url),
            "retrieved_at_hint": None,
        }
    return content, metadata
