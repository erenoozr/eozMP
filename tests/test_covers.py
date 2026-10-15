"""
Album covers: the picture inside the file (A17), and finding covers online without breaking other
albums' folders (A5), remembering network errors as "no cover" (A6) or matching the wrong album (A7).
Nothing here goes on the internet: the lookups are answered by fakes.
Run from the project folder:   py -3 -m unittest discover tests -p "test_covers.py"
"""
import base64
import struct
import unittest

from mutagen import File
from mutagen.flac import Picture
from mutagen.id3 import APIC

import audio_samples as s
from test_core import TempDirTest, mp, tagged_mp3


def flac_picture(kind, data):
    pic = Picture()
    pic.type, pic.mime, pic.data = kind, "image/jpeg", data
    return pic


class EmbeddedCoverTest(TempDirTest):
    """A17: the front cover (picture type 3) in every format, not just whichever picture comes first."""

    def test_flac_front_cover_wins_over_an_earlier_back_cover(self):
        p = s.flac(self.tmp / "a.flac")
        a = File(str(p))
        a.add_picture(flac_picture(4, s.BACK_JPEG))
        a.add_picture(flac_picture(3, s.JPEG))
        a.save()
        self.assertEqual(mp.embedded_cover(str(p)), s.JPEG)

    def test_mp3_front_cover_wins_over_an_earlier_back_cover(self):
        p = self.tmp / "a.mp3"
        tagged_mp3(p, title="Song")
        s.id3_frames(p, [APIC(encoding=3, mime="image/jpeg", type=4, desc="back", data=s.BACK_JPEG),
                         APIC(encoding=3, mime="image/jpeg", type=3, desc="front", data=s.JPEG)])
        self.assertEqual(mp.embedded_cover(str(p)), s.JPEG)

    def test_any_picture_when_none_is_marked_front(self):
        p = s.flac(self.tmp / "a.flac")
        a = File(str(p))
        a.add_picture(flac_picture(0, s.PNG))
        a.save()
        self.assertEqual(mp.embedded_cover(str(p)), s.PNG)

    def test_wav_and_aiff_covers(self):
        for p in (s.wav(self.tmp / "a.wav"), s.aiff(self.tmp / "a.aiff")):
            with self.subTest(p.suffix):
                s.id3_frames(p, [APIC(encoding=3, mime="image/jpeg", type=3, desc="", data=s.JPEG)])
                self.assertEqual(mp.embedded_cover(str(p)), s.JPEG)

    def test_ogg_opus_and_vorbis_covers(self):
        for p in (s.opus(self.tmp / "a.opus"), s.vorbis(self.tmp / "a.ogg")):
            with self.subTest(p.suffix):
                a = File(str(p))
                a["metadata_block_picture"] = [base64.b64encode(flac_picture(4, s.BACK_JPEG).write()).decode(),
                                               base64.b64encode(flac_picture(3, s.JPEG).write()).decode()]
                a.save()
                self.assertEqual(mp.embedded_cover(str(p)), s.JPEG)

    def test_old_style_ogg_coverart(self):
        p = s.vorbis(self.tmp / "a.ogg")
        a = File(str(p))
        a["coverart"] = [base64.b64encode(s.JPEG).decode()]
        a.save()
        self.assertEqual(mp.embedded_cover(str(p)), s.JPEG)

    def test_wavpack_and_monkeys_audio_covers(self):
        from mutagen.apev2 import APEValue, BINARY
        for p in (s.wavpack(self.tmp / "a.wv"), s.monkeys(self.tmp / "a.ape")):
            with self.subTest(p.suffix):
                s.ape_tags(p, **{"Cover Art (Back)": APEValue(b"back.jpg\0" + s.BACK_JPEG, BINARY),
                                 "Cover Art (Front)": APEValue(b"front.jpg\0" + s.JPEG, BINARY)})
                self.assertEqual(mp.embedded_cover(str(p)), s.JPEG)

    def test_wma_cover(self):
        from mutagen.asf import ASFByteArrayAttribute
        p = s.ffmpeg_make(self.tmp / "a.wma", "wmav2")
        if p is None:
            self.skipTest("ffmpeg can't make a WMA file here")

        def wm_picture(kind, data):
            text = "image/jpeg".encode("utf-16-le") + b"\0\0" + "".encode("utf-16-le") + b"\0\0"
            return ASFByteArrayAttribute(bytes([kind]) + struct.pack("<I", len(data)) + text + data)
        a = File(str(p))
        a["WM/Picture"] = [wm_picture(4, s.BACK_JPEG), wm_picture(3, s.JPEG)]
        a.save()
        self.assertEqual(mp.embedded_cover(str(p)), s.JPEG)

    def test_mka_attached_cover(self):
        p = s.mka(self.tmp / "a.mka", [s.mka_tag(None, TITLE="Song")],
                  attachments=[("small_cover.jpg", "image/jpeg", s.BACK_JPEG), ("notes.txt", "text/plain", b"hi"),
                               ("cover.jpg", "image/jpeg", s.JPEG)])
        self.assertEqual(mp.embedded_cover(str(p)), s.JPEG)

    def test_file_without_a_cover(self):
        p = s.flac(self.tmp / "a.flac")
        self.assertIsNone(mp.embedded_cover(str(p)))
        self.assertIsNone(mp.embedded_cover(str(s.mka(self.tmp / "a.mka"))))


if __name__ == "__main__":
    unittest.main()
