"""
The Soulseek side of eozMP against a small fake slskd on this PC: searching, queueing downloads,
the downloads poll, sorting finished downloads, and picking a discography.
"""
import json
import os
import socket
import threading
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from test_core import TempDirTest, mp  # noqa: E402
from test_mpv_engine import tone, wait_for  # noqa: E402
from test_player import PlayerHarness  # noqa: E402


class FakeClock:
    """Stands in for the time module inside musicplayer, so a 'two minute' search takes no time."""

    def __init__(self):
        self.t = 1000.0

    def time(self):
        return self.t

    monotonic = time

    def sleep(self, seconds):
        self.t += seconds


class FakeSlskd(BaseHTTPRequestHandler):
    """Answers like slskd does. Everything it should do is in `world`, set by each test."""
    world = {}

    def reply(self, code, body=None):
        raw = json.dumps(body).encode() if body is not None else b""
        self.send_response(code)
        if raw:
            self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def handle_any(self, method):
        w = self.world
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length)) if length else None
        path = urllib.parse.unquote(self.path[len("/api/v0"):])
        w.setdefault("log", []).append((method, path, body))
        parts = [p for p in path.split("?")[0].split("/") if p]
        if parts[:1] == ["searches"]:
            return self.search(method, parts, body)
        if parts[:2] == ["transfers", "downloads"]:
            if method == "GET" and len(parts) == 2:
                return self.reply(200, w.get("downloads", []))
            if method == "POST" and len(parts) == 3:
                user = parts[2]
                if user in w.get("offline", ()):
                    return self.reply(500, f"User {user} appears to be offline")
                failed = [f["filename"] for f in body if f["filename"] in w.get("refused", ())]
                return self.reply(201, {"enqueued": [f for f in body if f["filename"] not in failed],
                                        "failed": failed})
            if method == "DELETE":
                return self.reply(204)
        return self.reply(404)

    def search(self, method, parts, body):
        w = self.world
        clock = w["clock"]
        if method == "POST":
            w["search"] = {"id": body["id"], "started": clock.t, "stopped": False}
            return self.reply(200, {"id": body["id"], "isComplete": False})
        s = w.get("search")
        if s is None or parts[1] != s["id"]:
            return self.reply(404)
        if method == "PUT":           # slskd: stop this search
            s["stopped"] = True
            return self.reply(204)
        if method == "DELETE":
            return self.reply(204)
        done_after = w.get("done_after")
        complete = s["stopped"] or (done_after is not None and clock.t - s["started"] >= done_after)
        if len(parts) == 3 and parts[2] == "responses":
            # real slskd only saves the answers once the search is over
            return self.reply(200, w["responses"] if complete or w.get("live") else [])
        answered = min(len(w["responses"]), int(clock.t - s["started"]) // 2)
        return self.reply(200, {"id": s["id"], "isComplete": complete, "responseCount": answered})

    def do_GET(self):
        self.handle_any("GET")

    def do_POST(self):
        self.handle_any("POST")

    def do_PUT(self):
        self.handle_any("PUT")

    def do_DELETE(self):
        self.handle_any("DELETE")

    def log_message(self, *_args):
        pass


def start_fake(test):
    """Starts a fake slskd for one test and returns its address."""
    FakeSlskd.world = {"clock": FakeClock(), "responses": [], "log": []}
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), FakeSlskd)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    test.addCleanup(httpd.server_close)
    test.addCleanup(httpd.shutdown)
    return f"http://127.0.0.1:{httpd.server_port}"


def response(user, files, free=True, speed=1000):
    return {"username": user, "hasFreeUploadSlot": free, "uploadSpeed": speed, "queueLength": 0,
            "files": [{"filename": f, "size": 1000, "bitRate": 320} for f in files]}


def row(user, filename, ext="mp3", free=True, speed=1000):
    return {"username": user, "filename": filename, "size": 1000, "ext": ext, "bitrate": 320,
            "free": free, "speed": speed, "queue": 0}


def album(user, folder, n=4, ext="mp3", free=True):
    return [row(user, f"{folder}\\{i:02d} Song {i}.{ext}", ext, free) for i in range(1, n + 1)]


# ---------------------------------------------------------------- D3: long searches
class LongSearchTest(unittest.TestCase):
    def setUp(self):
        self.url = start_fake(self)
        self.world = FakeSlskd.world
        self.world["responses"] = [response(f"user{i}", [f"Music\\Band\\Album\\0{i} Song.flac"])
                                   for i in range(5)]
        patcher = mock.patch.object(mp, "time", self.world["clock"])
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_search(self):
        w = mp.SearchWorker(mp.Slskd(self.url, "key"), "band album")
        got, progress, errors = [], [], []
        w.results.connect(got.append)
        w.failed.connect(errors.append)
        if hasattr(w, "progress"):
            w.progress.connect(progress.append)
        w.run()            # right here, so the signals arrive straight away
        self.assertEqual(errors, [])
        return got, progress

    def test_search_longer_than_30_seconds_still_shows_its_results(self):
        self.world["done_after"] = 45
        got, _progress = self.run_search()
        self.assertTrue(got, "no results were sent at all")
        self.assertEqual(len(got[-1]), 5)

    def test_shows_how_many_people_answered_while_waiting(self):
        self.world["done_after"] = 20
        _got, progress = self.run_search()
        self.assertTrue(any(n > 0 for n in progress), progress)

    def test_search_that_never_ends_is_stopped_and_its_results_shown(self):
        self.world["done_after"] = None
        got, _progress = self.run_search()
        self.assertIn("PUT", [m for m, _p, _b in self.world["log"]])
        self.assertEqual(len(got[-1]), 5)

    def test_results_slskd_hands_out_early_are_shown_early(self):
        self.world["done_after"] = 20
        self.world["live"] = True
        got, _progress = self.run_search()
        self.assertGreater(len(got), 1)
        self.assertEqual(len(got[0]), 5)


# ---------------------------------------------------------------- D7: cap after filtering
class ResultCapTest(unittest.TestCase):
    def test_lossless_files_are_not_cut_off_before_the_filter(self):
        fast_mp3 = [response(f"m{i}", [f"A\\{n}.mp3" for n in range(10)], speed=9999) for i in range(250)]
        slow_flac = [response("slow", [f"B\\{n}.flac" for n in range(10)], free=False, speed=1)]
        rows = mp.flatten_responses(fast_mp3 + slow_flac)
        lossless = [r for r in rows if mp.passes_filters(r, "Lossless only", False)]
        self.assertEqual(len(lossless), 10)


# ---------------------------------------------------------------- D6: discography picking
class DiscographyPickTest(unittest.TestCase):
    def names(self, rows, artist):
        return sorted(pk["name"] for pk in mp.pick_discography(rows, artist))

    def test_album_named_after_the_artist_is_kept(self):
        rows = album("u1", "Music\\Weezer\\Weezer - Weezer (1994) [FLAC]", ext="flac") \
            + album("u2", "Music\\Weezer\\Weezer - Pinkerton (1996)")
        self.assertEqual(self.names(rows, "Weezer"), ["Weezer - Pinkerton (1996)",
                                                      "Weezer - Weezer (1994) [FLAC]"])

    def test_self_titled_album_matches_the_one_you_own(self):
        a = mp.album_key("Weezer", "Weezer")
        self.assertTrue(a)
        self.assertEqual(mp.album_key("Weezer - Weezer (1994) [FLAC]", "Weezer"), a)
        self.assertEqual(mp.album_key("Weezer (1994)", "Weezer"), a)

    def test_album_named_like_a_year_is_kept(self):
        rows = album("u1", "Taylor Swift\\Taylor Swift - 1989 (2014) [FLAC]", ext="flac") \
            + album("u2", "Taylor Swift\\Taylor Swift - Red")
        self.assertEqual(self.names(rows, "Taylor Swift"), ["Taylor Swift - 1989 (2014) [FLAC]",
                                                            "Taylor Swift - Red"])
        self.assertEqual(mp.album_key("Taylor Swift - 1989 (2014) [FLAC]", "Taylor Swift"),
                         mp.album_key("1989", "Taylor Swift"))
        self.assertEqual(mp.album_key("Taylor Swift - 2014 - 1989", "Taylor Swift"),
                         mp.album_key("1989", "Taylor Swift"))

    def test_years_and_formats_are_still_ignored(self):
        self.assertEqual(mp.album_key("Band - Album (2009) [FLAC 24bit]", "Band"), "album")
        self.assertEqual(mp.album_key("Album", "Band"), "album")

    def test_other_artist_whose_name_starts_the_same_is_left_out(self):
        rows = album("u1", "Music\\Museum of Love\\Museum of Love - Monsters") \
            + album("u2", "Music\\Muse\\Muse - Absolution")
        self.assertEqual(self.names(rows, "Muse"), ["Muse - Absolution"])

    def test_artist_name_inside_an_album_word_is_not_cut_out(self):
        self.assertEqual(mp.album_key("Muse - Museum Pieces", "Muse"), "museum pieces")

    def test_non_latin_names_work(self):
        rows = album("u1", "Музыка\\Кино\\Кино - Группа крови (1988)") \
            + album("u2", "Музыка\\Кино\\Кино - Звезда по имени Солнце") \
            + album("u3", "Музыка\\Аквариум\\Аквариум - Радио Африка")
        self.assertEqual(self.names(rows, "Кино"), ["Кино - Группа крови (1988)",
                                                    "Кино - Звезда по имени Солнце"])

    def test_accents_do_not_matter(self):
        rows = album("u1", "Bjork\\Bjork - Homogenic")
        self.assertEqual(self.names(rows, "Björk"), ["Bjork - Homogenic"])

    def test_disc_folders_still_join_their_album(self):
        rows = album("u1", "Band\\Band - Big Album\\CD1") + album("u1", "Band\\Band - Big Album\\CD2")
        self.assertEqual(self.names(rows, "Band"), ["Band - Big Album (CD1)", "Band - Big Album (CD2)"])


# ---------------------------------------------------------------- D8: untagged downloads
class UntaggedDownloadTest(TempDirTest):
    def setUp(self):
        super().setUp()
        self.src = self.tmp / "downloads"
        self.dest = self.tmp / "library"
        self.dest.mkdir()

    def download(self, folder, name="01 Song.wav"):
        (self.src / folder).mkdir(parents=True, exist_ok=True)
        tone(self.src / folder / name, 0.05)

    def moved(self):
        return sorted(p.relative_to(self.dest).as_posix() for p in self.dest.rglob("*.wav"))

    def test_artist_and_album_come_from_the_folder_name(self):
        self.download("Some Band - Great Album (2009) [FLAC]")
        self.assertEqual(mp.organize_downloads(str(self.src), str(self.dest)), 1)
        self.assertEqual(self.moved(), ["Some Band/Great Album/01 Song.wav"])

    def test_artist_year_album_folder(self):
        self.download("Some Band - 2009 - Great Album")
        mp.organize_downloads(str(self.src), str(self.dest))
        self.assertEqual(self.moved(), ["Some Band/Great Album/01 Song.wav"])

    def test_folder_with_only_the_album_name(self):
        self.download("Great Album")
        mp.organize_downloads(str(self.src), str(self.dest))
        self.assertEqual(self.moved(), ["Unknown Artist/Great Album/01 Song.wav"])

    def test_disc_folder_uses_the_album_folder_above_it(self):
        self.download("Some Band - Great Album/CD2")
        mp.organize_downloads(str(self.src), str(self.dest))
        self.assertEqual(self.moved(), ["Some Band/Great Album/01 Song.wav"])

    def test_file_right_in_the_downloads_folder_stays_unknown(self):
        self.src.mkdir()
        tone(self.src / "song.wav", 0.05)
        mp.organize_downloads(str(self.src), str(self.dest))
        self.assertEqual(self.moved(), ["Unknown Artist/Unknown Album/song.wav"])


# ---------------------------------------------------------------- the real window
class SoulseekWindowTest(PlayerHarness):
    def make(self, **cfg):
        self.url = start_fake(self)
        self.world = FakeSlskd.world
        cfg.setdefault("slskd_url", self.url)
        self.make_player(["One"], slskd_key="key", **cfg)
        return self.player

    def posted_to(self):
        return [p.rsplit("/", 1)[-1] for m, p, _b in self.world["log"]
                if m == "POST" and p.startswith("/transfers/downloads/")]

    def status(self):
        return self.player.statusBar().currentMessage()

    # D4
    def test_queueing_goes_on_past_an_offline_user_and_says_what_failed(self):
        p = self.make()
        self.world["offline"] = {"gone"}
        self.world["refused"] = {"Music\\Alb\\03.mp3"}
        p.enqueue_downloads([row("gone", "Music\\Alb\\01.mp3"), row("bob", "Music\\Alb\\02.mp3"),
                             row("bob", "Music\\Alb\\03.mp3"), row("carol", "Music\\Alb\\04.mp3")])
        self.assertTrue(wait_for(lambda: "Queued" in self.status() or "Failed" in self.status(), 10),
                        self.status())
        self.assertEqual(self.posted_to(), ["gone", "bob", "carol"])
        self.assertIn("Queued 2 ", self.status())
        self.assertIn("2 couldn't be queued", self.status())
        self.assertIn("gone", self.status())

    def test_retry_goes_on_past_an_offline_user(self):
        p = self.make()
        self.world["offline"] = {"gone"}
        p.dl_rows = [{"username": u, "id": u + "1", "filename": f"Music\\{u}.mp3", "size": 1,
                      "status": "Failed (Rejected)", "percent": 0} for u in ("gone", "bob")]
        p.retry_failed()
        self.assertTrue(wait_for(lambda: "Retr" in self.status() or "Failed" in self.status(), 10),
                        self.status())
        self.assertEqual(self.posted_to(), ["gone", "bob"])
        self.assertIn("1 couldn't be queued", self.status())

    # D14
    def test_enter_in_the_search_box_only_searches_the_library(self):
        p = self.make()
        p.search.setText("One")
        p.search.returnPressed.emit()
        wait_for(lambda: False, 0.5)
        self.assertNotIn("POST", [m for m, path, _b in self.world["log"] if path.startswith("/searches")])
        self.assertIsNone(p.inline_soul_worker)

    # D10
    def test_unreachable_slskd_is_shown_and_polled_less_often(self):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()                       # nothing listens here now
        p = self.make(slskd_url=f"http://127.0.0.1:{port}")
        p.poll_busy = False
        p.poll_downloads()
        self.assertTrue(wait_for(lambda: "reach slskd" in p.dl_status.text(), 10), p.dl_status.text())
        self.assertGreater(p.poll_timer.interval(), 3000)
        first = p.poll_timer.interval()
        p.poll_downloads()
        self.assertTrue(wait_for(lambda: p.poll_timer.interval() > first, 10))

    def test_polling_speeds_up_again_when_slskd_comes_back(self):
        p = self.make()
        p.poll_timer.setInterval(48000)
        p.poll_fails = 4
        p.poll_busy = False
        p.poll_downloads()
        self.assertTrue(wait_for(lambda: p.poll_timer.interval() == 3000, 10))
        self.assertNotIn("reach slskd", p.dl_status.text())

    # D11
    def test_downloads_finished_while_closed_are_organized(self):
        dl = self.tmp / "dl"
        (dl / "Band - Record").mkdir(parents=True)
        tone(dl / "Band - Record" / "01 Track.wav", 0.05)
        sorted_root = self.tmp / "sorted"
        url = start_fake(self)
        FakeSlskd.world["downloads"] = [{"username": "bob", "directories": [{"files": [
            {"id": "1", "filename": "Music\\Band - Record\\01 Track.wav", "size": 1,
             "state": "Completed, Succeeded", "percentComplete": 100}]}]}]
        self.make_player(["One"], slskd_url=url, slskd_key="key", downloads_dir=str(dl),
                         organize_downloads=True, organize_root=str(sorted_root))
        self.player.poll_busy = False
        self.player.poll_downloads()
        self.assertTrue(wait_for(lambda: (sorted_root / "Band" / "Record" / "01 Track.wav").exists(), 10))


if __name__ == "__main__":
    unittest.main()
