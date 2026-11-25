"""
Sharing the library on Soulseek: eozMP's part of slskd.yml, the rescan it asks slskd for (against a small fake
slskd on this PC), the one-time notice and the Sharing tab. slskd.yml is always a temp file here, never yours.
Run alone with:   python -m unittest discover tests -p "test_sharing.py"
"""
import json
import os
import re
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from test_core import TempDirTest, mp  # noqa: E402
from test_mpv_engine import wait_for  # noqa: E402
from test_player import PlayerHarness  # noqa: E402

INSTALLER_YML = ("# Written by the eozMP installer.\r\nsoulseek:\r\n  username: \"me\"\r\n  password: \"pw\"\r\n\r\n"
                 "directories:\r\n  downloads: 'C:\\Music\\Soulseek'\r\n\r\n"
                 "# eozMP shares your music library: change it in eozMP > Preferences > Sharing.\r\n")


class FakeSlskd(BaseHTTPRequestHandler):
    put_answers = []      # HTTP codes for the next PUT /shares calls (then 204)
    puts = []
    shares = {}

    def answer(self, code, body=None):
        raw = json.dumps(body).encode() if body is not None else b""
        self.send_response(code)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/api/v0/application" and self.headers.get("X-API-Key") == "key":
            return self.answer(200, {"shares": self.shares})
        self.answer(404)

    def do_PUT(self):
        if self.path != "/api/v0/shares" or self.headers.get("X-API-Key") != "key":
            return self.answer(404)
        FakeSlskd.puts.append(self.path)
        self.answer(FakeSlskd.put_answers.pop(0) if FakeSlskd.put_answers else 204)

    def log_message(self, *_args):
        pass


def start_fake(test):
    FakeSlskd.put_answers, FakeSlskd.puts, FakeSlskd.shares = [], [], {}
    httpd = HTTPServer(("127.0.0.1", 0), FakeSlskd)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    test.addCleanup(httpd.server_close)
    test.addCleanup(httpd.shutdown)
    return f"http://127.0.0.1:{httpd.server_port}"


class ShareBlockTest(unittest.TestCase):
    def test_block_is_added_at_the_end_and_crlf_is_kept(self):
        out = mp.with_share_block(INSTALLER_YML, ["C:\\Users\\x\\Music"])
        self.assertTrue(out.startswith(INSTALLER_YML))
        self.assertEqual(out.count("\n"), out.count("\r\n"))
        self.assertTrue(out.endswith(mp.SHARE_END + "\r\n"))
        self.assertIn("shares:\r\n  directories:\r\n    - '[Music]C:\\Users\\x\\Music'\r\n", out)

    def test_block_is_replaced_not_added_twice(self):
        once = mp.with_share_block(INSTALLER_YML, ["C:\\A\\Music"])
        twice = mp.with_share_block(once, ["D:\\Songs"])
        self.assertEqual(twice.count(mp.SHARE_END), 1)
        self.assertNotIn("C:\\A\\Music", twice)
        self.assertIn("'[Songs]D:\\Songs'", twice)
        self.assertEqual(mp.with_share_block(twice, ["D:\\Songs"]), twice)

    def test_sharing_nothing_takes_the_block_out(self):
        on = mp.with_share_block(INSTALLER_YML, ["C:\\Music"])
        self.assertEqual(mp.with_share_block(on, []), INSTALLER_YML)
        self.assertEqual(mp.with_share_block(INSTALLER_YML, []), INSTALLER_YML)

    def test_lf_file_stays_lf(self):
        lf = INSTALLER_YML.replace("\r\n", "\n")
        out = mp.with_share_block(lf, ["C:\\Music"])
        self.assertNotIn("\r", out)
        self.assertTrue(out.startswith(lf))

    def test_users_own_shares_are_left_alone(self):
        own = INSTALLER_YML + "shares:\r\n  directories:\r\n    - D:\\Mine\r\n"
        self.assertIsNone(mp.with_share_block(own, ["C:\\Music"]))
        self.assertIsNone(mp.with_share_block(own, []))
        # an indented "shares:" belongs to something else; a commented one is no setting
        self.assertIsNotNone(mp.with_share_block(INSTALLER_YML + "web:\r\n  shares: x\r\n# shares:\r\n", []))

    def test_missing_end_mark_leaves_the_file_alone(self):
        broken = INSTALLER_YML + mp.SHARE_BEGIN + "\r\nshares:\r\n  directories:\r\n    - 'C:\\Music'\r\n"
        self.assertIsNone(mp.with_share_block(broken, []))

    def test_only_music_files_pass_the_filters(self):
        # slskd checks folders with the same patterns (ignoring case), so folder names must pass too
        left_out = lambda path: any(re.search(f, path, re.I) for f in mp.SHARE_FILTERS)
        for path in ("D:\\M\\a\\01.mp3", "D:\\M\\a\\01 Song.FLAC", "D:\\M\\a\\x.opus", "D:\\M\\R.E.M",
                     "D:\\M\\Vol.10", "D:\\M\\Vol.II", "D:\\M\\Mr. Bungle", "D:\\M\\Album (2004) [FLAC]"):
            self.assertFalse(left_out(path), path)
        for path in ("D:\\M\\a\\cover.jpg", "D:\\M\\a\\x.lrc", "D:\\M\\a\\tax.PDF", "D:\\M\\a\\v.mp4",
                     "D:\\M\\a\\x.docx", "D:\\M\\a\\b.torrent", "D:\\M\\a\\x.7z"):
            self.assertTrue(left_out(path), path)
        self.assertIn("  filters:", mp.share_block(["C:\\Music"]))

    def test_quotes_are_doubled(self):
        line = mp.share_block(["C:\\Rock 'n' Roll"])[3]
        self.assertEqual(line, "    - '[Rock ''n'' Roll]C:\\Rock ''n'' Roll'")

    def test_same_folder_names_get_their_own_alias(self):
        lines = mp.share_block(["C:\\Music", "D:\\music", "E:\\Music", "F:\\", "G:\\[odd]"])[3:-2 - len(mp.SHARE_FILTERS)]
        self.assertEqual(lines, ["    - '[Music]C:\\Music'", "    - '[music 2]D:\\music'", "    - '[Music 3]E:\\Music'",
                                 "    - '[Drive F]F:\\'", "    - '[odd]G:\\[odd]'"])


class SharedFoldersTest(TempDirTest):
    def test_missing_nested_and_repeated_folders_are_dropped(self):
        music, dl, extra = self.tmp / "Music", self.tmp / "Music" / "Soulseek", self.tmp / "Extra"
        for d in (dl, extra):
            d.mkdir(parents=True)
        cfg = {"folders": [str(music), str(self.tmp / "gone")], "downloads_dir": str(dl),
               "share_extra": [str(extra), str(music).upper(), "relative\\path", ""]}
        self.assertEqual(mp.shared_folders(cfg), [str(music), str(extra)])

    def test_a_folder_inside_a_later_one_goes_too(self):
        outer, inner = self.tmp / "All", self.tmp / "All" / "Rock"
        inner.mkdir(parents=True)
        cfg = {"folders": [str(inner)], "downloads_dir": "", "share_extra": [str(outer)]}
        self.assertEqual(mp.shared_folders(cfg), [str(outer)])

    def test_whole_drives_and_the_home_folder_are_never_shared(self):
        music = self.tmp / "Music"
        music.mkdir()
        home = mp.Path.home()
        cfg = {"folders": ["C:\\", str(home), str(home.parent), str(music)], "downloads_dir": ""}
        self.assertEqual(mp.shared_folders(cfg), [str(music)])
        self.assertFalse(mp.unsafe_to_share(str(home / "Music")))

    def test_a_name_that_only_starts_the_same_is_not_inside(self):
        a, b = self.tmp / "Music", self.tmp / "Music2"
        a.mkdir()
        b.mkdir()
        self.assertEqual(mp.shared_folders({"folders": [str(a), str(b)], "downloads_dir": ""}), [str(a), str(b)])


class WriteSettingsTest(TempDirTest):
    def setUp(self):
        super().setUp()
        self.yml = self.tmp / "slskd.yml"
        patcher = mock.patch.object(mp, "SLSKD_YML", self.yml)   # nothing may reach the real one
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_write_keeps_bom_and_settings_and_says_same_after(self):
        self.yml.write_bytes(b"\xef\xbb\xbf" + INSTALLER_YML.encode("utf-8"))
        self.assertEqual(mp.write_share_settings(["C:\\Müzik"]), "written")
        raw = self.yml.read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf" + INSTALLER_YML.encode("utf-8")))
        self.assertIn("'[Müzik]C:\\Müzik'".encode("utf-8"), raw)
        self.assertEqual(mp.write_share_settings(["C:\\Müzik"]), "same")
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir()), ["slskd.yml"])   # no temp file left
        self.assertEqual(mp.write_share_settings([]), "written")
        self.assertEqual(self.yml.read_bytes(), b"\xef\xbb\xbf" + INSTALLER_YML.encode("utf-8"))

    def test_users_own_shares_file_is_untouched(self):
        own = (INSTALLER_YML + "shares:\r\n  directories:\r\n    - D:\\Mine\r\n").encode()
        self.yml.write_bytes(own)
        self.assertEqual(mp.write_share_settings(["C:\\Music"]), "user")
        self.assertEqual(self.yml.read_bytes(), own)
        self.assertIn("leaves sharing to you", mp.share_problem({"share_enabled": True, "slskd_key": "k",
                                                                 "slskd_url": "http://localhost:5030"}))

    def test_reasons_not_to_share(self):
        cfg = {"share_enabled": True, "slskd_key": "k", "slskd_url": "http://localhost:5030"}
        self.assertIn("wasn't found", mp.share_problem(cfg))
        self.yml.write_text(INSTALLER_YML, encoding="utf-8")
        self.assertEqual(mp.share_problem(cfg), "")
        self.assertEqual(mp.share_problem(dict(cfg, share_enabled=False)), "Sharing is off.")
        self.assertIn("another computer", mp.share_problem(dict(cfg, slskd_url="http://192.168.1.5:5030")))
        self.assertIn("Set up Soulseek", mp.share_problem(dict(cfg, slskd_key="")))


class RescanTest(unittest.TestCase):
    def setUp(self):
        mp.STOP_BG.clear()           # an earlier test's shutdown leaves it set
        self.client = mp.Slskd(start_fake(self), "key")

    def test_rescan_waits_out_a_running_scan(self):
        FakeSlskd.put_answers = [409, 409]
        self.assertTrue(mp.rescan_shares(self.client, wait=0, pause=0.01))
        self.assertEqual(len(FakeSlskd.puts), 3)

    def test_rescan_gives_up_with_the_reason(self):
        FakeSlskd.put_answers = [409] * 5
        with self.assertRaises(RuntimeError) as cm:
            mp.rescan_shares(self.client, wait=0, tries=3, pause=0.01)
        self.assertIn("409", str(cm.exception))

    def test_status_lines(self):
        self.assertEqual(mp.share_status_text({"files": 1200, "directories": 80, "ready": True}),
                         "slskd shares 1200 files in 80 folders.")
        self.assertEqual(mp.share_status_text({"scanning": True, "scanProgress": 0.42}),
                         "slskd is scanning the shared folders... 42%")
        self.assertIn("in a moment", mp.share_status_text({"scanPending": True}))
        self.assertIn("couldn't scan", mp.share_status_text({"faulted": True}))


class SharingPlayerTest(PlayerHarness):
    """The real window: the notice, writing slskd.yml + the rescan, and the Sharing tab."""

    def setUp(self):
        super().setUp()
        mp.STOP_BG.clear()
        self.url = start_fake(self)

    def start_player(self, **cfg):
        patcher = mock.patch.object(mp, "run_dialog", return_value=0)   # the notice is "closed" unless a test says
        self.dialog = patcher.start()
        self.addCleanup(patcher.stop)
        self.make_player(["One"], slskd_url=self.url, slskd_key="key", **cfg)
        mp.SLSKD_YML.write_text(INSTALLER_YML, encoding="utf-8", newline="")
        return self.player

    def wait_idle(self):
        self.assertTrue(wait_for(lambda: not self.player.workers, 20))

    def test_closing_the_notice_turns_sharing_off(self):
        p = self.start_player()
        p.share_notice()
        self.assertTrue(p.cfg["share_notice_shown"])
        self.assertFalse(p.cfg["share_enabled"])
        self.wait_idle()
        self.assertEqual(mp.SLSKD_YML.read_bytes().decode(), INSTALLER_YML)
        self.dialog.reset_mock()
        p.share_notice()
        self.dialog.assert_not_called()        # only once

    def test_ok_on_the_notice_shares_the_library_and_rescans(self):
        p = self.start_player()

        def press_ok(box):
            box.clickedButton = lambda: next(b for b in box.buttons() if b.text() == "Share my music")
            return 0
        self.dialog.side_effect = press_ok
        p.share_notice()
        self.assertTrue(p.cfg["share_enabled"])
        self.assertTrue(wait_for(lambda: FakeSlskd.puts, 20), "no rescan asked for")
        self.wait_idle()
        text = mp.SLSKD_YML.read_bytes().decode()
        self.assertIn(f"'[music]{self.tmp / 'music'}'", text)
        # off in Preferences: the part goes again
        p.apply_prefs({"share_enabled": False})
        self.assertTrue(wait_for(lambda: mp.SLSKD_YML.read_bytes().decode() == INSTALLER_YML, 10))
        self.wait_idle()

    def test_nothing_is_written_before_the_notice(self):
        p = self.start_player()
        p.apply_sharing()
        self.wait_idle()
        self.assertEqual(mp.SLSKD_YML.read_bytes().decode(), INSTALLER_YML)

    def test_sharing_tab_lists_folders_and_slskd_count(self):
        FakeSlskd.shares = {"files": 7, "directories": 2, "ready": True}
        p = self.start_player(share_notice_shown=True, share_enabled=True)
        dlg = mp.PreferencesDialog(p.cfg, p, tab="Sharing")
        self.addCleanup(dlg.deleteLater)
        self.assertIs(dlg.tabs.currentWidget(), dlg.share_page)
        self.assertEqual([dlg.share_auto.item(i).text() for i in range(dlg.share_auto.count())],
                         [str(self.tmp / "music")])
        self.assertTrue(wait_for(lambda: dlg.share_status.text() == "slskd shares 7 files in 2 folders.", 10))
        dlg.share_on.setChecked(False)
        dlg.share_extra.addItem("D:\\More")
        self.assertEqual((dlg.values()["share_enabled"], dlg.values()["share_extra"]), (False, ["D:\\More"]))
        self.wait_idle()

    def test_sharing_tab_says_a_whole_drive_is_not_shared(self):
        p = self.start_player(share_notice_shown=True, share_enabled=True)
        cfg = dict(p.cfg, folders=[*p.cfg["folders"], "C:\\"])
        dlg = mp.PreferencesDialog(cfg, p, tab="Sharing")
        self.addCleanup(dlg.deleteLater)
        self.assertTrue(any(lab.text().startswith("Not shared, because") and "C:\\" in lab.text()
                            for lab in dlg.share_page.findChildren(mp.QLabel)))
        self.wait_idle()


if __name__ == "__main__":
    unittest.main()
