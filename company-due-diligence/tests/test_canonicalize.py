from cdd.canonicalize import PROFILE_VERSIONS, canonicalize


def test_html_strips_scripts_and_normalizes_whitespace():
    a = canonicalize(b"<html><body><script>x=1</script>Hello   World</body></html>", "text/html")
    b = canonicalize(b"<html><body>Hello World<!-- ad --></body></html>", "text/html")
    assert a.text == b.text == "Hello World"
    assert a.profile_id == "html"
    assert a.profile_version == PROFILE_VERSIONS["html"]


def test_json_sorts_keys_and_drops_volatile():
    a = canonicalize(b'{"b":1,"a":2,"timestamp":"now","requestId":"x"}', "application/json")
    b = canonicalize(b'{"a":2,"b":1,"timestamp":"later","requestId":"y"}', "application/json")
    assert a.text == b.text


def test_text_dehyphenates_and_strips_page_numbers():
    raw = b"This is a hy-\nphenated word.\n\f\n12\n"
    out = canonicalize(raw, "text/plain")
    assert "hyphenated word" in out.text
    assert "\n12\n" not in out.text


def test_unknown_mime_falls_back_to_text():
    out = canonicalize(b"  spaced   out  ", "application/octet-stream")
    assert out.text == "spaced out"
    assert out.profile_id == "text"
