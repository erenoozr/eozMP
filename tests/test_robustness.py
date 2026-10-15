"""
Errors nobody expected must not close the player: they go to a log file and the status bar.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

from test_core import TempDirTest, mp


class FakeBar:
    def __init__(self):
        self.shown = []

    def showMessage(self, text, ms=0):
        self.shown.append(text)


class FakeWindow:
    def __init__(self):
        self.bar = FakeBar()

    def statusBar(self):
        return self.bar


class ErrorLogTest(TempDirTest):
    def test_an_uncaught_error_is_logged_and_shown(self):
        log = self.tmp / "crash.log"
        win = FakeWindow()
        with mock.patch.object(mp, "CRASH_FILE", log):
            try:
                {}["gone"]
            except KeyError:
                mp.log_uncaught(*sys.exc_info(), window=win)
        self.assertIn("KeyError", log.read_text(encoding="utf-8"))
        self.assertEqual(len(win.bar.shown), 1)
        self.assertIn("crash.log", win.bar.shown[0])

    def test_the_log_stays_small(self):
        log = self.tmp / "crash.log"
        with mock.patch.object(mp, "CRASH_FILE", log):
            for _ in range(300):
                try:
                    raise ValueError("x" * 2000)
                except ValueError:
                    mp.log_uncaught(*sys.exc_info())
        self.assertLessEqual(log.stat().st_size, 210000)

    def test_an_unwritable_log_does_not_raise(self):
        with mock.patch.object(mp, "CRASH_FILE", self.tmp / "no" / "such" / "dir" / "c.log"):
            try:
                raise ValueError("x")
            except ValueError:
                mp.log_uncaught(*sys.exc_info(), window=FakeWindow())   # must not raise


if __name__ == "__main__":
    unittest.main()
