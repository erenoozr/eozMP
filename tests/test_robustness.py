"""
Errors nobody expected must not close the player: they go to a log file and the status bar.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

from test_core import TempDirTest, mp
from test_player import PlayerHarness


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


class StatsArtistTest(PlayerHarness):
    def test_compilation_songs_count_for_their_singers(self):          # B26
        self.make_player(["One", "Two"])
        p = self.player
        for t, _k in p.track_by_path.values():
            t["artist"], t["track_artist"] = "Various Artists", "Singer A"
            p.stats["events"].append([int(mp.time.time()), t["path"], 30.0])
        p.show_stats()
        names = [p.top_artists.item(r, 0).text() for r in range(p.top_artists.rowCount())]
        self.assertEqual(names, ["Singer A"])


class DuplicatesDialogTest(PlayerHarness):
    def test_other_album_copies_start_unticked(self):                  # B13
        self.make_player(["One"])
        a = {"title": "Intro", "artist": "Band", "album": "First", "disc": 1, "num": 1, "length": 30,
             "path": "a.flac", "size": 9}
        same = dict(a, path="b.mp3")
        other = dict(a, album="Second", path="c.mp3")
        dlg = mp.DuplicatesDialog(self.player, [[a, same, other]])
        top = dlg.tree.topLevelItem(0)
        states = {top.child(i).data(0, mp.KEY_ROLE): top.child(i).checkState(0) for i in range(1, 3)}
        self.assertEqual(states["b.mp3"], mp.Qt.CheckState.Checked)
        self.assertEqual(states["c.mp3"], mp.Qt.CheckState.Unchecked)
        dlg.deleteLater()


class StaleRowTest(PlayerHarness):
    def test_playing_a_song_that_left_the_library_does_not_crash(self):      # B7
        self.make_player(["One", "Two"])
        p = self.player
        p.play_path(str(self.tmp / "music" / "gone.wav"))          # no KeyError
        self.assertIn("no longer", p.statusBar().currentMessage())
        p.play_path(p.queue[0][0]["path"])                           # a real song still plays
        self.assertEqual(self.played, ["One"])


if __name__ == "__main__":
    unittest.main()
