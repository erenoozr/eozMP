"""
The duplicate finder moves copies aside, so two different songs must never count as one.
"""
import json
import os
import unittest

from test_core import TempDirTest, mp


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


class SafeMovingTest(TempDirTest):
    def make(self, rel, data=b"x"):
        f = self.tmp / "music" / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(data)
        return f

    def test_one_file_reached_by_two_paths_is_not_a_copy(self):                 # B5
        real = self.make("a/song.mp3")
        link = self.tmp / "music" / "a" / "again.mp3"
        try:
            os.link(real, link)          # a second name for the same file
        except OSError:
            self.skipTest("hard links not available")
        tracks = [song("Song", "Band", 200, str(real)), song("Song", "Band", 200, str(link))]
        self.assertEqual(mp.find_duplicates(tracks), [])

    def test_an_unreachable_folder_raises_instead_of_crashing_later(self):      # B6
        blocker = self.make("not-a-folder")
        with self.assertRaises(OSError):
            mp.move_aside([str(self.make("a.mp3"))], str(blocker))              # root is a file

    def test_moved_copies_keep_their_folders_and_are_listed(self):              # B15
        a = self.make("Alb1/01.mp3")
        b = self.make("Alb2/01.mp3")
        done, dest = mp.move_aside([str(a), str(b)], str(self.tmp / "music"))
        self.assertEqual(len(done), 2)
        self.assertTrue((self.tmp / "music" / mp.DUPLICATES_FOLDER / "Alb1" / "01.mp3").exists())
        self.assertTrue((self.tmp / "music" / mp.DUPLICATES_FOLDER / "Alb2" / "01.mp3").exists())
        manifest = json.loads((self.tmp / "music" / mp.DUPLICATES_FOLDER / "moved.json").read_text(encoding="utf-8"))
        self.assertEqual([m["from"] for m in manifest], [str(a), str(b)])

    def test_playlists_favorites_and_plays_follow_the_kept_copy(self):          # B15
        playlists = {"Mix": ["old.mp3", "other.mp3", "keep.mp3"]}
        stats = {"favorites": ["old.mp3"], "plays": {"old.mp3": {"count": 3, "last": 5, "seconds": 90.0},
                                                        "keep.mp3": {"count": 1, "last": 9, "seconds": 30.0}},
                 "events": [[1, "old.mp3", 10.0]]}
        self.assertTrue(mp.carry_over(playlists, stats, {"old.mp3": "keep.mp3"}))
        self.assertEqual(playlists["Mix"], ["other.mp3", "keep.mp3"])
        self.assertEqual(stats["favorites"], ["keep.mp3"])
        self.assertEqual(stats["plays"], {"keep.mp3": {"count": 4, "last": 9, "seconds": 120.0}})
        self.assertEqual(stats["events"], [[1, "keep.mp3", 10.0]])

    def test_the_organizer_leaves_moved_aside_copies_alone(self):               # B12
        src = self.tmp / "dl"
        (src / mp.DUPLICATES_FOLDER).mkdir(parents=True)
        aside = src / mp.DUPLICATES_FOLDER / "x.mp3"
        aside.write_bytes(b"x")
        mp.organize_downloads(str(src), str(self.tmp / "lib"), True, True, ())
        self.assertTrue(aside.exists())


class SameNameTest(unittest.TestCase):
    def test_same_title_on_another_album_is_not_ticked_by_default(self):       # B13
        a = {"album": "First", "disc": 1, "num": 1}
        self.assertFalse(mp.same_recording(a, {"album": "Second", "disc": 1, "num": 1}))
        self.assertFalse(mp.same_recording(a, {"album": "First", "disc": 2, "num": 1}))
        self.assertTrue(mp.same_recording(a, {"album": "first", "disc": 1, "num": 1}))
        self.assertTrue(mp.same_recording({"album": "X"}, {"album": "X", "num": 3}))


if __name__ == "__main__":
    unittest.main()
