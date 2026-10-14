"""
Tests that drive the real Player window (offscreen, volume 0) on a small fake library.
Every settings/cache path is moved into a temp folder first, so your own eozMP data is never touched.
"""
import json
import os
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtMultimedia import QMediaPlayer  # noqa: E402

from test_core import TempDirTest, mp  # noqa: E402
from test_mpv_engine import APP, tone, wait_for  # noqa: E402

assert APP is not None   # the shared QApplication

HOME_PATHS = ("CONFIG_FILE", "CACHE_FILE", "PLAYLIST_FILE", "LYRICS_DIR", "UI_DIR", "STATS_FILE", "COVERS_DIR")


class PlayerTest(TempDirTest):
    engine = "Qt (built-in)"

    def make_player(self, names, seconds=1.0, **cfg):
        for name in HOME_PATHS:
            patcher = mock.patch.object(mp, name, self.tmp / "home" / Path(getattr(mp, name)).name)
            patcher.start()
            self.addCleanup(patcher.stop)
        (self.tmp / "home").mkdir()
        lib = self.tmp / "music" / "Band" / "Alb"
        lib.mkdir(parents=True)
        self.songs = []
        for i, name in enumerate(names, 1):
            path = lib / f"{i:02d} - {name}.wav"
            tone(path, seconds)
            self.songs.append(path)
        settings = {"folders": [str(self.tmp / "music")], "audio_engine": self.engine, "volume": 0,
                    "media_keys": False, "lyrics_online": False, "covers_auto": False, "resume": False,
                    "close_to_tray": False, "mpv_dir": os.environ.get("EOZMP_LIBMPV", "")}
        settings.update(cfg)
        mp.CONFIG_FILE.write_text(json.dumps(settings), encoding="utf-8")
        self.player = mp.Player()
        self.addCleanup(self.close_player)
        self.assertTrue(wait_for(lambda: len(self.player.all_tracks) == len(names) and not self.player.scanning))
        self.played = []
        real = self.player.play_index

        def counting(idx, *a, **k):
            self.played.append(Path(self.player.queue[idx][0]["path"]).stem.split(" - ", 1)[1])
            return real(idx, *a, **k)
        self.player.play_index = counting

    def delete(self, path):
        """The app may be reading the file for a moment (cover art), so retry briefly."""
        self.assertTrue(wait_for(lambda: self._try_unlink(path), 5), f"couldn't delete {path}")

    @staticmethod
    def _try_unlink(path):
        try:
            path.unlink()
            return True
        except PermissionError:
            return False

    def close_player(self):
        self.player.quitting = True
        self.player.close()
        self.player.deleteLater()

    def title(self):
        p = self.player
        return Path(p.queue[p.index][0]["path"]).stem.split(" - ", 1)[1] if 0 <= p.index < len(p.queue) else None

    def start(self, name):
        p = self.player
        p.play_from_library(next(i for i, (t, _k) in enumerate(p.queue) if Path(t["path"]).stem.endswith(" - " + name)))

    def seeks_during(self, action):
        calls = []
        real = self.player.player.setPosition
        with mock.patch.object(self.player.player, "setPosition", side_effect=lambda ms: (calls.append(ms), real(ms))):
            action()
            wait_for(lambda: False, 0.2)
        return calls

    def test_dragging_the_seek_bar_seeks_once_when_let_go(self):
        self.make_player(["One"], seconds=4)
        self.start("One")
        self.assertTrue(wait_for(lambda: self.player.seek.maximum() > 0))
        bar = self.player.seek

        def drag():
            bar.setSliderDown(True)
            for v in range(200, 3001, 200):
                bar.setSliderPosition(v)
            bar.setSliderDown(False)
        self.assertEqual(self.seeks_during(drag), [3000])

    def test_clicking_the_seek_bar_jumps_there(self):
        from PyQt6.QtCore import QPoint, Qt
        from PyQt6.QtTest import QTest
        self.make_player(["One"], seconds=4)
        self.start("One")
        self.assertTrue(wait_for(lambda: self.player.seek.maximum() > 0))
        bar = self.player.seek
        bar.resize(400, 20)
        calls = self.seeks_during(lambda: QTest.mouseClick(bar, Qt.MouseButton.LeftButton, pos=QPoint(300, 10)))
        self.assertEqual(len(calls), 1)
        self.assertAlmostEqual(calls[0] / bar.maximum(), 0.75, delta=0.08)

    def test_clicking_the_handle_without_moving_does_not_seek(self):
        from PyQt6.QtCore import QPoint, Qt
        from PyQt6.QtTest import QTest
        self.make_player(["One"], seconds=4)
        self.start("One")
        self.assertTrue(wait_for(lambda: self.player.seek.maximum() > 0))
        bar = self.player.seek
        bar.resize(400, 20)
        bar.setValue(0)   # handle at the far left
        calls = self.seeks_during(lambda: QTest.mouseClick(bar, Qt.MouseButton.LeftButton, pos=QPoint(4, 10)))
        self.assertEqual(calls, [])

    def test_a_missing_song_is_skipped(self):
        self.make_player(["One", "Two", "Three"])
        self.delete(self.songs[1])
        self.start("One")
        self.assertTrue(wait_for(lambda: self.title() == "Three", 8))
        self.assertEqual(self.played, ["One", "Two", "Three"])

    def test_stops_when_nothing_can_be_played(self):
        self.make_player(["One", "Two", "Three"], repeat_mode="all")
        for s in self.songs:
            self.delete(s)
        self.start("One")
        wait_for(lambda: False, 3)
        self.assertLessEqual(len(self.played), 3)
        self.assertNotEqual(self.player.player.playbackState(), QMediaPlayer.PlaybackState.PlayingState)


@unittest.skipUnless(mp.load_mpv(os.environ.get("EOZMP_LIBMPV", "")), "libmpv-2.dll not found")
class MpvPlayerTest(PlayerTest):
    engine = "mpv"

    def test_engine_is_mpv(self):
        self.make_player(["One"])
        self.assertEqual(self.player.engine_name, "mpv")


@unittest.skipUnless(mp.vlc is not None, "python-vlc / VLC not installed")
class VlcPlayerTest(PlayerTest):
    engine = "VLC"


if __name__ == "__main__":
    unittest.main()
