"""
Reading tags from every format eozMP plays (A17), the year of a date (A18), and keeping a song's own
artist apart from its album's artist (A4: compilations and soundtracks).
Run from the project folder:   py -3 -m unittest discover tests -p "test_tags.py"
"""
import unittest

from mutagen import File
from mutagen.id3 import TALB, TBPM, TCON, TDRC, TIT2, TPE1, TPE2, TPOS, TRCK

import audio_samples as s
from test_core import TempDirTest, mp, tagged_mp3

FULL = dict(title="Song", album="Album", num=3, disc=2, year=2019, genre="Rock", bpm=120, artist="Band")


def id3_full():
    return [TIT2(encoding=3, text="Song"), TPE1(encoding=3, text="Singer"), TPE2(encoding=3, text="Band"),
            TALB(encoding=3, text="Album"), TRCK(encoding=3, text="3/12"), TPOS(encoding=3, text="2/2"),
            TDRC(encoding=3, text="2019-05-03"), TCON(encoding=3, text="Rock"), TBPM(encoding=3, text="120")]


class FormatTagsTest(TempDirTest):
    """A17: the same tags, whatever the file format keeps them as."""

    def check(self, path, **expect):
        t = mp.read_track(str(path))
        want = {**FULL, **expect}
        self.assertEqual({k: t[k] for k in want}, want)
        self.assertGreater(t["length"], 0)
        return t

    def test_mp3(self):
        p = self.tmp / "a.mp3"
        tagged_mp3(p, title="Song", artist="Singer", albumartist="Band", album="Album", tracknumber="3/12",
                   discnumber="2", date="2019", genre="Rock", bpm="120")
        self.check(p)

    def test_aiff_id3(self):
        p = s.aiff(self.tmp / "a.aiff")
        s.id3_frames(p, id3_full())
        self.check(p)

    def test_wav_id3(self):
        p = s.wav(self.tmp / "a.wav")
        s.id3_frames(p, id3_full())
        self.check(p)

    def test_wav_riff_info(self):
        p = s.wav(self.tmp / "a.wav")
        s.add_riff_info(p, {"INAM": "Song", "IART": "Singer", "IPRD": "Album", "ICRD": "2019-05-03",
                            "IGNR": "Rock", "ITRK": "3"})
        self.check(p, artist="Singer", disc=1, bpm=0)

    def test_wav_riff_info_in_turkish_windows_encoding(self):
        p = s.wav(self.tmp / "a.wav")
        s.add_riff_info(p, {"INAM": "Gül Döktüm Yollarına", "IART": "Barış Manço"}, encoding="cp1254")
        t = mp.read_track(str(p))
        self.assertEqual((t["title"], t["artist"]), ("Gül Döktüm Yollarına", "Barış Manço"))

    def test_wav_id3_wins_over_riff_info(self):
        p = s.wav(self.tmp / "a.wav")
        s.add_riff_info(p, {"INAM": "Old name", "IGNR": "Pop"})
        s.id3_frames(p, [TIT2(encoding=3, text="Song")])
        t = mp.read_track(str(p))
        self.assertEqual((t["title"], t["genre"]), ("Song", "Pop"))

    def test_flac(self):
        p = s.flac(self.tmp / "a.flac")
        a = File(str(p))
        a.update({"title": "Song", "artist": "Singer", "albumartist": "Band", "album": "Album",
                  "tracknumber": "3", "discnumber": "2", "date": "2019", "genre": "Rock", "bpm": "120"})
        a.save()
        self.check(p)

    def test_vorbis_album_artist_spelled_with_a_space(self):
        p = s.vorbis(self.tmp / "a.ogg")
        a = File(str(p))
        a.update({"title": "Song", "artist": "Singer", "album artist": "Band", "album": "Album",
                  "tracknumber": "3", "discnumber": "2", "date": "2019", "genre": "Rock", "bpm": "120"})
        a.save()
        self.check(p)

    def test_opus(self):
        p = s.opus(self.tmp / "a.opus")
        a = File(str(p))
        a.update({"title": "Song", "artist": "Singer", "albumartist": "Band", "album": "Album",
                  "tracknumber": "3/12", "discnumber": "2/2", "date": "2019-05-03", "genre": "Rock", "bpm": "120"})
        a.save()
        self.check(p)

    def test_wavpack(self):
        p = s.wavpack(self.tmp / "a.wv")
        s.ape_tags(p, Title="Song", Artist="Singer", Album="Album", Track="3/12", Disc="2/2", Year="2019",
                   Genre="Rock", BPM="120", **{"Album Artist": "Band"})
        self.check(p)

    def test_monkeys_audio(self):
        p = s.monkeys(self.tmp / "a.ape")
        s.ape_tags(p, Title="Song", Artist="Singer", Album="Album", Track="3", Disc="2", Year="2019-05-03",
                   Genre="Rock", BPM="120", **{"Album Artist": "Band"})
        self.check(p)

    def test_wma(self):
        p = s.ffmpeg_make(self.tmp / "a.wma", "wmav2")
        if p is None:
            self.skipTest("ffmpeg can't make a WMA file here")
        a = File(str(p))
        a.update({"Title": ["Song"], "Author": ["Singer"], "WM/AlbumArtist": ["Band"], "WM/AlbumTitle": ["Album"],
                  "WM/TrackNumber": ["3"], "WM/PartOfSet": ["2/2"], "WM/Year": ["2019"], "WM/Genre": ["Rock"],
                  "WM/BeatsPerMinute": ["120"]})
        a.save()
        self.check(p)

    def test_m4a(self):
        p = s.ffmpeg_make(self.tmp / "a.m4a", "aac", ("-strict", "-2"))
        if p is None:
            self.skipTest("ffmpeg can't make an M4A file here")
        a = File(str(p))
        a.update({"\xa9nam": ["Song"], "\xa9ART": ["Singer"], "aART": ["Band"], "\xa9alb": ["Album"],
                  "trkn": [(3, 12)], "disk": [(2, 2)], "\xa9day": ["2019-05-03"], "\xa9gen": ["Rock"], "tmpo": [120]})
        a.save()
        self.check(p)

    def test_mka_like_ffmpeg_writes_it(self):
        p = s.mka(self.tmp / "a.mka", [s.mka_tag(None, TITLE="Song", ARTIST="Singer", ALBUM_ARTIST="Band",
                                                 ALBUM="Album", PART_NUMBER="3", DISC="2", DATE="2019",
                                                 GENRE="Rock", BPM="120"),
                                       s.mka_tag(None, uid=1, DURATION="00:03:20.5", ENCODER="Lavc")])
        t = self.check(p)
        self.assertAlmostEqual(t["length"], 200.5, places=1)

    def test_mka_album_and_track_levels(self):
        """Album tags (level 50) and the song's own (level 30), like foobar2000 and mkvpropedit write."""
        p = s.mka(self.tmp / "a.mka", [s.mka_tag(50, TITLE="Album", ARTIST="Band", DATE_RELEASED="2019",
                                                 GENRE="Rock"),
                                       s.mka_tag(30, TITLE="Song", ARTIST="Singer", PART_NUMBER="3", BPM="120")])
        self.check(p, disc=1)

    def test_mka_tags_before_the_audio_and_unknown_segment_size(self):
        p = s.mka(self.tmp / "a.mka", [s.mka_tag(None, TITLE="Song", ARTIST="Band", ALBUM="Album")],
                  tags_after_audio=False, unknown_size=True)
        t = mp.read_track(str(p))
        self.assertEqual((t["title"], t["artist"], t["album"]), ("Song", "Band", "Album"))

    def test_mka_made_by_ffmpeg(self):
        meta = ("title=Song", "artist=Singer", "album_artist=Band", "album=Album", "track=3", "date=2019")
        p = s.ffmpeg_make(self.tmp / "a.mka", "flac", [x for m in meta for x in ("-metadata", m)])
        if p is None:
            self.skipTest("ffmpeg can't make an MKA file here")
        t = mp.read_track(str(p))
        self.assertEqual((t["title"], t["artist"], t["album"], t["num"], t["year"]), ("Song", "Band", "Album", 3, 2019))
        self.assertGreater(t["length"], 0.3)

    def test_broken_mka_is_just_untagged(self):
        p = self.tmp / "a.mka"
        p.write_bytes(b"\x1a\x45\xdf\xa3\x88garbage")
        t = mp.read_track(str(p))
        self.assertEqual((t["title"], t["artist"]), ("a", "Unknown Artist"))


class CachedTagsTest(TempDirTest):
    def test_songs_cached_by_an_older_version_are_read_again(self):
        lib = self.tmp / "lib"
        lib.mkdir()
        s.add_riff_info(s.wav(lib / "a.wav"), {"INAM": "Song", "IART": "Singer"})
        cache = mp.scan_folders([str(lib)])
        old = []
        for t in cache:          # what the version before could read of this WAV file: nothing
            t = {**t, "title": "a", "artist": "Unknown Artist", "artist_raw": ""}
            t.pop("tags_version", None)
            old.append(t)
        again = mp.scan_folders([str(lib)], old)
        self.assertEqual((again[0]["title"], again[0]["artist"]), ("Song", "Singer"))
        self.assertIs(mp.scan_folders([str(lib)], again)[0], again[0])     # and then it's cached


class YearTest(TempDirTest):
    """A18: the year of a date written any way round."""

    def year_of(self, date):
        p = s.flac(self.tmp / "a.flac")
        a = File(str(p))
        a["date"] = date
        a.save()
        return mp.read_track(str(p))["year"]

    def test_dates(self):
        for date, year in (("05/03/2019", 2019), ("03.05.2019", 2019), ("2019-05-03", 2019), ("2019", 2019),
                           ("20190503", 2019), ("1999/2000", 1999), ("", 0), ("unknown", 0)):
            with self.subTest(date=date):
                self.assertEqual(self.year_of(date), year)


if __name__ == "__main__":
    unittest.main()
