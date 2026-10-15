"""
1.3.1 fixes: the PC stays silent while the music plays on a TV or phone, moved-aside duplicates stay out of
the library, and the installer's slskd web page never keeps the well-known password.
Nothing here plays a song, so no sound comes out.
"""
import time
import unittest

from test_core import TempDirTest, mp
from test_player import PlayerHarness


class SilentWhileElsewhereTest(PlayerHarness):
    def setUp(self):
        super().setUp()
        self.make_player(["One"], remote_port=18877)
        self.p = self.player
        self.assertFalse(self.p.audio.isMuted())

    def test_casting_keeps_the_pc_silent_until_it_stops(self):
        p = self.p
        p.start_cast({"name": "Nowhere", "location": "x", "av": "http://127.0.0.1:9/av", "rc": ""})
        self.assertTrue(p.audio.isMuted())
        p.volume.setValue(40)                    # moving the volume must not un-mute the PC
        p.toggle_mute()                          # neither may the mute button
        self.assertTrue(p.audio.isMuted())
        p.stop_cast()
        self.assertFalse(p.audio.isMuted())
        p.set_remote(False)

    def test_phone_listening_ends_when_the_phone_stops_asking(self):
        p = self.p
        p.set_remote(True)
        self.addCleanup(lambda: p.set_remote(False))
        p.on_remote_command("mute", "1")
        p.volume.setValue(40)
        self.assertTrue(p.audio.isMuted())
        p.remote.last_poll = time.time() - 60    # the phone page was closed a minute ago
        p.update_remote_state()
        self.assertFalse(p.audio.isMuted())

    def test_a_muted_pc_stays_muted_after_casting(self):
        p = self.p
        p.toggle_mute()
        p.start_cast({"name": "Nowhere", "location": "x", "av": "http://127.0.0.1:9/av", "rc": ""})
        p.stop_cast()
        self.assertTrue(p.audio.isMuted())
        p.set_remote(False)


class DuplicatesFolderTest(TempDirTest):
    def test_moved_copies_are_not_scanned_again(self):
        music = self.tmp / "music"
        (music / mp.DUPLICATES_FOLDER).mkdir(parents=True)
        keep, moved = music / "song.wav", music / "song (2).wav"
        for f in (keep, moved):
            f.write_bytes(b"")
        mp.move_to_duplicates([str(moved)], str(music))
        self.assertTrue((music / mp.DUPLICATES_FOLDER / "song (2).wav").exists())   # moved, not deleted
        scanned = [t["path"] for t in mp.scan_folders([str(music)])]
        self.assertEqual([p.replace("\\", "/").rsplit("/", 1)[1] for p in scanned], ["song.wav"])


class InstallerSlskdPasswordTest(TempDirTest):
    YML = ('﻿# Written by the eozMP installer. See "Soulseek Guide.txt" in the eozMP folder.\r\n'
           'soulseek:\r\n  username: "me123"\r\n  password: "slskd"\r\n\r\nweb:\r\n  authentication:\r\n'
           '    username: slskd\r\n    password: slskd\r\n    api_keys:\r\n')

    def test_the_well_known_web_password_is_replaced(self):
        path = self.tmp / "slskd.yml"
        path.write_text(self.YML, encoding="utf-8", newline="")
        self.assertTrue(mp.secure_installer_slskd(path))
        text = path.read_text(encoding="utf-8")
        self.assertNotIn("    password: slskd\n", text)
        self.assertIn('  password: "slskd"', text)          # the Soulseek login is left alone
        self.assertFalse(mp.secure_installer_slskd(path))   # and only once

    def test_a_file_you_wrote_yourself_is_never_touched(self):
        path = self.tmp / "slskd.yml"
        mine = self.YML.replace("# Written by the eozMP installer", "# my own settings")
        path.write_text(mine, encoding="utf-8", newline="")
        self.assertFalse(mp.secure_installer_slskd(path))
        with open(path, encoding="utf-8", newline="") as f:
            self.assertEqual(f.read(), mine)


if __name__ == "__main__":
    unittest.main()
