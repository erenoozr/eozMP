"""
Tiny but valid audio files of every format eozMP plays, built in a temp folder for the tag, cover
and lyrics tests. Most are written byte by byte; WMA and M4A need ffmpeg (tests skip without it).
"""
import math
import shutil
import struct
import subprocess
import wave
from pathlib import Path

FFMPEG = shutil.which("ffmpeg")
JPEG = b"\xff\xd8\xff\xe0" + b"front" * 20
BACK_JPEG = b"\xff\xd8\xff\xe0" + b"back!" * 20
PNG = b"\x89PNG\r\n\x1a\n" + b"png" * 20


def wav(path, seconds=0.25, rate=8000):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\0\0" * int(rate * seconds))
    return Path(path)


def add_riff_info(path, info, encoding="utf-8"):
    """Append a LIST/INFO chunk (INAM, IART, IPRD...) to a WAV file, as Windows and many rippers write it."""
    body = b"INFO"
    for key, value in info.items():
        raw = value.encode(encoding) + b"\0"
        body += key.encode("ascii") + struct.pack("<I", len(raw)) + raw + (b"\0" if len(raw) % 2 else b"")
    data = bytearray(Path(path).read_bytes()) + b"LIST" + struct.pack("<I", len(body)) + body
    data[4:8] = struct.pack("<I", len(data) - 8)
    Path(path).write_bytes(bytes(data))


def aiff(path, seconds=0.25, rate=8000):
    frames = int(rate * seconds)
    e = int(math.floor(math.log2(rate)))
    comm = struct.pack(">hLh", 1, frames, 16) + struct.pack(">HQ", 16383 + e, rate << (63 - e))
    ssnd = struct.pack(">LL", 0, 0) + b"\0\0" * frames
    body = b"AIFF" + b"COMM" + struct.pack(">L", len(comm)) + comm + b"SSND" + struct.pack(">L", len(ssnd)) + ssnd
    Path(path).write_bytes(b"FORM" + struct.pack(">L", len(body)) + body)
    return Path(path)


def flac(path, seconds=1, rate=44100):
    samples = rate * seconds
    info = struct.pack(">HH", 4096, 4096) + b"\0" * 6
    info += ((rate << 44) | (1 << 41) | (15 << 36) | samples).to_bytes(8, "big") + b"\0" * 16
    Path(path).write_bytes(b"fLaC" + bytes([0x80, 0, 0, len(info)]) + info)
    return Path(path)


def _ogg(path, pages):
    from mutagen.ogg import OggPage
    out = b""
    for seq, (packets, position) in enumerate(pages):
        page = OggPage()
        page.serial, page.sequence, page.position, page.packets = 7, seq, position, packets
        page.first = seq == 0
        page.last = seq == len(pages) - 1
        out += page.write()
    Path(path).write_bytes(out)
    return Path(path)


def _vcomment(vendor=b"test"):
    return struct.pack("<I", len(vendor)) + vendor + struct.pack("<I", 0)


def opus(path):
    head = b"OpusHead" + struct.pack("<BBHIhB", 1, 2, 312, 48000, 0, 0)
    return _ogg(path, [([head], 0), ([b"OpusTags" + _vcomment()], 0), ([b"\xfc\xff\xfe"], 48312)])


def vorbis(path):
    ident = b"\x01vorbis" + struct.pack("<IBIiiiBB", 0, 2, 44100, 0, 128000, 0, 0xB8, 1)
    comment = b"\x03vorbis" + _vcomment() + b"\x01"
    return _ogg(path, [([ident], 0), ([comment, b"\x05vorbis" + b"\0" * 20], 0), ([b"\0" * 10], 44100)])


def wavpack(path, seconds=1, rate=44100):
    samples = rate * seconds
    flags = (9 << 23) | 1                 # 44.1 kHz, 16 bit, stereo
    head = b"wvpk" + struct.pack("<IHBBIIII", 24, 0x410, 0, 0, samples, 0, samples, flags) + b"\0" * 4
    Path(path).write_bytes(head)
    return Path(path)


def monkeys(path, seconds=1, rate=44100):
    head = b"MAC " + struct.pack("<H", 3990) + b"\0" * 50
    head += struct.pack("<IIIHHI", rate * seconds, rate * seconds, 1, 16, 2, rate)
    Path(path).write_bytes(head)
    return Path(path)


def ape_tags(path, **tags):
    from mutagen.apev2 import APEv2
    t = APEv2()
    for k, v in tags.items():
        t[k] = v
    t.save(str(path))


def id3_frames(path, frames, cls=None):
    """Add ID3 frames to a WAV/AIFF/MP3 file through mutagen."""
    from mutagen import File
    audio = File(str(path))
    if audio.tags is None:
        audio.add_tags()
    for f in frames:
        audio.tags.add(f)
    audio.save()


def ffmpeg_make(path, codec, extra=()):
    """WMA, M4A... from a short WAV. Returns None when ffmpeg isn't there or can't do it."""
    if not FFMPEG:
        return None
    src = wav(Path(path).with_suffix(".src.wav"), 0.5, 44100)
    try:
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(src), "-c:a", codec, *extra, str(path)],
                       check=True, capture_output=True, timeout=60)
    except Exception:
        return None
    finally:
        src.unlink(missing_ok=True)
    return Path(path) if Path(path).exists() and Path(path).stat().st_size else None


# ---------------------------------------------------------------- Matroska (no tool needed)
def ebml(eid, payload):
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    elif isinstance(payload, int):
        payload = payload.to_bytes(max(1, (payload.bit_length() + 7) // 8), "big")
    elif isinstance(payload, float):
        payload = struct.pack(">d", payload)
    elif isinstance(payload, (list, tuple)):
        payload = b"".join(payload)
    return eid.to_bytes((eid.bit_length() + 7) // 8, "big") + ((1 << 56) | len(payload)).to_bytes(8, "big") + payload


def mka_tag(level, uid=None, **names):
    targets = [ebml(0x68CA, level)] if level is not None else []
    if uid is not None:
        targets.append(ebml(0x63C5, uid))
    simple = [ebml(0x67C8, [ebml(0x45A3, k), ebml(0x4487, v)]) for k, v in names.items()]
    return ebml(0x7373, ([ebml(0x63C0, targets)] if targets else []) + simple)


def mka(path, tags=(), seconds=200.5, attachments=(), tags_after_audio=True, unknown_size=False):
    """A Matroska audio file: Info with the duration, a cluster of 'audio', Tags and Attachments."""
    header = ebml(0x1A45DFA3, [ebml(0x4282, "matroska")])
    info = ebml(0x1549A966, [ebml(0x2AD7B1, 1000000), ebml(0x4489, seconds * 1000.0)])
    cluster = ebml(0x1F43B675, [ebml(0xE7, 0), ebml(0xA3, b"\0" * 5000)])
    tag_el = ebml(0x1254C367, list(tags)) if tags else b""
    files = [ebml(0x61A7, [ebml(0x466E, name), ebml(0x4660, mime), ebml(0x465C, data), ebml(0x46AE, i + 1)])
             for i, (name, mime, data) in enumerate(attachments)]
    att = ebml(0x1941A469, files) if files else b""
    body = info + (cluster + tag_el + att if tags_after_audio else tag_el + att + cluster)
    if unknown_size:
        segment = (0x18538067).to_bytes(4, "big") + b"\x01\xff\xff\xff\xff\xff\xff\xff" + body
    else:
        segment = ebml(0x18538067, body)
    Path(path).write_bytes(header + segment)
    return Path(path)
