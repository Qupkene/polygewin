"""Tests for NOAA NWS forecast fetcher."""

from polybot.data.noaa import _c_to_f, _f_to_c


class TestTemperatureConversions:
    """Test temperature conversion functions."""

    def test_c_to_f_freezing(self):
        assert _c_to_f(0) == 32

    def test_c_to_f_boiling(self):
        assert _c_to_f(100) == 212

    def test_f_to_c_freezing(self):
        assert _f_to_c(32) == 0

    def test_f_to_c_boiling(self):
        assert _f_to_c(212) == 100

    def test_roundtrip(self):
        """Converting C->F->C should return original value."""
        original = 25.0
        assert abs(_f_to_c(_c_to_f(original)) - original) < 0.01

    def test_negative_40_same(self):
        """At -40, both scales are equal."""
        assert _c_to_f(-40) == -40
        assert _f_to_c(-40) == -40
