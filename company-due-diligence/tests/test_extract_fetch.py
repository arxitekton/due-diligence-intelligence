import pytest

from cdd.extract.fetch import UnsafeURLError, _is_blocked_ip, assert_public_url


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
