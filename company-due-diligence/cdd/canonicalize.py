"""Versioned, MIME-aware canonicalization for stable change detection.

stdlib-only. HTML is reduced to visible text via a tag-stripping parser
(good enough for hashing; semantic extraction is the agent's job).
"""

import json
import re
import unicodedata
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import cast

PROFILE_VERSIONS = {"html": "1", "json": "1", "text": "1"}
_VOLATILE_JSON_KEYS = {"timestamp", "requestid", "csrf", "session", "nonce", "_ts"}


@dataclass(frozen=True)
class Canonical:
    text: str
    profile_id: str
    profile_version: str


def _norm_ws(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"\s+", " ", text).strip()


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def _canon_html(raw: bytes) -> str:
    parser = _TextExtractor()
    parser.feed(raw.decode("utf-8", "replace"))
    return _norm_ws(" ".join(parser.parts))


def _strip_volatile(obj: object) -> object:
    if isinstance(obj, dict):
        d = cast("dict[str, object]", obj)
        return {k: _strip_volatile(v) for k, v in sorted(d.items())
                if k.lower() not in _VOLATILE_JSON_KEYS}
    if isinstance(obj, list):
        lst = cast("list[object]", obj)
        return [_strip_volatile(v) for v in lst]
    return obj


def _canon_json(raw: bytes) -> str:
    data: object = json.loads(raw.decode("utf-8", "replace"))
    return json.dumps(_strip_volatile(data), sort_keys=True, separators=(",", ":"))


def _canon_text(raw: bytes) -> str:
    text = raw.decode("utf-8", "replace")
    text = re.sub(r"-\n", "", text)            # de-hyphenate across line breaks
    text = re.sub(r"\f", "\n", text)           # form feeds -> newlines
    text = re.sub(r"\n\s*\d+\s*\n", "\n", text)  # bare page-number lines
    return _norm_ws(text)


def canonicalize(raw: bytes, mime: str) -> Canonical:
    mime = (mime or "").split(";")[0].strip().lower()
    if mime in ("text/html", "application/xhtml+xml"):
        return Canonical(_canon_html(raw), "html", PROFILE_VERSIONS["html"])
    if mime in ("application/json", "text/json"):
        return Canonical(_canon_json(raw), "json", PROFILE_VERSIONS["json"])
    return Canonical(_canon_text(raw), "text", PROFILE_VERSIONS["text"])
