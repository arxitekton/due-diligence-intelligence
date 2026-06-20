from cdd.hashing import classify_diff, hash_content


def test_hash_content_returns_raw_and_canonical():
    h = hash_content(b"<html><body>Hello   World</body></html>", "text/html")
    assert len(h.raw_hash) == 64 and len(h.canonical_hash) == 64
    assert h.profile_id == "html"


def test_canonical_hash_ignores_cosmetic_changes():
    a = hash_content(b"<body>Hello World<script>t=1</script></body>", "text/html")
    b = hash_content(b"<body>Hello   World<!-- x --></body>", "text/html")
    assert a.raw_hash != b.raw_hash
    assert a.canonical_hash == b.canonical_hash


def test_classify_unchanged():
    a = hash_content(b"<body>Hi</body>", "text/html")
    assert classify_diff(a, a) == "unchanged"


def test_classify_cosmetic_change():
    a = hash_content(b"<body>Hi<script>t=1</script></body>", "text/html")
    b = hash_content(b"<body>Hi</body>", "text/html")
    assert classify_diff(a, b) == "cosmetic_change"


def test_classify_content_change():
    a = hash_content(b"<body>Hi</body>", "text/html")
    b = hash_content(b"<body>Bye</body>", "text/html")
    assert classify_diff(a, b) == "content_change"


def test_classify_unavailable_when_new_is_none():
    a = hash_content(b"<body>Hi</body>", "text/html")
    assert classify_diff(a, None) == "unavailable"
