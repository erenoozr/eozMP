"""
Errors nobody expected must not close the player: they go to a log file and the status bar.
"""
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

from test_core import TempDirTest, mp
from test_mpv_engine import wait_for
from test_player import PlayerHarness
from test_silent_and_duplicates import FakeTV, free_port


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


class OrganizeTimingTest(PlayerHarness):
    @staticmethod
    def downloads(finished, queued):
        files = [{"id": f"f{i}", "filename": f"x_{i}.mp3", "size": 1, "state": "Completed, Succeeded"}
                 for i in range(finished)]
        files += [{"id": f"q{i}", "filename": f"x_q{i}.mp3", "size": 1, "state": "Queued, Remotely"}
                  for i in range(queued)]
        return [{"username": "u", "directories": [{"files": files}]}]

    def test_a_compilation_is_sorted_only_when_all_its_files_are_in(self):      # B11
        self.make_player(["One"])
        p = self.player
        calls = []
        p.after_downloads_finished = lambda: calls.append(1)
        p.on_downloads(self.downloads(1, 2))        # first answer: nothing to do
        p.on_downloads(self.downloads(2, 1))        # one more arrived, two still to come
        self.assertEqual(calls, [])
        p.on_downloads(self.downloads(3, 0))        # the last one is in
        self.assertEqual(calls, [1])
        p.on_downloads(self.downloads(3, 0))
        self.assertEqual(calls, [1])                # and it is not repeated


class RestoreTest(unittest.TestCase):
    def test_a_backup_cannot_change_what_is_loaded_or_opened_to_the_network(self):    # S1
        theirs = json.dumps({"volume": 40, "mpv_dir": r"\\evil\share", "remote_on": True,
                             "remote_token": "known", "slskd_url": "http://evil:5030",
                             "downloads_dir": r"Z:\x"}).encode()
        mine = {"volume": 10, "mpv_dir": "C:/mpv", "remote_on": False, "slskd_url": "http://localhost:5030"}
        out = json.loads(mp.keep_local_settings(theirs, mine))
        self.assertEqual(out["volume"], 40)                       # ordinary settings do come back
        self.assertEqual(out["mpv_dir"], "C:/mpv")
        self.assertFalse(out["remote_on"])
        self.assertNotIn("remote_token", out)
        self.assertEqual(out["slskd_url"], "http://localhost:5030")
        self.assertNotIn("downloads_dir", out)

    def test_backup_file_names_must_be_plain(self):                                      # S2
        for bad in ("D:planted.json", r"..\x.json", "a/b.json", "x.json:stream", "con:.json", "x.txt", ".json"):
            self.assertFalse(mp.safe_backup_name(bad), bad)
        for good in ("Song Name.json", "it's (live) & more.json", "Gül - Şarkı.json"):
            self.assertTrue(mp.safe_backup_name(good), good)


class TagFixDefaultsTest(PlayerHarness):
    def test_enter_does_not_apply_the_tags(self):                                       # U2
        from PyQt6.QtWidgets import QPushButton as Btn
        self.make_player(["One"])
        t = self.player.all_tracks[0]
        new = {"artist": "A", "title": "T", "album": "Al", "tracknumber": "1", "date": "2000"}
        dlg = mp.TagFixDialog(self.player, [t], {t["path"]: ("rid", new)}, {"rid": {"title": "Al"}})
        buttons = {b.text(): b for b in dlg.findChildren(Btn)}
        self.assertFalse(buttons["Apply to ticked songs"].autoDefault())
        self.assertTrue(buttons["Cancel"].isDefault())
        dlg.deleteLater()


class CastTest(PlayerHarness):
    def setUp(self):
        super().setUp()
        self.make_player(["One", "Two"], seconds=5.0, remote_port=free_port())
        self.p = self.player
        self.tv = FakeTV()
        self.addCleanup(self.tv.close)
        self.addCleanup(lambda: self.p.set_remote(False))

    def test_a_tv_that_refuses_gives_the_pc_its_sound_back(self):               # B23, U4
        bad = FakeTV(fail=True)
        self.addCleanup(bad.close)
        self.p.play_from_library(0)
        self.p.start_cast(bad.device)
        self.assertTrue(self.p.audio.isMuted())
        self.assertTrue(wait_for(lambda: self.p.cast is None, 5))
        self.assertFalse(self.p.audio.isMuted())
        self.assertIn("Couldn't play", self.p.statusBar().currentMessage())

    def test_casting_does_not_leave_the_remote_on(self):                         # S7, U5
        p = self.p
        p.start_cast(self.tv.device)
        self.assertIsNotNone(p.remote)
        self.assertFalse(json.loads(mp.CONFIG_FILE.read_text(encoding="utf-8"))["remote_on"])
        p.stop_cast()
        self.assertIsNone(p.remote)
        self.assertFalse(p.cfg["remote_on"])

    def test_a_remote_you_turned_on_stays_after_casting(self):
        p = self.p
        p.set_remote(True)
        p.start_cast(self.tv.device)
        p.stop_cast()
        self.assertIsNotNone(p.remote)
        self.assertTrue(p.cfg["remote_on"])

    def test_switching_the_remote_off_ends_phone_listening(self):                # B20
        p = self.p
        p.set_remote(True)
        p.on_remote_command("mute", "1")
        self.assertTrue(p.audio.isMuted())
        p.set_remote(False)
        self.assertFalse(p.audio.isMuted())

    def test_the_tv_joins_a_song_in_the_middle(self):                            # B21
        p = self.p
        p.start_cast(self.tv.device)
        p.player.position = lambda: 4000
        track, _key = p.queue[0]
        p.cast_load(track, "id")
        self.assertTrue(wait_for(lambda: "Seek" in self.tv.actions, 3))

    def test_the_volume_slider_reaches_the_tv(self):                             # U6
        p = self.p
        p.start_cast(self.tv.device)
        p.volume.setValue(33)
        self.assertTrue(wait_for(lambda: "SetVolume" in self.tv.actions, 3))

    def test_odd_numbers_from_the_network_do_not_crash(self):                    # S6
        p = self.p
        for do, value in (("seek", "1e400"), ("seek", "nan"), ("vol", "1e30"), ("vol", "-inf"), ("seek", "x")):
            p.on_remote_command(do, value)
        p.on_remote_command("vol", "1e30")
        self.assertEqual(p.volume.value(), 100)

    def test_the_phone_page_does_not_skip_songs_itself(self):                    # B3
        self.assertNotIn("onended", mp.REMOTE_PAGE)

    def test_only_http_addresses_of_the_device_itself_are_trusted(self):         # S3
        self.assertTrue(mp.device_url_ok("http://192.168.1.5:49152/d.xml", "192.168.1.5"))
        self.assertFalse(mp.device_url_ok("file:///C:/Windows/win.ini"))
        self.assertFalse(mp.device_url_ok("http://192.168.1.66/d.xml", "192.168.1.5"))
        self.assertFalse(mp.device_url_ok("//192.168.1.66/share/x", "192.168.1.66"))


class RemoteServerTest(TempDirTest):
    def request(self, port, path, headers=None):
        import http.client
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        c.request("GET", path, headers=headers or {})
        r = c.getresponse()
        body = r.read()
        c.close()
        return r.status, body

    def test_bad_ranges_get_an_answer(self):                                     # S8
        song = self.tmp / "s.mp3"
        song.write_bytes(b"x" * 1000)
        port = free_port()
        srv = mp.RemoteServer("tok", port)
        srv.files["abc"] = str(song)
        srv.start()
        self.addCleanup(srv.stop)
        url = "/tok/stream/abc.mp3"
        self.assertEqual(self.request(port, url, {"Range": "bytes=10-5"})[0], 416)
        self.assertEqual(self.request(port, url, {"Range": "bytes=5000-"})[0], 416)
        self.assertEqual(self.request(port, url, {"Range": "bytes=" + "9" * 5000 + "-"})[0], 200)
        status, body = self.request(port, url, {"Range": "bytes=10-19"})
        self.assertEqual((status, len(body)), (206, 10))
        self.assertEqual(self.request(port, url)[0], 200)


if __name__ == "__main__":
    unittest.main()
