"""
Small usability fixes found while looking through the screens: readable selected rows, a first-run
button, a question before emptying the library, browse headings and menu shortcuts. The real window
runs offscreen on a fake library in a temp folder (see test_player.py).
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QColor  # noqa: E402

from test_mpv_engine import wait_for  # noqa: E402
from test_player import PlayerHarness, mp  # noqa: E402


def far_from(c, ref, limit=90):
    return abs(c.red() - ref.red()) + abs(c.green() - ref.green()) + abs(c.blue() - ref.blue()) > limit


class SelectedRowTest(PlayerHarness):
    def test_the_playing_song_stays_readable_when_selected(self):
        self.make_player(["One", "Two"], seconds=4)
        p = self.player
        p.resize(1100, 700)
        p.show()
        p.open_album(next(iter(p.albums)))
        self.start("One")
        self.assertTrue(wait_for(lambda: p.current_path() == str(self.songs[0]), 5))
        table = p.track_table
        accent = QColor(p.scheme["accent"])
        for row in (0, 1):                         # the playing song, and another one
            table.selectRow(row)
            wait_for(lambda: False, 0.2)
            img = table.viewport().grab().toImage()
            rect = table.visualRect(table.model().index(row, 2))      # the title
            dpr = img.devicePixelRatio()
            text = sum(far_from(img.pixelColor(int(x * dpr), int(y * dpr)), accent)
                       for x in range(rect.left() + 2, rect.right() - 2)
                       for y in range(rect.top() + 3, rect.bottom() - 3))
            self.assertGreater(text, 15, f"row {row}: no text to be seen on the selected row")


if __name__ == "__main__":
    unittest.main()
