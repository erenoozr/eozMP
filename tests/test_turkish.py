"""
The Turkish interface ("tr" in eozmp_lang.py): every translation keeps the placeholders, the spacing the
layout depends on and the menu shortcuts of the English text, and a few fixed texts read right through _t().
Run alone with:   python -m unittest discover tests -p "test_turkish.py"
"""
import importlib.util
import os
import re
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from test_core import mp  # noqa: E402
from test_player import PlayerHarness  # noqa: E402
from eozmp_lang import LANG  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TR = LANG["tr"]
PH = re.compile(r"\{\d+\}")
ACCEL = re.compile(r"(?<!&)&([^&\s])")   # "&Library" -> "L"; "&&" is a plain "&", "A & B" is no shortcut

# English placeholders that only carry an English word or plural ending ("s", "people have", "Added to"...):
# the Turkish sentence leaves them out on purpose. A placeholder may be dropped only here, never added.
DROPPED = {
    "{0} album{1}  ·  {2} songs": {"{1}"},
    "{0} song{1}  ·  {2}  -  drag to reorder. ": {"{1}"},
    "{0} {1} answered so far.": {"{1}"},
    "{0} {1} shown ({2} files found)": {"{1}"},
    "{0} Favorites: {1} song(s)": {"{0}"},
    "{0}: {1} song(s)": {"{0}"},
}
BRANDS = ["Soulseek", "slskd", "eozMP", "MusicBrainz", "VLC", "lrclib.net", "AcoustID", "Last.fm", "ReplayGain",
          "Eren Özer"]


def edges(text):
    """The spaces / line breaks at the start and at the end."""
    return text[:len(text) - len(text.lstrip())], text[len(text.rstrip()):]


def load_generator():
    spec = importlib.util.spec_from_file_location("make_translations", ROOT / "tools" / "make_translations.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    return gen


class TurkishTableTest(unittest.TestCase):
    """Checks that hold for every Turkish entry."""

    def test_every_interface_text_has_a_turkish_entry(self):
        missing = [t for t in load_generator().collect() if t not in TR]
        self.assertEqual(missing, [], "run tools/make_translations.py")

    def test_placeholders_match_the_english(self):
        for en, tr in TR.items():
            with self.subTest(en=en):
                want, got = PH.findall(en), PH.findall(tr)
                self.assertEqual(len(got), len(set(got)), "a placeholder twice")
                self.assertEqual(sorted(set(want) - DROPPED.get(en, set())), sorted(got))

    def test_dropped_placeholders_are_really_gone(self):
        for en, dropped in DROPPED.items():
            with self.subTest(en=en):
                self.assertIn(en, TR)
                self.assertFalse(dropped & set(PH.findall(TR[en])))

    def test_leading_and_trailing_spaces_are_kept(self):
        # "   (best - kept)" is glued to a file name, "Searching... " to a count, "Up next\n" to a song
        for en, tr in TR.items():
            with self.subTest(en=en):
                self.assertEqual(edges(tr), edges(en))

    def test_menu_shortcut_letters_are_kept(self):
        for en, tr in TR.items():
            if ACCEL.search(en):
                with self.subTest(en=en):
                    self.assertEqual(len(ACCEL.findall(tr)), 1, tr)

    def test_brand_names_stay(self):
        # the generator also re-translates an entry whose brand name went missing
        for en, tr in TR.items():
            for brand in BRANDS:
                if brand in en:
                    with self.subTest(en=en, brand=brand):
                        self.assertIn(brand, tr)

    def test_menu_bar_shortcuts_are_unique_and_plain_letters(self):
        src = (ROOT / "musicplayer.py").read_text(encoding="utf-8")
        titles = re.findall(r'menuBar\(\)\.add(?:Menu|Action)\("([^"]+)"\)', src)
        self.assertGreaterEqual(len(titles), 6)
        letters = []
        for en in titles:
            found = ACCEL.findall(TR.get(en, en))
            self.assertEqual(len(found), 1, en)
            self.assertTrue(found[0].isascii() and found[0].isalpha(), f"{TR.get(en, en)}: Alt+letter on every keyboard")
            letters.append(found[0].lower())
        self.assertEqual(len(letters), len(set(letters)), [TR.get(t, t) for t in titles])

    def test_one_word_for_one_thing(self):
        # glossary: Kitaplık (not Kütüphane), Sıra (not Kuyruk), Çal (not Oynat), Ayarlar (not Tercihler),
        # Ekolayzer, and the friendly "sen" form ("seç", not "seçin"; "kitaplığın", not "kitaplığınız")
        banned = re.compile(r"[Kk]ütüphane|[Kk]uyru|[Oo]ynat(?!ıcı)|Tercihler|[Ee]kolayzır|"
                            r"(?:ınız|iniz|unuz|ünüz)\b|\b(?:seçin|tıklayın|kullanın|deneyin|ekleyin|basın|yapın)\b")
        for en, tr in TR.items():
            with self.subTest(en=en):
                self.assertIsNone(banned.search(tr), tr)


class TurkishTextsTest(unittest.TestCase):
    """A few fixed texts, read the way the app reads them."""

    def setUp(self):
        mp.set_ui_language("tr")
        self.addCleanup(mp.set_ui_language, "en")

    def test_fixed_texts(self):
        t = mp._t
        self.assertEqual(t("&Library"), "&Kitaplık")
        self.assertEqual(t("Library"), "Kitaplık")
        self.assertEqual(t("P&references"), "&Ayarlar")
        self.assertEqual(t("Add to queue"), "Sıraya ekle")
        self.assertEqual(t("Shuffle: on"), "Karıştırma: açık")
        self.assertEqual(t("  ·  12 plays"), "  ·  12 kez çalındı")
        self.assertEqual(t("   (best - kept)"), "   (en iyisi - kalıyor)")
        self.assertEqual(t("Searching... "), "Aranıyor... ")
        self.assertEqual(t("No lyrics found.\nOnline lookup is off (Preferences > Lyrics)."),
                         "Şarkı sözü bulunamadı.\nİnternette arama kapalı (Ayarlar > Şarkı sözleri).")

    def test_english_plurals_do_not_leak(self):
        t = mp._t
        self.assertEqual(t("3 albums  ·  12 songs"), "3 albüm  ·  12 şarkı")
        self.assertEqual(t("1 album  ·  2 songs"), "1 albüm  ·  2 şarkı")
        self.assertEqual(t("Added to queue: 3 song(s)"), "Sıraya eklendi: 3 şarkı")
        self.assertEqual(t("Playing next: 1 song(s)"), "Sıraya eklendi: 1 şarkı")
        self.assertEqual(t("Removed from Favorites: 2 song(s)"), "Favoriler güncellendi: 2 şarkı")
        self.assertEqual(t("12 albums shown (40 files found)"), "12 sonuç gösteriliyor (40 dosya bulundu)")
        self.assertEqual(mp.answered_text(1), "Şu ana kadar 1 kişi yanıt verdi.")
        self.assertEqual(mp._t(mp.searching_text(3)),     # the label's setText() does this _t()
                         "Soulseek'te aranıyor... Şu ana kadar 3 kişi yanıt verdi. Sonuçlar arama bitince görünür.")

    def test_texts_built_from_parts(self):
        self.assertEqual(mp._t("Up next\nHadi Bakalım  -  Sezen Aksu"), "Sıradaki\nHadi Bakalım  -  Sezen Aksu")
        msg = mp.enqueue_report(2, {"ayse": 1}, "Queued {n} file(s). Watch them on the Downloads page - finished "
                                               "files appear in your library by themselves.")
        self.assertTrue(msg.startswith("2 dosya sıraya alındı."), msg)
        self.assertIn(" 1 dosya sıraya alınamadı: ayse çevrimdışı olabilir", msg)

    def test_names_are_never_translated(self):
        self.assertEqual(mp._t(mp._raw("Home")), "Home")
        self.assertEqual(mp._t("Home"), "Ana sayfa")


class TurkishMenuTest(PlayerHarness):
    """The real menus: inside every menu each shortcut letter is used once."""

    def test_shortcut_letters_unique_in_every_menu(self):
        self.make_player(["One"])
        mp.set_ui_language("tr")
        self.addCleanup(mp.set_ui_language, "en")
        menus = [("menu bar", self.player.menuBar().actions())]
        for act in self.player.menuBar().actions():
            if act.menu() is not None:
                menus.append((act.text(), act.menu().actions()))
        for name, actions in menus:
            with self.subTest(menu=name):
                letters = []
                for act in actions:
                    en = act.text()
                    if ACCEL.search(en):
                        found = ACCEL.findall(mp._t(en))
                        self.assertEqual(len(found), 1, mp._t(en))
                        letters.append(found[0].lower())
                self.assertEqual(len(letters), len(set(letters)), [mp._t(a.text()) for a in actions])
                if name == "menu bar":
                    self.assertGreaterEqual(len(letters), 6)


if __name__ == "__main__":
    unittest.main()
