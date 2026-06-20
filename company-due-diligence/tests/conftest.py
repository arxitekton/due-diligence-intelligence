"""Shared pytest fixtures."""

from datetime import UTC, datetime

import pytest


@pytest.fixture
def fixed_now() -> datetime:
    """A fixed UTC instant for reproducible tests."""
    return datetime(2026, 6, 20, 18, 30, 0, tzinfo=UTC)
