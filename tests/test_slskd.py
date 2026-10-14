"""
The slskd address and the connection test, against a small fake slskd on this PC.
"""
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from test_core import mp


class FakeSlskd(BaseHTTPRequestHandler):
    server_state = {}

    def do_GET(self):
        if self.headers.get("X-API-Key") != "good-key":
            self.send_response(401)
            self.end_headers()
            return
        if self.path == "/api/v0/server":
            body = json.dumps(self.server_state).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, *_args):
        pass


class SlskdAddressTest(unittest.TestCase):
    def test_address_without_http_gets_it(self):
        self.assertEqual(mp.slskd_address("localhost:5030"), "http://localhost:5030")
        self.assertEqual(mp.slskd_address("  localhost:5030/ "), "http://localhost:5030")

    def test_full_address_is_kept(self):
        self.assertEqual(mp.slskd_address("http://192.168.1.5:5030"), "http://192.168.1.5:5030")
        self.assertEqual(mp.slskd_address("https://box.local/slskd/"), "https://box.local/slskd")

    def test_empty_stays_empty(self):
        self.assertEqual(mp.slskd_address(""), "")


class ConnectionTestTest(unittest.TestCase):
    def setUp(self):
        self.httpd = HTTPServer(("127.0.0.1", 0), FakeSlskd)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        self.url = f"127.0.0.1:{self.httpd.server_port}"     # typed without http://

    def check(self, state, key="good-key"):
        FakeSlskd.server_state = state
        return mp.check_slskd(mp.Slskd(self.url, key))

    def test_logged_in(self):
        ok, msg = self.check({"isConnected": True, "isLoggedIn": True, "state": "Connected, LoggedIn"})
        self.assertTrue(ok)
        self.assertIn("logged in to Soulseek", msg)

    def test_slskd_runs_but_soulseek_login_failed(self):
        ok, msg = self.check({"isConnected": True, "isLoggedIn": False, "state": "Connected"})
        self.assertFalse(ok)
        self.assertIn("isn't logged in", msg)

    def test_slskd_runs_but_is_not_connected(self):
        ok, msg = self.check({"isConnected": False, "isLoggedIn": False, "state": "Disconnected"})
        self.assertFalse(ok)
        self.assertIn("isn't connected to Soulseek", msg)

    def test_wrong_key(self):
        with self.assertRaises(RuntimeError) as cm:
            self.check({}, key="bad")
        self.assertIn("API key", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
