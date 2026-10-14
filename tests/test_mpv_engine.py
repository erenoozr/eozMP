"""
Tests for the mpv audio engine. They need libmpv-2.dll: put it next to musicplayer.py (or in a
"libmpv" folder there), or point the EOZMP_LIBMPV environment variable at the folder that has it.
Without it these tests are skipped. Nothing is played out loud (mpv's "null" audio output).
"""
import math
import os
import struct
import time
import unittest
import wave

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QCoreApplication, QUrl  # noqa: E402
from PyQt6.QtMultimedia import QMediaPlayer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from test_core import TempDirTest, mp  # noqa: E402

APP = QApplication.instance() or QApplication([])
State = QMediaPlayer.PlaybackState
Status = QMediaPlayer.MediaStatus


def tone(path, seconds, rate=44100):
    w = wave.open(str(path), "wb")
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(rate)
    w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / rate)))
                           for i in range(int(seconds * rate))))
    w.close()


def wait_for(cond, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        QCoreApplication.processEvents()
        if cond():
            return True
        time.sleep(0.01)
    return False


@unittest.skipUnless(mp.load_mpv(), "libmpv-2.dll not found (see the note at the top)")
class MpvEngineTest(TempDirTest):
    def setUp(self):
        super().setUp()
        self.song = self.tmp / "tone.wav"
        tone(self.song, 1.5)
        self.engine = mp.MpvEngine(ao="null")
        self.events = []
        self.engine.mediaStatusChanged.connect(lambda s: self.events.append(("status", s)))
        self.engine.playbackStateChanged.connect(lambda s: self.events.append(("state", s)))
        self.engine.errorOccurred.connect(lambda _e, msg: self.events.append(("error", msg)))
        self.positions = []
        self.engine.positionChanged.connect(self.positions.append)
        self.durations = []
        self.engine.durationChanged.connect(self.durations.append)

    def tearDown(self):
        self.engine.shutdown()
        super().tearDown()

    def load(self, path=None):
        self.engine.setSource(QUrl.fromLocalFile(str(path or self.song)))

    def test_plays_reports_duration_and_moves_forward(self):
        self.load()
        self.engine.play()
        self.assertEqual(self.engine.playbackState(), State.PlayingState)
        self.assertTrue(wait_for(lambda: self.durations and self.durations[-1] > 0))
        self.assertAlmostEqual(self.durations[-1], 1500, delta=50)
        self.assertTrue(wait_for(lambda: self.engine.position() > 300))

    def test_end_of_song_is_reported_once(self):
        self.load()
        self.engine.play()
        self.assertTrue(wait_for(lambda: ("status", Status.EndOfMedia) in self.events))
        self.assertEqual(self.engine.playbackState(), State.StoppedState)
        wait_for(lambda: False, 0.3)
        self.assertEqual(self.events.count(("status", Status.EndOfMedia)), 1)
        self.assertFalse([e for e in self.events if e[0] == "error"])

    def test_missing_file_is_an_error_not_the_end_of_the_song(self):
        self.load(self.tmp / "gone.flac")
        self.engine.play()
        self.assertTrue(wait_for(lambda: any(e[0] == "error" for e in self.events)))
        self.assertNotIn(("status", Status.EndOfMedia), self.events)
        self.assertEqual(self.engine.playbackState(), State.StoppedState)

    def test_position_set_before_playing_is_where_it_starts(self):
        self.load()
        self.engine.setPosition(900)
        self.engine.play()
        self.assertTrue(wait_for(lambda: self.engine.position() >= 900))
        self.assertTrue(all(p >= 900 for p in self.positions))

    def test_pause_and_resume(self):
        self.load()
        self.engine.play()
        self.assertTrue(wait_for(lambda: self.engine.position() > 100))
        self.engine.pause()
        self.assertEqual(self.engine.playbackState(), State.PausedState)
        at = self.engine.position()
        wait_for(lambda: False, 0.3)
        self.assertLess(abs(self.engine.position() - at), 60)
        self.engine.play()
        self.assertTrue(wait_for(lambda: self.engine.position() > at + 150))

    def test_play_again_after_the_song_ended(self):
        self.load()
        self.engine.play()
        self.assertTrue(wait_for(lambda: ("status", Status.EndOfMedia) in self.events))
        self.engine.play()
        self.assertEqual(self.engine.playbackState(), State.PlayingState)
        self.assertTrue(wait_for(lambda: 0 < self.engine.position() < 1400))

    def test_stop_goes_back_to_the_start(self):
        self.load()
        self.engine.play()
        self.assertTrue(wait_for(lambda: self.engine.position() > 300))
        self.engine.stop()
        self.assertEqual(self.engine.playbackState(), State.StoppedState)
        self.assertEqual(self.engine.position(), 0)

    def two_songs(self):
        second = self.tmp / "second.wav"
        tone(second, 1.0)
        advanced = []
        self.engine.advanced.connect(lambda: advanced.append(self.engine.source().toLocalFile()))
        return second, advanced

    def test_next_song_follows_without_stopping(self):
        second, advanced = self.two_songs()
        self.load()
        self.engine.setNext(QUrl.fromLocalFile(str(second)))
        self.engine.play()
        self.assertTrue(wait_for(lambda: advanced))
        self.assertEqual(os.path.normcase(advanced[0]), os.path.normcase(str(second)))
        self.assertNotIn(("status", Status.EndOfMedia), self.events)
        self.assertNotIn(("state", State.StoppedState), self.events)
        self.assertEqual(self.engine.playbackState(), State.PlayingState)
        self.assertTrue(wait_for(lambda: self.durations and abs(self.durations[-1] - 1000) < 50))
        # the second song ends normally when nothing is queued after it
        self.assertTrue(wait_for(lambda: ("status", Status.EndOfMedia) in self.events))
        self.assertEqual(len(advanced), 1)

    def test_next_song_can_be_taken_back(self):
        second, advanced = self.two_songs()
        self.load()
        self.engine.setNext(QUrl.fromLocalFile(str(second)))
        self.engine.setNext(None)
        self.engine.play()
        self.assertTrue(wait_for(lambda: ("status", Status.EndOfMedia) in self.events))
        self.assertEqual(advanced, [])

    def test_next_song_can_be_changed(self):
        second, advanced = self.two_songs()
        third = self.tmp / "third.wav"
        tone(third, 0.5)
        self.load()
        self.engine.setNext(QUrl.fromLocalFile(str(second)))
        self.engine.setNext(QUrl.fromLocalFile(str(third)))
        self.engine.play()
        self.assertTrue(wait_for(lambda: ("status", Status.EndOfMedia) in self.events, 6))
        self.assertEqual([os.path.normcase(a) for a in advanced], [os.path.normcase(str(third))])

    def test_a_new_song_drops_the_one_lined_up(self):
        second, advanced = self.two_songs()
        self.load()
        self.engine.setNext(QUrl.fromLocalFile(str(second)))
        self.load(second)
        self.engine.play()
        self.assertTrue(wait_for(lambda: ("status", Status.EndOfMedia) in self.events))
        self.assertEqual(advanced, [])

    def test_a_broken_next_song_is_an_error(self):
        _second, advanced = self.two_songs()
        self.load()
        self.engine.setNext(QUrl.fromLocalFile(str(self.tmp / "gone.flac")))
        self.engine.play()
        self.assertTrue(wait_for(lambda: any(e[0] == "error" for e in self.events)))
        self.assertEqual(len(advanced), 1)
        self.assertNotIn(("status", Status.EndOfMedia), self.events)

    def test_volume_and_mute_look_like_qaudiooutput(self):
        audio = self.engine.audio
        audio.setVolume(0.4)
        audio.setMuted(True)
        self.assertAlmostEqual(audio.volume(), 0.4)
        self.assertTrue(audio.isMuted())
        self.assertAlmostEqual(self.engine.mp.volume, 40)
        self.assertTrue(self.engine.mp.mute)


class EngineChoiceTest(unittest.TestCase):
    def test_old_automatic_setting_still_means_automatic(self):
        self.assertEqual(mp.engine_order("Automatic (VLC if installed)"), ["mpv", "VLC", "Qt"])

    def test_each_choice_falls_back_to_the_built_in_engine(self):
        self.assertEqual(mp.engine_order("mpv"), ["mpv", "Qt"])
        self.assertEqual(mp.engine_order("VLC"), ["VLC", "Qt"])
        self.assertEqual(mp.engine_order("Qt (built-in)"), ["Qt"])


if __name__ == "__main__":
    unittest.main()
