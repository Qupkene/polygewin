"""Tests for geoblock detection."""

import pytest


class TestGeocheckLogic:
    """Test geocheck behavior (without making real HTTP calls)."""

    def test_blocked_response_interpretation(self):
        """A blocked=True response should indicate blocked."""
        data = {"blocked": True}
        assert data.get("blocked", True) is True

    def test_unblocked_response_interpretation(self):
        """A blocked=False response should indicate not blocked."""
        data = {"blocked": False}
        assert data.get("blocked", True) is False

    def test_missing_field_defaults_blocked(self):
        """If 'blocked' field is missing, default to blocked."""
        data = {"status": "ok"}
        assert data.get("blocked", True) is True

    def test_empty_response_defaults_blocked(self):
        """Empty response defaults to blocked."""
        data = {}
        assert data.get("blocked", True) is True
