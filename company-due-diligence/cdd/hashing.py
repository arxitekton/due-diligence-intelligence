"""Dual hashing (raw + canonical) and diff classification."""

import hashlib
from dataclasses import dataclass
from typing import Literal

from cdd.canonicalize import canonicalize

DiffClass = Literal["unchanged", "cosmetic_change", "table_change", "content_change", "unavailable"]


@dataclass(frozen=True)
class ContentHash:
    raw_hash: str
    canonical_hash: str
    profile_id: str
    profile_version: str


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_content(raw: bytes, mime: str) -> ContentHash:
    canon = canonicalize(raw, mime)
    return ContentHash(
        raw_hash=_sha256(raw),
        canonical_hash=_sha256(canon.text.encode("utf-8")),
        profile_id=canon.profile_id,
        profile_version=canon.profile_version,
    )


def classify_diff(old: ContentHash, new: ContentHash | None) -> DiffClass:
    if new is None:
        return "unavailable"
    if old.raw_hash == new.raw_hash:
        return "unchanged"
    if old.canonical_hash == new.canonical_hash:
        return "cosmetic_change"
    return "content_change"
