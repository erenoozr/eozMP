"""
The v1.5 features: lyric search, word lookup, lyric pictures, Latin readings, moved-song repair, the artist
timeline, the listening heatmap, the command palette, desktop lyrics and the phone remote's library.
Nothing here goes to the internet: the translation and MusicBrainz calls are replaced by fakes.
"""
import json
import time
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

from test_core import TempDirTest, mp
from test_mpv_engine import wait_for
from test_player import PlayerHarness
from test_silent_and_duplicates import free_port

LRC = "[00:00.10]Hello darkness my old friend\n[00:01.00]I've come to talk with you again\n[00:02.00]\n"


class ReadingTest(TempDirTest):
    def test_other_scripts_are_read_in_latin_letters(self):
        self.assertEqual(mp.local_romanize("Я тебя люблю"), "Ya tebya lyublyu")
        self.assertEqual(mp.local_romanize("사랑해요"), "saranghaeyo")
        self.assertEqual(mp.local_romanize("ちょっと"), "chotto")
        self.assertEqual(mp.local_romanize("コーヒー"), "koohii")
        self.assertEqual(mp.local_romanize("Αγάπη μου"), "Agapi mou")
        self.assertIsNone(mp.local_romanize("天気"))            # kanji need the online reading

    def test_only_other_scripts_need_a_reading(self):
        self.assertTrue(mp.foreign_script("夜に駆ける"))
        self.assertFalse(mp.foreign_script("Beyoncé, ¿qué tal? Şeker"))

    def test_the_reading_comes_with_the_translation(self):
        data = [[["Seni seviyorum", "Я тебя люблю", None, None, 10],
                 [None, None, "Seni seviyorum", "Ya tebya lyublyu"]], None, "ru"]
        self.assertEqual(mp.gtx_parse(data), ("Seni seviyorum", "Ya tebya lyublyu"))

    def test_offline_lines_still_get_a_local_reading(self):
        with mock.patch.object(mp, "TRANSLATE_DIR", self.tmp / "tr"), \
                mock.patch.object(mp, "gtx_translate", side_effect=OSError("offline")):
            out = mp.lyric_line_extras(["Я тебя люблю", "plain english"], "", True)
        self.assertEqual(out, {"Я тебя люблю": {"t": "", "r": "Ya tebya lyublyu"}})

    def test_words_of_a_line(self):
        self.assertEqual(mp.lyric_words("夜に駆ける 君の名は"), ["夜に", "駆ける", "君の", "名は"])
        self.assertEqual(mp.lyric_words("I don't wanna-go, l'amour!"), ["I", "don't", "wanna-go", "l'amour"])

    def test_folding_ignores_case_and_accents_in_every_script(self):
        self.assertEqual(mp._fold("İstanbul BEYONCÉ!"), "istanbul beyonce")
        self.assertEqual(mp._fold("Привет"), "привет")


class LogicTest(TempDirTest):
    def test_lyrics_search_needs_every_word_and_ranks_phrases_first(self):
        prepared = mp.prepare_lyrics_search({
            "a": [[0], "Hello darkness my old friend\nI've come to talk"],
            "b": [[0], "My friend is old\nDarkness falls"],
            "c": [[0], ""]})
        self.assertEqual([h[0] for h in mp.search_lyrics(prepared, "old friend")], ["a", "b"])
        self.assertEqual(mp.search_lyrics(prepared, "DÁRKNESS")[1][1], "Darkness falls")
        self.assertEqual(mp.search_lyrics(prepared, "friend talk"), [("a", "Hello darkness my old friend", 2)])

    def test_fuzzy_match_order(self):
        self.assertGreater(mp.fuzzy_score("desk", "Desktop lyrics"), mp.fuzzy_score("lyr", "Desktop lyrics"))
        self.assertIsNotNone(mp.fuzzy_score("dsk lyr", "Desktop lyrics"))
        self.assertIsNone(mp.fuzzy_score("zzz", "Desktop lyrics"))

    def test_timeline_merges_editions_and_adds_missing_albums(self):
        items = mp.merge_timeline([("k1", "OK Computer", 1997), ("k2", "Kid A (Deluxe)", 0)],
                                  [{"id": "1", "title": "OK Computer", "year": 1997, "type": "Album"},
                                   {"id": "2", "title": "Kid A", "year": 2000, "type": "Album"},
                                   {"id": "3", "title": "Amnesiac", "year": 2001, "type": "Album"}])
        self.assertEqual([(i["title"], i["year"], i["key"]) for i in items],
                         [("OK Computer", 1997, "k1"), ("Kid A (Deluxe)", 2000, "k2"), ("Amnesiac", 2001, None)])

    def test_heatmap_counts_when_listening_started(self):
        ts = time.mktime((2026, 10, 19, 22, 10, 0, 0, 0, -1))      # a Monday, 22:10
        grid = mp.listening_heatmap([[ts, "p", 200], [ts - 400 * 86400, "p", 99]], since=ts - 86400)
        self.assertEqual(grid[0][22], 200)
        self.assertEqual(sum(map(sum, grid)), 200)

    def test_moved_songs_are_found_by_name_and_folders(self):
        new = self.tmp / "Music" / "Band" / "Album" / "01 - Song.mp3"
        other = self.tmp / "Music" / "Else" / "Other" / "01 - Song.mp3"
        tracks = [{"path": str(new), "artist": "Band", "artist_raw": "Band", "album": "Album", "title": "Song"},
                  {"path": str(other), "artist": "Else", "artist_raw": "Else", "album": "Other", "title": "Song"}]
        old = str(self.tmp / "Old" / "Band" / "Album" / "01 - Song.mp3")
        gone = str(self.tmp / "Old" / "Nobody" / "x.mp3")
        refs = mp.song_references({"Mix": [old, gone]}, {"favorites": [old], "plays": {}})
        found = mp.find_moved_songs(refs, tracks)
        self.assertEqual(found[old][0][1], str(new))       # the same album and band folders win
        self.assertEqual(found[gone], [])
        self.assertEqual(mp.sure_moves(found), {old: str(new)})

    def test_the_phone_never_sees_file_paths(self):
        albums = {("band", "alb"): {"album": "Alb", "artist": "Band", "year": "2001", "tracks": [
            {"path": "C:/secret/One.mp3", "title": "One", "artist": "Band", "artist_raw": "Band", "album": "Alb"}]}}
        lib = mp.remote_library(albums, {"band": "Band"}, {"band": [("band", "alb")]})
        res = mp.remote_search(lib, "one band")
        self.assertEqual([s["title"] for s in res["songs"]], ["One"])
        self.assertNotIn("secret", json.dumps(res))
        self.assertEqual(mp.remote_search(lib, "   "), {"songs": [], "albums": [], "artists": []})


class FakeDialogs:
    """run_dialog without exec(): the dialog is kept for the test to look at."""

    def __init__(self):
        self.shown = []

    def __call__(self, dlg):
        self.shown.append(dlg)
        return 0


class WindowFeaturesTest(PlayerHarness):
    def setUp(self):
        super().setUp()
        self.make_player(["One", "Two"], seconds=3)
        for song in self.songs:
            song.with_suffix(".lrc").write_text(LRC, encoding="utf-8")
        self.dialogs = FakeDialogs()
        patcher = mock.patch.object(mp, "run_dialog", self.dialogs)
        patcher.start()
        self.addCleanup(patcher.stop)

    def with_lyrics(self):
        self.start("One")
        p = self.player
        self.assertTrue(wait_for(lambda: p.lyric_lines and p.lyric_lines[0].startswith("Hello"), 6))

    def test_translation_and_reading_appear_under_the_lines(self):
        self.with_lyrics()
        p = self.player
        with mock.patch.object(mp, "gtx_translate", lambda text, lang, extra="": ("TR " + text, "", [])):
            p.set_translate_lang("Türkçe")
            self.assertTrue(wait_for(lambda: p.lyrics_list.item(p.ly_off).data(mp.TRANS_ROLE), 5))
        self.assertEqual(p.lyrics_list.item(p.ly_off).data(mp.TRANS_ROLE), "TR Hello darkness my old friend")
        self.assertEqual(p.lyric_extras["Hello darkness my old friend"]["t"], "TR Hello darkness my old friend")

    def test_a_lyric_picture_is_made_from_the_ticked_lines(self):
        self.with_lyrics()
        dlg = mp.LyricCardDialog(self.player, 0)
        self.addCleanup(dlg.deleteLater)
        dlg.render()
        self.assertEqual((dlg.image.width(), dlg.image.height()), (1080, 1080))
        dlg.size_box.setCurrentText("Story")
        dlg.render()
        self.assertEqual(dlg.image.height(), 1920)
        for i in range(dlg.lines.count()):
            dlg.lines.item(i).setCheckState(mp.Qt.CheckState.Unchecked)
        dlg.render()
        self.assertIsNone(dlg.image)

    def test_every_picture_look_and_size_renders(self):
        for style in mp.CARD_STYLES:
            for name, size in mp.CARD_SIZES.items():
                img = mp.render_lyric_card([("Line one", "", "Bir"), ("Line two", "", "")], "Song", "Band", None,
                                           style, size, "#4C8DFF")
                self.assertEqual((img.width(), img.height()), size, (style, name))

    def test_looking_up_a_word(self):
        self.with_lyrics()
        res = {"t": "karanlık", "r": "", "senses": [("noun", ["karanlık", "gece"])]}
        with mock.patch.object(mp, "lookup_word", lambda w, lang: res):
            dlg = mp.WordLookupDialog(self.player, "Hello darkness my old friend")
            self.addCleanup(dlg.deleteLater)
            dlg.words.setCurrentRow(1)
            self.assertTrue(wait_for(lambda: "karanlık" in dlg.result.text(), 5))
        self.assertEqual(dlg.words.count(), 5)

    def test_searching_every_songs_lyrics(self):
        p = self.player
        p.open_lyrics_search()
        dlg = self.dialogs.shown[-1]
        self.addCleanup(dlg.deleteLater)
        self.assertTrue(wait_for(lambda: len(dlg.prepared) == 2, 10))
        dlg.query.setText("old friend")
        dlg.search()
        self.assertEqual(dlg.table.rowCount(), 2)
        self.assertEqual(dlg.table.item(0, 2).text(), "Hello darkness my old friend")
        self.assertTrue(mp.LYRICS_INDEX_FILE.exists())          # saved, so the next search starts at once

    def test_repairing_a_song_that_moved(self):
        p = self.player
        old = str(self.tmp / "old place" / "Band" / "Alb" / self.songs[0].name)
        p.playlists["Mix"] = [old]
        p.stats["favorites"] = [old]
        p.open_moved_songs()
        self.assertTrue(wait_for(lambda: self.dialogs.shown, 5))
        dlg = self.dialogs.shown[-1]
        self.addCleanup(dlg.deleteLater)
        self.assertEqual(dlg.rows[0][1].currentData(), str(self.songs[0]))
        dlg.repair()
        self.assertEqual(p.playlists["Mix"], [str(self.songs[0])])
        self.assertIn(str(self.songs[0]), p.fav_set)

    def test_the_artist_timeline_shows_missing_albums(self):
        p = self.player
        akey = next(iter(p.artists))
        p.show_artist(akey)
        owned = p.albums[p.artist_album_keys(akey)[0]]["album"]
        groups = [{"id": "g1", "title": owned, "year": 1999, "type": "Album"},
                  {"id": "g2", "title": "Later", "year": 2004, "type": "EP"}]
        with mock.patch.object(mp, "mb_artist_id", lambda name, known: "mbid"), \
                mock.patch.object(mp, "artist_release_groups", lambda mbid: groups), \
                mock.patch.object(mp, "http_bytes", side_effect=OSError("offline")):
            p.open_timeline()
            dlg = self.dialogs.shown[-1]
            self.addCleanup(dlg.deleteLater)
            self.assertTrue(wait_for(lambda: len(dlg.items) == 2, 5))
        self.assertEqual([(i["title"], i["key"] is None) for i in dlg.items], [(owned, False), ("Later", True)])
        self.assertEqual(dlg.items[0]["year"], 1999)         # the year comes from MusicBrainz when the tags have none

    def test_heatmap_on_the_stats_page(self):
        p = self.player
        mp.record_play(p.stats, str(self.songs[0]), 120)
        p.open_stats()
        self.assertEqual(sum(map(sum, p.heatmap.grid)), 120)
        self.assertTrue(p.heat_peak.text())

    def test_command_palette_finds_songs_and_commands(self):
        p = self.player
        pal = mp.CommandPalette(p)
        self.addCleanup(pal.deleteLater)
        pal.box.setText("two")
        labels = [pal.list.item(i).text() for i in range(pal.list.count())]
        self.assertTrue(any(l.startswith("02 - Two") for l in labels), labels)
        pal.box.setText("rescan")
        self.assertEqual(pal.list.item(0).text(), "Rescan library")
        pal.box.setText("two")
        row = next(i for i in range(pal.list.count()) if pal.list.item(i).text().startswith("02 - Two"))
        pal.list.setCurrentRow(row)
        pal.run()
        self.assertTrue(wait_for(lambda: self.title() == "Two", 5))

    def test_desktop_lyrics_follow_the_song_and_can_be_locked(self):
        self.with_lyrics()
        p = self.player
        p.set_desktop_lyrics(True)
        self.addCleanup(lambda: p.set_desktop_lyrics(False))
        d = p.desktop_lyrics
        self.assertTrue(d.isVisible())
        self.assertTrue(wait_for(lambda: d.line.startswith("Hello") or d.line.startswith("I've"), 5))
        p.set_desktop_lyrics_locked(True)
        self.assertTrue(d.windowFlags() & mp.Qt.WindowType.WindowTransparentForInput)
        p.set_desktop_lyrics_locked(False)
        self.assertFalse(d.windowFlags() & mp.Qt.WindowType.WindowTransparentForInput)
        p.toggle_desktop_lyrics()
        self.assertFalse(d.isVisible())
        self.assertFalse(p.cfg["desktop_lyrics_on"])


class PhoneLibraryTest(PlayerHarness):
    def setUp(self):
        super().setUp()
        self.make_player(["One", "Two", "Three"], remote_port=free_port())
        self.player.set_remote(True)
        self.addCleanup(lambda: self.player.set_remote(False))
        self.base = self.player.remote.base_url().replace(mp.local_ip(), "127.0.0.1")

    def get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=5) as r:
            return r.read()

    def test_search_album_and_queue_from_the_phone(self):
        p = self.player
        res = json.loads(self.get("api/search?q=two"))
        self.assertEqual([s["title"] for s in res["songs"]], ["02 - Two"])     # untagged: the file name
        self.assertNotIn(str(self.tmp), json.dumps(res))
        album = json.loads(self.get("api/album?id=" + res["songs"][0]["albumId"]))
        self.assertEqual([s["title"] for s in album["songs"]], ["01 - One", "02 - Two", "03 - Three"])
        self.get(f"api/cmd?do=queue&value={res['songs'][0]['id']}")
        self.assertTrue(wait_for(lambda: p.up_next == [str(self.songs[1])], 5))
        self.assertTrue(wait_for(lambda: json.loads(self.get("api/state")).get("queue"), 5))
        self.assertEqual(json.loads(self.get("api/state"))["queue"][0]["title"], "02 - Two")
        self.get("api/cmd?do=unqueue&value=0")
        self.assertTrue(wait_for(lambda: p.up_next == [], 5))

    def test_playing_a_song_from_the_phone_keeps_its_album_going(self):
        p = self.player
        res = json.loads(self.get("api/search?q=three"))
        self.get(f"api/cmd?do=play&value={res['songs'][0]['id']}")
        self.assertTrue(wait_for(lambda: self.title() == "Three", 5))
        self.assertEqual(len(p.ctx_paths), 3)

    def test_unknown_ids_and_odd_values_do_nothing(self):
        p = self.player
        for do, value in (("play", "nope"), ("queue", "../../x"), ("playalbum", ""), ("unqueue", "1e400"),
                          ("unqueue", "nan"), ("unqueue", "-5")):
            self.get(f"api/cmd?do={do}&value={urllib.request.quote(value)}")
        self.assertEqual(json.loads(self.get("api/album?id=nope")), {})
        self.assertEqual(p.up_next, [])


if __name__ == "__main__":
    unittest.main()
