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


def tone(path, seconds, rate=44100, freq=440):
    w = wave.open(str(path), "wb")
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(rate)
    w.writeframes(b"".join(struct.pack("<h", int(4000 * math.sin(2 * math.pi * freq * i / rate)))
                           for i in range(int(seconds * rate))))
    w.close()


def read_wav(path):
    """Samples as floats (-1..1); mpv's pcm output writes float or 16-bit."""
    w = wave.open(str(path), "rb")
    width, data = w.getsampwidth(), w.readframes(w.getnframes())
    w.close()
    if width == 4:
        return struct.unpack(f"<{len(data) // 4}f", data)
    return [v / 32768 for v in struct.unpack(f"<{len(data) // 2}h", data)]


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

    def test_lists_output_devices_with_automatic_first(self):
        devices = self.engine.output_devices()
        self.assertEqual(devices[0][0], "auto")
        self.assertTrue(all(isinstance(n, str) and isinstance(d, str) for n, d in devices))

    def test_audio_options_reach_mpv(self):
        self.engine.set_audio_options(replaygain="Album", device="auto", exclusive=True)
        self.assertEqual(self.engine.mp.replaygain, "album")
        self.assertTrue(self.engine.mp.audio_exclusive)
        self.engine.set_audio_options(replaygain="Off", device="auto", exclusive=False)
        self.assertIn(self.engine.mp.replaygain, ("no", False))   # python-mpv turns "no" into False
        self.assertFalse(self.engine.mp.audio_exclusive)

    def test_a_device_that_is_gone_falls_back_to_automatic(self):
        self.engine.set_audio_options(replaygain="Off", device="wasapi/{not-plugged-in}", exclusive=False)
        self.assertEqual(self.engine.mp.audio_device, "auto")
        self.load()
        self.engine.play()
        self.assertTrue(wait_for(lambda: self.engine.position() > 200))

    def test_volume_and_mute_look_like_qaudiooutput(self):
        audio = self.engine.audio
        audio.setVolume(0.4)
        audio.setMuted(True)
        self.assertAlmostEqual(audio.volume(), 0.4)
        self.assertTrue(audio.isMuted())
        self.assertAlmostEqual(self.engine.mp.volume, 40)
        self.assertTrue(self.engine.mp.mute)


@unittest.skipUnless(mp.load_mpv(), "libmpv-2.dll not found (see the note at the top)")
class MpvEqualizerTest(TempDirTest):
    """Plays into a WAV file (mpv's "pcm" output) and measures what the equalizer did."""

    def render(self, freq, setup, during=None, seconds=2.0):
        src = self.tmp / f"in-{freq}.wav"
        tone(src, seconds, freq=freq)
        out = self.tmp / f"out-{len(list(self.tmp.iterdir()))}.wav"
        engine = mp.MpvEngine(ao="pcm", ao_pcm_file=str(out), ao_pcm_waveheader=True, audio_format="s16")
        setup(engine)
        ended = []
        engine.mediaStatusChanged.connect(lambda s: s == Status.EndOfMedia and ended.append(s))
        engine.setSource(QUrl.fromLocalFile(str(src)))
        engine.play()
        if during:
            self.assertTrue(wait_for(lambda: engine.position() > seconds * 500))
            during(engine)
        self.assertTrue(wait_for(lambda: ended, 10))
        engine.shutdown()
        return read_wav(out)

    @staticmethod
    def db(samples, a=0.1, b=0.9):
        part = samples[int(len(samples) * a):int(len(samples) * b)]
        return 20 * math.log10(math.sqrt(sum(v * v for v in part) / len(part)))

    def test_flat_preset_keeps_the_level(self):
        plain = self.db(self.render(1000, lambda e: None))
        flat = self.db(self.render(1000, lambda e: e.set_equalizer(True, 12.0, [0.0] * 10)))
        self.assertAlmostEqual(flat, plain, delta=0.3)

    def test_a_band_boosts_its_own_frequency(self):
        plain = self.db(self.render(1000, lambda e: None))
        bands = [0.0] * 10
        bands[5] = 12.0                      # the 1 kHz band
        boosted = self.db(self.render(1000, lambda e: e.set_equalizer(True, 12.0, bands)))
        self.assertAlmostEqual(boosted - plain, 12.0, delta=1.0)
        low = self.db(self.render(125, lambda e: e.set_equalizer(True, 12.0, bands)))
        low_plain = self.db(self.render(125, lambda e: None))
        self.assertLess(abs(low - low_plain), 1.0)   # 125 Hz is left alone

    def test_moving_a_slider_while_playing_takes_effect(self):
        # pcm output runs faster than real time, so this one plays in real time (null output)
        # and reads the level from an ffmpeg meter placed after the equalizer
        src = self.tmp / "long.wav"
        tone(src, 6, freq=1000)
        engine = mp.MpvEngine(ao="null")
        self.addCleanup(engine.shutdown)
        engine.set_equalizer(True, 12.0, [0.0] * 10)
        engine.mp.command("af", "add", "@meter:lavfi=[astats=metadata=1:reset=5]")
        engine.setSource(QUrl.fromLocalFile(str(src)))
        engine.play()

        def level():
            meta = engine.mp._get_property("af-metadata/meter")
            return float(meta["lavfi.astats.Overall.RMS_level"])
        self.assertTrue(wait_for(lambda: engine.position() > 1200))
        before = level()
        bands = [0.0] * 10
        bands[5] = 12.0
        from unittest import mock
        with mock.patch.object(engine.mp, "command", wraps=engine.mp.command) as cmd:
            engine.set_equalizer(True, 12.0, bands)
        self.assertEqual([c.args[0] for c in cmd.call_args_list], ["af-command"])   # not rebuilt
        self.assertTrue(wait_for(lambda: engine.position() > 2500))
        self.assertAlmostEqual(level() - before, 12.0, delta=1.0)

    def test_turning_it_off_restores_the_sound(self):
        bands = [12.0] * 10
        plain = self.db(self.render(1000, lambda e: None))
        off = self.db(self.render(1000, lambda e: (e.set_equalizer(True, 12.0, bands),
                                                   e.set_equalizer(False, 12.0, bands))))
        self.assertAlmostEqual(off, plain, delta=0.3)


class EngineChoiceTest(unittest.TestCase):
    def test_old_automatic_setting_still_means_automatic(self):
        self.assertEqual(mp.engine_order("Automatic (VLC if installed)"), ["mpv", "VLC", "Qt"])

    def test_each_choice_falls_back_to_the_built_in_engine(self):
        self.assertEqual(mp.engine_order("mpv"), ["mpv", "Qt"])
        self.assertEqual(mp.engine_order("VLC"), ["VLC", "Qt"])
        self.assertEqual(mp.engine_order("Qt (built-in)"), ["Qt"])


if __name__ == "__main__":
    unittest.main()
