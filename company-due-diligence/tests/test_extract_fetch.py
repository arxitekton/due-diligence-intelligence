import pytest

from cdd.extract.fetch import (
    UnsafeURLError,
    _is_blocked_ip,
    assert_public_url,
    get,
    resolve_user_agent,
)


def test_resolve_user_agent_default_has_contact():
    ua = resolve_user_agent(None)
    # SEC EDGAR requires a descriptive UA with a contact; default must carry one.
    assert "contact" in ua.lower() and "@" in ua


def test_resolve_user_agent_env_override(monkeypatch):
    monkeypatch.setenv("CDD_HTTP_USER_AGENT", "Acme DD admin@acme.com")
    assert resolve_user_agent(None) == "Acme DD admin@acme.com"


def test_resolve_user_agent_explicit_wins(monkeypatch):
    monkeypatch.setenv("CDD_HTTP_USER_AGENT", "env-ua admin@acme.com")
    assert resolve_user_agent("explicit-ua x@y.com") == "explicit-ua x@y.com"


class _FakeResp:
    def __init__(self, status, headers, content=b"", url="https://example.com/"):
        self.status_code = status
        self.headers = headers
        self.content = content
        self.url = url


class _FakeClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.closed = False

    def get(self, url):  # noqa: ARG002
        return self._responses.pop(0)

    def close(self):
        self.closed = True


def _ipish(host: str) -> list[str]:
    """Resolver: treat dotted-numeric hosts as their own IP, else a public IP."""
    return [host] if host[0].isdigit() else ["93.184.216.34"]


def test_rejects_non_http_schemes():
    for url in ("file:///etc/passwd", "ftp://example.com/x", "gopher://x"):
        with pytest.raises(UnsafeURLError):
            assert_public_url(url, resolver=lambda h: ["93.184.216.34"])


def test_is_blocked_ip_for_private_and_special_ranges():
    for ip in ("127.0.0.1", "10.0.0.1", "192.168.1.1", "172.16.0.1",
               "169.254.169.254", "0.0.0.0", "::1", "224.0.0.1", "fe80::1",
               "not-an-ip"):
        assert _is_blocked_ip(ip) is True, ip


def test_is_blocked_ip_allows_public():
    for ip in ("8.8.8.8", "1.1.1.1", "93.184.216.34", "2606:2800:220:1:248:1893:25c8:1946"):
        assert _is_blocked_ip(ip) is False, ip


def test_assert_public_url_blocks_private_resolution():
    with pytest.raises(UnsafeURLError):
        assert_public_url("https://internal.example", resolver=lambda h: ["10.0.0.5"])


def test_assert_public_url_blocks_cloud_metadata_ip():
    with pytest.raises(UnsafeURLError):
        assert_public_url("http://169.254.169.254/latest/meta-data/",
                          resolver=lambda h: ["169.254.169.254"])


def test_assert_public_url_blocks_metadata_hostname():
    with pytest.raises(UnsafeURLError):
        assert_public_url("http://metadata.google.internal/computeMetadata/v1/",
                          resolver=lambda h: ["93.184.216.34"])


def test_assert_public_url_allows_public_host():
    # must not raise
    assert_public_url("https://example.com/ir", resolver=lambda h: ["93.184.216.34"])


def test_assert_public_url_requires_host():
    with pytest.raises(UnsafeURLError):
        assert_public_url("https://", resolver=lambda h: ["93.184.216.34"])


def test_get_blocks_redirect_to_private():
    client = _FakeClient([_FakeResp(302, {"location": "http://10.0.0.1/meta"})])
    with pytest.raises(UnsafeURLError):
        get("https://example.com/", resolver=_ipish, client=client)


def test_get_success_returns_content_and_metadata():
    client = _FakeClient([_FakeResp(200, {"content-type": "text/html"}, b"<html/>")])
    content, meta = get("https://example.com/", resolver=_ipish, client=client)
    assert content == b"<html/>"
    assert meta["status"] == 200
    assert meta["content_type"] == "text/html"
    # injected client is owned by the caller, so get() must not close it
    assert client.closed is False


def test_get_rejects_too_many_redirects():
    loop = [_FakeResp(302, {"location": "https://example.com/next"}) for _ in range(10)]
    client = _FakeClient(loop)
    with pytest.raises(UnsafeURLError):
        get("https://example.com/", resolver=_ipish, client=client)
