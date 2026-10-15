"""
The duplicate finder moves copies aside, so two different songs must never count as one.
"""
import unittest

from test_core import mp


def song(title, artist, length, path):
    return {"title": title, "artist": artist, "length": length, "path": path, "size": 1}


class DuplicateKeyTest(unittest.TestCase):
    def test_different_songs_in_another_script_are_not_duplicates(self):
        # their titles used to shrink to "" (only a-z and 0-9 were kept), so any two songs of
        # about the same length by a Cyrillic or Japanese artist looked like the same song
        tracks = [song("Группа крови", "Кино", 286, "a.mp3"), song("Звезда по имени Солнце", "Кино", 288, "b.mp3"),
                  song("First Love", "宇多田ヒカル", 260, "c.mp3"), song("花束を君に", "宇多田ヒカル", 261, "d.mp3")]
        self.assertEqual(mp.find_duplicates(tracks), [])

    def test_the_same_song_in_another_script_is_still_found(self):
        tracks = [song("Группа крови", "Кино", 286, "a.mp3"), song("Группа крови", "Кино", 287, "b.flac")]
        groups = mp.find_duplicates(tracks)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0][0]["path"], "b.flac")   # the lossless copy is the one kept

    def test_case_and_punctuation_still_do_not_matter(self):
        tracks = [song("Hey Jude", "The Beatles", 431, "a.mp3"), song("hey jude!", "the beatles", 430, "b.mp3")]
        self.assertEqual(len(mp.find_duplicates(tracks)), 1)


if __name__ == "__main__":
    unittest.main()
