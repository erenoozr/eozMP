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


class PlayerHarness(TempDirTest):
    """Starts the real Player on a small fake library; no tests of its own."""
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
                    "close_to_tray": False, "mpv_dir": os.environ.get("EOZMP_LIBMPV", ""),
                    "update_check": False}
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



class PlayerTest(PlayerHarness):
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

    def test_next_after_previous_goes_back_where_you_were(self):
        self.make_player(["One", "Two", "Three"], seconds=4)
        self.start("One")
        self.player.next_track()
        self.player.next_track()
        self.assertEqual(self.title(), "Three")
        self.player.prev_track()
        self.player.prev_track()
        self.assertEqual(self.title(), "One")
        self.player.next_track()
        self.assertEqual(self.title(), "Two")
        self.assertEqual(self.player.fwd, [str(self.songs[2])])
        self.player.next_track()
        self.assertEqual(self.title(), "Three")
        self.assertEqual(self.player.fwd, [])

    def test_previous_after_a_rescan_goes_one_song_back(self):          # B9
        self.make_player(["One", "Two", "Three"], seconds=4)
        self.start("One")
        self.player.next_track()
        self.player.next_track()
        p = self.player
        # a rescan where the song playing now (Three) is gone: moved, deleted, drive unplugged
        p.build_library([t for t in p.all_tracks if t["path"] != str(self.songs[2])])
        p.player.setPosition(0)
        p.prev_track()
        self.assertEqual(self.title(), "Two")
        p.prev_track()
        self.assertEqual(self.title(), "One")

    def test_shuffle_without_repeat_stops_after_every_song_played(self):   # B10
        self.make_player(["One", "Two", "Three"], seconds=4, shuffle_on=True)
        self.start("One")
        for _ in range(2):
            self.player.next_track(auto=True)
        self.assertEqual(sorted(self.played), ["One", "Three", "Two"])
        self.player.next_track(auto=True)                        # the list is done
        self.assertEqual(len(self.played), 3)
        self.assertNotEqual(self.player.player.playbackState(), QMediaPlayer.PlaybackState.PlayingState)

    def test_shuffle_with_repeat_all_keeps_going(self):
        self.make_player(["One", "Two"], seconds=4, shuffle_on=True, repeat_mode="all")
        self.start("One")
        for _ in range(3):
            self.player.next_track(auto=True)
        self.assertEqual(len(self.played), 4)

    def test_queued_song_comes_before_the_forward_history(self):          # B11
        self.make_player(["One", "Two", "Three"], seconds=4)
        self.start("One")
        self.player.next_track()
        self.player.prev_track()                                  # back on One, Two is "forward"
        self.player.queue_add([str(self.songs[2])], play_next=True)
        self.player.next_track()
        self.assertEqual(self.title(), "Three")

    def test_reopening_continues_the_playlist_you_were_in(self):           # B15
        self.make_player(["One", "Two", "Three", "Four"], seconds=4, resume=True)
        p = self.player
        p.play_paths([str(self.songs[3]), str(self.songs[1])], "Mix", start=1)   # Four, Two: on Two
        self.assertTrue(wait_for(lambda: p.player.position() > 200))
        p.save_session()
        saved = json.loads(mp.CONFIG_FILE.read_text(encoding="utf-8"))
        self.assertEqual(saved["ctx_kind"], "Mix")
        self.close_player()
        again = mp.Player()
        self.addCleanup(lambda: (setattr(again, "quitting", True), again.close(), again.deleteLater()))
        self.assertTrue(wait_for(lambda: again.qindex and again.index >= 0, 8))
        self.assertEqual(again.ctx_kind, "Mix")
        self.assertEqual(again.ctx_paths, [str(self.songs[3]), str(self.songs[1])])
        self.assertEqual(again.ctx_pos, 1)
        self.assertGreater(saved["last_pos"], 0)

    def test_quitting_after_close_keeps_the_saved_spot(self):              # B6
        self.make_player(["One"], seconds=4, resume=True)
        p = self.player
        self.start("One")
        self.assertTrue(wait_for(lambda: p.player.position() > 500))
        self.close_player()                  # saves, then stops the song
        p.save_session()                     # what aboutToQuit does right after
        self.assertGreater(json.loads(mp.CONFIG_FILE.read_text(encoding="utf-8"))["last_pos"], 400)

    def test_mini_player_saved_off_screen_opens_on_screen(self):           # B7
        self.make_player(["One"], mini_pos=[-40000, -40000])          # its monitor was unplugged
        self.player.enter_mini()
        mini = self.player.mini
        self.assertIsNotNone(mp.QApplication.screenAt(mini.frameGeometry().center()))

    def test_quitting_from_the_mini_player_remembers_where_it_was(self):   # B16
        self.make_player(["One"])
        p = self.player
        p.enter_mini()
        p.mini.move(100, 120)
        with mock.patch.object(mp.QApplication.instance(), "quit"):
            p.quit_app()
        self.assertEqual(json.loads(mp.CONFIG_FILE.read_text(encoding="utf-8"))["mini_pos"], [100, 120])

    def test_skipping_ahead_does_not_count_as_listening(self):
        self.make_player(["One"], seconds=4)
        self.start("One")
        p = self.player
        self.assertTrue(wait_for(lambda: p.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState))
        p.listen_ms, p.last_pos = 0, None
        for pos in range(0, 18001, 900):     # twenty small jumps in no time at all
            p.on_position(pos)
        self.assertLess(p.listen_ms, 1000)

    def test_listening_time_is_counted(self):
        self.make_player(["One"], seconds=4)
        self.start("One")
        p = self.player
        self.assertTrue(wait_for(lambda: p.player.position() > 300))
        start_ms, start_pos = p.listen_ms, p.player.position()
        wait_for(lambda: False, 2)
        heard = p.player.position() - start_pos
        self.assertGreater(p.listen_ms - start_ms, heard * 0.8)

    def test_mute_survives_an_engine_switch(self):
        self.make_player(["One"], seconds=4)
        self.start("One")
        self.player.toggle_mute()
        self.player.switch_engine("Qt (built-in)")
        self.assertTrue(self.player.audio.isMuted())

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

    def test_audio_settings_reach_mpv_and_follow_changes(self):
        self.make_player(["One"], replaygain="Album", audio_exclusive=False)
        mpv_ = self.player.player.mp
        self.assertEqual(mpv_.replaygain, "album")
        self.player.apply_prefs({"replaygain": "Track"})
        self.assertEqual(mpv_.replaygain, "track")
        self.player.switch_engine("mpv")          # a new engine gets the same settings
        self.assertEqual(self.player.player.mp.replaygain, "track")

    def test_equalizer_works_with_mpv(self):
        self.make_player(["One"])
        dlg = mp.EqualizerDialog(self.player)
        self.assertTrue(hasattr(dlg, "preset"))           # the real equalizer, not the "needs VLC" note
        dlg.preset.setCurrentText("Rock")
        self.assertEqual(self.player.cfg["eq_preset"], "Rock")
        self.assertTrue(self.player.cfg["eq_enabled"])
        pre, bands = self.player.player._eq
        self.assertEqual((pre, bands), (5.0, [8.0, 4.8, -5.6, -8.0, -3.2, 4.0, 8.8, 11.2, 11.2, 11.2]))
        dlg.deleteLater()
        self.player.switch_engine("mpv")                  # a new engine starts with the same setting
        self.assertEqual(self.player.player._eq[0], 5.0)

    def test_settings_window_lists_output_devices(self):
        self.make_player(["One"])
        dlg = mp.PreferencesDialog(self.player.cfg, self.player)
        names = [dlg.audio_device.itemData(i) for i in range(dlg.audio_device.count())]
        self.assertEqual(names[0], "auto")
        self.assertEqual(dlg.values()["audio_device"], "auto")
        self.assertEqual(dlg.values()["replaygain"], "Off")
        dlg.deleteLater()

    def count_loads(self):
        loads = []
        real = self.player.player.setSource
        patcher = mock.patch.object(self.player.player, "setSource",
                                    side_effect=lambda url: (loads.append(Path(url.toLocalFile()).stem), real(url)))
        patcher.start()
        self.addCleanup(patcher.stop)
        return loads

    def test_songs_follow_each_other_without_reloading(self):
        self.make_player(["One", "Two", "Three"])
        loads = self.count_loads()
        self.start("One")
        self.assertTrue(wait_for(lambda: self.title() == "Three", 8))
        self.assertEqual(self.played, ["One", "Two", "Three"])
        self.assertEqual(loads, ["01 - One"])      # Two and Three were lined up, not loaded
        self.assertEqual(self.player.history[-3:], [str(s) for s in self.songs])

    def test_queueing_a_song_changes_what_follows(self):
        self.make_player(["One", "Two", "Three"], seconds=1.5)
        loads = self.count_loads()
        self.start("One")
        self.assertTrue(wait_for(lambda: self.player.player.position() > 200))
        self.player.queue_add([str(self.songs[2])], play_next=True)
        self.assertTrue(wait_for(lambda: self.title() == "Three", 8))
        self.assertEqual(self.played[:2], ["One", "Three"])
        self.assertEqual(loads, ["01 - One"])

    def test_shuffle_plays_the_song_it_lined_up(self):
        self.make_player(["One", "Two", "Three", "Four"], shuffle_on=True)
        loads = self.count_loads()
        self.start("One")
        self.assertTrue(wait_for(lambda: len(self.played) >= 4, 10))
        self.assertEqual(len(loads), 1)
        self.assertEqual(sorted(self.played[:4]), ["Four", "One", "Three", "Two"])

    def test_repeat_one_keeps_playing_the_same_song(self):
        self.make_player(["One", "Two"], repeat_mode="one")
        self.start("One")
        wait_for(lambda: False, 2.5)
        self.assertEqual(self.title(), "One")
        self.assertEqual(self.played, ["One"])
        self.assertEqual(self.player.player.playbackState(), QMediaPlayer.PlaybackState.PlayingState)


@unittest.skipUnless(mp.vlc is not None, "python-vlc / VLC not installed")
class VlcPlayerTest(PlayerTest):
    engine = "VLC"


if __name__ == "__main__":
    unittest.main()
