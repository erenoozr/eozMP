"""
The "a new version is out" check. GitHub is never contacted here: the lookup is replaced by a fake.
"""
import json
import time
import unittest
from unittest import mock

from test_mpv_engine import wait_for
from test_player import PlayerHarness, mp

LATEST = {"tag_name": "v9.9", "html_url": "https://github.com/erenoozr/eozMP/releases/tag/v9.9", "name": "eozMP v9.9"}


class VersionTest(unittest.TestCase):
    def test_newer_versions(self):
        self.assertTrue(mp.is_newer("v1.2", "1.1"))
        self.assertTrue(mp.is_newer("1.10", "1.9"))
        self.assertTrue(mp.is_newer("v2", "1.9.9"))
        self.assertTrue(mp.is_newer("v1.1.1", "1.1"))

    def test_same_or_older_versions(self):
        self.assertFalse(mp.is_newer("v1.1", "1.1"))
        self.assertFalse(mp.is_newer("v1.1.0", "1.1"))
        self.assertFalse(mp.is_newer("v1.0", "1.1"))

    def test_odd_tags_are_never_newer(self):
        self.assertFalse(mp.is_newer("nightly", "1.1"))
        self.assertFalse(mp.is_newer("", "1.1"))

    def test_tag_with_words_after_the_number(self):
        self.assertTrue(mp.is_newer("v1.2 - Bugfix", "1.1"))

    def test_beta_comes_after_the_last_release_and_before_its_own(self):
        self.assertTrue(mp.is_newer("v1.2-beta.1", "1.1"))
        self.assertTrue(mp.is_newer("v1.2", "1.2-beta.1"))
        self.assertTrue(mp.is_newer("v1.2-beta.2", "1.2-beta.1"))
        self.assertTrue(mp.is_newer("v1.2-rc.1", "1.2-beta.3"))
        self.assertFalse(mp.is_newer("v1.2-beta.1", "1.2"))
        self.assertFalse(mp.is_newer("v1.1", "1.2-beta.1"))


class UpdateCheckTest(PlayerHarness):
    def start_with(self, latest=LATEST, **cfg):
        self.prompts = []
        self.lookups = []

        def fake_lookup():
            self.lookups.append(time.time())
            if isinstance(latest, Exception):
                raise latest
            return latest
        for target, value in (("latest_release", fake_lookup),):
            patcher = mock.patch.object(mp, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(mp.Player, "offer_update", lambda _self, rel: self.prompts.append(rel))
        patcher.start()
        self.addCleanup(patcher.stop)
        settings = {"update_check": True}
        settings.update(cfg)
        self.make_player(["One"], **settings)

    def test_a_newer_release_is_offered_once(self):
        self.start_with()
        self.assertTrue(wait_for(lambda: self.prompts, 10))
        self.assertEqual(self.prompts[0]["tag_name"], "v9.9")
        saved = json.loads(mp.CONFIG_FILE.read_text(encoding="utf-8"))
        self.assertGreater(saved["update_last_check"], 0)

    def test_checks_at_most_once_a_day(self):
        self.start_with(update_last_check=time.time() - 3600)
        wait_for(lambda: False, 1.5)
        self.player.auto_check_updates()
        wait_for(lambda: False, 0.5)
        self.assertEqual(self.lookups, [])

    def test_turned_off_means_no_lookup(self):
        self.start_with(update_check=False)
        self.player.auto_check_updates()
        wait_for(lambda: False, 0.5)
        self.assertEqual(self.lookups, [])

    def test_skipped_version_is_not_offered_again(self):
        self.start_with(update_skip="v9.9")
        self.player.auto_check_updates()
        self.assertTrue(wait_for(lambda: self.lookups, 5))
        wait_for(lambda: False, 0.5)
        self.assertEqual(self.prompts, [])

    def test_up_to_date_says_nothing(self):
        self.start_with(latest={"tag_name": "v" + mp.APP_VERSION, "html_url": "x"})
        self.player.auto_check_updates()
        self.assertTrue(wait_for(lambda: self.lookups, 5))
        wait_for(lambda: False, 0.5)
        self.assertEqual(self.prompts, [])

    def test_no_internet_is_quiet(self):
        self.start_with(latest=OSError("no network"))
        self.player.auto_check_updates()
        self.assertTrue(wait_for(lambda: self.lookups, 5))
        wait_for(lambda: False, 0.5)
        self.assertEqual(self.prompts, [])

    def test_asking_from_the_menu_ignores_the_daily_limit_and_the_skip(self):
        self.start_with(update_last_check=time.time(), update_skip="v9.9")
        self.player.check_updates_now()
        self.assertTrue(wait_for(lambda: self.prompts, 5))


class OfferWindowTest(PlayerHarness):
    def press(self, label, rel=LATEST):
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import QApplication, QMessageBox

        def click():
            box = QApplication.activeModalWidget()
            if not isinstance(box, QMessageBox):
                QTimer.singleShot(20, click)
                return
            self.shown_text = box.text()
            next(b for b in box.buttons() if b.text() == label).click()
        QTimer.singleShot(20, click)
        self.player.offer_update(rel)

    def test_skip_remembers_the_version(self):
        self.make_player(["One"])
        self.press("Skip this version")
        self.assertIn("v9.9", self.shown_text)
        self.assertEqual(json.loads(mp.CONFIG_FILE.read_text(encoding="utf-8"))["update_skip"], "v9.9")

    def test_download_opens_only_the_github_page(self):
        self.make_player(["One"])
        opened = []
        with mock.patch.object(mp.QDesktopServices, "openUrl", side_effect=lambda u: opened.append(u.toString())):
            self.press("Download")
            self.press("Download", dict(LATEST, html_url="https://evil.example/eozMP.exe"))
        self.assertEqual(opened, [LATEST["html_url"], "https://github.com/erenoozr/eozMP/releases/latest"])


if __name__ == "__main__":
    unittest.main()
