"""
Song tags come from files people download, so a title like '<img src="...">' must be shown as text,
never rendered as HTML (it could load a network file or break the layout).
"""
import unittest

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel

from test_mpv_engine import APP
from test_player import PlayerHarness, mp

EVIL = '<img src="file://example.invalid/x.png"><b>Bold</b>'


class TagHtmlTest(PlayerHarness):
    def test_no_label_guesses_html(self):
        self.make_player(["One"])
        p = self.player
        p.queue[0][0]["title"] = EVIL
        p.show()
        p.play_from_library(0)
        APP.processEvents()
        guessing = [w for w in APP.allWidgets()
                    if isinstance(w, QLabel) and w.isVisible() and w.textFormat() == Qt.TextFormat.AutoText]
        self.assertEqual(guessing, [])

    def test_a_label_made_later_shows_tags_as_text(self):
        self.make_player(["One"])
        self.player.show()
        later = QLabel(EVIL, self.player)
        later.show()
        APP.processEvents()
        self.assertEqual(later.textFormat(), Qt.TextFormat.PlainText)

    def test_labels_meant_for_links_still_escape_tags(self):
        self.make_player(["One"])
        p = self.player
        p.queue[0][0]["title"] = EVIL
        p.show()
        p.play_from_library(0)
        APP.processEvents()
        rich = [w for w in APP.allWidgets() if isinstance(w, QLabel) and w.textFormat() == Qt.TextFormat.RichText]
        self.assertTrue(rich)
        for w in rich:
            self.assertNotIn("<img", w.text())

    def test_tooltips_escape_tags(self):
        self.assertEqual(mp.plain_tip("a <b>b</b> & c"), "<qt>a &lt;b&gt;b&lt;/b&gt; &amp; c</qt>")


if __name__ == "__main__":
    unittest.main()
