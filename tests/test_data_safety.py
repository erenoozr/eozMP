"""
More tests for things that could lose your music or settings:
organizing downloads, scanning folders that are offline, and settings files that can't be read.
"""
import copy
import json
import os
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from test_core import TempDirTest, mp, tagged_mp3


def make_junction(link, target):
    """Windows directory junction (no admin rights needed). Returns False if it can't be made."""
    if os.name != "nt":
        return False
    r = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True)
    return r.returncode == 0 and Path(link).exists()


class OrganizeKeepsFilesTest(TempDirTest):
    def setUp(self):
        super().setUp()
        self.src = self.tmp / "downloads"
        self.dest = self.tmp / "library"
        self.src.mkdir()
        self.dest.mkdir()

    def song(self, folder, name, **tags):
        folder.mkdir(parents=True, exist_ok=True)
        tagged_mp3(folder / name, **tags)
        return folder / name

    def test_song_reached_through_a_second_path_is_not_deleted(self):
        song = self.song(self.dest / "Band" / "Alb", "03 - T.mp3",
                         artist="Band", album="Alb", title="T", tracknumber="3")
        alias = self.tmp / "alias"
        if not make_junction(alias, self.dest):
            self.skipTest("can't create a junction here")
        mp.organize_downloads(str(alias), str(self.dest))
        self.assertTrue(song.exists())

    def test_album_extras_move_with_the_album(self):
        dl = self.src / "Band - Alb (2001)"
        for n in (1, 2):
            self.song(dl, f"track{n}.mp3", artist="Band", album="Alb", title=f"T{n}", tracknumber=str(n))
        (dl / "Alb.cue").write_text("cue")
        (dl / "rip.log").write_text("log")
        (dl / "Scans").mkdir()
        (dl / "Scans" / "back.png").write_bytes(b"png")
        self.assertEqual(mp.organize_downloads(str(self.src), str(self.dest)), 2)
        album = self.dest / "Band" / "Alb"
        self.assertEqual((album / "Alb.cue").read_text(), "cue")
        self.assertEqual((album / "rip.log").read_text(), "log")
        self.assertEqual((album / "Scans" / "back.png").read_bytes(), b"png")
        self.assertFalse(dl.exists())

    def test_extras_stay_when_a_folder_holds_two_albums(self):
        dl = self.src / "mixed"
        self.song(dl, "a.mp3", artist="Band", album="One", title="A", tracknumber="1")
        self.song(dl, "b.mp3", artist="Band", album="Two", title="B", tracknumber="1")
        (dl / "notes.txt").write_text("mine")
        mp.organize_downloads(str(self.src), str(self.dest))
        self.assertEqual((dl / "notes.txt").read_text(), "mine")

    def test_nothing_else_in_the_downloads_folder_itself_is_touched(self):
        self.song(self.src, "song.mp3", artist="Band", album="Alb", title="S", tracknumber="1")
        (self.src / "holiday.jpg").write_bytes(b"photo")
        mp.organize_downloads(str(self.src), str(self.dest))
        self.assertEqual((self.src / "holiday.jpg").read_bytes(), b"photo")

    def test_collaboration_setting_is_respected(self):
        self.song(self.src / "x", "s.mp3", artist="Foo & Bar", album="Alb", title="S", tracknumber="1")
        mp.organize_downloads(str(self.src), str(self.dest), split_collabs=False)
        self.assertTrue((self.dest / "Foo & Bar" / "Alb" / "01 - S.mp3").exists())

    def test_keep_together_list_is_respected(self):
        self.song(self.src / "x", "s.mp3", artist="Foo & Bar", album="Alb", title="S", tracknumber="1")
        mp.organize_downloads(str(self.src), str(self.dest), keep={"foo & bar"})
        self.assertTrue((self.dest / "Foo & Bar" / "Alb" / "01 - S.mp3").exists())


class ScanTest(TempDirTest):
    def test_offline_folder_keeps_its_songs(self):
        lib = self.tmp / "usb"
        song = lib / "a.mp3"
        lib.mkdir()
        tagged_mp3(song, artist="Band", album="Alb", title="A")
        cache = mp.scan_folders([str(lib)])
        lib.rename(self.tmp / "unplugged")
        tracks = mp.scan_folders([str(lib)], cache)
        self.assertEqual([t["path"] for t in tracks], [str(song)])

    def test_songs_from_removed_folders_are_dropped(self):
        lib = self.tmp / "old"
        lib.mkdir()
        tagged_mp3(lib / "a.mp3", artist="Band", album="Alb", title="A")
        cache = mp.scan_folders([str(lib)])
        self.assertEqual(mp.scan_folders([], cache), [])

    def test_same_folder_written_two_ways_counts_once(self):
        lib = self.tmp / "Music"
        (lib / "Soulseek").mkdir(parents=True)
        tagged_mp3(lib / "Soulseek" / "a.mp3", artist="Band", album="Alb", title="A")
        tracks = mp.scan_folders([str(lib).replace("\\", "/"), str(lib / "Soulseek").upper()])
        self.assertEqual(len(tracks), 1)

    def test_locked_file_is_read_again_next_time(self):
        lib = self.tmp / "lib"
        lib.mkdir()
        tagged_mp3(lib / "a.mp3", artist="Band", album="Alb", title="A")
        with mock.patch.object(mp, "MutagenFile", side_effect=PermissionError("locked")):
            first = mp.scan_folders([str(lib)])
        self.assertEqual(first[0]["artist"], "Unknown Artist")
        again = mp.scan_folders([str(lib)], first)
        self.assertEqual(again[0]["artist"], "Band")


class SettingsFilesTest(TempDirTest):
    def patch_files(self):
        files = {"CONFIG_FILE": self.tmp / "s.json", "PLAYLIST_FILE": self.tmp / "p.json",
                 "STATS_FILE": self.tmp / "st.json"}
        for name, path in files.items():
            patcher = mock.patch.object(mp, name, path)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(mp, "LOAD_PROBLEMS", [])
        patcher.start()
        self.addCleanup(patcher.stop)
        return files

    def test_files_saved_with_a_bom_still_load(self):
        f = self.patch_files()
        bom = b"\xef\xbb\xbf"
        f["STATS_FILE"].write_bytes(bom + json.dumps({"favorites": ["a.mp3"]}).encode())
        f["PLAYLIST_FILE"].write_bytes(bom + json.dumps({"Mix": ["a.mp3"]}).encode())
        f["CONFIG_FILE"].write_bytes(bom + json.dumps({"folders": ["D:/Music"]}).encode())
        self.assertEqual(mp.load_stats()["favorites"], ["a.mp3"])
        self.assertEqual(mp.load_playlists(), {"Mix": ["a.mp3"]})
        self.assertEqual(mp.load_config()["folders"], ["D:/Music"])

    def test_unreadable_file_is_kept_aside_before_defaults_are_used(self):
        f = self.patch_files()
        f["STATS_FILE"].write_text("{not json", encoding="utf-8")
        stats = mp.load_stats()
        self.assertEqual(stats["favorites"], [])
        copies = list(self.tmp.glob("st.json.corrupt-*"))
        self.assertEqual(len(copies), 1)
        self.assertEqual(copies[0].read_text(encoding="utf-8"), "{not json")
        self.assertEqual(len(mp.LOAD_PROBLEMS), 1)

    def test_wrong_kind_of_data_is_kept_aside_too(self):
        f = self.patch_files()
        f["PLAYLIST_FILE"].write_text("[1, 2, 3]", encoding="utf-8")
        self.assertEqual(mp.load_playlists(), {})
        self.assertEqual(len(list(self.tmp.glob("p.json.corrupt-*"))), 1)

    def test_file_locked_for_a_moment_is_read_after_a_retry(self):
        f = self.patch_files()
        f["CONFIG_FILE"].write_text(json.dumps({"volume": 12}), encoding="utf-8")
        real = Path.read_text
        calls = []

        def locked_once(path, *a, **k):
            calls.append(path)
            if len(calls) == 1:
                raise PermissionError("in use by another process")
            return real(path, *a, **k)

        with mock.patch.object(Path, "read_text", locked_once), mock.patch.object(mp.time, "sleep"):
            self.assertEqual(mp.load_config()["volume"], 12)
        self.assertEqual(mp.LOAD_PROBLEMS, [])

    def test_missing_files_are_not_a_problem(self):
        self.patch_files()
        mp.load_config(); mp.load_playlists(); mp.load_stats()
        self.assertEqual(mp.LOAD_PROBLEMS, [])

    def test_loaded_settings_never_change_the_defaults(self):
        self.patch_files()
        before = copy.deepcopy(mp.DEFAULT_CFG)
        cfg = mp.load_config()
        cfg["folders"].append("D:/Music")
        cfg["keep_together"].append("x")
        self.assertEqual(mp.DEFAULT_CFG, before)

    def test_setting_with_the_wrong_type_falls_back_to_default(self):
        f = self.patch_files()
        f["CONFIG_FILE"].write_text(json.dumps({"ui_font_size": "big", "volume": 40, "resume": False}))
        cfg = mp.load_config()
        self.assertEqual(cfg["ui_font_size"], mp.DEFAULT_CFG["ui_font_size"])
        self.assertEqual(cfg["volume"], 40)
        self.assertIs(cfg["resume"], False)


if __name__ == "__main__":
    unittest.main()
