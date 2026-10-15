"""
D6: which copy of an album the Soulseek discography download picks. A copy that misses songs loses;
otherwise lossless beats lossy, then the higher bitrate, then a free upload slot, then speed.
Run from the project folder:   py -3 -m unittest discover tests -p "test_discography.py"
"""
import unittest

from test_core import mp


def copy_of(user, n, ext="mp3", kbps=320, free=True, speed=1000, folder="Band\\Band - Album (2001)"):
    return [{"username": user, "filename": f"{user}\\{folder}\\{i:02d} Song {i}.{ext}", "size": 1000, "ext": ext,
             "bitrate": kbps if ext == "mp3" else 0, "free": free, "speed": speed, "queue": 0}
            for i in range(1, n + 1)]


class DiscographyQualityTest(unittest.TestCase):
    def picked(self, *copies):
        picks = mp.pick_discography([row for c in copies for row in c], "Band")
        self.assertEqual(len(picks), 1)
        return picks[0]["files"][0]["username"]

    def test_lossless_beats_a_bonus_track(self):
        self.assertEqual(self.picked(copy_of("mp3", 13), copy_of("flac", 12, "flac")), "flac")

    def test_a_copy_missing_songs_loses_even_when_lossless(self):
        self.assertEqual(self.picked(copy_of("mp3", 12), copy_of("flac", 8, "flac")), "mp3")

    def test_on_a_short_album_every_song_counts(self):
        self.assertEqual(self.picked(copy_of("mp3", 5), copy_of("flac", 4, "flac")), "mp3")

    def test_lossless_beats_a_free_slot(self):
        self.assertEqual(self.picked(copy_of("mp3", 10, free=True), copy_of("flac", 10, "flac", free=False)), "flac")

    def test_higher_bitrate_beats_a_free_slot(self):
        self.assertEqual(self.picked(copy_of("low", 10, kbps=128, free=True), copy_of("high", 10, free=False)), "high")

    def test_free_slot_then_speed_decide_between_equal_copies(self):
        self.assertEqual(self.picked(copy_of("queued", 10, free=False, speed=9000), copy_of("free", 10)), "free")
        self.assertEqual(self.picked(copy_of("slow", 10, speed=10), copy_of("fast", 10, speed=5000)), "fast")

    def test_nearly_the_same_bitrate_is_the_same(self):
        """V0 (~245k) against ~250k: not worth waiting in someone's queue for."""
        self.assertEqual(self.picked(copy_of("queued", 10, kbps=250, free=False), copy_of("free", 10, kbps=245)),
                         "free")


if __name__ == "__main__":
    unittest.main()
