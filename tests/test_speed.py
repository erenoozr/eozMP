"""
Speed checks for screens that list many songs. They build a fake library in memory (no audio files),
so they run on the real Player window without scanning anything.
"""
import time
import unittest

from test_mpv_engine import APP
from test_player import PlayerHarness, mp


class TableSpeedTest(PlayerHarness):
    def fake_songs(self, n):
        tracks = []
        for i in range(n):
            t = {"path": str(self.tmp / f"song{i}.mp3"), "title": f"Song {i}", "artist": f"Artist {i % 40}",
                 "album": f"Album {i % 60}", "length": 200, "num": i % 12 + 1}
            tracks.append(t)
            self.player.track_by_path[t["path"]] = (t, (t["artist"], t["album"]))
        return tracks

    def test_showing_a_big_playlist_again_is_quick(self):
        self.make_player(["One"])
        p = self.player
        tracks = self.fake_songs(500)
        p.playlists["Big"] = [t["path"] for t in tracks]
        p.playlists["Big too"] = [t["path"] for t in reversed(tracks)]
        p.show()                            # column auto-sizing only costs anything on screen
        p.show_playlist("Big")
        APP.processEvents()
        started = time.perf_counter()
        p.show_playlist("Big too")          # overwrites the 500 rows already on screen
        APP.processEvents()
        took = time.perf_counter() - started
        self.assertEqual(p.pl_table.rowCount(), 500)
        self.assertEqual(p.pl_table.item(0, 1).text(), "Song 499")
        print(f" 500 rows over 500 rows: {took:.2f} s", end=" ")
        self.assertLess(took, 1.0, f"took {took:.2f} s")

    def test_clicking_a_playlist_fills_the_table_once(self):
        from unittest import mock
        from PyQt6.QtCore import Qt
        from PyQt6.QtTest import QTest
        self.make_player(["One"])
        p = self.player
        p.playlists["Mix"] = [t["path"] for t in self.fake_songs(20)]
        p.refresh_playlist_list()
        p.left_stack.setCurrentIndex(1)     # the playlists panel
        p.show()
        APP.processEvents()
        item = next(p.pl_list.item(i) for i in range(p.pl_list.count()) if p.pl_list.item(i).data(mp.KEY_ROLE) == "Mix")
        rect = p.pl_list.visualItemRect(item)
        with mock.patch.object(p, "show_playlist", wraps=p.show_playlist) as shown:
            QTest.mouseClick(p.pl_list.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
            APP.processEvents()
        self.assertEqual(shown.call_count, 1)


if __name__ == "__main__":
    unittest.main()
