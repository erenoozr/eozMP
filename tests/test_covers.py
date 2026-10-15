"""
Album covers: the picture inside the file (A17), and finding covers online without breaking other
albums' folders (A5), remembering network errors as "no cover" (A6) or matching the wrong album (A7).
Nothing here goes on the internet: the lookups are answered by fakes.
Run from the project folder:   py -3 -m unittest discover tests -p "test_covers.py"
"""
import base64
import struct
import unittest
import urllib.error
from unittest import mock

from mutagen import File
from mutagen.flac import Picture
from mutagen.id3 import APIC

import audio_samples as s
from test_core import TempDirTest, mp, tagged_mp3
from test_mpv_engine import wait_for
from test_player import PlayerHarness


def flac_picture(kind, data):
    pic = Picture()
    pic.type, pic.mime, pic.data = kind, "image/jpeg", data
    return pic


class EmbeddedCoverTest(TempDirTest):
    """A17: the front cover (picture type 3) in every format, not just whichever picture comes first."""

    def test_flac_front_cover_wins_over_an_earlier_back_cover(self):
        p = s.flac(self.tmp / "a.flac")
        a = File(str(p))
        a.add_picture(flac_picture(4, s.BACK_JPEG))
        a.add_picture(flac_picture(3, s.JPEG))
        a.save()
        self.assertEqual(mp.embedded_cover(str(p)), s.JPEG)

    def test_mp3_front_cover_wins_over_an_earlier_back_cover(self):
        p = self.tmp / "a.mp3"
        tagged_mp3(p, title="Song")
        s.id3_frames(p, [APIC(encoding=3, mime="image/jpeg", type=4, desc="back", data=s.BACK_JPEG),
                         APIC(encoding=3, mime="image/jpeg", type=3, desc="front", data=s.JPEG)])
        self.assertEqual(mp.embedded_cover(str(p)), s.JPEG)

    def test_any_picture_when_none_is_marked_front(self):
        p = s.flac(self.tmp / "a.flac")
        a = File(str(p))
        a.add_picture(flac_picture(0, s.PNG))
        a.save()
        self.assertEqual(mp.embedded_cover(str(p)), s.PNG)

    def test_wav_and_aiff_covers(self):
        for p in (s.wav(self.tmp / "a.wav"), s.aiff(self.tmp / "a.aiff")):
            with self.subTest(p.suffix):
                s.id3_frames(p, [APIC(encoding=3, mime="image/jpeg", type=3, desc="", data=s.JPEG)])
                self.assertEqual(mp.embedded_cover(str(p)), s.JPEG)

    def test_ogg_opus_and_vorbis_covers(self):
        for p in (s.opus(self.tmp / "a.opus"), s.vorbis(self.tmp / "a.ogg")):
            with self.subTest(p.suffix):
                a = File(str(p))
                a["metadata_block_picture"] = [base64.b64encode(flac_picture(4, s.BACK_JPEG).write()).decode(),
                                               base64.b64encode(flac_picture(3, s.JPEG).write()).decode()]
                a.save()
                self.assertEqual(mp.embedded_cover(str(p)), s.JPEG)

    def test_old_style_ogg_coverart(self):
        p = s.vorbis(self.tmp / "a.ogg")
        a = File(str(p))
        a["coverart"] = [base64.b64encode(s.JPEG).decode()]
        a.save()
        self.assertEqual(mp.embedded_cover(str(p)), s.JPEG)

    def test_wavpack_and_monkeys_audio_covers(self):
        from mutagen.apev2 import APEValue, BINARY
        for p in (s.wavpack(self.tmp / "a.wv"), s.monkeys(self.tmp / "a.ape")):
            with self.subTest(p.suffix):
                s.ape_tags(p, **{"Cover Art (Back)": APEValue(b"back.jpg\0" + s.BACK_JPEG, BINARY),
                                 "Cover Art (Front)": APEValue(b"front.jpg\0" + s.JPEG, BINARY)})
                self.assertEqual(mp.embedded_cover(str(p)), s.JPEG)

    def test_wma_cover(self):
        from mutagen.asf import ASFByteArrayAttribute
        p = s.ffmpeg_make(self.tmp / "a.wma", "wmav2")
        if p is None:
            self.skipTest("ffmpeg can't make a WMA file here")

        def wm_picture(kind, data):
            text = "image/jpeg".encode("utf-16-le") + b"\0\0" + "".encode("utf-16-le") + b"\0\0"
            return ASFByteArrayAttribute(bytes([kind]) + struct.pack("<I", len(data)) + text + data)
        a = File(str(p))
        a["WM/Picture"] = [wm_picture(4, s.BACK_JPEG), wm_picture(3, s.JPEG)]
        a.save()
        self.assertEqual(mp.embedded_cover(str(p)), s.JPEG)

    def test_mka_attached_cover(self):
        p = s.mka(self.tmp / "a.mka", [s.mka_tag(None, TITLE="Song")],
                  attachments=[("small_cover.jpg", "image/jpeg", s.BACK_JPEG), ("notes.txt", "text/plain", b"hi"),
                               ("cover.jpg", "image/jpeg", s.JPEG)])
        self.assertEqual(mp.embedded_cover(str(p)), s.JPEG)

    def test_file_without_a_cover(self):
        p = s.flac(self.tmp / "a.flac")
        self.assertIsNone(mp.embedded_cover(str(p)))
        self.assertIsNone(mp.embedded_cover(str(s.mka(self.tmp / "a.mka"))))


class FakeClock:
    """Stands in for the time module inside musicplayer, so waiting between requests takes no time."""

    def __init__(self):
        self.t = 1000.0

    def time(self):
        return self.t

    monotonic = time

    def sleep(self, seconds):
        self.t += max(0.0, seconds)


class FakeWeb:
    """Answers iTunes, MusicBrainz and the Cover Art Archive like they would, from what a test sets."""

    def __init__(self, itunes=(), mb=(), down=False):
        self.itunes, self.mb, self.down = list(itunes), list(mb), down
        self.asked, self.images = [], []

    def json(self, url):
        self.asked.append(url)
        if self.down:
            raise urllib.error.URLError("no internet")
        if "itunes.apple.com" in url:
            return {"results": self.itunes}
        if "musicbrainz.org" in url:
            return {"release-groups": self.mb}
        raise AssertionError(url)

    def bytes(self, url, timeout=15):
        self.images.append(url)
        if self.down:
            raise urllib.error.URLError("no internet")
        return s.JPEG


def itunes(artist, album):
    return {"artistName": artist, "collectionName": album, "artworkUrl100": f"https://img/{album}/100x100bb.jpg"}


def rg(title, score=100):
    return {"id": f"id-{title}", "title": title, "score": score}


class CoverLookupTest(TempDirTest):
    def lookup(self, web, artist, album):
        with mock.patch.object(mp, "http_json", web.json), mock.patch.object(mp, "http_bytes", web.bytes), \
                mock.patch.object(mp, "time", FakeClock()):
            return mp.fetch_cover_bytes(artist, album)

    # A7: whole titles, not a piece of one
    def test_album_1_does_not_take_the_cover_of_1967_1970(self):
        web = FakeWeb(itunes=[itunes("The Beatles", "1967-1970")], mb=[rg("1967-1970")])
        self.assertIsNone(self.lookup(web, "The Beatles", "1"))
        self.assertEqual(web.images, [])

    def test_the_right_album_still_matches(self):
        web = FakeWeb(itunes=[itunes("The Beatles", "1967-1970"), itunes("The Beatles", "1")])
        self.assertEqual(self.lookup(web, "The Beatles", "1"), s.JPEG)
        self.assertEqual(web.images, ["https://img/1/600x600bb.jpg"])

    def test_an_edition_in_brackets_still_matches(self):
        for mine, theirs in (("Abbey Road", "Abbey Road (Remastered)"), ("Abbey Road (Super Deluxe)", "Abbey Road"),
                             ("Rumours", "Rumours [Deluxe Edition]"), ("Hunky Dory", "Hunky Dory - 2015 Remaster")):
            with self.subTest(mine):
                self.assertEqual(self.lookup(FakeWeb(itunes=[itunes("Band", theirs)]), "Band", mine), s.JPEG)

    def test_another_artist_whose_name_starts_the_same_is_not_taken(self):
        web = FakeWeb(itunes=[itunes("Museum", "Absolution")])
        self.assertIsNone(self.lookup(web, "Muse", "Absolution"))

    def test_musicbrainz_needs_the_same_title_too(self):
        web = FakeWeb(mb=[rg("Greatest Hits")])
        self.assertIsNone(self.lookup(web, "Band", "Hits"))
        web = FakeWeb(mb=[rg("Greatest Hits"), rg("Hits", 90)])
        self.assertEqual(self.lookup(web, "Band", "Hits"), s.JPEG)
        self.assertEqual(web.images, ["https://coverartarchive.org/release-group/id-Hits/front-500"])

    def test_names_in_other_scripts_are_searched(self):
        web = FakeWeb(itunes=[itunes("Кино", "Группа крови")])
        self.assertEqual(self.lookup(web, "Кино", "Группа крови"), s.JPEG)
        web = FakeWeb(itunes=[itunes("宇多田ヒカル", "First Love")])
        self.assertEqual(self.lookup(web, "宇多田ヒカル", "First Love"), s.JPEG)

    # A6: no internet is not "this album has no cover"
    def test_no_internet_is_an_error_not_a_missing_cover(self):
        with self.assertRaises(OSError):
            self.lookup(FakeWeb(down=True), "Band", "Album")

    def test_nothing_found_is_a_missing_cover(self):
        self.assertIsNone(self.lookup(FakeWeb(), "Band", "Album"))

    def test_cover_archive_without_a_front_cover_is_not_an_error(self):
        web = FakeWeb(mb=[rg("Album")])

        def no_front(url, timeout=15):
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        web.bytes = no_front
        self.assertIsNone(self.lookup(web, "Band", "Album"))

    def test_only_a_real_miss_is_remembered_by_the_batch(self):
        song = self.tmp / "a.mp3"
        tagged_mp3(song, title="A")
        for web, remembered in ((FakeWeb(down=True), []), (FakeWeb(), ["band|album"])):
            with self.subTest(down=web.down), mock.patch.object(mp, "COVERS_DIR", self.tmp / "covers"), \
                    mock.patch.object(mp, "http_json", web.json), mock.patch.object(mp, "http_bytes", web.bytes), \
                    mock.patch.object(mp, "time", FakeClock()):
                batch = mp.CoverBatch([(("band", "album"), "Band", "Album", [str(song)])], False)
                batch.run()
                self.assertEqual(batch.missed, remembered)

    # A20: MusicBrainz wants to know who's asking, and one request a second
    def test_requests_say_who_is_asking(self):
        seen = []

        class Answer:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return b"{}"

        def urlopen(req, timeout=None):
            seen.append(req.get_header("User-agent"))
            return Answer()
        with mock.patch.object(mp.urllib.request, "urlopen", urlopen):
            mp.http_json("https://musicbrainz.org/ws/2/release-group/?query=x")
            mp.http_bytes("https://coverartarchive.org/release-group/x/front-500")
        self.assertEqual(len(seen), 2)
        for ua in seen:
            self.assertRegex(ua, r"^eozMP/\S+ \( https://github\.com/erenoozr/eozMP \)$")

    def test_musicbrainz_is_asked_at_most_once_a_second(self):
        clock, times = FakeClock(), []
        web = FakeWeb()

        def answer(url):
            if "musicbrainz.org" in url:
                times.append(clock.t)
            return web.json(url)
        mp._mb_last[0] = 0.0
        with mock.patch.object(mp, "http_json", answer), mock.patch.object(mp, "http_bytes", web.bytes), \
                mock.patch.object(mp, "time", clock):
            for album in ("One", "Two", "Three"):
                mp.fetch_cover_bytes("Band", album)
        self.assertEqual(len(times), 3)
        self.assertTrue(all(b - a >= 1.0 for a, b in zip(times, times[1:])), times)


class CoverFileTest(TempDirTest):
    """A5: a cover.jpg found online goes into the folder only when that folder holds just this album."""

    def setUp(self):
        super().setUp()
        for name, value in (("COVERS_DIR", self.tmp / "covers"), ("fetch_cover_bytes", lambda a, b: s.JPEG),
                            ("time", FakeClock())):
            patcher = mock.patch.object(mp, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def batch(self, folder, album, titles):
        songs = [str(folder / f"{t}.mp3") for t in titles]
        mp.CoverBatch([(("band", album.lower()), "Band", album, songs)], True).run()

    def test_cover_goes_into_a_folder_that_holds_just_this_album(self):
        folder = self.tmp / "Band - One"
        folder.mkdir()
        for t in ("a", "b"):
            tagged_mp3(folder / f"{t}.mp3", title=t, artist="Band", album="One")
        self.batch(folder, "One", ["a", "b"])
        self.assertEqual((folder / "cover.jpg").read_bytes(), s.JPEG)

    def test_no_cover_file_in_a_folder_shared_with_other_albums(self):
        folder = self.tmp / "Downloads"
        folder.mkdir()
        tagged_mp3(folder / "a.mp3", title="a", artist="Band", album="One")
        tagged_mp3(folder / "b.mp3", title="b", artist="Other", album="Two")
        self.batch(folder, "One", ["a"])
        self.assertFalse((folder / "cover.jpg").exists())
        self.assertEqual(mp.read_cached_cover("Band", "One"), s.JPEG)      # still found and shown


class PlayerCoverTest(PlayerHarness):
    """A5 and A6 in the real window: covers looked up while you browse and play."""

    def test_offline_is_tried_again_and_a_shared_folder_gets_no_cover_file(self):
        self.make_player(["a"], covers_auto=True, covers_to_folder=True)
        mixed = self.tmp / "music" / "Downloads"
        mixed.mkdir()
        for name, artist, album in (("01 - x", "Band", "One"), ("02 - y", "Band", "One"), ("01 - z", "Other", "Two")):
            tagged_mp3(mixed / f"{name}.mp3", title=name, artist=artist, album=album, tracknumber=name[:2])
        p = self.player
        p.rescan()
        self.assertTrue(wait_for(lambda: len(p.all_tracks) == 4 and not p.scanning))
        key = ("band", "one")

        def lookup(fake):
            with mock.patch.object(mp, "fetch_cover_bytes", fake):
                p.maybe_fetch_cover(key)
                self.assertTrue(wait_for(lambda: key not in p.cover_fetching))

        def offline(artist, album):
            raise urllib.error.URLError("no internet")
        lookup(offline)
        self.assertNotIn("band|one", p.stats["cover_misses"])      # not "no cover" for a month
        lookup(lambda artist, album: s.JPEG)
        self.assertEqual(mp.read_cached_cover("Band", "One"), s.JPEG)
        self.assertFalse((mixed / "cover.jpg").exists())             # it would be album Two's cover too


if __name__ == "__main__":
    unittest.main()
