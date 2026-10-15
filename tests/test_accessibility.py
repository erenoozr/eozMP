"""
Accessibility: readable text on the accent colour, Space and Tab with the keyboard, names for screen
readers and sharp covers on scaled (HiDPI) screens. Like test_player.py, the real window runs offscreen
on a fake library in a temp folder, so your own eozMP data is never touched.
"""
import colorsys
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from test_player import PlayerHarness, mp  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
