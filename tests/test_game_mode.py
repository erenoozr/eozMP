"""
The full-screen player's drifting background stands still while a full-screen game is in front,
so a second-monitor eozMP doesn't make the game stutter.
"""
import os
import types
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from test_core import mp  # noqa: E402


def fake_player():
    fp = types.SimpleNamespace(_game_checked=0.0, _game=False, _motion_last=0.0, motion_clock=0.0)
    fp.update = mock.Mock()
    return fp


class GameModeTest(unittest.TestCase):
    def tick(self, fp):
        mp.FullPlayer._motion_tick(fp)

    def test_background_moves_without_a_game(self):
        fp = fake_player()
        with mock.patch.object(mp, "game_in_front", return_value=False):
            self.tick(fp)
        fp.update.assert_called_once()

    def test_background_stands_still_behind_a_game(self):
        fp = fake_player()
        with mock.patch.object(mp, "game_in_front", return_value=True):
            self.tick(fp)
            self.tick(fp)
        fp.update.assert_not_called()
        self.assertEqual(fp.motion_clock, 0.0)   # time behind the game doesn't count

    def test_asks_windows_at_most_once_a_second(self):
        fp = fake_player()
        with mock.patch.object(mp, "game_in_front", return_value=False) as ask:
            for _ in range(5):
                self.tick(fp)
        self.assertEqual(ask.call_count, 1)

    def test_helper_never_raises(self):
        self.assertIn(mp.game_in_front(), (True, False))


if __name__ == "__main__":
    unittest.main()
