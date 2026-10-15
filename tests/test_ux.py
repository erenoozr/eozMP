"""
Small usability fixes found while looking through the screens: readable selected rows, a first-run
button, a question before emptying the library, browse headings and menu shortcuts. The real window
runs offscreen on a fake library in a temp folder (see test_player.py).
"""
import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QColor  # noqa: E402
from PyQt6.QtWidgets import QMessageBox, QStyle, QStyleOptionButton  # noqa: E402

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


class EmptyLibraryTest(PlayerHarness):
    def test_first_run_home_page_offers_to_add_music(self):
        self.make_player([])
        p = self.player
        p.resize(1100, 700)
        p.show()
        p.show_home()
        self.assertTrue(p.home_add_btn.isVisible())
        with mock.patch.object(p, "add_folder") as add:
            p.home_add_btn.click()
        add.assert_called_once()

    def test_the_button_goes_away_once_there_is_music(self):
        self.make_player(["One"])
        p = self.player
        p.show()
        p.show_home()
        self.assertFalse(p.home_add_btn.isVisible())


class RemoveFoldersTest(PlayerHarness):
    def test_removing_all_folders_asks_first(self):
        self.make_player(["One"])
        p = self.player
        folders = list(p.cfg["folders"])
        with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No) as ask:
            p.clear_folders()
        ask.assert_called_once()
        self.assertEqual(p.cfg["folders"], folders)
        with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            p.clear_folders()
        self.assertEqual(p.cfg["folders"], [])


class BrowseHeadingsTest(PlayerHarness):
    def test_headings_are_not_rows(self):
        self.make_player(["One"])
        p = self.player
        p.refresh_browse_list()
        items = [p.browse_list.item(i) for i in range(p.browse_list.count())]
        heads = [it for it in items if it.data(mp.KEY_ROLE) is None and it.text() in ("Moods", "Genres", "Decades")]
        self.assertEqual([h.text() for h in heads], ["Moods", "Genres", "Decades"])   # translatable, unlike "MOODS"
        rows = [it for it in items if it.data(mp.KEY_ROLE) is not None]
        for h in heads:
            self.assertFalse(h.flags() & mp.Qt.ItemFlag.ItemIsEnabled)
            self.assertTrue(h.font().bold())
            self.assertNotEqual(h.font().bold(), rows[0].font().bold())


class MenuShortcutTest(PlayerHarness):
    def test_library_menu_has_shortcuts_and_none_clash(self):
        self.make_player(["One"])
        p = self.player
        lib = p.menuBar().actions()[0].menu()
        keys = {a.text().replace("&", ""): a.shortcut().toString() for a in lib.actions()}
        self.assertEqual(keys["Add music folder..."], "Ctrl+O")
        self.assertEqual(keys["Rescan library"], "F5")
        seen = {}
        for a in p.findChildren(mp.QAction):
            k = a.shortcut().toString()
            if k:
                self.assertNotIn(k, seen, f"{k}: {a.text()} and {seen.get(k)}")
                seen[k] = a.text()



class TickBoxTest(PlayerHarness):
    def test_an_empty_tick_box_can_be_seen_on_the_dark_theme(self):
        self.make_player(["One"], theme="Dark")
        p = self.player
        p.resize(1100, 700)
        p.show()
        p.stack.setCurrentIndex(1)                     # Soulseek results: "Free slots only"
        box = p.free_check
        self.assertTrue(wait_for(box.isVisible, 2))
        bg = QColor(p.scheme["bg"])

        opt = QStyleOptionButton()
        box.initStyleOption(opt)
        square = box.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, opt, box)   # not the text

        def strongest(checked):
            box.setChecked(checked)
            img = box.grab().toImage()
            dpr = img.devicePixelRatio()
            return max(mp.contrast_ratio(img.pixelColor(int(x * dpr), int(y * dpr)), bg)
                       for x in range(square.left(), square.right() + 1)
                       for y in range(square.top(), square.bottom() + 1))
        self.assertGreaterEqual(strongest(False), 3.0)        # WCAG: 3:1 for the outline of a control
        self.assertGreaterEqual(strongest(True), 3.0)



class SmallScreenTest(PlayerHarness):
    def test_the_window_fits_a_laptop_screen(self):
        """1366 x 768, or 1920 x 1080 at 150 %, leave about 700 px of height (eozMP's own default size)."""
        self.make_player(["One"])
        self.assertLessEqual(self.player.minimumSizeHint().height(), 700)

    def test_search_results_show_several_songs(self):
        self.make_player([f"Song {i}" for i in range(1, 9)])
        p = self.player
        p.resize(1100, 700)
        p.show()
        p.search.setText("unknown")       # the artist, the album and every song match
        table = p.search_songs
        self.assertTrue(wait_for(lambda: table.rowCount() == 8 and table.isVisible(), 5))
        self.assertTrue(p.search_sections["artists"][1].isVisible() and p.search_sections["albums"][1].isVisible())
        wait_for(lambda: False, 0.3)
        self.assertGreaterEqual(table.viewport().height() // table.rowHeight(0), 5)


if __name__ == "__main__":
    unittest.main()
