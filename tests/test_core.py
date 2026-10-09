"""
Tests for the parts of eozMP that touch your files (settings, playlists, downloads).
Run them from the project folder with:   python -m unittest discover tests
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import musicplayer as mp  # noqa: E402


def crash_halfway(self, data, *args, **kwargs):
    """Stand-in for Path.write_text: writes half the data, then 'the power goes out'."""
    with open(self, "w", encoding="utf-8") as f:
        f.write(data[: len(data) // 2])
    raise OSError("simulated crash while saving")


def tagged_mp3(path, **tags):
    """Write a tiny but valid MP3 (20 silent-ish frames) with the given tags."""
    from mutagen.easyid3 import EasyID3
    frame = b"\xff\xfb\x90\x64" + b"\0" * 413     # MPEG-1 Layer III, 128 kbps, 44.1 kHz
    Path(path).write_bytes(frame * 20)
    id3 = EasyID3()
    for key, value in tags.items():
        id3[key] = value
    id3.save(path)


class TempDirTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="eozmp-test-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class SaveSurvivesCrashTest(TempDirTest):
    """A crash while saving must not wipe what was saved before."""

    def test_settings_survive_crash_during_save(self):
        cfg_file = self.tmp / "settings.json"
        with mock.patch.object(mp, "CONFIG_FILE", cfg_file):
            mp.save_config({**mp.DEFAULT_CFG, "folders": ["D:/Music"]})
            with mock.patch.object(Path, "write_text", crash_halfway):
                mp.save_config({**mp.DEFAULT_CFG, "folders": ["D:/Music", "E:/More"]})
            self.assertEqual(mp.load_config()["folders"], ["D:/Music"])

    def test_playlists_survive_crash_during_save(self):
        pl_file = self.tmp / "playlists.json"
        with mock.patch.object(mp, "PLAYLIST_FILE", pl_file):
            mp.save_playlists({"Road trip": ["a.mp3", "b.mp3"]})
            with mock.patch.object(Path, "write_text", crash_halfway):
                mp.save_playlists({"Road trip": ["a.mp3", "b.mp3", "c.mp3"]})
            self.assertEqual(mp.load_playlists(), {"Road trip": ["a.mp3", "b.mp3"]})

    def test_stats_survive_crash_during_save(self):
        stats_file = self.tmp / "stats.json"
        with mock.patch.object(mp, "STATS_FILE", stats_file):
            stats = mp.load_stats()
            stats["favorites"] = ["a.mp3"]
            mp.save_stats(stats)
            with mock.patch.object(Path, "write_text", crash_halfway):
                stats["favorites"] = ["a.mp3", "b.mp3"]
                mp.save_stats(stats)
            self.assertEqual(mp.load_stats()["favorites"], ["a.mp3"])

    def test_no_temp_file_left_after_save(self):
        cfg_file = self.tmp / "settings.json"
        with mock.patch.object(mp, "CONFIG_FILE", cfg_file):
            mp.save_config(dict(mp.DEFAULT_CFG))
            with mock.patch.object(Path, "write_text", crash_halfway):
                mp.save_config(dict(mp.DEFAULT_CFG))
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir()), ["settings.json"])


class OrganizeDownloadsTest(TempDirTest):
    """Untagged files land in Unknown Artist/Unknown Album/<file name>."""

    def setUp(self):
        super().setUp()
        self.src = self.tmp / "downloads"
        self.dest = self.tmp / "library"
        self.album = self.dest / "Unknown Artist" / "Unknown Album"
        (self.src / "some user folder").mkdir(parents=True)
        self.album.mkdir(parents=True)

    def download(self, name, data):
        path = self.src / "some user folder" / name
        path.write_bytes(data)
        return path

    def test_same_size_but_different_song_is_kept(self):
        (self.album / "song.mp3").write_bytes(b"A" * 4096)
        self.download("song.mp3", b"B" * 4096)
        mp.organize_downloads(str(self.src), str(self.dest))
        self.assertEqual((self.album / "song.mp3").read_bytes(), b"A" * 4096)
        self.assertEqual((self.album / "song (2).mp3").read_bytes(), b"B" * 4096)

    def test_exact_duplicate_is_removed(self):
        (self.album / "song.mp3").write_bytes(b"A" * 4096)
        dup = self.download("song.mp3", b"A" * 4096)
        mp.organize_downloads(str(self.src), str(self.dest))
        self.assertFalse(dup.exists())
        self.assertEqual(sorted(p.name for p in self.album.iterdir()), ["song.mp3"])

    def test_second_run_is_skipped_while_one_is_already_running(self):
        new = self.download("new.mp3", b"C" * 100)
        with mp.ORGANIZE_LOCK:      # another organize is busy with the same folder
            moved = mp.organize_downloads(str(self.src), str(self.dest))
        self.assertEqual(moved, 0)
        self.assertTrue(new.exists())
        self.assertEqual(mp.organize_downloads(str(self.src), str(self.dest)), 1)

    def test_album_named_like_a_windows_device_is_still_moved(self):
        song = self.download("song.mp3", b"")
        tagged_mp3(song, artist="Band", album="NUL", title="Song", tracknumber="3")
        self.assertEqual(mp.organize_downloads(str(self.src), str(self.dest)), 1)
        self.assertFalse(song.exists())
        moved = [p for p in (self.dest / "Band").rglob("*.mp3")]
        self.assertEqual([p.name for p in moved], ["03 - Song.mp3"])


class SafeNameTest(unittest.TestCase):
    def test_windows_device_names_are_renamed(self):
        for name in ("CON", "con", "Nul", "AUX", "PRN", "COM1", "lpt9", "CON.flac"):
            with self.subTest(name=name):
                cleaned = mp.safe_name(name, "x")
                stem = cleaned.split(".")[0].upper()
                self.assertNotIn(stem, mp.WINDOWS_RESERVED_NAMES)

    def test_normal_names_are_untouched(self):
        for name in ("Conan", "Console", "Com Truise", "Nullsleep", "The Album"):
            with self.subTest(name=name):
                self.assertEqual(mp.safe_name(name, "x"), name)


if __name__ == "__main__":
    unittest.main()
