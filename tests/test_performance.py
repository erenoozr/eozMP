"""
Performance checks: work that used to grow with the library or repeat on every song. Most assert
how often something happens (stylesheet applied, file written, covers decoded) rather than time,
so they don't get flaky on a busy machine. Big libraries are faked in memory, like test_speed.py.
"""
import os
import shutil
import time
import unittest
from pathlib import Path
from unittest import mock

from PyQt6.QtCore import QBuffer, QByteArray, QIODevice
from PyQt6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu

from test_core import TempDirTest
from test_mpv_engine import APP, tone, wait_for
from test_player import PlayerHarness, mp


def jpeg(width, height):
    """A big cover, like the ones embedded in downloaded albums."""
    img = QImage(width, height, QImage.Format.Format_RGB32)
    p = QPainter(img)
    grad = QLinearGradient(0, 0, width, height)
    grad.setColorAt(0, QColor("#d02020"))
    grad.setColorAt(1, QColor("#2040d0"))
    p.fillRect(img.rect(), grad)
    p.end()
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "JPG", 90)
    return bytes(data)


def pixel(widget, x, y):
    return widget.grab().toImage().pixelColor(x, y).name()


class AlbumAccentTest(PlayerHarness):
    """'Accent color: From album art' changes the accent on every song. That used to re-apply the
    whole app's stylesheet (~0.3-0.5 s per song); now only the widgets that show the accent change."""

    def accent_player(self):
        self.make_player(["One"], accent=mp.ALBUM_ART_ACCENT)
        p = self.player
        p.resize(1200, 800)
        p.show()
        APP.processEvents()
        return p

    def set_album_accent(self, color):
        p = self.player
        p.accent_cache[("x", color)] = color
        p.update_album_accent(("x", color))
        APP.processEvents()

    def test_song_change_does_not_restyle_the_whole_app(self):
        p = self.accent_player()
        before = APP.styleSheet()
        with mock.patch.object(QApplication, "setStyleSheet") as restyle:
            for color in ("#d02020", "#20a040", "#2040d0"):
                self.set_album_accent(color)
        self.assertEqual(restyle.call_count, 0)
        self.assertEqual(APP.styleSheet(), before)
        self.assertEqual(p.scheme["accent"], "#2040d0")

    def test_accent_shows_on_screen(self):
        p = self.accent_player()
        btn = p.play_btn
        for color in ("#d02020", "#20a040"):
            self.set_album_accent(color)
            self.assertEqual(pixel(btn, 3, btn.height() // 2), color)

    def test_widgets_shown_later_get_the_new_accent(self):
        p = self.accent_player()
        self.set_album_accent("#d02020")
        menu = QMenu(p)
        act = menu.addAction("Something long enough")
        menu.popup(p.mapToGlobal(p.rect().center()))
        menu.setActiveAction(act)
        APP.processEvents()
        rect = menu.actionGeometry(act)
        self.assertEqual(pixel(menu, rect.left() + 4, rect.center().y()), "#d02020")
        menu.close()

    def test_accent_widgets_look_the_same_as_after_a_full_restyle(self):
        p = self.accent_player()
        p.np_timer.stop()                   # the now-playing animation would differ between grabs
        p.setFixedSize(1700, 900)           # offscreen, restyles nudge the window's size otherwise
        if APP.focusWidget() is not None:
            APP.focusWidget().clearFocus()  # a blinking text cursor would differ between grabs
        p.refresh_colors()
        APP.processEvents()
        self.set_album_accent("#d02020")    # quick path: small sheets on the accent widgets
        widgets = [w for w in p.findChildren(mp.QWidget) if w.isVisible() and mp.is_accent_target(w)]
        self.assertGreater(len(widgets), 8)
        quick = [w.grab().toImage() for w in widgets]
        p.refresh_colors()                  # full path: the app stylesheet carries the same accent
        APP.processEvents()
        self.assertIn("#d02020", APP.styleSheet())
        self.assertEqual(p.accent_sheet, "")
        different = [f"{type(w).__name__}#{w.objectName()}" for w, img in zip(widgets, quick) if w.grab().toImage() != img]
        self.assertEqual(different, [])

    def test_theme_change_still_restyles_everything(self):
        p = self.accent_player()
        self.set_album_accent("#d02020")
        p.cfg["theme"] = "Light"
        p.apply_settings()
        APP.processEvents()
        self.assertIn("#d02020", APP.styleSheet())
        btn = p.play_btn
        self.assertEqual(pixel(btn, 3, btn.height() // 2), "#d02020")

    def test_lyrics_page_keeps_its_own_white_links(self):
        """The album-art lyrics style paints white links over the blurred cover; the accent must not win."""
        p = self.accent_player()
        self.set_album_accent("#d02020")
        p.cfg["lyrics_style"] = "Album art"
        p.apply_settings()
        self.set_album_accent("#20a040")
        links = [b for b in p.ly_page.findChildren(mp.QPushButton) if b.objectName() == "link"]
        self.assertTrue(links)
        for b in links:
            self.assertEqual(b.styleSheet(), "")

    def test_song_change_is_quick(self):
        p = self.accent_player()
        self.set_album_accent("#d02020")
        took = []
        for color in ("#20a040", "#2040d0", "#c0a020", "#d02020"):
            started = time.perf_counter()
            self.set_album_accent(color)
            took.append(time.perf_counter() - started)
        print(f" accent change: {min(took) * 1000:.0f}-{max(took) * 1000:.0f} ms", end=" ")
        self.assertLess(min(took), 0.15)



class CoverThumbTest(PlayerHarness):
    """Library covers are decoded and shrunk in the ThumbLoader thread; the GUI thread only turns a
    small finished image into a pixmap (it used to decode every full-size cover itself)."""

    def test_loader_hands_over_a_small_decoded_image(self):
        big = jpeg(1600, 1200)
        with mock.patch.object(mp, "embedded_cover", return_value=big):
            img = mp.load_thumb(["a.mp3"], "Artist", "Album")
        self.assertIsInstance(img, QImage)
        self.assertEqual((img.width(), img.height()), (160, 160))
        old = QPixmap()                     # what the GUI thread used to make from the same bytes
        old.loadFromData(big)
        old = mp.rounded_pixmap(old, 160, 0).toImage()
        for x, y in ((2, 2), (80, 80), (157, 20), (20, 157), (157, 157)):
            a, b = img.pixelColor(x, y), old.pixelColor(x, y)
            self.assertLessEqual(max(abs(a.red() - b.red()), abs(a.green() - b.green()), abs(a.blue() - b.blue())), 6)
        with mock.patch.object(mp, "embedded_cover", return_value=b"not an image"),                 mock.patch.object(mp, "folder_cover", return_value=None),                 mock.patch.object(mp, "read_cached_cover", return_value=None):
            self.assertIsNone(mp.load_thumb(["a.mp3"], "Artist", "Album"))

    def test_decoding_is_shrunk_while_reading(self):
        """QImageReader.setScaledSize: a 3000 px JPEG is never decoded at full size."""
        reads = []
        real = mp.QImageReader.read

        def read(reader):
            reads.append(reader.scaledSize())
            return real(reader)
        with mock.patch.object(mp, "embedded_cover", return_value=jpeg(3000, 3000)),                 mock.patch.object(mp.QImageReader, "read", read):
            mp.load_thumb(["a.mp3"], "Artist", "Album")
        self.assertEqual(len(reads), 1)
        self.assertLessEqual(reads[0].width(), 320)

    def test_gui_thread_does_not_decode_covers(self):
        self.make_player(["One"])
        p = self.player
        with mock.patch.object(mp, "embedded_cover", return_value=jpeg(1200, 1200)):
            img = mp.load_thumb(["a.mp3"], "Artist", "Album")
        started = time.perf_counter()
        with mock.patch.object(QPixmap, "loadFromData") as decode:
            for i in range(100):
                p.on_thumb_loaded(("artist", f"album {i}"), img)
        took = time.perf_counter() - started
        print(f" 100 covers on the GUI thread: {took * 1000:.0f} ms", end=" ")
        self.assertEqual(decode.call_count, 0)
        self.assertEqual(p.thumb_cache.get(("artist", "album 5")).width(), 160)
        self.assertLess(took, 0.3)



class ThumbCacheTest(unittest.TestCase):
    """thumb_cache keeps only the most recently used covers (825 covers were 80 MB)."""

    def pix(self):
        return QPixmap(4, 4)

    def test_keeps_only_the_newest_covers(self):
        cache = mp.ThumbCache(limit=3)
        for k in "abcd":
            cache[k] = self.pix()
        self.assertNotIn("a", cache)
        self.assertEqual(len(cache), 3)
        cache.get("b")                      # used: now the newest
        cache["e"] = self.pix()
        self.assertIn("b", cache)
        self.assertNotIn("c", cache)

    def test_no_cover_is_remembered_and_costs_nothing(self):
        cache = mp.ThumbCache(limit=2)
        cache["none"] = None
        for k in "abc":
            cache[k] = self.pix()
        self.assertIn("none", cache)        # known to have no cover: not read again
        self.assertIsNone(cache.get("none"))
        self.assertEqual(len(cache), 2)

    def test_dropped_covers_are_still_known_to_exist(self):
        cache = mp.ThumbCache(limit=1)
        cache["a"] = self.pix()
        cache["b"] = self.pix()
        self.assertNotIn("a", cache)
        self.assertTrue(cache.has_cover("a"))
        self.assertTrue(cache.known("a"))
        cache.pop("a", None)
        self.assertFalse(cache.known("a"))


def fake_tracks(folder, n, artists, albums_each):
    """n songs spread over artists x albums_each albums, as a scan would return them."""
    out = []
    for i in range(n):
        a = i % artists
        out.append({"path": str(folder / f"s{i}.mp3"), "title": f"Song {i}", "artist": f"Artist {a}",
                    "album": f"Album {a}-{i // artists % albums_each}", "length": 200, "num": i % 12 + 1,
                    "disc": 1, "year": 1990 + i % 30, "genre": "Rock", "mtime": 1.0, "size": 1})
    return out


class BoundedCoversTest(PlayerHarness):
    def fake_albums(self, n):
        p = self.player
        p.build_library(fake_tracks(self.tmp, n, 1, n))
        p.thumbs.clear()

    def test_cache_stays_bounded_with_a_big_library(self):
        self.make_player(["One"])
        p = self.player
        img = QImage(160, 160, QImage.Format.Format_RGB32)
        for i in range(1000):
            p.on_thumb_loaded(("band", f"a{i}"), img)
        self.assertLessEqual(len(p.thumb_cache), mp.THUMB_CACHE_SIZE)
        mb = len(p.thumb_cache) * 160 * 160 * 4 / 2 ** 20
        print(f" 1000 covers kept: {len(p.thumb_cache)} ({mb:.0f} MB)", end=" ")
        self.assertLess(mb, 40)

    def test_library_row_asks_again_for_a_dropped_cover_once(self):
        self.make_player(["One"])
        p = self.player
        self.fake_albums(3)
        p.thumb_cache = mp.ThumbCache(limit=1)
        img = QImage(160, 160, QImage.Format.Format_RGB32)
        p.on_thumb_loaded(("artist 0", "album 0-0"), img)
        p.on_thumb_loaded(("artist 0", "album 0-1"), img)          # a0 dropped
        p.tree_px.clear()
        with mock.patch.object(p.thumbs, "add") as ask:
            for _ in range(5):                          # painted again and again
                p.tree_thumb(("artist 0", "album 0-0"))
        self.assertEqual(ask.call_count, 1)
        p.on_thumb_loaded(("artist 0", "album 0-0"), img)
        self.assertEqual(p.tree_thumb(("artist 0", "album 0-0")).width(), 28)

    def test_artist_picture_still_uses_an_album_with_a_cover(self):
        self.make_player(["One"])
        p = self.player
        self.fake_albums(3)
        p.thumb_cache = mp.ThumbCache(limit=1)
        img = QImage(160, 160, QImage.Format.Format_RGB32)
        p.on_thumb_loaded(("artist 0", "album 0-0"), None)
        p.on_thumb_loaded(("artist 0", "album 0-1"), img)
        p.on_thumb_loaded(("artist 0", "album 0-2"), img)          # a1 dropped, but it has a cover
        self.assertEqual(p.artist_cover_key("artist 0"), ("artist 0", "album 0-1"))



class LibraryBuildTest(PlayerHarness):
    def test_many_artists_build_quickly(self):
        """Albums used to be found by scanning every album for every artist (artists x albums)."""
        self.make_player(["One"])
        tracks = fake_tracks(self.tmp, 18000, 3000, 2)      # 6000 albums
        started = time.perf_counter()
        self.player.build_library(tracks)
        took = time.perf_counter() - started
        print(f" 18k songs / 6000 albums: {took:.2f} s", end=" ")
        self.assertEqual(len(self.player.albums), 6000)
        self.assertEqual(self.player.artist_album_keys("artist 7"), [("artist 7", "album 7-0"), ("artist 7", "album 7-1")])
        self.assertLess(took, 1.5)

    def test_rescan_without_changes_does_not_rebuild(self):
        self.make_player(["One", "Two"])
        p = self.player
        with mock.patch.object(p, "build_library", wraps=p.build_library) as build:
            p.rescan()
            self.assertTrue(wait_for(lambda: not p.scanning))
            self.assertEqual(build.call_count, 0)
            (self.tmp / "music" / "Band" / "Alb" / "01 - One.wav").unlink()
            p.rescan()
            self.assertTrue(wait_for(lambda: not p.scanning))
            self.assertEqual(build.call_count, 1)
        self.assertEqual(len(p.all_tracks), 1)



class ScanSpeedTest(TempDirTest):
    """Every start-up rescans the library; files that didn't change come from the cache."""

    def library(self, n):
        lib = self.tmp / "lib"
        first = lib / "Band" / "Alb"
        first.mkdir(parents=True)
        tone(first / "00.wav", 0.01)
        for i in range(1, n):
            folder = lib / f"Band {i // 50}" / f"Alb {i // 10}"
            folder.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(first / "00.wav", folder / f"{i:04d}.wav")
        return lib

    def test_unchanged_files_need_no_stat_each(self):
        """os.scandir already knows size and dates on Windows; os.walk + os.stat asked again per file."""
        lib = self.library(300)
        cache = mp.scan_folders([str(lib)])
        self.assertEqual(len(cache), 300)
        with mock.patch.object(mp.os, "stat", wraps=os.stat) as stat:
            started = time.perf_counter()
            again = mp.scan_folders([str(lib)], cache)
            took = time.perf_counter() - started
        print(f" 300 cached files: {took * 1000:.0f} ms, {stat.call_count} stat calls", end=" ")
        self.assertTrue(mp.same_tracks(again, cache))
        self.assertLess(stat.call_count, 5)

    def test_scan_order_and_paths_match_os_walk(self):
        """Paths are the cache's keys: they must be spelled exactly as before, in the same order."""
        lib = self.library(60)
        (lib / "notes.txt").write_text("not music")
        expected = [os.path.join(root, f) for root, _d, files in os.walk(str(lib)) for f in files
                    if f.endswith(".wav")]
        self.assertEqual([t["path"] for t in mp.scan_folders([str(lib)])], expected)

    def test_unreadable_subfolder_keeps_its_songs(self):
        lib = self.library(30)
        cache = mp.scan_folders([str(lib)])
        locked = str(lib / "Band 0")
        real = os.scandir

        def scandir(path="."):
            if os.path.normcase(str(path)) == os.path.normcase(locked):
                raise PermissionError(13, "denied", str(path))
            return real(path)
        with mock.patch.object(mp.os, "scandir", scandir):
            again = mp.scan_folders([str(lib)], cache)
        self.assertEqual(sorted(t["path"] for t in again), sorted(t["path"] for t in cache))


class CacheWriteTest(PlayerHarness):
    def test_rescan_without_changes_does_not_rewrite_the_cache(self):
        self.make_player(["One", "Two"])
        p = self.player
        with mock.patch.object(mp, "save_cache", wraps=mp.save_cache) as save:
            p.rescan()
            self.assertTrue(wait_for(lambda: not p.scanning))
            self.assertEqual(save.call_count, 0)
            tone(self.tmp / "music" / "Band" / "Alb" / "03 - Three.wav", 0.2)
            p.rescan()
            self.assertTrue(wait_for(lambda: not p.scanning))
            self.assertEqual(save.call_count, 1)
        self.assertEqual(len(mp.load_cache()), 3)



class StatsSaveTest(PlayerHarness):
    """Listening stats used to be rewritten (~10 MB, ~60 ms on the GUI thread) after every song."""

    def listen(self, times):
        p = self.player
        for _ in range(times):
            p.listen_path, p.listen_ms = str(self.songs[0]), 40000
            p.finalize_listen()

    def stats_writes(self):
        real = mp.write_json_atomic
        writes = []

        def counting(path, data):
            if Path(path) == mp.STATS_FILE:
                writes.append(len(data["events"]))
            return real(path, data)
        return writes, mock.patch.object(mp, "write_json_atomic", counting)

    def test_songs_in_a_row_write_the_stats_once(self):
        self.make_player(["One"])
        p = self.player
        writes, patch = self.stats_writes()
        with patch:
            self.listen(5)
            self.assertEqual(writes, [])
            self.assertTrue(p.stats_timer.isActive())
            self.assertGreaterEqual(p.stats_timer.interval(), 10000)
            p.stats_timer.timeout.emit()         # the timer runs out
            self.listen(2)
        self.assertEqual(writes, [5])
        self.assertEqual(len(mp.load_stats()["events"]), 5)

    def test_closing_saves_what_is_pending(self):
        self.make_player(["One"])
        writes, patch = self.stats_writes()
        with patch:
            self.listen(3)
            self.player.quitting = True
            self.player.close()
        self.assertEqual(writes, [3])
        self.assertEqual(len(mp.load_stats()["events"]), 3)

    def test_logging_off_saves_what_is_pending(self):
        self.make_player(["One"])
        self.listen(2)
        self.player.save_session()               # what Windows' log-off / shutdown request calls
        self.assertEqual(len(mp.load_stats()["events"]), 2)


if __name__ == "__main__":
    unittest.main()
