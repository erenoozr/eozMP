"""
Lyrics: the LRC [offset:] tag (A14), word timings like <00:01.50> (A15), files saved in Turkish
Windows encoding or UTF-16 (A16), and "Search online" replacing lyrics that were saved wrong.
lrclib.net is never asked: the lookups are answered by fakes.
Run from the project folder:   py -3 -m unittest discover tests -p "test_lyrics.py"
"""
import json
import unittest
from unittest import mock

from test_core import TempDirTest, mp, tagged_mp3
from test_mpv_engine import wait_for
from test_player import PlayerHarness


class LrcTest(unittest.TestCase):
    def test_offset_moves_every_line(self):
        """A14: a positive offset shows the lines earlier, a negative one later."""
        self.assertEqual(mp.parse_lrc("[offset:+500]\n[00:10.00]Hello\n[00:12.00]World"),
                         (True, [(9500, "Hello"), (11500, "World")]))
        self.assertEqual(mp.parse_lrc("[offset:-250]\n[00:10.00]Hello")[1], [(10250, "Hello")])
        self.assertEqual(mp.parse_lrc("[ar:Band]\n[offset: 1000]\n[00:00.50]Hi")[1], [(0, "Hi")])

    def test_word_timings_are_not_shown_as_text(self):
        """A15: enhanced LRC times every word; the line shows just the words."""
        text = "[00:10.00]<00:10.00>Hello <00:10.50>big <00:11.00>world<00:11.40>\n[00:12.00] <00:12.00> Again"
        self.assertEqual(mp.parse_lrc(text)[1], [(10000, "Hello big world"), (12000, "Again")])

    def test_plain_text_is_still_plain(self):
        self.assertEqual(mp.parse_lrc("Just words\n\nMore words\n"),
                         (False, [(None, "Just words"), (None, ""), (None, "More words")]))


class EncodingTest(TempDirTest):
    """A16: .lrc/.txt files come in whatever encoding the tool that wrote them liked."""
    TEXT = "Şarkı söyle, gönlüm: ığüşöç İĞÜŞÖÇ"

    def read(self, data):
        p = self.tmp / "song.lrc"
        p.write_bytes(data)
        return mp.read_text_file(str(p))

    def test_encodings(self):
        for name, data in (("utf-8", self.TEXT.encode("utf-8")),
                           ("utf-8 with BOM", b"\xef\xbb\xbf" + self.TEXT.encode("utf-8")),
                           ("cp1254 (Turkish Windows)", self.TEXT.encode("cp1254")),
                           ("utf-16 LE with BOM", self.TEXT.encode("utf-16")),
                           ("utf-16 BE with BOM", b"\xfe\xff" + self.TEXT.encode("utf-16-be")),
                           ("utf-16 LE without BOM", ("[00:01.00]" + self.TEXT).encode("utf-16-le"))):
            with self.subTest(name):
                self.assertTrue(self.read(data).endswith(self.TEXT), repr(self.read(data)))

    def test_windows_line_ends_become_plain_ones(self):
        self.assertEqual(self.read(b"[00:01.00]a\r\n[00:02.00]b\r\n"), "[00:01.00]a\n[00:02.00]b\n")

    def test_turkish_lrc_next_to_the_song(self):
        song = self.tmp / "song.mp3"
        tagged_mp3(song, title="Song", artist="Band")
        (self.tmp / "song.lrc").write_bytes(("[00:01.00]" + self.TEXT).encode("cp1254"))
        with mock.patch.object(mp, "LYRICS_DIR", self.tmp / "lyrics"):
            res = mp.get_lyrics(mp.read_track(str(song)), online=False, save_files=False)
        self.assertEqual(mp.parse_lrc(res["text"])[1], [(1000, self.TEXT)])


class EmbeddedLyricsTest(TempDirTest):
    def test_wma_lyrics(self):
        import audio_samples as s
        from mutagen import File
        p = s.ffmpeg_make(self.tmp / "a.wma", "wmav2")
        if p is None:
            self.skipTest("ffmpeg can't make a WMA file here")
        a = File(str(p))
        a["WM/Lyrics"] = ["La la la"]
        a.save()
        self.assertEqual(mp.embedded_lyrics(str(p)), "La la la")


class SearchOnlineTest(TempDirTest):
    """"Search online" asks lrclib again and replaces what eozMP saved before, but never your own file."""

    def setUp(self):
        super().setUp()
        self.song = self.tmp / "song.mp3"
        tagged_mp3(self.song, title="Song", artist="Band", album="Album")
        self.track = mp.read_track(str(self.song))
        self.answer = {"lrc": "[00:01.00]Wrong song", "plain": "", "instrumental": False}
        for name, value in (("LYRICS_DIR", self.tmp / "lyrics"), ("fetch_lrclib", self.fetch)):
            patcher = mock.patch.object(mp, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def fetch(self, artist, title, album, duration):
        if isinstance(self.answer, Exception):
            raise self.answer
        return dict(self.answer) if self.answer else None

    def lyrics(self, force=False, save=True):
        return mp.get_lyrics(self.track, online=True, save_files=save, force=force)

    def test_lyrics_saved_wrong_are_replaced(self):
        self.assertEqual(self.lyrics()["text"], "[00:01.00]Wrong song")
        self.assertTrue((self.tmp / "song.lrc").exists())
        self.answer = {"lrc": "[00:01.00]Right song", "plain": "", "instrumental": False}
        self.assertEqual(self.lyrics(force=True)["text"], "[00:01.00]Right song")
        self.assertEqual(mp.read_text_file(str(self.tmp / "song.lrc")), "[00:01.00]Right song")
        self.assertEqual(self.lyrics()["text"], "[00:01.00]Right song")           # and it stays

    def test_saved_lookup_without_a_file_is_replaced_too(self):
        self.lyrics(save=False)
        self.answer = {"lrc": "", "plain": "Right words", "instrumental": False}
        self.assertEqual(self.lyrics(force=True, save=False)["text"], "Right words")
        self.assertEqual(self.lyrics(save=False)["text"], "Right words")
        self.assertFalse((self.tmp / "song.lrc").exists() or (self.tmp / "song.txt").exists())

    def test_your_own_file_is_never_overwritten(self):
        (self.tmp / "song.lrc").write_text("[00:01.00]My own words", encoding="utf-8")
        self.answer = {"lrc": "[00:01.00]From lrclib", "plain": "", "instrumental": False}
        self.assertEqual(self.lyrics(force=True)["text"], "[00:01.00]From lrclib")    # shown now...
        self.assertEqual(mp.read_text_file(str(self.tmp / "song.lrc")), "[00:01.00]My own words")
        self.assertEqual(self.lyrics()["text"], "[00:01.00]My own words")             # ...yours stays first

    def test_nothing_new_online_keeps_what_you_have(self):
        self.lyrics()
        self.answer = None
        res = self.lyrics(force=True)
        self.assertEqual(res["text"], "[00:01.00]Wrong song")
        self.assertTrue(res.get("missed"))
        cached = json.loads(mp.lyrics_cache_path(self.track).read_text(encoding="utf-8"))
        self.assertTrue(cached["found"])          # a found lookup isn't thrown away

    def test_no_internet_keeps_what_you_have(self):
        self.lyrics()
        self.answer = OSError("no internet")
        res = self.lyrics(force=True)
        self.assertEqual((res["text"], res.get("error")), ("[00:01.00]Wrong song", "no internet"))

    def test_without_search_online_the_saved_lyrics_are_used(self):
        self.lyrics()
        self.answer = {"lrc": "[00:01.00]Right song", "plain": "", "instrumental": False}
        self.assertEqual(self.lyrics()["text"], "[00:01.00]Wrong song")


class SearchOnlineInPlayerTest(PlayerHarness):
    def test_search_online_replaces_what_is_shown(self):
        answer = {"lrc": "[00:01.00]Wrong song", "plain": "", "instrumental": False}
        fetch = mock.patch.object(mp, "fetch_lrclib", lambda *a: dict(answer) if answer else None)
        fetch.start()
        self.addCleanup(fetch.stop)
        self.make_player(["a"], lyrics_online=True, lyrics_save_lrc=True)
        folder = self.tmp / "music" / "Tagged"
        folder.mkdir()
        tagged_mp3(folder / "01 - Song.mp3", title="Song", artist="Band", album="Album")
        p = self.player
        p.rescan()
        self.assertTrue(wait_for(lambda: len(p.all_tracks) == 2 and not p.scanning))
        p.play_index(next(i for i, (t, _k) in enumerate(p.queue) if t["title"] == "Song"), autoplay=False)
        self.assertTrue(wait_for(lambda: p.lyric_lines == ["Wrong song"]))
        answer.update(lrc="[00:01.00]Right song")
        p.fetch_lyrics_online()
        self.assertTrue(wait_for(lambda: p.lyric_lines == ["Right song"]))
        answer.clear()
        p.fetch_lyrics_online()
        self.assertTrue(wait_for(lambda: p.statusBar().currentMessage() == "No other lyrics found online."))
        self.assertEqual(p.lyric_lines, ["Right song"])


if __name__ == "__main__":
    unittest.main()
