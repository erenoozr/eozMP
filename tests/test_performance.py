"""
Performance checks: work that used to grow with the library or repeat on every song. Most assert
how often something happens (stylesheet applied, file written, covers decoded) rather than time,
so they don't get flaky on a busy machine. Big libraries are faked in memory, like test_speed.py.
"""
import time
import unittest
from unittest import mock

from PyQt6.QtCore import QBuffer, QByteArray, QIODevice
from PyQt6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu

from test_mpv_engine import APP, wait_for
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


if __name__ == "__main__":
    unittest.main()
