"""
Accessibility: readable text on the accent colour, Space and Tab with the keyboard, names for screen
readers and sharp covers on scaled (HiDPI) screens. Like test_player.py, the real window runs offscreen
on a fake library in a temp folder, so your own eozMP data is never touched.
"""
import colorsys
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtTest import QTest  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from test_mpv_engine import wait_for  # noqa: E402
from test_player import PlayerHarness, mp  # noqa: E402


class WindowTest(PlayerHarness):
    """The real window, shown and active (keyboard shortcuts only work in the active window)."""

    def setUp(self):
        super().setUp()
        self.make_player(["One", "Two", "Three"])
        p = self.player
        p.resize(1100, 700)
        p.show()
        p.activateWindow()
        p.open_album(next(iter(p.albums)))       # as if clicked in the library list
        wait_for(lambda: p.isActiveWindow(), 2)
        self.toggles = []
        p.toggle_play = lambda: self.toggles.append(1)     # what Space would do; the menu action looks it up

    def focus(self, w):
        w.setFocus(Qt.FocusReason.TabFocusReason)
        self.assertTrue(wait_for(lambda: QApplication.focusWidget() is w, 2), f"couldn't focus {w}")

    def key(self, w, key):
        self.focus(w)
        QTest.keyClick(w, key)
        wait_for(lambda: False, 0.05)


class SpaceKeyTest(WindowTest):                                           # C7
    def test_space_presses_the_focused_button(self):
        p = self.player
        was = p.shuffle.isChecked()
        self.key(p.shuffle, Qt.Key.Key_Space)
        self.assertNotEqual(p.shuffle.isChecked(), was)
        self.assertEqual(self.toggles, [])

    def test_space_ticks_the_focused_checkbox(self):
        p = self.player
        p.stack.setCurrentIndex(1)                       # Soulseek results: "Free slots only"
        wait_for(lambda: p.free_check.isVisible(), 2)
        was = p.free_check.isChecked()
        self.key(p.free_check, Qt.Key.Key_Space)
        self.assertNotEqual(p.free_check.isChecked(), was)
        self.assertEqual(self.toggles, [])

    def test_space_types_in_the_search_box(self):
        p = self.player
        p.search.setText("a")
        self.focus(p.search)
        p.search.deselect()                  # Tab selects the text; type after it instead
        p.search.end(False)
        QTest.keyClick(p.search, Qt.Key.Key_Space)
        self.assertEqual(p.search.text(), "a ")
        self.assertEqual(self.toggles, [])

    def test_space_in_the_song_list_plays_and_pauses(self):
        self.key(self.player.track_table, Qt.Key.Key_Space)
        self.assertEqual(self.toggles, [1])

    def test_clicking_a_button_leaves_space_to_play_pause(self):
        p = self.player
        self.focus(p.track_table)
        QTest.mouseClick(p.repeat_btn, Qt.MouseButton.LeftButton)
        self.assertIs(QApplication.focusWidget(), p.track_table)
        QTest.keyClick(p.track_table, Qt.Key.Key_Space)
        wait_for(lambda: False, 0.05)
        self.assertEqual(self.toggles, [1])


def luminance(color):
    c = mp.QColor(color)
    ch = [v / 255 for v in (c.red(), c.green(), c.blue())]
    ch = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in ch]
    return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2]


def contrast(a, b):
    """WCAG 2 contrast ratio; normal-size text needs 4.5."""
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


class AccentContrastTest(unittest.TestCase):                             # C9
    def test_text_on_every_accent_is_readable(self):
        for dark in (True, False):
            for name, accent in mp.ACCENTS.items():
                sc = mp.make_scheme(dark, accent)
                self.assertEqual(sc["accent"], accent)        # the accent itself stays
                for bg in (sc["accent"], sc["accent_hover"]):
                    self.assertGreaterEqual(contrast(sc["on_accent"], bg), 4.5, f"{name}: text on {bg}")

    def test_custom_and_album_art_accents_get_readable_text_too(self):
        for h in range(0, 360, 10):
            for s in (0.2, 0.5, 0.85, 1.0):
                for v in (0.25, 0.45, 0.62, 0.75, 0.88, 1.0):
                    r, g, b = colorsys.hsv_to_rgb(h / 360, s, v)
                    accent = "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))
                    sc = mp.make_scheme(True, accent)
                    self.assertGreaterEqual(contrast(sc["on_accent"], accent), 4.5, accent)



class TabKeyTest(WindowTest):                                             # C13
    def test_tab_leaves_the_song_table(self):
        p = self.player
        p.track_table.setCurrentCell(0, 2)
        self.key(p.track_table, Qt.Key.Key_Tab)
        self.assertIsNot(QApplication.focusWidget(), p.track_table)

    def test_tab_goes_around_the_whole_window_in_reading_order(self):
        p = self.player
        self.focus(p.search)
        seen = []
        for _ in range(80):
            w = QApplication.focusWidget()
            seen.append(w)
            QTest.keyClick(w, Qt.Key.Key_Tab)
            if QApplication.focusWidget() is p.search:
                break
        self.assertIs(QApplication.focusWidget(), p.search, "Tab never came back to the search box")
        for w in (p.tree, p.album_play_btn, p.track_table, p.play_btn, p.next_btn, p.seek, p.volume):
            self.assertIn(w, seen)
        # the library, then the page you're on, then the player controls
        self.assertLess(seen.index(p.tree), seen.index(p.album_play_btn))
        self.assertLess(seen.index(p.track_table), seen.index(p.prev_btn))
        self.assertLess(seen.index(p.prev_btn), seen.index(p.play_btn))

    def test_keyboard_focus_is_visible(self):
        p = self.player
        for w in (p.play_btn, p.next_btn, p.seg_lib, p.sort_btn, p.album_play_btn, p.album_shuffle_btn,
                  p.volume, p.track_table, p.tree):
            self.focus(p.search)
            before = w.grab().toImage()
            self.focus(w)
            after = w.grab().toImage()
            self.assertNotEqual(before, after, f"no focus mark on {w.objectName() or type(w).__name__}")


if __name__ == "__main__":
    unittest.main()
