"""
A4 in the real window: a soundtrack whose songs have different singers is one album in the library,
the song's own singer is shown while it plays and used to look up its lyrics, and the album's
artist is used to find its cover. Nothing goes on the internet (the lookups are fakes).
"""
import unittest
from unittest import mock

from test_core import mp, tagged_mp3
from test_mpv_engine import wait_for
from test_player import PlayerHarness


class CompilationTest(PlayerHarness):
    def setUp(self):
        super().setUp()
        for name, fake in (("fetch_lrclib", mock.Mock(return_value=None)),
                           ("download_cover", mock.Mock(return_value=False))):
            patcher = mock.patch.object(mp, name, fake)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.make_player(["a"], lyrics_online=True, covers_auto=True)
        ost = self.tmp / "music" / "Witcher OST"
        ost.mkdir()
        for i, artist in enumerate(["Marcin Przybyłowicz", "Percival", "Marcin Przybyłowicz",
                                    "Mikolai Stroinski", "Marcin Przybyłowicz"], 1):
            tagged_mp3(ost / f"{i:02d} - Track {i}.mp3", title=f"Track {i}", artist=artist, album="The Witcher 3",
                       tracknumber=str(i))
        self.player.rescan()
        self.assertTrue(wait_for(lambda: len(self.player.all_tracks) == 6 and not self.player.scanning))

    def test_soundtrack_is_one_album_under_its_main_composer(self):
        keys = sorted(k for k in self.player.albums if k[1] == "the witcher 3")
        self.assertEqual(keys, [("marcin przybyłowicz", "the witcher 3")])
        self.assertNotIn("percival", self.player.artists)

    def test_the_singer_is_shown_and_used_for_lyrics_and_the_album_artist_for_the_cover(self):
        p = self.player
        idx = next(i for i, (t, _k) in enumerate(p.queue) if t["title"] == "Track 2")
        p.play_index(idx, autoplay=False)
        self.assertTrue(wait_for(lambda: mp.fetch_lrclib.called and mp.download_cover.called))
        self.assertEqual(mp.fetch_lrclib.call_args[0][:2], ("Percival", "Track 2"))
        self.assertEqual(mp.download_cover.call_args[0][:2], ("Marcin Przybyłowicz", "The Witcher 3"))
        self.assertIn("Percival", p.now_playing.text())

    def test_album_page_shows_who_sings_the_songs_by_someone_else(self):
        p = self.player
        p.show_album(("marcin przybyłowicz", "the witcher 3"))
        titles = [p.track_table.item(r, 2).text() for r in range(p.track_table.rowCount())]
        self.assertEqual(titles[:2], ["Track 1", "Track 2  ·  Percival"])

    def test_searching_for_the_singer_finds_the_album(self):
        p = self.player
        p.search.setText("percival")
        p.apply_filter()
        shown = [k for k, item in p.tree_albums.items() if not item.isHidden()]
        self.assertEqual(shown, [("marcin przybyłowicz", "the witcher 3")])


if __name__ == "__main__":
    unittest.main()
