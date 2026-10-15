"""
The PC stays silent while the music plays on a TV or phone, and moved-aside duplicates stay out of the library.
Nothing here plays a song, so no sound comes out.
"""
import socket
import time
import unittest

from test_core import TempDirTest, mp
from test_player import PlayerHarness


def free_port():
    """A port nothing uses right now: a fixed one clashes when two test runs share the PC, and the
    "couldn't start the remote" message box then waits for a click forever."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class FakeTV:
    """Answers every UPnP request with OK (or with an error) and remembers what it was asked."""

    def __init__(self, fail=False):
        import http.server
        import threading
        self.actions = []
        outer = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length") or 0))
                outer.actions.append(self.headers.get("SOAPACTION", "").strip('"').split("#")[-1])
                self.send_response(500 if fail else 200)
                self.send_header("Content-Length", "0")
                self.end_headers()

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        port = self.httpd.server_address[1]
        self.device = {"name": "Fake TV", "location": f"http://127.0.0.1:{port}/d.xml",
                       "av": f"http://127.0.0.1:{port}/av", "rc": f"http://127.0.0.1:{port}/rc"}

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class SilentWhileElsewhereTest(PlayerHarness):
    def setUp(self):
        super().setUp()
        self.make_player(["One"], remote_port=free_port())
        self.p = self.player
        self.tv = FakeTV()
        self.addCleanup(self.tv.close)
        self.assertFalse(self.p.audio.isMuted())

    def test_casting_keeps_the_pc_silent_until_it_stops(self):
        p = self.p
        p.start_cast(self.tv.device)
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
        p.start_cast(self.tv.device)
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


if __name__ == "__main__":
    unittest.main()
