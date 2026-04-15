"""Tests for kill switch logic."""

from polybot.risk.kill_switch import MAX_CONSECUTIVE_LOSSES


class TestKillSwitchConstants:

    def test_max_consecutive_losses(self):
        assert MAX_CONSECUTIVE_LOSSES == 5

    def test_max_consecutive_losses_is_reasonable(self):
        """Kill switch should trigger after a reasonable number of losses."""
        assert 3 <= MAX_CONSECUTIVE_LOSSES <= 10
