"""
eozMP - eren's definitely (not) sketchy music player.
Library, covers, synced lyrics, playlists, queue, mini/fullscreen player and Soulseek search (via slskd).

Copyright (C) 2026 Eren

This program is free software: you can redistribute it and/or modify it under the terms of
the GNU General Public License as published by the Free Software Foundation, either
version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with this program.
If not, see <https://www.gnu.org/licenses/>.

Requires: pip install PyQt6 mutagen numpy   (optional: python-vlc + VLC for the equalizer)
"""
import bisect
import colorsys
import hashlib
import html
import json
import os
import re
import struct
import subprocess
import sys
import threading
import time
import uuid
import random
import shutil
import zipfile
from collections import deque
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

from mutagen import File as MutagenFile
from PyQt6.QtCore import (
    QAbstractNativeEventFilter, QByteArray, QEasingCurve, QEvent, QMimeData, QPoint, QPointF, QRect, QRectF,
    QVariantAnimation, QFileSystemWatcher, QItemSelectionModel, QObject, QPropertyAnimation, QSize, Qt, QThread,
    QTimer, QUrl, pyqtSignal,
)
from PyQt6.QtGui import (
    QAction, QBrush, QColor, QCursor, QGradient, QImage, QKeySequence, QShortcut, QDesktopServices, QFont, QFontDatabase, QFontMetrics, QIcon, QLinearGradient, QPainter,
    QPainterPath, QPalette, QPen, QPixmap,
)
from PyQt6.QtMultimedia import QAudioFormat, QAudioOutput, QMediaPlayer
try:   # Qt 6.8+: lets us read the audio for the visualizer
    from PyQt6.QtMultimedia import QAudioBufferOutput
except ImportError:
    QAudioBufferOutput = None
try:   # optional, gives the visualizer a real frequency spectrum
    import numpy as np
except Exception:
    np = None
from array import array
import math
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog,
    QDialogButtonBox, QColorDialog, QFileDialog, QFontComboBox, QFrame, QGraphicsBlurEffect, QGraphicsOpacityEffect,
    QGraphicsPixmapItem, QGraphicsScene, QPlainTextEdit, QScrollArea, QFormLayout, QHBoxLayout, QHeaderView,
    QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMenu, QMessageBox,
    QPushButton, QSizePolicy, QSlider, QStyle, QStyledItemDelegate, QStyleOptionViewItem, QSpinBox, QSplitter, QStackedWidget,
    QSystemTrayIcon, QTabWidget,
    QTableWidget, QTableWidgetItem, QToolTip, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)

AUDIO_EXTS = {
    ".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg", ".oga", ".opus",
    ".wma", ".aiff", ".aif", ".mp4", ".m4b", ".ape", ".wv", ".mka",
}
COVER_NAMES = ("cover", "folder", "front", "album", "albumart")
COVER_EXTS = (".jpg", ".jpeg", ".png")
CONFIG_FILE = Path.home() / ".simple_music_player.json"
CACHE_FILE = Path.home() / ".simple_music_player_cache.json"
LOSSLESS_EXTS = {"flac", "wav", "aiff", "aif", "ape", "wv"}
FORMAT_OPTIONS = ["Any format", "Lossless only", "MP3 320k+", "MP3 (any)"]
KEY_ROLE = Qt.ItemDataRole.UserRole
ARTIST_ROLE = Qt.ItemDataRole.UserRole + 2
NUM_ROLE = Qt.ItemDataRole.UserRole + 3
YEAR_ROLE = Qt.ItemDataRole.UserRole + 4
SYSTEM_FONT_TAG = "__system__"
SYSTEM_FONT_FAMILY = "Segoe UI"
DEFAULT_CFG = {
    "folders": [],
    "volume": 70,
    "slskd_url": "http://localhost:5030",
    "slskd_key": "",
    "downloads_dir": "",
    "theme": "System",
    "accent": "Blue",
    "lyrics_font": "",
    "resume": True,
    "autoplay_next": True,
    "group_featured": True,
    "ignore_the": True,
    "lyrics_online": True,
    "lyrics_save_lrc": False,
    "lyrics_size": 26,
    "lyrics_style": "Album art",
    "lyrics_align": "Left",
    "lyrics_weight": "Bold",
    "lyrics_dim": 35,
    "show_lyric_line": True,
    "corner_style": "Rounded",
    "density": "Comfortable",
    "cover_size": "Medium",
    "ui_font": "",
    "ui_font_size": 11,
    "album_list_style": "Covers and numbers",
    "shuffle_on": False,
    "repeat_mode": "off",
    "page_fade": True,
    "fs_motion": True,
    "lyrics_shadow": True,
    "show_remaining": False,
    "visualizer": "Off",
    "lyrics_fade": True,
    "lyrics_animate": True,
    "split_collabs": True,
    "keep_together": [],
    "cfg_version": 1,
    "audio_engine": "Automatic (VLC if installed)",
    "eq_enabled": False,
    "eq_preamp": 0.0,
    "eq_bands": [],
    "eq_preset": "Flat",
    "covers_auto": True,
    "covers_to_folder": False,
    "mini_pos": [],
    "mini_opacity": 90,
    "library_sort": "A-Z",
    "organize_downloads": True,
    "organize_root": "",
    "accent_custom": "#4C8DFF",
    "close_to_tray": True,
    "tray_hint_shown": False,
    "media_keys": True,
    "soul_view": "Albums",
    "soul_quality": "Any format",
    "soul_free_only": False,
    "last_path": "",
    "queue": [],
    "last_pos": 0,
    "win_size": [1100, 700],
}


# ---------------------------------------------------------------- config
def load_config():
    cfg = dict(DEFAULT_CFG)
    try:
        cfg.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
    except Exception:
        pass
    return cfg


def save_config(cfg):
    try:
        CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except Exception:
        pass


PLAYLIST_FILE = Path.home() / ".simple_music_player_playlists.json"


def load_playlists():
    """{playlist name: [song file paths]}"""
    try:
        data = json.loads(PLAYLIST_FILE.read_text(encoding="utf-8"))
        return {str(k): [str(p) for p in v] for k, v in data.items() if isinstance(v, list)}
    except Exception:
        return {}


def save_playlists(playlists):
    try:
        PLAYLIST_FILE.write_text(json.dumps(playlists, indent=1), encoding="utf-8")
    except Exception:
        pass


# ---------------------------------------------------------------- tags
FEAT_RE = re.compile(r"\s*[\(\[]?\b(?:feat|ft|featuring)\b\.?.*$", re.IGNORECASE)


KEEP_TOGETHER = {
    "simon & garfunkel", "earth, wind & fire", "tyler, the creator", "crosby, stills, nash & young",
    "crosby, stills & nash", "hall & oates", "daryl hall & john oates", "mumford & sons",
    "belle & sebastian", "iron & wine", "chase & status", "above & beyond", "years & years",
    "peter, paul and mary", "brooks & dunn", "big & rich", "sam & dave", "ashford & simpson",
    "captain & tennille", "ike & tina turner", "kool & the gang", "sly & the family stone",
    "florence + the machine", "marina and the diamonds", "of monsters and men",
}
COLLAB_RE = re.compile(r",\s+(?!the\b)|\s+&\s+(?!the\b)|\s+x\s+", re.IGNORECASE)


def main_artist(name, split_collabs=True, keep=()):
    """'Drake feat. Rihanna' -> 'Drake'; 'A; B' -> 'A'; 'Jay-Z & Kanye West' -> 'Jay-Z'."""
    name = FEAT_RE.sub("", name or "")
    name = re.split(r"\s*;\s*|\s+/\s+", name)[0].strip()
    low = name.lower()
    if split_collabs and low not in KEEP_TOGETHER and low not in keep:
        name = COLLAB_RE.split(name)[0].strip()
    return name or "Unknown Artist"


def first(tags, key):
    try:
        val = tags.get(key)
        if val:
            return str(val[0]).strip()
    except Exception:
        pass
    return ""


def to_int(text, default=9999):
    try:
        return int(str(text).split("/")[0])
    except Exception:
        return default


def read_track(path):
    title = artist = album = genre = ""
    num, disc, year, length = 9999, 1, 0, 0
    try:
        audio = MutagenFile(path, easy=True)
        if audio is not None:
            if audio.info is not None:
                length = getattr(audio.info, "length", 0) or 0
            if audio.tags is not None:
                t = audio.tags
                title = first(t, "title")
                artist = first(t, "albumartist") or first(t, "artist")
                genre = first(t, "genre")
                album = first(t, "album")
                num = to_int(first(t, "tracknumber"))
                disc = to_int(first(t, "discnumber"), 1)
                year = to_int(first(t, "date")[:4], 0)
    except Exception:
        pass
    return {
        "path": path,
        "title": title or Path(path).stem,
        "artist": main_artist(artist),
        "artist_raw": artist,
        "genre": genre,
        "album": album or "Unknown Album",
        "num": num,
        "disc": disc,
        "year": year,
        "length": length,
    }


def load_cache():
    try:
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_cache(tracks):
    try:
        CACHE_FILE.write_text(json.dumps(tracks), encoding="utf-8")
    except Exception:
        pass


def scan_folders(folders, cache=None):
    """Walk the folders. Files that haven't changed since the last scan are
    taken from the cache instead of being re-read (this is what makes
    start-up fast)."""
    old = {t["path"]: t for t in (cache or []) if "path" in t}
    tracks, seen = [], set()
    for folder in folders:
        for root, _, files in os.walk(folder):
            for name in files:
                if Path(name).suffix.lower() not in AUDIO_EXTS:
                    continue
                path = os.path.join(root, name)
                if path in seen:
                    continue
                seen.add(path)
                try:
                    st = os.stat(path)
                except OSError:
                    continue
                prev = old.get(path)
                if (prev and prev.get("mtime") == st.st_mtime and prev.get("size") == st.st_size
                        and "artist_raw" in prev and "genre" in prev):
                    tracks.append(prev)
                else:
                    t = read_track(path)
                    t["mtime"], t["size"] = st.st_mtime, st.st_size
                    t["added"] = max(st.st_mtime, st.st_ctime)
                    tracks.append(t)
    return tracks


def embedded_cover(path):
    try:
        audio = MutagenFile(path)
        if audio is None:
            return None
        pics = getattr(audio, "pictures", None)
        if pics:
            return pics[0].data
        tags = audio.tags
        if tags is None:
            return None
        if hasattr(tags, "getall"):
            apic = tags.getall("APIC")
            if apic:
                return apic[0].data
        if "covr" in tags:
            return bytes(tags["covr"][0])
    except Exception:
        pass
    return None


def folder_cover(path):
    try:
        folder = Path(path).parent
        names = {p.name.lower(): p for p in folder.iterdir()}
        for base in COVER_NAMES:
            for ext in COVER_EXTS:
                if base + ext in names:
                    return names[base + ext].read_bytes()
    except Exception:
        pass
    return None


def fmt_time(ms):
    s = max(0, int(ms // 1000))
    return f"{s // 60}:{s % 60:02d}"


def fmt_size(n):
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


# ---------------------------------------------------------------- lyrics
LYRICS_DIR = Path.home() / ".simple_music_player_lyrics"
TS_RE = re.compile(r"\[(\d{1,3}):(\d{2})(?:[.:](\d{1,3}))?\]")
META_RE = re.compile(r"^\[[A-Za-z]+:.*\]$")
NEG_CACHE_SECONDS = 7 * 24 * 3600


def parse_lrc(text):
    """Return (synced, lines). lines = [(milliseconds or None, text)].
    Understands .lrc timestamps like [01:23.45]; anything else is plain text."""
    synced, plain = [], []
    for raw in text.splitlines():
        stamps = TS_RE.findall(raw)
        body = TS_RE.sub("", raw).strip()
        if stamps:
            for m, sec, frac in stamps:
                ms = (int(m) * 60 + int(sec)) * 1000
                if frac:
                    ms += int(frac.ljust(3, "0")[:3])
                synced.append((ms, body))
        elif not META_RE.match(raw.strip()):
            plain.append(raw.rstrip())
    if synced:
        synced.sort(key=lambda x: x[0])
        return True, synced
    while plain and not plain[-1].strip():
        plain.pop()
    return False, [(None, line) for line in plain]


def read_text_file(path):
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def embedded_lyrics(path):
    try:
        audio = MutagenFile(path)
        tags = getattr(audio, "tags", None)
        if tags is None:
            return ""
        if hasattr(tags, "getall"):
            for frame in tags.getall("USLT"):
                text = str(frame.text).strip()
                if text:
                    return text
        for key in ("\xa9lyr", "lyrics", "unsyncedlyrics", "LYRICS", "UNSYNCEDLYRICS"):
            try:
                val = tags.get(key)
            except Exception:
                val = None
            if val:
                text = str(val[0]).strip() if isinstance(val, (list, tuple)) else str(val).strip()
                if text:
                    return text
    except Exception:
        pass
    return ""


def http_json(url):
    req = urllib.request.Request(
        url, headers={"User-Agent": "eozMP/1.0 (personal music player)"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def fetch_lrclib(artist, title, album, duration):
    """Look the song up on lrclib.net (free lyrics database, no account needed)."""
    base = "https://lrclib.net/api/"
    params = {"artist_name": artist, "track_name": title}
    if album and album != "Unknown Album":
        params["album_name"] = album
    if duration:
        params["duration"] = int(round(duration))
    data = None
    try:
        data = http_json(base + "get?" + urllib.parse.urlencode(params))
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
    if not data:
        found = http_json(
            base + "search?" + urllib.parse.urlencode({"track_name": title, "artist_name": artist})
        )
        cands = []
        if isinstance(found, list):
            cands = [r for r in found if artist.lower() in str(r.get("artistName", "")).lower()]
        cands.sort(key=lambda r: not r.get("syncedLyrics"))
        data = cands[0] if cands else None
    if not data:
        return None
    return {
        "lrc": data.get("syncedLyrics") or "",
        "plain": data.get("plainLyrics") or "",
        "instrumental": bool(data.get("instrumental")),
    }


def lyrics_cache_path(track):
    raw = f"{track['artist']}|{track['title']}|{track['album']}".lower()
    key = hashlib.sha1(raw.encode("utf-8", "replace")).hexdigest()[:24]
    return LYRICS_DIR / f"{key}.json"


def get_lyrics(track, online, save_files, force=False):
    """Runs in a background thread. Order: .lrc/.txt next to the song,
    lyrics embedded in the file, saved earlier lookup, then the internet."""
    path = track["path"]
    stem = os.path.splitext(path)[0]
    for ext in (".lrc", ".txt"):
        text = read_text_file(stem + ext)
        if text.strip():
            return {"text": text, "source": f"from {os.path.basename(stem + ext)}"}
    text = embedded_lyrics(path)
    if text:
        return {"text": text, "source": "embedded in the file"}

    cpath = lyrics_cache_path(track)
    cached = None
    try:
        cached = json.loads(cpath.read_text(encoding="utf-8"))
    except Exception:
        pass
    if cached and cached.get("found"):
        return {
            "text": cached.get("lrc") or cached.get("plain") or "",
            "instrumental": bool(cached.get("instrumental")),
            "source": "lrclib.net (saved)",
        }
    if not online or track["artist"] == "Unknown Artist":
        return {"text": "", "source": ""}
    if cached and not force and time.time() - cached.get("ts", 0) < NEG_CACHE_SECONDS:
        return {"text": "", "source": ""}

    try:
        res = fetch_lrclib(track["artist"], track["title"], track["album"], track["length"])
    except Exception as e:
        return {"text": "", "source": "", "error": str(e)}
    try:
        LYRICS_DIR.mkdir(exist_ok=True)
        if res and (res["lrc"] or res["plain"] or res["instrumental"]):
            cpath.write_text(json.dumps({"found": True, **res}), encoding="utf-8")
        else:
            cpath.write_text(json.dumps({"found": False, "ts": time.time()}), encoding="utf-8")
    except Exception:
        pass
    if not res or not (res["lrc"] or res["plain"]):
        return {"text": "", "source": "", "instrumental": bool(res and res["instrumental"])}
    text = res["lrc"] or res["plain"]
    if save_files:
        try:
            Path(stem + (".lrc" if res["lrc"] else ".txt")).write_text(text, encoding="utf-8")
        except OSError:
            pass
    return {"text": text, "source": "lrclib.net"}


# ---------------------------------------------------------------- slskd
class Slskd:
    """Tiny client for the slskd REST API (https://github.com/slskd/slskd)."""

    def __init__(self, url, key):
        self.base = url.rstrip("/") + "/api/v0"
        self.key = key

    def call(self, method, path, body=None, timeout=20):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(
            self.base + path, data=data, method=method,
            headers={"X-API-Key": self.key, "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"slskd said HTTP {e.code} ({'check your API key' if e.code in (401, 403) else e.reason})")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Can't reach slskd ({e.reason}). Is it running?")
        return json.loads(raw) if raw else None


def flatten_responses(responses):
    rows = []
    for r in responses or []:
        for f in r.get("files", []) or []:
            fn = f.get("filename", "")
            ext = Path(fn.replace("\\", "/")).suffix.lower()
            if ext not in AUDIO_EXTS:
                continue
            rows.append({
                "username": r.get("username", ""),
                "filename": fn,
                "size": f.get("size", 0),
                "ext": ext.lstrip("."),
                "bitrate": f.get("bitRate") or 0,
                "free": bool(r.get("hasFreeUploadSlot")),
                "speed": r.get("uploadSpeed", 0) or 0,
                "queue": r.get("queueLength", 0) or 0,
            })
    rows.sort(key=lambda x: (not x["free"], -x["speed"]))
    return rows[:2000]


def passes_filters(row, fmt, free_only):
    if free_only and not row["free"]:
        return False
    ext, br = row["ext"], row["bitrate"]
    if fmt == "Lossless only":
        return ext in LOSSLESS_EXTS
    if fmt == "MP3 320k+":
        return ext == "mp3" and br >= 320
    if fmt == "MP3 (any)":
        return ext == "mp3"
    return True


def split_path(filename):
    """'a\\b\\c.mp3' -> ('c.mp3', 'a/b')"""
    parts = filename.replace("\\", "/").split("/")
    return parts[-1], "/".join(parts[:-1])


def group_by_folder(rows):
    """Group result files by (user, folder) so a folder = one album."""
    groups = {}
    for r in rows:
        _, folder = split_path(r["filename"])
        groups.setdefault((r["username"], folder), []).append(r)
    out = list(groups.values())
    out.sort(key=lambda g: (not g[0]["free"], -len(g), -g[0]["speed"]))
    return out


def quality_text(rows):
    exts = Counter(r["ext"] for r in rows)
    ext = exts.most_common(1)[0][0]
    brs = [r["bitrate"] for r in rows if r["bitrate"] and r["ext"] == ext]
    text = ext.upper()
    if brs:
        text += f" ~{sum(brs) // len(brs)}k"
    if len(exts) > 1:
        text += " (mixed)"
    return text


def parse_state(state):
    s = str(state)
    if "Succeeded" in s:
        return "Finished"
    if "Completed" in s:
        reason = s.split(",")[-1].strip() if "," in s else "stopped"
        return f"Failed ({reason})"
    if "InProgress" in s:
        return "Downloading"
    if "Queued" in s:
        return "Waiting in queue"
    return "Starting"


class Worker(QThread):
    ok = pyqtSignal(object)
    fail = pyqtSignal(str)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self):
        try:
            self.ok.emit(self.fn())
        except Exception as e:
            self.fail.emit(str(e))


class SearchWorker(QThread):
    results = pyqtSignal(list)
    failed = pyqtSignal(str)
    finished_search = pyqtSignal()

    def __init__(self, client, text):
        super().__init__()
        self.client = client
        self.text = text
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        sid = str(uuid.uuid4())
        try:
            self.client.call("POST", "/searches", {"id": sid, "searchText": self.text})
            deadline = time.time() + 30
            while time.time() < deadline and not self._stop:
                time.sleep(2)
                state = self.client.call("GET", f"/searches/{sid}") or {}
                resp = self.client.call("GET", f"/searches/{sid}/responses") or []
                if not self._stop:
                    self.results.emit(flatten_responses(resp))
                if state.get("isComplete"):
                    break
            try:
                self.client.call("DELETE", f"/searches/{sid}")
            except Exception:
                pass
        except Exception as e:
            self.failed.emit(str(e))
        self.finished_search.emit()


# ---------------------------------------------------------------- theme + preferences
ACCENTS = {
    "Blue": "#4C8DFF",
    "Violet": "#8B6CFF",
    "Pink": "#F2528A",
    "Red": "#EE5555",
    "Orange": "#EE7F38",
    "Green": "#1FA85A",
    "Teal": "#11A5A5",
    "Indigo": "#5B5BD6",
    "Yellow": "#E3B505",
    "Lime": "#7CB518",
    "Coral": "#FF6F61",
    "Slate": "#64748B",
}


def make_scheme(dark, accent):
    """All the colours the app uses, in one place."""
    if dark:
        sc = {"bg": "#141417", "panel": "#1b1b20", "raised": "#26262d",
              "hover": "#2f2f37", "border": "#2c2c34",
              "text": "#ececf1", "sub": "#9b9ba8"}
    else:
        sc = {"bg": "#f4f4f7", "panel": "#ffffff", "raised": "#eceef2",
              "hover": "#e2e4ea", "border": "#dcdee5",
              "text": "#1c1c1e", "sub": "#6b6b76"}
    sc["accent"] = accent
    sc["accent_hover"] = QColor(accent).lighter(115).name()
    dim = QColor(sc["text"])
    dim.setAlpha(105)
    sc["lyric_dim"] = dim
    sc["dark"] = dark
    c = QColor(accent)
    lum = (0.2126 * c.red() + 0.7152 * c.green() + 0.0722 * c.blue()) / 255
    sc["on_accent"] = "#111111" if lum > 0.62 else "#ffffff"   # text/icons drawn on the accent
    sc["accent_soft"] = f"rgba({c.red()}, {c.green()}, {c.blue()}, {70 if dark else 52})"
    return sc


def palette_from_scheme(sc):
    p = QPalette()
    R = QPalette.ColorRole
    roles = {
        R.Window: sc["bg"], R.WindowText: sc["text"],
        R.Base: sc["panel"], R.AlternateBase: sc["raised"],
        R.ToolTipBase: sc["raised"], R.ToolTipText: sc["text"],
        R.Text: sc["text"], R.Button: sc["raised"], R.ButtonText: sc["text"],
        R.BrightText: "#ff5050", R.Link: sc["accent"],
        R.Highlight: sc["accent"], R.HighlightedText: sc["on_accent"],
        R.PlaceholderText: sc["sub"],
    }
    for role, color in roles.items():
        p.setColor(role, QColor(color))
    for role in (R.Text, R.ButtonText, R.WindowText):
        p.setColor(QPalette.ColorGroup.Disabled, role, QColor(sc["sub"]))
    return p


QSS_TEMPLATE = r"""
QMainWindow, QDialog { background: @bg@; }
QWidget { color: @text@; }
QLabel { background: transparent; }
QLabel#heading { font-family: "@display_font@"; font-size: 28px; font-weight: 700; }
QLabel#heading2 { font-family: "@display_font@"; font-size: 21px; font-weight: 700; }
QLabel#heading3 { font-size: 13px; font-weight: 600; }
QLabel#sub { color: @sub@; }
QLabel#lyricline { color: @accent@; font-style: italic; }
QLabel#nowplaying { font-size: 14px; font-weight: 600; }
QToolTip { background: @raised@; color: @text@; border: 1px solid @border@; padding: 4px; }

QMenuBar { background: @bg@; color: @text@; }
QMenuBar::item { padding: 6px 12px; background: transparent; border-radius: @r_sm@; }
QMenuBar::item:selected { background: @raised@; }
QMenu { background: @panel@; color: @text@; border: 1px solid @border@; padding: 6px; }
QMenu::item { padding: 7px 28px 7px 14px; border-radius: @r_sm@; }
QMenu::item:selected { background: @accent@; color: @on_accent@; }
QStatusBar { background: @bg@; color: @sub@; }

QLineEdit, QComboBox { background: @panel@; border: 1px solid @border@; border-radius: @r_md@; padding: 7px 10px; selection-background-color: @accent@; }
QSpinBox { background: @panel@; border: 1px solid @border@; border-radius: @r_md@; padding: 4px 8px; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border: 1px solid @accent@; }
QComboBox QAbstractItemView { background: @panel@; border: 1px solid @border@; selection-background-color: @accent@; selection-color: @on_accent@; outline: none; }

QPushButton { background: @raised@; border: 1px solid @border@; border-radius: @r_md@; padding: 7px 14px; }
QPushButton:hover { background: @hover@; }
QPushButton:pressed { background: @border@; }
QPushButton:disabled { color: @sub@; }
QPushButton#primary { background: @accent@; color: @on_accent@; border: none; font-weight: 600; }
QPushButton#primary:hover { background: @accent_hover@; }
QPushButton#play { background: @accent@; color: @on_accent@; border: none; border-radius: @r_pill@; padding: 0px; font-weight: 700; }
QPushButton#play:hover { background: @accent_hover@; }
QPushButton#transport { background: transparent; border: none; padding: 8px 12px; }
QPushButton#transport:hover { background: @raised@; }
QPushButton#transport:checked { background: transparent; }

QTreeWidget, QTableWidget, QListWidget { background: @panel@; border: 1px solid @border@; border-radius: @r_lg@; outline: none; }
QTreeWidget::item { padding: @pad_tree@; border-radius: @r_sm@; border: 1px solid transparent; }
QTreeWidget::item:hover { background: @hover@; }
QTreeWidget { show-decoration-selected: 0; }
QTreeWidget::item:selected, QTreeWidget::item:selected:!active { background: transparent; border: 1px solid @accent@; color: @text@; }
QTreeWidget::branch { background: transparent; }
QTreeWidget::branch:selected, QTreeWidget::branch:hover { background: transparent; }
QTreeWidget::branch:has-children:closed { image: url("@chev_right@"); }
QTreeWidget::branch:has-children:open { image: url("@chev_down@"); }
QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }
QListWidget#tiles { background: transparent; border: none; }
QListWidget#tiles::item { padding: 6px; border-radius: @r_md@; border: 1px solid transparent; }
QListWidget#tiles::item:hover { background: @hover@; }
QListWidget#tiles::item:selected { background: transparent; border: 1px solid @accent@; color: @text@; }
QTableWidget { gridline-color: transparent; selection-background-color: @accent@; selection-color: @on_accent@; }
QTableWidget::item { padding: @pad_table@; border: none; }
QHeaderView::section { background: @panel@; color: @sub@; border: none; border-bottom: 1px solid @border@; padding: 6px 8px; font-weight: 600; }

QListWidget::item { padding: @pad_list@; border-radius: @r_sm@; border: 1px solid transparent; }
QListWidget::item:hover { background: @hover@; }
QListWidget::item:selected { background: transparent; border: 1px solid @accent@; color: @text@; }
QLabel#brand { font-family: "@display_font@"; font-size: 19px; font-weight: 800; }
QPushButton#seg { background: transparent; border: none; border-bottom: 2px solid transparent; border-radius: 0px; padding: 6px 9px; color: @sub@; font-weight: 600; }
QPushButton#seg:hover { color: @text@; background: transparent; }
QPushButton#seg:checked { color: @text@; border-bottom: 2px solid @accent@; }
QPushButton#link { background: transparent; border: none; padding: 0px 2px; color: @accent@; font-size: 12px; }
QPushButton#link:hover { text-decoration: underline; background: transparent; }
QListWidget#lyrics { background: transparent; border: none; }
QWidget#drawer QListWidget { background: transparent; border: none; }
QListWidget#lyrics::item { padding: 8px 14px; }
QListWidget#lyrics::item:hover { background: transparent; }

QScrollBar:vertical { background: transparent; width: 12px; margin: 2px; }
QScrollBar::handle:vertical { background: @border@; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: @sub@; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: transparent; height: 12px; margin: 2px; }
QScrollBar::handle:horizontal { background: @border@; border-radius: 4px; min-width: 30px; }
QScrollBar::handle:horizontal:hover { background: @sub@; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }

QSlider::groove:horizontal { height: 4px; background: @border@; border-radius: 2px; }
QSlider::sub-page:horizontal { background: @accent@; border-radius: 2px; }
QSlider::handle:horizontal { background: @text@; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }
QSlider::handle:horizontal:hover { background: @accent@; }
QSlider::groove:vertical { width: 4px; background: @border@; border-radius: 2px; }
QSlider::add-page:vertical { background: @accent@; border-radius: 2px; }
QSlider::handle:vertical { background: @text@; width: 14px; height: 14px; margin: 0 -5px; border-radius: 7px; }
QSlider::handle:vertical:hover { background: @accent@; }
QFrame#card { background: @panel@; border: 1px solid @border@; border-radius: @r_lg@; }
QLabel#statnum { font-family: "@display_font@"; font-size: 26px; font-weight: 700; }

QTabWidget::pane { border: 1px solid @border@; border-radius: @r_md@; top: -1px; }
QTabBar::tab { padding: 8px 16px; background: transparent; color: @sub@; border-bottom: 2px solid transparent; }
QTabBar::tab:selected { color: @text@; border-bottom: 2px solid @accent@; }
QTabBar::tab:hover { color: @text@; }
QSplitter::handle:horizontal { background: transparent; width: 8px; }
"""


def build_qss(sc):
    qss = QSS_TEMPLATE
    for key, val in sc.items():
        if isinstance(val, str):
            qss = qss.replace(f"@{key}@", val)
    return qss


def apply_look(app, theme, accent_name, system_dark, tokens=None):
    dark = theme == "Dark" or (theme == "System" and system_dark)
    accent = accent_name if str(accent_name).startswith("#") else ACCENTS.get(accent_name, ACCENTS["Blue"])
    sc = make_scheme(dark, accent)
    sc.update(tokens or {})
    sc.update(chevron_tokens(sc["sub"]))
    app.setPalette(palette_from_scheme(sc))
    app.setStyleSheet(build_qss(sc))
    return sc


def rounded_pixmap(pix, size, radius):
    """Square, centre-cropped cover with rounded corners."""
    scaled = pix.scaled(
        size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation)
    out = QPixmap(size, size)
    out.fill(Qt.GlobalColor.transparent)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    path = QPainterPath()
    path.addRoundedRect(0, 0, size, size, radius, radius)
    painter.setClipPath(path)
    painter.drawPixmap((size - scaled.width()) // 2, (size - scaled.height()) // 2, scaled)
    painter.end()
    return out


def placeholder_cover(size, radius, accent):
    """Shown when an album has no artwork: accent gradient with a note."""
    out = QPixmap(size, size)
    out.fill(Qt.GlobalColor.transparent)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(0, 0, size, size, radius, radius)
    grad = QLinearGradient(0, 0, size, size)
    grad.setColorAt(0, QColor(accent).darker(170))
    grad.setColorAt(1, QColor(accent))
    painter.fillPath(path, grad)
    font = QFont()
    font.setPixelSize(max(10, size // 2))
    painter.setFont(font)
    painter.setPen(QColor(255, 255, 255, 190))
    painter.drawText(out.rect(), Qt.AlignmentFlag.AlignCenter, "\u266a")
    painter.end()
    return out


LOGO_BG = "#111114"


def logo_pixmap(size):
    """eozMP logo: just the word 'eozMP' in white on a dark rounded square (neutral, no colours)."""
    out = QPixmap(size, size)
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    bg = QPainterPath()
    corner = size * 0.22
    bg.addRoundedRect(0, 0, size, size, corner, corner)
    p.fillPath(bg, QColor(LOGO_BG))
    font = QFont(pick_display_family() or "Segoe UI")
    font.setWeight(QFont.Weight.Bold)
    font.setPixelSize(100)
    width = QFontMetrics(font).horizontalAdvance("eozMP")
    font.setPixelSize(max(4, int(100 * size * 0.8 / max(1, width))))
    p.setFont(font)
    p.setPen(QColor("#ffffff"))
    p.drawText(out.rect(), Qt.AlignmentFlag.AlignCenter, "eozMP")
    p.end()
    return out


def app_icon():
    icon = QIcon()
    for n in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(logo_pixmap(n))
    return icon


SERIF_FONTS = ("Times New Roman", "Liberation Serif", "Georgia", "DejaVu Serif",
               "Segoe UI", "Arial")


def pick_ui_font():
    try:
        families = set(QFontDatabase.families())
    except Exception:
        return None
    for name in SERIF_FONTS:
        if name in families:
            font = QFont(name)
            font.setPointSize(10)
            return font
    return None


LYRIC_WEIGHTS = {
    "Regular": QFont.Weight.Normal,
    "Medium": QFont.Weight.Medium,
    "Semibold": QFont.Weight.DemiBold,
    "Bold": QFont.Weight.Bold,
    "Heavy": QFont.Weight.ExtraBold,
}
CORNER_FACTORS = {"Rounded": 1.0, "Subtle": 0.5, "Square": 0.0}
DENSITY = {
    "Comfortable": {"pad_tree": "5px 4px", "pad_table": "6px", "pad_list": "8px 10px"},
    "Compact": {"pad_tree": "2px 4px", "pad_table": "3px", "pad_list": "4px 8px"},
}
COVER_SIZES = {"Small": 160, "Medium": 220, "Large": 280}


def style_tokens(cfg, display_family):
    f = CORNER_FACTORS.get(cfg["corner_style"], 1.0)

    def px(r):
        return f"{int(round(r * f))}px"

    tokens = {"r_sm": px(6), "r_md": px(8), "r_lg": px(10), "r_pill": px(23),
              "display_font": display_family}
    tokens.update(DENSITY.get(cfg["density"], DENSITY["Comfortable"]))
    return tokens


def pick_display_family():
    """Big-text font: the closest thing on this PC to Apple's SF Pro Display."""
    try:
        families = set(QFontDatabase.families())
    except Exception:
        return None
    for name in SERIF_FONTS:
        if name in families:
            return name
    return None


def blur_pixmap(pix, size=600, radius=46):
    """Real (gaussian) blur at a good resolution, so the backdrop stays smooth and rich."""
    pad = radius * 2
    big = pix.scaled(size + 2 * pad, size + 2 * pad, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                     Qt.TransformationMode.SmoothTransformation)
    scene = QGraphicsScene()
    item = QGraphicsPixmapItem(big)
    effect = QGraphicsBlurEffect()
    effect.setBlurRadius(radius)
    effect.setBlurHints(QGraphicsBlurEffect.BlurHint.QualityHint)
    item.setGraphicsEffect(effect)
    scene.addItem(item)
    ox = (big.width() - size) / 2
    oy = (big.height() - size) / 2
    img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.black)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    scene.render(p, QRectF(0, 0, size, size), QRectF(ox, oy, size, size))
    p.end()
    return QPixmap.fromImage(img)


def make_backdrop(pix, accent):
    """Blurred version of the cover (or a soft accent gradient when there's no cover)."""
    if pix is None or pix.isNull():
        src = QPixmap(64, 64)
        painter = QPainter(src)
        grad = QLinearGradient(0, 0, 64, 64)
        grad.setColorAt(0, QColor(accent).darker(260))
        grad.setColorAt(1, QColor(accent).darker(140))
        painter.fillRect(src.rect(), grad)
        painter.end()
        return src.scaled(320, 320, Qt.AspectRatioMode.IgnoreAspectRatio,
                          Qt.TransformationMode.SmoothTransformation)
    return blur_pixmap(pix)


UI_DIR = Path.home() / ".simple_music_player_ui"


def chevron_tokens(color):
    """Thin chevron images for the library tree (QSS needs real image files)."""
    tokens = {}
    try:
        UI_DIR.mkdir(exist_ok=True)
        tag = QColor(color).name().lstrip("#")
        for kind in ("right", "down"):
            for scale, suffix in ((1, ""), (2, "@2x")):
                path = UI_DIR / f"chev_{kind}_{tag}{suffix}.png"
                if not path.exists():
                    n = 12 * scale
                    pm = QPixmap(n, n)
                    pm.fill(Qt.GlobalColor.transparent)
                    painter = QPainter(pm)
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                    pen = QPen(QColor(color))
                    pen.setWidthF(1.6 * scale)
                    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    painter.setPen(pen)
                    if kind == "right":
                        pts = [(0.38, 0.22), (0.66, 0.5), (0.38, 0.78)]
                    else:
                        pts = [(0.22, 0.38), (0.5, 0.66), (0.78, 0.38)]
                    path_ = QPainterPath()
                    path_.moveTo(pts[0][0] * n, pts[0][1] * n)
                    for x, y in pts[1:]:
                        path_.lineTo(x * n, y * n)
                    painter.drawPath(path_)
                    painter.end()
                    pm.save(str(path))
            tokens[f"chev_{kind}"] = (UI_DIR / f"chev_{kind}_{tag}.png").as_posix()
    except Exception:
        tokens = {"chev_right": "", "chev_down": ""}
    return tokens


def avatar_pixmap(name, size, bg, fg):
    """Round picture with the artist's first letter (used until a cover is found)."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    circle = QPainterPath()
    circle.addEllipse(0, 0, size, size)
    p.fillPath(circle, QColor(bg))
    font = QFont()
    font.setPixelSize(max(6, int(size * 0.42)))
    font.setWeight(QFont.Weight.Bold)
    p.setFont(font)
    p.setPen(QColor(fg))
    p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, (name.strip()[:1] or "?").upper())
    p.end()
    return pm


def header_qss(sc):
    """White text + glassy buttons for headers that sit on a blurred cover."""
    return (
        "QLabel { color: #ffffff; }"
        "QLabel#sub { color: rgba(255, 255, 255, 195); }"
        "QPushButton { background: rgba(255, 255, 255, 36); color: #ffffff; border: none;"
        " border-radius: 8px; padding: 7px 14px; }"
        "QPushButton:hover { background: rgba(255, 255, 255, 64); }"
        f"QPushButton#primary {{ background: {sc['accent']}; color: {sc['on_accent']}; font-weight: 600; }}"
        f"QPushButton#primary:hover {{ background: {sc['accent_hover']}; }}"
    )


def static_icon(pix):
    """An icon that looks the same when its row is selected (Qt would tint it otherwise)."""
    icon = QIcon()
    for mode in (QIcon.Mode.Normal, QIcon.Mode.Selected, QIcon.Mode.Active):
        icon.addPixmap(pix, mode)
    return icon


VIZ_STATUS = (
    "Ready" if QAudioBufferOutput is not None else
    "Needs a newer PyQt6 (6.8 or later): run  pip install -U PyQt6")


def spectrum_levels(mono, n):
    """Frequency spectrum squeezed into n bars (0..1), log-spaced like the ear hears it."""
    size = len(mono)
    if size < 64:
        return [0.0] * n
    mag = np.abs(np.fft.rfft(mono * np.hanning(size)))
    edges = np.unique(np.logspace(np.log10(2), np.log10(len(mag) - 1), n + 1).astype(int))
    bands = [mag[a:b].mean() if b > a else mag[a] for a, b in zip(edges[:-1], edges[1:])]
    db = 20 * np.log10(np.asarray(bands) + 1e-9)
    levels = np.clip((db + 5) / 50, 0, 1).tolist()
    if len(levels) < n:
        levels += [levels[-1] if levels else 0.0] * (n - len(levels))
    return levels[:n]


def loudness_levels(raw, sample_format, channels, n):
    """Without numpy: loudness of n slices of the buffer (still follows the music)."""
    code = {QAudioFormat.SampleFormat.Int16: "h", QAudioFormat.SampleFormat.Int32: "i",
            QAudioFormat.SampleFormat.Float: "f", QAudioFormat.SampleFormat.UInt8: "B"}.get(sample_format)
    if code is None:
        return [0.0] * n
    data = array(code)
    data.frombytes(raw[: len(raw) - len(raw) % data.itemsize])
    scale = {"h": 32768.0, "i": 2147483648.0, "f": 1.0, "B": 128.0}[code]
    mono = data[::max(1, channels)]
    step = max(1, len(mono) // n)
    out = []
    for i in range(n):
        chunk = mono[i * step:(i + 1) * step]
        if not chunk:
            out.append(0.0)
            continue
        if code == "B":
            rms = math.sqrt(sum((x - 128) ** 2 for x in chunk) / len(chunk)) / scale
        else:
            rms = math.sqrt(sum(x * x for x in chunk) / len(chunk)) / scale
        out.append(min(1.0, rms * 2.2))
    return out


class Visualizer(QWidget):
    """Bars or a wave that dance to the music."""

    def __init__(self, parent=None, bars=48):
        super().__init__(parent)
        self.levels = [0.0] * bars
        self.style = "Bars"
        self.color = QColor(255, 255, 255, 170)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def feed(self, values):
        n = len(self.levels)
        if not values:
            return
        for i in range(n):
            v = values[min(len(values) - 1, int(i * len(values) / n))]
            self.levels[i] = max(v, self.levels[i] * 0.82)

    def tick(self):
        self.levels = [v * 0.9 for v in self.levels]
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h, n = self.width(), self.height(), len(self.levels)
        if n == 0 or w <= 0 or h <= 0:
            return
        if self.style == "Wave":
            path = QPainterPath()
            path.moveTo(0, h)
            pts = [(i * w / (n - 1), h - max(2.0, v * h * 0.95)) for i, v in enumerate(self.levels)]
            path.lineTo(*pts[0])
            for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
                mx = (x0 + x1) / 2
                path.cubicTo(mx, y0, mx, y1, x1, y1)
            path.lineTo(w, h)
            path.closeSubpath()
            grad = QLinearGradient(0, 0, 0, h)
            top = QColor(self.color)
            bottom = QColor(self.color)
            bottom.setAlpha(20)
            grad.setColorAt(0, top)
            grad.setColorAt(1, bottom)
            p.fillPath(path, grad)
        else:
            gap = 3.0
            bw = max(2.0, (w - gap * (n - 1)) / n)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(self.color)
            for i, v in enumerate(self.levels):
                bh = max(2.0, v * h * 0.95)
                p.drawRoundedRect(QRectF(i * (bw + gap), h - bh, bw, bh), min(3.0, bw / 2), min(3.0, bw / 2))
        p.end()


def _flag(value):
    return value.value if hasattr(value, "value") else int(value)


class LyricDelegate(QStyledItemDelegate):
    """Draws lyric lines (with an optional soft shadow for bright covers)."""

    def __init__(self, main):
        super().__init__(main.lyrics_list)
        self.main = main

    def sizeHint(self, option, index):
        hint = index.data(Qt.ItemDataRole.SizeHintRole)
        if hint is not None and hint.isValid():
            return hint
        font = index.data(Qt.ItemDataRole.FontRole) or option.font
        hpad, vpad = self.main.lyric_pad
        width = max(60, self.main.lyrics_list.viewport().width() - 2 * hpad)
        text = index.data(Qt.ItemDataRole.DisplayRole) or " "
        rect = QFontMetrics(font).boundingRect(QRect(0, 0, width, 100000),
                                               _flag(Qt.TextFlag.TextWordWrap), text)
        return QSize(width + 2 * hpad, rect.height() + 2 * vpad)

    def paint(self, painter, option, index):
        if index.data(KEY_ROLE) == "spacer":
            return
        text = index.data(Qt.ItemDataRole.DisplayRole) or ""
        font = index.data(Qt.ItemDataRole.FontRole) or option.font
        fg = index.data(Qt.ItemDataRole.ForegroundRole)
        if isinstance(fg, QBrush):
            color = fg.color()
        elif isinstance(fg, QColor):
            color = fg
        else:
            color = option.palette.color(QPalette.ColorRole.Text)
        align = index.data(Qt.ItemDataRole.TextAlignmentRole)
        flags = (_flag(align) if align is not None
                 else _flag(Qt.AlignmentFlag.AlignLeft) | _flag(Qt.AlignmentFlag.AlignVCenter))
        flags |= _flag(Qt.TextFlag.TextWordWrap)
        hpad, vpad = self.main.lyric_pad
        r = QRect(option.rect).adjusted(hpad, vpad, -hpad, -vpad)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setFont(font)
        if self.main.cfg["lyrics_shadow"]:
            alpha = color.alphaF()
            painter.setPen(QColor(0, 0, 0, int(150 * alpha)))
            painter.drawText(r.translated(0, 2), flags, text)
            painter.setPen(QColor(0, 0, 0, int(70 * alpha)))
            painter.drawText(r.translated(1, 3), flags, text)
        painter.setPen(color)
        painter.drawText(r, flags, text)
        painter.restore()


class FrameDelegate(QStyledItemDelegate):
    """Selected rows get a thin rounded frame in the accent colour instead of a filled bar."""

    def __init__(self, view, color_fn, hover_fn=None, playing_fn=None, phase_fn=None):
        super().__init__(view)
        self.view = view
        self.color_fn = color_fn
        self.hover_fn = hover_fn
        self.playing_fn = playing_fn
        self.phase_fn = phase_fn
        self._hide_text = False

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        if self._hide_text:
            option.text = ""

    def _is_playing_row(self, index):
        if self.playing_fn is None or not hasattr(self.view, "paths_fn"):
            return False
        current = self.playing_fn()
        if not current:
            return False
        got = self.view.paths_fn([index.row()])
        return bool(got) and got[0] == current

    def paint(self, painter, option, index):
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        opt = QStyleOptionViewItem(option)
        if selected:
            opt.state &= ~QStyle.StateFlag.State_Selected
        opt.state &= ~QStyle.StateFlag.State_HasFocus
        opt.state &= ~QStyle.StateFlag.State_MouseOver
        hover = getattr(self.view, "hover_row", -1) == index.row() and not selected
        if hover and self.hover_fn is not None:
            self._row_shape(painter, option, index, fill=QColor(self.hover_fn()))
        playing = self._is_playing_row(index)
        bars = playing and index.column() == 0 and getattr(self.view, "number_col", False)
        if playing:
            accent = QColor(self.color_fn())
            opt.palette.setColor(QPalette.ColorRole.Text, accent)
            opt.palette.setColor(QPalette.ColorRole.WindowText, accent)
        self._hide_text = bars
        super().paint(painter, opt, index)
        self._hide_text = False
        if bars:
            self._draw_bars(painter, option.rect)
        if not selected:
            return
        self._row_shape(painter, option, index, fill=None)

    def _draw_bars(self, painter, rect):
        phase = self.phase_fn() if self.phase_fn else 0.0
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self.color_fn()))
        h = rect.height() * 0.5
        x = rect.left() + max(4, (rect.width() - 16) / 2)
        base = rect.top() + (rect.height() + h) / 2
        for i, speed in enumerate((1.0, 1.7, 1.3)):
            level = 0.35 + 0.65 * abs(math.sin(phase * speed + i * 1.1)) if phase else 0.35 + 0.2 * i
            bh = max(2.0, h * level)
            painter.drawRoundedRect(QRectF(x + i * 6, base - bh, 3.5, bh), 1.5, 1.5)
        painter.restore()

    def _row_shape(self, painter, option, index, fill):
        cols = index.model().columnCount()
        hidden = [c for c in range(cols) if self.view.isColumnHidden(c)]
        visible = [c for c in range(cols) if c not in hidden]
        first = index.column() == visible[0]
        last = index.column() == visible[-1]
        r = QRectF(option.rect).adjusted(0.75, 1.5, -0.75, -1.5)
        x0, y0, x1, y1, rad = r.left(), r.top(), r.right(), r.bottom(), 6.0
        path = QPainterPath()
        if fill is not None:
            if first and last:
                path.addRoundedRect(r, rad, rad)
            elif first:
                path.moveTo(x1 + 1, y0)
                path.lineTo(x0 + rad, y0)
                path.arcTo(QRectF(x0, y0, 2 * rad, 2 * rad), 90, 90)
                path.lineTo(x0, y1 - rad)
                path.arcTo(QRectF(x0, y1 - 2 * rad, 2 * rad, 2 * rad), 180, 90)
                path.lineTo(x1 + 1, y1)
                path.closeSubpath()
            elif last:
                path.moveTo(x0 - 1, y0)
                path.lineTo(x1 - rad, y0)
                path.arcTo(QRectF(x1 - 2 * rad, y0, 2 * rad, 2 * rad), 90, -90)
                path.lineTo(x1, y1 - rad)
                path.arcTo(QRectF(x1 - 2 * rad, y1 - 2 * rad, 2 * rad, 2 * rad), 0, -90)
                path.lineTo(x0 - 1, y1)
                path.closeSubpath()
            else:
                path.addRect(QRectF(x0 - 1, y0, (x1 - x0) + 2, y1 - y0))
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.fillPath(path, fill)
            painter.restore()
            return
        if first and last:
            path.addRoundedRect(r, rad, rad)
        elif first:
            path.moveTo(x1 + 1, y0)
            path.lineTo(x0 + rad, y0)
            path.arcTo(QRectF(x0, y0, 2 * rad, 2 * rad), 90, 90)
            path.lineTo(x0, y1 - rad)
            path.arcTo(QRectF(x0, y1 - 2 * rad, 2 * rad, 2 * rad), 180, 90)
            path.lineTo(x1 + 1, y1)
        elif last:
            path.moveTo(x0 - 1, y0)
            path.lineTo(x1 - rad, y0)
            path.arcTo(QRectF(x1 - 2 * rad, y0, 2 * rad, 2 * rad), 90, -90)
            path.lineTo(x1, y1 - rad)
            path.arcTo(QRectF(x1 - 2 * rad, y1 - 2 * rad, 2 * rad, 2 * rad), 0, -90)
            path.lineTo(x0 - 1, y1)
        else:
            path.moveTo(x0 - 1, y0)
            path.lineTo(x1 + 1, y0)
            path.moveTo(x0 - 1, y1)
            path.lineTo(x1 + 1, y1)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(self.color_fn()))
        pen.setWidthF(1.4)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        painter.restore()


class BackdropWidget(QWidget):
    """A panel that paints a blurred cover (darkened) behind its contents."""

    def __init__(self, radius=12, overlay=120):
        super().__init__()
        self.radius = radius
        self.overlay = overlay
        self.backdrop = None
        self._cache = None

    def set_backdrop(self, pix):
        self.backdrop = pix
        self._cache = None
        self.update()

    def paintEvent(self, event):
        if self.backdrop is None:
            return
        size = self.size()
        if size.isEmpty():
            return
        if self._cache is None or self._cache.size() != size:
            scaled = self.backdrop.scaled(size, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                          Qt.TransformationMode.SmoothTransformation)
            canvas = QPixmap(size)
            canvas.fill(Qt.GlobalColor.transparent)
            p = QPainter(canvas)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            clip = QPainterPath()
            clip.addRoundedRect(0, 0, size.width(), size.height(), self.radius, self.radius)
            p.setClipPath(clip)
            p.drawPixmap((size.width() - scaled.width()) // 2, (size.height() - scaled.height()) // 2, scaled)
            p.fillRect(canvas.rect(), QColor(0, 0, 0, self.overlay))
            p.end()
            self._cache = canvas
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._cache)
        painter.end()


class ThumbLoader(QThread):
    """Reads album covers in the background so the library list never freezes."""
    loaded = pyqtSignal(object, object)   # album key, image bytes (or None)

    def __init__(self):
        super().__init__()
        self.jobs = deque()
        self.lock = threading.Lock()
        self.event = threading.Event()
        self._stop = False

    def add(self, items, front=False):
        with self.lock:
            if front:
                for it in reversed(items):
                    self.jobs.appendleft(it)
            else:
                self.jobs.extend(items)
        self.event.set()

    def clear(self):
        with self.lock:
            self.jobs.clear()

    def stop(self):
        self._stop = True
        self.event.set()

    def run(self):
        while not self._stop:
            with self.lock:
                job = self.jobs.popleft() if self.jobs else None
            if job is None:
                self.event.wait(0.5)
                self.event.clear()
                continue
            key, paths, artist, album = job
            data = None
            try:
                for path in paths[:3]:
                    data = embedded_cover(path)
                    if data:
                        break
                if not data and paths:
                    data = folder_cover(paths[0])
                if not data:
                    data = read_cached_cover(artist, album)
            except Exception:
                data = None
            self.loaded.emit(key, data)


BAD_NAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
LEFTOVER_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".nfo", ".m3u", ".m3u8", ".sfv",
                 ".log", ".cue", ".txt", ".url", ".ini", ".db", ".md5"}


def safe_name(text, fallback):
    cleaned = BAD_NAME_CHARS.sub("", str(text)).strip().rstrip(". ")
    return (cleaned or fallback)[:120]


def organize_downloads(src_root, dest_root, group_featured=True):
    """Move finished downloads to dest_root/Artist/Album/NN - Title.ext (runs in a background thread)."""
    moved = 0
    if not src_root or not os.path.isdir(src_root) or not dest_root:
        return 0
    emptied = set()
    for root, _dirs, files in os.walk(src_root):
        for name in files:
            ext = Path(name).suffix.lower()
            if ext not in AUDIO_EXTS:
                continue
            src = os.path.join(root, name)
            try:
                t = read_track(src)
                raw = t.get("artist_raw") or ""
                artist = main_artist(raw) if group_featured else (raw.strip() or "Unknown Artist")
                folder = os.path.join(dest_root, safe_name(artist, "Unknown Artist"),
                                      safe_name(t["album"], "Unknown Album"))
                base = safe_name(t["title"], Path(name).stem)
                if t["num"] != 9999:
                    base = f"{t['num']:02d} - {base}"
                    if t["disc"] > 1:
                        base = f"{t['disc']}-{base}"
                target = os.path.join(folder, base + ext)
                if os.path.normcase(os.path.abspath(target)) == os.path.normcase(os.path.abspath(src)):
                    continue   # already in place
                os.makedirs(folder, exist_ok=True)
                if os.path.exists(target):
                    if os.path.getsize(target) == os.path.getsize(src):
                        os.remove(src)          # exact duplicate of a song you already have
                        emptied.add(root)
                        continue
                    n = 2
                    while os.path.exists(os.path.join(folder, f"{base} ({n}){ext}")):
                        n += 1
                    target = os.path.join(folder, f"{base} ({n}){ext}")
                shutil.move(src, target)
                moved += 1
                emptied.add(root)
                stem_src = os.path.splitext(src)[0]
                stem_dst = os.path.splitext(target)[0]
                for side in (".lrc", ".txt"):           # lyrics files travel with their song
                    if os.path.exists(stem_src + side) and not os.path.exists(stem_dst + side):
                        shutil.move(stem_src + side, stem_dst + side)
                for img in os.listdir(root):            # and the album cover comes along
                    if Path(img).suffix.lower() in COVER_EXTS:
                        dst_img = os.path.join(folder, img)
                        if not os.path.exists(dst_img):
                            shutil.copy2(os.path.join(root, img), dst_img)
            except Exception:
                continue   # file still busy or unreadable: try again next time
    # tidy up download folders that now only hold leftovers (covers, .nfo, playlists...)
    for folder in sorted(emptied, key=len, reverse=True):
        try:
            if os.path.normcase(folder) == os.path.normcase(src_root) or not os.path.isdir(folder):
                continue
            left = []
            for r, _d, fs in os.walk(folder):
                left += fs
            if all(Path(f).suffix.lower() in LEFTOVER_EXTS for f in left):
                shutil.rmtree(folder, ignore_errors=True)
        except Exception:
            pass
    return moved


def lyrics_page_qss(apple, immersive):
    qss = ""
    if apple:
        qss += "QListWidget#lyrics::item { padding: 10px 28px; }"
    if immersive:
        qss += (
            "QLabel { color: #ffffff; }"
            "QLabel#sub { color: rgba(255, 255, 255, 170); }"
            "QPushButton { background: rgba(255, 255, 255, 36); color: #ffffff; border: none;"
            " border-radius: 8px; padding: 7px 14px; }"
            "QPushButton:hover { background: rgba(255, 255, 255, 64); }"
            "QPushButton#link { background: transparent; padding: 0px 2px; color: rgba(255, 255, 255, 210);"
            " font-size: 12px; }"
            "QPushButton#link:hover { background: transparent; color: #ffffff; text-decoration: underline; }"
        )
    return qss


class LyricsPage(QWidget):
    """The lyrics page. In "Album art" style it paints the blurred cover behind everything."""

    def __init__(self):
        super().__init__()
        self.backdrop = None
        self._cache = None

    def set_backdrop(self, pix):
        self.backdrop = pix
        self._cache = None
        self.update()

    def paintEvent(self, event):
        if self.backdrop is None:
            return
        size = self.size()
        if size.isEmpty():
            return
        if self._cache is None or self._cache.size() != size:
            scaled = self.backdrop.scaled(
                size, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation)
            canvas = QPixmap(size)
            canvas.fill(QColor(0, 0, 0))
            p = QPainter(canvas)
            p.drawPixmap((size.width() - scaled.width()) // 2,
                         (size.height() - scaled.height()) // 2, scaled)
            p.fillRect(canvas.rect(), QColor(0, 0, 0, 115))
            p.end()
            self._cache = canvas
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._cache)
        painter.end()


class PreferencesDialog(QDialog):
    def __init__(self, cfg, parent=None, tab=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(640)
        self.player = parent
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # --- General
        gen = QWidget()
        gf = QFormLayout(gen)
        self.resume = QCheckBox("Reopen on the song and position where I stopped")
        self.resume.setChecked(bool(cfg["resume"]))
        self.autoplay = QCheckBox("Keep playing the next song automatically")
        self.autoplay.setChecked(bool(cfg["autoplay_next"]))
        self.show_line = QCheckBox("Show the current lyric line under the song title")
        self.show_line.setChecked(bool(cfg["show_lyric_line"]))
        gf.addRow(self.resume)
        gf.addRow(self.autoplay)
        gf.addRow(self.show_line)
        self.close_tray = QCheckBox("Keep eozMP playing in the system tray when I close the window")
        self.close_tray.setChecked(bool(cfg["close_to_tray"]))
        self.media_keys = QCheckBox("Use the keyboard's media keys (play/pause, next, previous)")
        self.media_keys.setChecked(bool(cfg["media_keys"]))
        gf.addRow(self.close_tray)
        gf.addRow(self.media_keys)
        self.tabs.addTab(gen, "General")

        # --- Appearance
        ap = QWidget()
        af = QFormLayout(ap)
        self.theme = QComboBox()
        self.theme.addItems(["System", "Dark", "Light"])
        self.theme.setCurrentText(cfg["theme"])
        self.accent = QComboBox()
        for name, hexcol in ACCENTS.items():
            swatch = QPixmap(14, 14)
            swatch.fill(QColor(hexcol))
            self.accent.addItem(QIcon(swatch), name)
        self.accent.addItem(ALBUM_ART_ACCENT)
        custom_swatch = QPixmap(14, 14)
        custom_swatch.fill(QColor(cfg["accent_custom"]) if QColor(cfg["accent_custom"]).isValid() else QColor("#888888"))
        self.accent.addItem(QIcon(custom_swatch), CUSTOM_ACCENT)
        self.accent.setCurrentText(cfg["accent"])
        self.corners = QComboBox()
        self.corners.addItems(list(CORNER_FACTORS))
        self.corners.setCurrentText(cfg["corner_style"])
        self.density = QComboBox()
        self.density.addItems(list(DENSITY))
        self.density.setCurrentText(cfg["density"])
        self.cover_size = QComboBox()
        self.cover_size.addItems(list(COVER_SIZES))
        self.cover_size.setCurrentText(cfg["cover_size"])
        self.ui_font_mode, self.ui_font = self.font_picker(cfg["ui_font"], "Times New Roman")
        self.ui_size = QSpinBox()
        self.ui_size.setRange(8, 16)
        self.ui_size.setSuffix(" pt")
        self.ui_size.setValue(int(cfg["ui_font_size"]))
        af.addRow("Theme", self.theme)
        af.addRow("Accent color", self.accent)
        self.custom_hex = QLineEdit(cfg["accent_custom"])
        self.custom_hex.setMaxLength(7)
        self.custom_hex.setPlaceholderText("#RRGGBB")
        self.custom_hex.setFixedWidth(110)
        self.custom_hex.textEdited.connect(lambda _t: self.accent.setCurrentText(CUSTOM_ACCENT))
        pick = QPushButton("Pick a color...")
        pick.clicked.connect(self.pick_accent)
        crow = QHBoxLayout()
        crow.addWidget(self.custom_hex)
        crow.addWidget(pick)
        crow.addStretch(1)
        af.addRow("Custom color (hex)", crow)
        self.mini_opacity = QSpinBox()
        self.mini_opacity.setRange(30, 100)
        self.mini_opacity.setSuffix(" %")
        self.mini_opacity.setValue(int(cfg["mini_opacity"]))
        af.addRow("Mini player opacity (mouse away)", self.mini_opacity)
        af.addRow("Corners", self.corners)
        af.addRow("Spacing", self.density)
        af.addRow("Album cover size", self.cover_size)
        self.list_style = QComboBox()
        self.list_style.addItems(["Covers and numbers", "Numbers", "Covers", "Plain"])
        self.list_style.setCurrentText(cfg["album_list_style"])
        af.addRow("Albums in the left list", self.list_style)
        self.page_fade = QCheckBox("Fade between pages")
        self.page_fade.setChecked(bool(cfg["page_fade"]))
        af.addRow(self.page_fade)
        af.addRow("App font", self.ui_font_mode)
        af.addRow("", self.ui_font)
        af.addRow("Interface text size", self.ui_size)
        self.tabs.addTab(ap, "Appearance")

        # --- Library
        lib = QWidget()
        lv = QVBoxLayout(lib)
        lv.addWidget(QLabel("Music folders"))
        self.folder_list = QListWidget()
        self.folder_list.addItems(cfg["folders"])
        lv.addWidget(self.folder_list)
        brow = QHBoxLayout()
        add = QPushButton("Add folder...")
        add.clicked.connect(self.add_folder)
        rem = QPushButton("Remove selected")
        rem.clicked.connect(self.remove_folder)
        brow.addWidget(add)
        brow.addWidget(rem)
        brow.addStretch(1)
        lv.addLayout(brow)
        self.group = QCheckBox("Group featured artists under the main artist (Drake feat. X -> Drake)")
        self.group.setChecked(bool(cfg["group_featured"]))
        self.ignore_the = QCheckBox('Ignore "The" when sorting artists (The Beatles sorts under B)')
        self.ignore_the.setChecked(bool(cfg["ignore_the"]))
        lv.addWidget(self.group)
        lv.addWidget(self.ignore_the)
        self.split_collabs = QCheckBox("Put collaborations (A, B  /  A & B  /  A x B) under the first artist")
        self.split_collabs.setChecked(bool(cfg["split_collabs"]))
        lv.addWidget(self.split_collabs)
        lv.addWidget(QLabel("Never split these names (one per line), e.g. Simon & Garfunkel:"))
        self.keep_together = QPlainTextEdit("\n".join(cfg["keep_together"]))
        self.keep_together.setFixedHeight(64)
        lv.addWidget(self.keep_together)
        self.covers_auto = QCheckBox("Find missing album covers online automatically (iTunes / MusicBrainz)")
        self.covers_auto.setChecked(bool(cfg["covers_auto"]))
        self.covers_folder = QCheckBox("Also save found covers into the album folder as cover.jpg")
        self.covers_folder.setChecked(bool(cfg["covers_to_folder"]))
        lv.addWidget(self.covers_auto)
        lv.addWidget(self.covers_folder)
        self.tabs.addTab(lib, "Library")

        # --- Lyrics
        ly = QWidget()
        yf = QFormLayout(ly)
        self.ly_style = QComboBox()
        self.ly_style.addItems(["Album art", "Classic"])
        self.ly_style.setCurrentText(cfg["lyrics_style"])
        self.ly_align = QComboBox()
        self.ly_align.addItems(["Left", "Center"])
        self.ly_align.setCurrentText(cfg["lyrics_align"])
        self.ly_font_mode, self.ly_font = self.font_picker(cfg["lyrics_font"], "Same as app font")
        self.ly_weight = QComboBox()
        self.ly_weight.addItems(list(LYRIC_WEIGHTS))
        self.ly_weight.setCurrentText(cfg["lyrics_weight"])
        self.ly_size = QSpinBox()
        self.ly_size.setRange(10, 60)
        self.ly_size.setSuffix(" pt")
        self.ly_size.setValue(int(cfg["lyrics_size"]))
        self.ly_dim = QSpinBox()
        self.ly_dim.setRange(10, 90)
        self.ly_dim.setSuffix(" %")
        self.ly_dim.setValue(int(cfg["lyrics_dim"]))
        self.ly_online = QCheckBox("Look up missing lyrics online (sends artist + song title to lrclib.net)")
        self.ly_online.setChecked(bool(cfg["lyrics_online"]))
        self.ly_save = QCheckBox("Save lyrics I find next to the song file (.lrc / .txt)")
        self.ly_save.setChecked(bool(cfg["lyrics_save_lrc"]))
        yf.addRow("Style", self.ly_style)
        yf.addRow("Alignment", self.ly_align)
        yf.addRow("Font", self.ly_font_mode)
        yf.addRow("", self.ly_font)
        yf.addRow("Weight", self.ly_weight)
        yf.addRow("Text size", self.ly_size)
        yf.addRow("Brightness of other lines", self.ly_dim)
        self.ly_fade = QCheckBox("Fade the lyrics out at the top and bottom")
        self.ly_fade.setChecked(bool(cfg["lyrics_fade"]))
        self.ly_anim = QCheckBox("Smoothly light up each new line")
        self.ly_anim.setChecked(bool(cfg["lyrics_animate"]))
        yf.addRow(self.ly_fade)
        yf.addRow(self.ly_anim)
        self.ly_shadow = QCheckBox("Soft shadow behind the lyrics (easier to read on bright covers)")
        self.ly_shadow.setChecked(bool(cfg["lyrics_shadow"]))
        yf.addRow(self.ly_shadow)
        yf.addRow(self.ly_online)
        yf.addRow(self.ly_save)
        self.tabs.addTab(ly, "Lyrics")

        # --- Audio
        au = QWidget()
        uf = QFormLayout(au)
        self.engine = QComboBox()
        self.engine.addItems(["Automatic (VLC if installed)", "Qt (built-in)"])
        self.engine.setCurrentText(cfg["audio_engine"])
        using = getattr(parent, "engine_name", "Qt")
        problem = getattr(parent, "vlc_error", "") or ENGINE_ERROR
        info = QLabel(
            f"Now playing through: {'VLC' if using == 'VLC' else 'the built-in Qt engine'}.\n"
            f"VLC: {VLC_STATUS}." + (f"\nLast VLC problem: {problem}" if problem else "") + "\n"
            "VLC plays more formats and powers the equalizer. If VLC can't play, eozMP switches "
            "back to the built-in engine by itself."
        )
        info.setWordWrap(True)
        info.setObjectName("sub")
        eq_open = QPushButton("Open equalizer...")
        eq_open.clicked.connect(lambda: self.player.open_equalizer())
        uf.addRow("Audio engine", self.engine)
        self.viz_style = QComboBox()
        self.viz_style.addItems(["Off", "Bars", "Wave"])
        self.viz_style.setCurrentText(cfg["visualizer"])
        uf.addRow("Visualizer (lyrics page and fullscreen)", self.viz_style)
        viz_note = QLabel(
            f"Visualizer: {VIZ_STATUS}. It works with the built-in engine"
            + ("" if np is not None else "; install numpy (pip install numpy) for a real frequency spectrum")
            + ".")
        viz_note.setWordWrap(True)
        viz_note.setObjectName("sub")
        uf.addRow(viz_note)
        self.fs_motion = QCheckBox("Slowly moving background in the fullscreen player")
        self.fs_motion.setChecked(bool(cfg["fs_motion"]))
        uf.addRow(self.fs_motion)
        uf.addRow(info)
        uf.addRow(eq_open)
        self.tabs.addTab(au, "Audio")

        # --- Soulseek
        sl = QWidget()
        sf = QFormLayout(sl)
        self.url = QLineEdit(cfg["slskd_url"])
        self.key = QLineEdit(cfg["slskd_key"])
        self.dl = QLineEdit(cfg["downloads_dir"])
        browse = QPushButton("Browse...")
        browse.clicked.connect(self.pick)
        drow = QHBoxLayout()
        drow.addWidget(self.dl, 1)
        drow.addWidget(browse)
        self.soul_view = QComboBox()
        self.soul_view.addItems(["Albums", "Files"])
        self.soul_view.setCurrentText(cfg["soul_view"])
        self.soul_quality = QComboBox()
        self.soul_quality.addItems(FORMAT_OPTIONS)
        self.soul_quality.setCurrentText(cfg["soul_quality"])
        self.soul_free = QCheckBox("Only show users with a free upload slot")
        self.soul_free.setChecked(bool(cfg["soul_free_only"]))
        test = QPushButton("Test connection")
        test.clicked.connect(self.test_connection)
        self.test_label = QLabel("")
        trow = QHBoxLayout()
        trow.addWidget(test)
        trow.addWidget(self.test_label, 1)
        sf.addRow("slskd address", self.url)
        sf.addRow("slskd API key", self.key)
        sf.addRow("slskd downloads folder", drow)
        sf.addRow("Search results view", self.soul_view)
        sf.addRow("Default quality filter", self.soul_quality)
        sf.addRow(self.soul_free)
        self.organize = QCheckBox("Organize finished downloads into Artist / Album folders")
        self.organize.setChecked(bool(cfg["organize_downloads"]))
        self.organize_root = QLineEdit(cfg["organize_root"])
        self.organize_root.setPlaceholderText("Your first music folder")
        org_browse = QPushButton("Browse...")
        org_browse.clicked.connect(self.pick_organize_root)
        orow = QHBoxLayout()
        orow.addWidget(self.organize_root, 1)
        orow.addWidget(org_browse)
        sf.addRow(self.organize)
        sf.addRow("Organize into", orow)
        sf.addRow(trow)
        self.tabs.addTab(sl, "Soulseek")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(
            lambda: self.player.apply_prefs(self.values()))
        layout.addWidget(buttons)

        if tab:
            for i in range(self.tabs.count()):
                if self.tabs.tabText(i) == tab:
                    self.tabs.setCurrentIndex(i)

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose your music folder")
        if folder:
            existing = [self.folder_list.item(i).text() for i in range(self.folder_list.count())]
            if folder not in existing:
                self.folder_list.addItem(folder)

    def remove_folder(self):
        for item in self.folder_list.selectedItems():
            self.folder_list.takeItem(self.folder_list.row(item))

    def pick(self):
        folder = QFileDialog.getExistingDirectory(self, "slskd downloads folder")
        if folder:
            self.dl.setText(folder)

    def set_test_text(self, text):
        try:
            self.test_label.setText(text)
        except RuntimeError:
            pass

    def test_connection(self):
        client = Slskd(self.url.text().strip(), self.key.text().strip())
        self.test_label.setText("Testing...")
        w = Worker(lambda: client.call("GET", "/searches", timeout=8))
        w.ok.connect(lambda _r: self.set_test_text("Connected to slskd."))
        w.fail.connect(lambda m: self.set_test_text(m))
        self.player.keep(w)

    def values(self):
        return {
            "resume": self.resume.isChecked(),
            "autoplay_next": self.autoplay.isChecked(),
            "show_lyric_line": self.show_line.isChecked(),
            "theme": self.theme.currentText(),
            "accent": self.accent.currentText(),
            "corner_style": self.corners.currentText(),
            "density": self.density.currentText(),
            "cover_size": self.cover_size.currentText(),
            "album_list_style": self.list_style.currentText(),
            "page_fade": self.page_fade.isChecked(),
            "ui_font": self.font_value(self.ui_font_mode, self.ui_font),
            "ui_font_size": self.ui_size.value(),
            "folders": [self.folder_list.item(i).text() for i in range(self.folder_list.count())],
            "group_featured": self.group.isChecked(),
            "ignore_the": self.ignore_the.isChecked(),
            "lyrics_style": self.ly_style.currentText(),
            "lyrics_align": self.ly_align.currentText(),
            "lyrics_font": self.font_value(self.ly_font_mode, self.ly_font),
            "lyrics_fade": self.ly_fade.isChecked(),
            "lyrics_animate": self.ly_anim.isChecked(),
            "lyrics_shadow": self.ly_shadow.isChecked(),
            "fs_motion": self.fs_motion.isChecked(),
            "visualizer": self.viz_style.currentText(),
            "split_collabs": self.split_collabs.isChecked(),
            "keep_together": [x.strip() for x in self.keep_together.toPlainText().splitlines() if x.strip()],
            "lyrics_weight": self.ly_weight.currentText(),
            "lyrics_size": self.ly_size.value(),
            "lyrics_dim": self.ly_dim.value(),
            "lyrics_online": self.ly_online.isChecked(),
            "lyrics_save_lrc": self.ly_save.isChecked(),
            "slskd_url": self.url.text().strip(),
            "slskd_key": self.key.text().strip(),
            "downloads_dir": self.dl.text().strip(),
            "soul_view": self.soul_view.currentText(),
            "soul_quality": self.soul_quality.currentText(),
            "soul_free_only": self.soul_free.isChecked(),
            "organize_downloads": self.organize.isChecked(),
            "organize_root": self.organize_root.text().strip(),
            "covers_auto": self.covers_auto.isChecked(),
            "covers_to_folder": self.covers_folder.isChecked(),
            "audio_engine": self.engine.currentText(),
            "accent_custom": self.custom_value(),
            "mini_opacity": self.mini_opacity.value(),
            "close_to_tray": self.close_tray.isChecked(),
            "media_keys": self.media_keys.isChecked(),
        }

    @staticmethod
    def font_picker(current, default_label):
        mode = QComboBox()
        mode.addItems([default_label, "System font", "Custom"])
        picker = QFontComboBox()
        if current == SYSTEM_FONT_TAG:
            mode.setCurrentText("System font")
        elif current:
            mode.setCurrentText("Custom")
            picker.setCurrentFont(QFont(current))
        picker.setEnabled(mode.currentText() == "Custom")
        mode.currentTextChanged.connect(lambda t: picker.setEnabled(t == "Custom"))
        return mode, picker

    @staticmethod
    def font_value(mode, picker):
        if mode.currentText() == "System font":
            return SYSTEM_FONT_TAG
        if mode.currentText() == "Custom":
            return picker.currentFont().family()
        return ""

    def pick_organize_root(self):
        folder = QFileDialog.getExistingDirectory(self, "Organize downloads into...")
        if folder:
            self.organize_root.setText(folder)

    def custom_value(self):
        c = QColor(self.custom_hex.text().strip())
        return c.name() if c.isValid() else "#4C8DFF"

    def pick_accent(self):
        start = QColor(self.custom_hex.text().strip())
        c = QColorDialog.getColor(start if start.isValid() else QColor("#4C8DFF"), self, "Pick an accent color")
        if c.isValid():
            self.custom_hex.setText(c.name())
            self.accent.setCurrentText(CUSTOM_ACCENT)


# ---------------------------------------------------------------- stats, favorites, covers, colours
STATS_FILE = Path.home() / ".simple_music_player_stats.json"
COVERS_DIR = Path.home() / ".simple_music_player_covers"
ALBUM_ART_ACCENT = "From album art"
SMART_FAV = "♥ Favorites"
SMART_MOST = "Most played"
SMART_ADDED = "Recently added"
SMART_RECENT = "Recently played"
SMART_PLAYLISTS = (SMART_FAV, SMART_MOST, SMART_ADDED, SMART_RECENT)


def load_stats():
    try:
        data = json.loads(STATS_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}
    data.setdefault("favorites", [])      # song paths, oldest first
    data.setdefault("plays", {})          # path -> {"count", "last", "seconds"}
    data.setdefault("events", [])         # [timestamp, path, seconds listened]
    data.setdefault("cover_misses", {})   # "artist|album" -> when we last failed
    return data


def save_stats(stats):
    try:
        stats["events"] = stats["events"][-50000:]
        STATS_FILE.write_text(json.dumps(stats), encoding="utf-8")
    except Exception:
        pass


def record_play(stats, path, seconds, now=None):
    now = now or time.time()
    entry = stats["plays"].setdefault(path, {"count": 0, "last": 0, "seconds": 0})
    entry["count"] += 1
    entry["last"] = now
    entry["seconds"] = round(entry["seconds"] + seconds, 1)
    stats["events"].append([round(now), path, round(seconds, 1)])


def summarize_stats(stats, track_info, since=0):
    """track_info: path -> (title, artist, album) for songs still in the library."""
    songs, artists, albums = Counter(), Counter(), Counter()
    total, plays, days = 0.0, 0, set()
    for ts, path, secs in stats["events"]:
        if ts < since:
            continue
        total += secs
        plays += 1
        days.add(time.strftime("%Y-%m-%d", time.localtime(ts)))
        info = track_info.get(path)
        if info:
            _title, artist, album = info
            songs[path] += 1
            artists[artist] += 1
            albums[(artist, album)] += 1
    return {
        "seconds": total, "plays": plays, "days": len(days), "distinct": len(songs),
        "songs": songs.most_common(15), "artists": artists.most_common(15),
        "albums": albums.most_common(15),
    }


def pick_shuffle(paths, played, avoid=None):
    """Random position in paths, without repeats until everything has played once."""
    left = [i for i, p in enumerate(paths) if p not in played and p != avoid]
    if not left:
        played.clear()
        left = [i for i, p in enumerate(paths) if p != avoid] or list(range(len(paths)))
    return random.choice(left)


def dominant_color(pixels):
    """pixels: iterable of (r, g, b). A lively '#rrggbb' from the art, or None for grey art."""
    buckets = {}
    for r, g, b in pixels:
        h, sat, val = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        if sat < 0.25 or val < 0.2:
            continue
        acc = buckets.setdefault(int(h * 12) % 12, [0.0, 0.0, 0.0, 0.0])
        w = sat * val
        acc[0] += r * w
        acc[1] += g * w
        acc[2] += b * w
        acc[3] += w
    if not buckets:
        return None
    r, g, b, w = max(buckets.values(), key=lambda a: a[3])
    h, sat, val = colorsys.rgb_to_hsv(r / w / 255, g / w / 255, b / w / 255)
    sat = min(max(sat, 0.45), 0.85)
    val = min(max(val, 0.62), 0.88)
    r, g, b = colorsys.hsv_to_rgb(h, sat, val)
    return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))


def accent_from_pixmap(pix):
    img = pix.toImage().scaled(
        32, 32, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
    pixels = []
    for y in range(img.height()):
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            pixels.append((c.red(), c.green(), c.blue()))
    return dominant_color(pixels)


def http_bytes(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "eozMP/1.0 (personal music player)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _norm(text):
    return re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip()


def looks_like_image(data):
    return bool(data) and (data[:3] == b"\xff\xd8\xff" or data[:8] == b"\x89PNG\r\n\x1a\n")


def fetch_cover_bytes(artist, album):
    """Album art from Apple's iTunes search, falling back to MusicBrainz + Cover Art Archive."""
    a, b = _norm(artist), _norm(album)
    if not a or not b:
        return None
    try:
        url = "https://itunes.apple.com/search?" + urllib.parse.urlencode(
            {"term": f"{artist} {album}", "entity": "album", "limit": 10})
        for r in http_json(url).get("results", []):
            name = _norm(r.get("collectionName", ""))
            if a in _norm(r.get("artistName", "")) and (b in name or (name and name in b)):
                art = r.get("artworkUrl100", "")
                if art:
                    data = http_bytes(art.replace("100x100bb", "600x600bb"))
                    if looks_like_image(data):
                        return data
    except Exception:
        pass
    try:
        query = f'releasegroup:"{album}" AND artist:"{artist}"'
        data = http_json("https://musicbrainz.org/ws/2/release-group/?" + urllib.parse.urlencode(
            {"query": query, "fmt": "json", "limit": 5}))
        for rg in data.get("release-groups", []):
            if int(rg.get("score", 0)) < 80:
                continue
            try:
                img = http_bytes(f"https://coverartarchive.org/release-group/{rg['id']}/front-500")
                if looks_like_image(img):
                    return img
            except Exception:
                continue
    except Exception:
        pass
    return None


def cover_cache_file(artist, album):
    key = hashlib.sha1(f"{artist}|{album}".lower().encode("utf-8", "replace")).hexdigest()[:24]
    return COVERS_DIR / f"{key}.img"


def read_cached_cover(artist, album):
    try:
        return cover_cache_file(artist, album).read_bytes()
    except OSError:
        return None


def download_cover(artist, album, folder=None):
    """Runs in a background thread. Saves the cover and returns True if one was found."""
    data = fetch_cover_bytes(artist, album)
    if not data:
        return False
    COVERS_DIR.mkdir(exist_ok=True)
    cover_cache_file(artist, album).write_bytes(data)
    if folder:
        ext = ".png" if data[:4] == b"\x89PNG" else ".jpg"
        target = os.path.join(folder, "cover" + ext)
        if not os.path.exists(target):
            try:
                with open(target, "wb") as f:
                    f.write(data)
            except OSError:
                pass
    return True


class CoverBatch(QThread):
    """Library > Find missing covers online: goes through every album slowly in the background."""
    progress = pyqtSignal(str)
    found = pyqtSignal(object)
    done = pyqtSignal(int)

    def __init__(self, jobs, to_folder):
        super().__init__()
        self.jobs = jobs            # [(key, artist, album, first song path)]
        self.to_folder = to_folder
        self.missed = []
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        got = 0
        total = len(self.jobs)
        for i, (key, artist, album, first) in enumerate(self.jobs):
            if self._stop:
                break
            if embedded_cover(first) or folder_cover(first) or read_cached_cover(artist, album):
                continue
            self.progress.emit(f"Finding covers {i + 1}/{total}: {artist} - {album}")
            try:
                ok = download_cover(artist, album, os.path.dirname(first) if self.to_folder else None)
            except Exception:
                ok = False
            if ok:
                got += 1
                self.found.emit(key)
            else:
                self.missed.append(f"{artist}|{album}".lower())
            for _ in range(30):   # be polite to the free services: ~3 s per album
                if self._stop:
                    break
                time.sleep(0.1)
        self.done.emit(got)


# ---------------------------------------------------------------- crisp white icons (no emoji)
_ICON_CACHE = {}


def icon_pixmap(kind, color, size=48):
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    col = QColor(color)
    n = size
    path = QPainterPath()
    path.setFillRule(Qt.FillRule.WindingFill)

    def tri(points):
        path.moveTo(points[0][0] * n, points[0][1] * n)
        for x, y in points[1:]:
            path.lineTo(x * n, y * n)
        path.closeSubpath()

    pen = QPen(col)
    pen.setWidthF(n * 0.075)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    if kind == "play":
        tri([(0.33, 0.2), (0.33, 0.8), (0.8, 0.5)])
    elif kind == "pause":
        path.addRoundedRect(n * 0.27, n * 0.2, n * 0.16, n * 0.6, n * 0.04, n * 0.04)
        path.addRoundedRect(n * 0.57, n * 0.2, n * 0.16, n * 0.6, n * 0.04, n * 0.04)
    elif kind == "next":
        tri([(0.2, 0.24), (0.2, 0.76), (0.62, 0.5)])
        path.addRoundedRect(n * 0.66, n * 0.24, n * 0.1, n * 0.52, n * 0.03, n * 0.03)
    elif kind == "prev":
        tri([(0.8, 0.24), (0.8, 0.76), (0.38, 0.5)])
        path.addRoundedRect(n * 0.24, n * 0.24, n * 0.1, n * 0.52, n * 0.03, n * 0.03)
    elif kind.startswith("vol"):
        path.addRect(n * 0.12, n * 0.38, n * 0.16, n * 0.24)
        tri([(0.28, 0.38), (0.48, 0.2), (0.48, 0.8), (0.28, 0.62)])
    elif kind in ("heart", "heart_fill"):
        path.moveTo(n * 0.5, n * 0.84)
        path.cubicTo(n * 0.06, n * 0.56, n * 0.14, n * 0.12, n * 0.5, n * 0.32)
        path.cubicTo(n * 0.86, n * 0.12, n * 0.94, n * 0.56, n * 0.5, n * 0.84)
        path.closeSubpath()
    if kind in ("shuffle", "repeat", "repeat_one", "back", "forward", "close", "minimize", "fullscreen",
                "search", "download"):
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        if kind == "shuffle":
            for y0, y1 in ((0.32, 0.68), (0.68, 0.32)):
                line = QPainterPath()
                line.moveTo(n * 0.14, n * y0)
                line.lineTo(n * 0.32, n * y0)
                line.cubicTo(n * 0.5, n * y0, n * 0.5, n * y1, n * 0.68, n * y1)
                line.lineTo(n * 0.82, n * y1)
                p.drawPath(line)
                head = QPainterPath()
                head.moveTo(n * 0.72, n * (y1 - 0.09))
                head.lineTo(n * 0.82, n * y1)
                head.lineTo(n * 0.72, n * (y1 + 0.09))
                p.drawPath(head)
        elif kind in ("repeat", "repeat_one"):
            p.drawRoundedRect(QRectF(n * 0.16, n * 0.3, n * 0.68, n * 0.4), n * 0.14, n * 0.14)
            for pts in (((0.52, 0.21), (0.62, 0.3), (0.52, 0.39)), ((0.48, 0.61), (0.38, 0.7), (0.48, 0.79))):
                head = QPainterPath()
                head.moveTo(n * pts[0][0], n * pts[0][1])
                head.lineTo(n * pts[1][0], n * pts[1][1])
                head.lineTo(n * pts[2][0], n * pts[2][1])
                p.drawPath(head)
            if kind == "repeat_one":
                f = QFont()
                f.setPixelSize(int(n * 0.3))
                f.setWeight(QFont.Weight.Bold)
                p.setFont(f)
                p.drawText(QRectF(0, 0, n, n), Qt.AlignmentFlag.AlignCenter, "1")
        elif kind in ("back", "forward"):
            line = QPainterPath()
            if kind == "back":
                line.moveTo(n * 0.6, n * 0.22)
                line.lineTo(n * 0.34, n * 0.5)
                line.lineTo(n * 0.6, n * 0.78)
            else:
                line.moveTo(n * 0.4, n * 0.22)
                line.lineTo(n * 0.66, n * 0.5)
                line.lineTo(n * 0.4, n * 0.78)
            p.drawPath(line)
        elif kind == "close":
            for a, b in (((0.28, 0.28), (0.72, 0.72)), ((0.72, 0.28), (0.28, 0.72))):
                line = QPainterPath()
                line.moveTo(n * a[0], n * a[1])
                line.lineTo(n * b[0], n * b[1])
                p.drawPath(line)
        elif kind == "minimize":
            line = QPainterPath()
            line.moveTo(n * 0.26, n * 0.5)
            line.lineTo(n * 0.74, n * 0.5)
            p.drawPath(line)
        elif kind == "fullscreen":
            for pts in (((0.18, 0.4), (0.18, 0.18), (0.4, 0.18)), ((0.6, 0.18), (0.82, 0.18), (0.82, 0.4)),
                        ((0.82, 0.6), (0.82, 0.82), (0.6, 0.82)), ((0.4, 0.82), (0.18, 0.82), (0.18, 0.6))):
                line = QPainterPath()
                line.moveTo(n * pts[0][0], n * pts[0][1])
                for x, y in pts[1:]:
                    line.lineTo(n * x, n * y)
                p.drawPath(line)
        elif kind == "search":
            p.drawEllipse(QRectF(n * 0.16, n * 0.16, n * 0.46, n * 0.46))
            line = QPainterPath()
            line.moveTo(n * 0.56, n * 0.56)
            line.lineTo(n * 0.84, n * 0.84)
            p.drawPath(line)
        elif kind == "download":
            for pts in (((0.5, 0.14), (0.5, 0.6)), ((0.3, 0.42), (0.5, 0.62), (0.7, 0.42)),
                        ((0.18, 0.64), (0.18, 0.82), (0.82, 0.82), (0.82, 0.64))):
                line = QPainterPath()
                line.moveTo(n * pts[0][0], n * pts[0][1])
                for x, y in pts[1:]:
                    line.lineTo(n * x, n * y)
                p.drawPath(line)
        p.end()
        return pm
    if kind == "heart":
        p.strokePath(path, pen)
    elif kind in ("mini", "expand"):
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(int(n * 0.12), int(n * 0.2), int(n * 0.76), int(n * 0.6), n * 0.08, n * 0.08)
        if kind == "mini":
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(col)
            p.drawRoundedRect(int(n * 0.46), int(n * 0.46), int(n * 0.32), int(n * 0.24), n * 0.04, n * 0.04)
        else:
            p.drawLine(int(n * 0.4), int(n * 0.6), int(n * 0.66), int(n * 0.34))
            p.drawLine(int(n * 0.5), int(n * 0.34), int(n * 0.66), int(n * 0.34))
            p.drawLine(int(n * 0.66), int(n * 0.34), int(n * 0.66), int(n * 0.5))
    else:
        p.fillPath(path, col)
    if kind.startswith("vol"):
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        cx, cy = int(n * 0.5), int(n * 0.5)
        if kind == "vol_mute":
            p.drawLine(int(n * 0.62), int(n * 0.38), int(n * 0.86), int(n * 0.62))
            p.drawLine(int(n * 0.62), int(n * 0.62), int(n * 0.86), int(n * 0.38))
        else:
            radii = (0.16, 0.3) if kind == "vol_high" else (0.16,)
            for r in radii:
                rr = int(n * r)
                p.drawArc(cx - rr, cy - rr, 2 * rr, 2 * rr, -50 * 16, 100 * 16)
    p.end()
    return pm


def badge_icon(kind, color, count, accent, on_accent):
    """Icon with a small round number in the corner (e.g. active downloads)."""
    pm = icon_pixmap(kind, color)
    if count:
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(48 - 24, 0, 24, 24)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(accent))
        p.drawEllipse(rect)
        f = QFont()
        f.setPixelSize(14)
        f.setWeight(QFont.Weight.Bold)
        p.setFont(f)
        p.setPen(QColor(on_accent))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(count) if count < 100 else "99")
        p.end()
    return QIcon(pm)


def make_icon(kind, color):
    key = (kind, str(color))
    if key not in _ICON_CACHE:
        _ICON_CACHE[key] = QIcon(icon_pixmap(kind, color))
    return _ICON_CACHE[key]


# ---------------------------------------------------------------- optional VLC engine (equalizer)
try:
    import vlc   # needs VLC installed + "pip install python-vlc"
    try:
        _ver = vlc.libvlc_get_version()
        VLC_STATUS = "Found VLC " + (_ver.decode() if isinstance(_ver, bytes) else str(_ver)).split()[0]
    except Exception:
        VLC_STATUS = "Found VLC"
except ImportError:
    vlc = None
    VLC_STATUS = "python-vlc isn't installed (run: pip install python-vlc)"
except Exception as _vlc_err:
    vlc = None
    VLC_STATUS = (f"VLC couldn't be loaded ({_vlc_err}). Is VLC installed? "
                  "64-bit Python needs the 64-bit VLC.")
ENGINE_ERROR = ""


class VlcAudio:
    """Looks like QAudioOutput, so the rest of the app doesn't care which engine plays."""

    def __init__(self, engine):
        self.engine = engine
        self._volume = 1.0
        self._muted = False

    def setVolume(self, v):
        self._volume = float(v)
        self.engine.mp.audio_set_volume(int(round(self._volume * 100)))

    def volume(self):
        return self._volume

    def isMuted(self):
        return self._muted

    def setMuted(self, muted):
        self._muted = bool(muted)
        self.engine.mp.audio_set_mute(self._muted)


class VlcEngine(QObject):
    """Wraps VLC so it behaves like QMediaPlayer for the rest of eozMP."""
    positionChanged = pyqtSignal(int)
    durationChanged = pyqtSignal(int)
    mediaStatusChanged = pyqtSignal(object)
    playbackStateChanged = pyqtSignal(object)
    errorOccurred = pyqtSignal(object, str)
    failed = pyqtSignal(str)      # VLC can't play at all -> eozMP falls back to the built-in engine

    def __init__(self):
        super().__init__()
        self.instance = vlc.Instance("--no-video", "--quiet")
        if self.instance is None:
            raise RuntimeError("VLC could not start (its plugins were not found)")
        self.mp = self.instance.media_player_new()
        if self.mp is None:
            raise RuntimeError("VLC could not create a player")
        self.audio = VlcAudio(self)
        self._source = QUrl()
        self._media = None
        self._state = QMediaPlayer.PlaybackState.StoppedState
        self._duration = 0
        self._pending = None
        self._ended = False
        self._fresh = False
        self._play_at = None
        self._ever_played = False
        self.eq = None
        self._eq_on = False
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self._poll)
        self.timer.start()

    def setAudioOutput(self, _audio):
        pass

    def source(self):
        return self._source

    def setSource(self, url):
        self._source = QUrl(url)
        try:
            self.mp.stop()
        except Exception:
            pass
        path = os.path.normpath(self._source.toLocalFile())
        self._media = self.instance.media_new_path(path)
        self.mp.set_media(self._media)
        self._duration, self._pending, self._ended, self._play_at = 0, None, False, None
        self._set_state(QMediaPlayer.PlaybackState.StoppedState)
        self.mediaStatusChanged.emit(QMediaPlayer.MediaStatus.LoadedMedia)

    def play(self):
        if self._source.isEmpty():
            return
        if self._ended:
            self.mp.stop()
            self._ended = False
        if self.mp.play() == -1:
            self._fail("VLC refused to start playback")
            return
        self._fresh = True
        self._play_at = time.time()
        self._set_state(QMediaPlayer.PlaybackState.PlayingState)

    def pause(self):
        self._play_at = None
        if self._state == QMediaPlayer.PlaybackState.PlayingState:
            self.mp.set_pause(1)
            self._set_state(QMediaPlayer.PlaybackState.PausedState)

    def stop(self):
        self._play_at = None
        self.mp.stop()
        self._set_state(QMediaPlayer.PlaybackState.StoppedState)
        self.positionChanged.emit(0)

    def shutdown(self):
        self.timer.stop()
        try:
            self.mp.stop()
        except Exception:
            pass

    def position(self):
        if self._pending is not None:
            return self._pending
        t = self.mp.get_time()
        return max(0, t or 0)

    def setPosition(self, ms):
        if self.mp.get_state() in (vlc.State.Playing, vlc.State.Paused):
            self.mp.set_time(int(ms))
        else:
            self._pending = int(ms)
        self.positionChanged.emit(int(ms))

    def playbackState(self):
        return self._state

    def set_equalizer(self, enabled, preamp, bands):
        self._eq_on = bool(enabled)
        if not enabled:
            self.mp.set_equalizer(None)
            return
        eq = vlc.AudioEqualizer()
        eq.set_preamp(float(preamp))
        for i, amp in enumerate(bands):
            eq.set_amp_at_index(float(amp), i)
        self.mp.set_equalizer(eq)
        self.eq = eq   # keep it alive

    def _set_state(self, state):
        if state != self._state:
            self._state = state
            self.playbackStateChanged.emit(state)

    def _fail(self, why):
        self._play_at = None
        self._ended = True
        self._set_state(QMediaPlayer.PlaybackState.StoppedState)
        if not self._ever_played:
            self.failed.emit(why)              # VLC itself doesn't work here
        else:
            self.errorOccurred.emit(None, why)  # just this one file

    def _poll(self):
        if self._source.isEmpty():
            return
        st = self.mp.get_state()
        if st == vlc.State.Playing:
            self._play_at = None
            self._ever_played = True
            if self._fresh:   # VLC only accepts volume once audio is running
                self._fresh = False
                self.mp.audio_set_mute(self.audio._muted)
                self.mp.audio_set_volume(int(round(self.audio._volume * 100)))
            if self._pending is not None:
                self.mp.set_time(self._pending)
                self._pending = None
            if not self._duration:
                d = self.mp.get_length()
                if d and d > 0:
                    self._duration = d
                    self.durationChanged.emit(d)
            now = max(0, self.mp.get_time() or 0)
            self.positionChanged.emit(now)
        elif st == vlc.State.Ended and not self._ended:
            self._ended = True
            self._set_state(QMediaPlayer.PlaybackState.StoppedState)
            self.mediaStatusChanged.emit(QMediaPlayer.MediaStatus.EndOfMedia)
        elif st == vlc.State.Error and not self._ended:
            self._fail("VLC could not play this file")
        elif self._play_at is not None and time.time() - self._play_at > 6:
            self._fail(f"VLC didn't start playing (stuck at {st})")


def vlc_eq_info():
    """(band frequencies, [(preset name, preamp, [band amps])])"""
    n = vlc.libvlc_audio_equalizer_get_band_count()
    freqs = [vlc.libvlc_audio_equalizer_get_band_frequency(i) for i in range(n)]
    presets = []
    for i in range(vlc.libvlc_audio_equalizer_get_preset_count()):
        name = vlc.libvlc_audio_equalizer_get_preset_name(i)
        if isinstance(name, bytes):
            name = name.decode("utf-8", "replace")
        eq = vlc.libvlc_audio_equalizer_new_from_preset(i)
        try:
            pre = eq.get_preamp()
            amps = [eq.get_amp_at_index(b) for b in range(n)]
        except AttributeError:
            pre = vlc.libvlc_audio_equalizer_get_preamp(eq)
            amps = [vlc.libvlc_audio_equalizer_get_amp_at_index(eq, b) for b in range(n)]
        presets.append((name, pre, amps))
    return freqs, presets


def create_engine(choice):
    """Returns (player, audio output, engine name)."""
    global ENGINE_ERROR
    if not str(choice).startswith("Qt") and vlc is not None:
        try:
            engine = VlcEngine()
            ENGINE_ERROR = ""
            return engine, engine.audio, "VLC"
        except Exception as e:
            ENGINE_ERROR = f"VLC failed to start: {e}"
    audio = QAudioOutput()
    player = QMediaPlayer()
    player.setAudioOutput(audio)
    return player, audio, "Qt"


class EqualizerDialog(QDialog):
    def __init__(self, main):
        super().__init__(main)
        self.main = main
        self._loading = False
        self.setWindowTitle("Equalizer")
        lay = QVBoxLayout(self)
        if main.engine_name != "VLC" or vlc is None:
            reason = main.vlc_error or ENGINE_ERROR or VLC_STATUS
            note = QLabel(
                "The equalizer needs the VLC audio engine.\n\n"
                f"Status: {reason}\n\n"
                "To set it up: install VLC (free) from videolan.org, then in a command window run\n"
                "pip install python-vlc  and restart eozMP (rebuild the exe if you use it).")
            note.setWordWrap(True)
            lay.addWidget(note)
            row = QHBoxLayout()
            row.addStretch(1)
            if vlc is not None:
                use = QPushButton("Use VLC now")
                use.setObjectName("primary")
                use.clicked.connect(self.use_vlc)
                row.addWidget(use)
            ok = QPushButton("Close")
            ok.clicked.connect(self.accept)
            row.addWidget(ok)
            lay.addLayout(row)
            return
        self.freqs, self.presets = vlc_eq_info()
        cfg = main.cfg
        bands = [float(x) for x in cfg["eq_bands"]] + [0.0] * len(self.freqs)
        top = QHBoxLayout()
        self.enable = QCheckBox("Equalizer on")
        self.enable.setChecked(bool(cfg["eq_enabled"]))
        self.preset = QComboBox()
        self.preset.addItem("Custom")
        names = [pr[0] for pr in self.presets]
        self.preset.addItems(names)
        self.preset.setCurrentText(cfg["eq_preset"] if cfg["eq_preset"] in names else "Custom")
        reset = QPushButton("Reset")
        top.addWidget(self.enable)
        top.addStretch(1)
        top.addWidget(QLabel("Preset"))
        top.addWidget(self.preset)
        top.addWidget(reset)
        lay.addLayout(top)
        grid = QHBoxLayout()
        self.pre = self._column(grid, "Preamp", float(cfg["eq_preamp"]))
        grid.addSpacing(14)
        self.sliders = [self._column(grid, self._fmt(f), bands[i]) for i, f in enumerate(self.freqs)]
        lay.addLayout(grid)
        done = QPushButton("Done")
        done.clicked.connect(self.accept)
        lay.addWidget(done, 0, Qt.AlignmentFlag.AlignRight)
        self.enable.toggled.connect(lambda _on: self.changed())
        self.preset.currentIndexChanged.connect(self.load_preset)
        reset.clicked.connect(self.reset)

    def use_vlc(self):
        self.main.cfg["audio_engine"] = "Automatic (VLC if installed)"
        save_config(self.main.cfg)
        self.main.switch_engine(self.main.cfg["audio_engine"])
        self.accept()
        if self.main.engine_name == "VLC":
            QTimer.singleShot(150, self.main.open_equalizer)

    @staticmethod
    def _fmt(freq):
        return f"{freq / 1000:g}K" if freq >= 1000 else f"{freq:g}"

    def _column(self, grid, label, value):
        col = QVBoxLayout()
        val = QLabel(f"{value:+.1f}")
        val.setObjectName("sub")
        val.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        slider = QSlider(Qt.Orientation.Vertical)
        slider.setRange(-200, 200)
        slider.setValue(int(round(value * 10)))
        slider.setMinimumHeight(180)
        name = QLabel(label)
        name.setObjectName("sub")
        name.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        col.addWidget(val)
        col.addWidget(slider, 1, Qt.AlignmentFlag.AlignHCenter)
        col.addWidget(name)
        grid.addLayout(col)
        slider.valueChanged.connect(lambda v, lab=val: self._moved(lab, v))
        return slider

    def _moved(self, label, v):
        label.setText(f"{v / 10:+.1f}")
        self.changed(custom=True)

    def load_preset(self, idx):
        if idx <= 0:
            return
        _name, pre, amps = self.presets[idx - 1]
        self._loading = True
        self.pre.setValue(int(round(pre * 10)))
        for slider, amp in zip(self.sliders, amps):
            slider.setValue(int(round(amp * 10)))
        self._loading = False
        self.enable.setChecked(True)
        self.changed()

    def reset(self):
        self._loading = True
        self.pre.setValue(0)
        for slider in self.sliders:
            slider.setValue(0)
        self._loading = False
        self.preset.blockSignals(True)
        self.preset.setCurrentIndex(0)
        self.preset.blockSignals(False)
        self.changed()

    def changed(self, custom=False):
        if self._loading:
            return
        if custom and self.preset.currentIndex() != 0:
            self.preset.blockSignals(True)
            self.preset.setCurrentIndex(0)
            self.preset.blockSignals(False)
        cfg = self.main.cfg
        cfg["eq_enabled"] = self.enable.isChecked()
        cfg["eq_preamp"] = self.pre.value() / 10
        cfg["eq_bands"] = [sl.value() / 10 for sl in self.sliders]
        cfg["eq_preset"] = self.preset.currentText()
        save_config(cfg)
        self.main.apply_equalizer()


# ---------------------------------------------------------------- media keys, discography
CUSTOM_ACCENT = "Custom"
MEDIA_KEYS = {9100: 0xB3, 9101: 0xB0, 9102: 0xB1, 9103: 0xB2}   # hotkey id -> play/pause, next, prev, stop


class MediaKeyFilter(QAbstractNativeEventFilter):
    """Catches the keyboard media keys anywhere in Windows (via RegisterHotKey)."""

    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def nativeEventFilter(self, event_type, message):
        try:
            if bytes(event_type) in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
                import ctypes.wintypes
                msg = ctypes.wintypes.MSG.from_address(int(message))
                if msg.message == 0x0312 and int(msg.wParam) in MEDIA_KEYS:   # WM_HOTKEY
                    hid = int(msg.wParam)
                    QTimer.singleShot(0, lambda: self.callback(hid))
                    return True, 0
        except Exception:
            pass
        return False, 0


DISC_RE = re.compile(r"^(cd|disc|disk)\s*\d+$")
QUALITY_RE = re.compile(
    r"\b(flac|mp3|aac|m4a|ogg|alac|320|256|192|v0|v2|kbps|kbit|24bit|16bit|24 bit|16 bit|"
    r"web|webrip|cd|cdrip|vinyl|lossless|hi res|hires|remaster|remastered)\b")


def album_key(name, artist):
    """'Artist - Album (2009) [FLAC]' -> 'album', so different uploads of one album match."""
    n = _norm(name)
    a = _norm(artist)
    if a:
        n = n.replace(a, " ")
    n = re.sub(r"\b(19|20)\d{2}\b", " ", n)
    n = QUALITY_RE.sub(" ", n)
    return re.sub(r"\s+", " ", n).strip()


def pick_discography(rows, artist):
    """From raw Soulseek results, pick the best folder for every album by this artist."""
    a = _norm(artist)
    best = {}
    for group in group_by_folder(rows):
        if len(group) < 3:
            continue
        _, folder = split_path(group[0]["filename"])
        parts = [x for x in folder.split("/") if x]
        if not parts:
            continue
        if a and a not in _norm(folder) and not any(a in _norm(f["filename"]) for f in group):
            continue
        name = parts[-1]
        disc = ""
        if DISC_RE.match(_norm(name)) and len(parts) > 1:
            disc, name = _norm(parts[-1]), parts[-2]
        key = album_key(name, artist)
        if not key:
            continue
        key = f"{key} {disc}".strip()
        lossless = sum(1 for f in group if f["ext"] in LOSSLESS_EXTS) * 2 > len(group)
        score = (group[0]["free"], len(group), lossless, group[0]["speed"])
        if key not in best or score > best[key]["score"]:
            best[key] = {"score": score, "key": album_key(name, artist),
                         "name": name + (f" ({parts[-1]})" if disc else ""), "files": group}
    return sorted(best.values(), key=lambda d: d["name"].lower())


class DiscographyDialog(QDialog):
    def __init__(self, parent, artist, picks, owned):
        super().__init__(parent)
        self.setWindowTitle(f"Discography: {artist}")
        self.resize(760, 500)
        self.picks = picks
        lay = QVBoxLayout(self)
        have = sum(1 for pk in picks if pk["key"] in owned)
        info = QLabel(f"Found {len(picks)} albums by {artist} on Soulseek."
                      + (f" {have} you already have are unticked." if have else "")
                      + " Pick what to download:")
        info.setWordWrap(True)
        lay.addWidget(info)
        self.table = QTableWidget(len(picks), 5)
        self.table.setHorizontalHeaderLabels(["Album", "From user", "Tracks", "Quality", "Size"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in (1, 2, 3, 4):
            hh.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        for r, pk in enumerate(picks):
            owned_it = pk["key"] in owned
            first = QTableWidgetItem(pk["name"] + ("   (you have it)" if owned_it else ""))
            first.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            first.setCheckState(Qt.CheckState.Unchecked if owned_it else Qt.CheckState.Checked)
            self.table.setItem(r, 0, first)
            files = pk["files"]
            vals = (files[0]["username"], str(len(files)), quality_text(files),
                    fmt_size(sum(f["size"] for f in files)))
            for c, v in enumerate(vals, start=1):
                self.table.setItem(r, c, QTableWidgetItem(v))
        lay.addWidget(self.table, 1)
        row = QHBoxLayout()
        all_btn = QPushButton("Select all")
        all_btn.clicked.connect(lambda: self.set_all(True))
        none_btn = QPushButton("Select none")
        none_btn.clicked.connect(lambda: self.set_all(False))
        go = QPushButton("Download selected")
        go.setObjectName("primary")
        go.clicked.connect(self.accept)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        row.addWidget(all_btn)
        row.addWidget(none_btn)
        row.addStretch(1)
        row.addWidget(cancel)
        row.addWidget(go)
        lay.addLayout(row)

    def set_all(self, on):
        state = Qt.CheckState.Checked if on else Qt.CheckState.Unchecked
        for r in range(self.table.rowCount()):
            self.table.item(r, 0).setCheckState(state)

    def selected(self):
        return [pk for r, pk in enumerate(self.picks)
                if self.table.item(r, 0).checkState() == Qt.CheckState.Checked]


# ---------------------------------------------------------------- mini player
class MarqueeLabel(QWidget):
    """One line of text that slowly slides when it doesn't fit."""

    def __init__(self, color="#ffffff", parent=None):
        super().__init__(parent)
        self._text = ""
        self._offset = 0.0
        self._pause = 0
        self.gap = 48
        self.color = QColor(color)
        self.timer = QTimer(self)
        self.timer.setInterval(30)
        self.timer.timeout.connect(self._tick)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(self.fontMetrics().height() + 2)

    def setFont(self, font):
        super().setFont(font)
        self.setFixedHeight(QFontMetrics(font).height() + 2)
        self._update_timer()

    def setText(self, text):
        self._text = text or ""
        self._offset = 0.0
        self._pause = 60
        self._update_timer()
        self.update()

    def text(self):
        return self._text

    def _too_long(self):
        return self.fontMetrics().horizontalAdvance(self._text) > self.width()

    def _update_timer(self):
        if self._too_long() and self.isVisible():
            if not self.timer.isActive():
                self.timer.start()
        else:
            self.timer.stop()
            self._offset = 0.0

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_timer()

    def showEvent(self, event):
        super().showEvent(event)
        self._update_timer()

    def hideEvent(self, event):
        super().hideEvent(event)
        self.timer.stop()

    def _tick(self):
        if self._pause > 0:
            self._pause -= 1
            return
        self._offset += 1.0
        if self._offset >= self.fontMetrics().horizontalAdvance(self._text) + self.gap:
            self._offset = 0.0
            self._pause = 60
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setFont(self.font())
        p.setPen(self.color)
        fm = self.fontMetrics()
        y = (self.height() + fm.ascent() - fm.descent()) // 2
        if not self._too_long():
            p.drawText(0, y, self._text)
        else:
            x = -int(self._offset)
            p.drawText(x, y, self._text)
            p.drawText(x + fm.horizontalAdvance(self._text) + self.gap, y, self._text)
        p.end()


class MiniPlayer(QWidget):
    BAR_ZONE = 14   # bottom strip you can click/drag to seek

    def __init__(self, main):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint)
        self.main = main
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("eozMP")
        self.setFixedSize(470, 138)
        self.setMouseTracking(True)
        self.backdrop = None
        self._cache = None
        self.progress = 0.0
        self.accent = "#4C8DFF"
        self._drag = None
        self._seeking = False
        self._hover = False
        self.idle_opacity = 0.9
        self.fade = QPropertyAnimation(self, b"windowOpacity", self)
        self.fade.setDuration(180)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(14, 12, 12, 18)
        outer.setSpacing(12)
        self.cover = QLabel()
        self.cover.setFixedSize(72, 72)
        outer.addWidget(self.cover, 0, Qt.AlignmentFlag.AlignVCenter)

        texts = QVBoxLayout()
        texts.setSpacing(1)
        self.title = MarqueeLabel("#ffffff")
        tf = QFont(self.font())
        tf.setPixelSize(14)
        tf.setWeight(QFont.Weight.Bold)
        self.title.setFont(tf)
        self.artist = QLabel("")
        self.artist.setStyleSheet("color: rgba(255, 255, 255, 185); font-size: 12px;")
        self.artist.setTextFormat(Qt.TextFormat.RichText)
        self.artist.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self.artist.linkActivated.connect(main.on_link)
        self.lyric = QLabel("")
        self.lyric.setWordWrap(True)
        self.lyric.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.lyric.setStyleSheet("color: #ffffff; font-style: italic; font-size: 12px;")
        self.lyric.setFixedHeight(34)
        self.next_label = QLabel("")
        self.next_label.setStyleSheet("color: rgba(255, 255, 255, 140); font-size: 11px;")
        texts.addWidget(self.title)
        texts.addWidget(self.artist)
        texts.addWidget(self.lyric)
        texts.addStretch(1)
        texts.addWidget(self.next_label)
        outer.addLayout(texts, 1)

        right = QVBoxLayout()
        right.setSpacing(2)
        top = QHBoxLayout()
        top.setSpacing(0)
        bottom = QHBoxLayout()
        bottom.setSpacing(0)
        self.heart = QPushButton()
        self.expand = QPushButton()
        self.prev = QPushButton()
        self.play = QPushButton()
        self.next = QPushButton()
        tips = {self.heart: "Add to / remove from Favorites", self.expand: "Back to the full player",
                self.prev: "Previous", self.play: "Play / pause", self.next: "Next"}
        for b, tip in tips.items():
            b.setFixedSize(34, 34)
            b.setIconSize(QSize(18, 18))
            b.setToolTip(tip)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet("QPushButton { background: transparent; border: none; border-radius: 17px; }"
                            "QPushButton:hover { background: rgba(255, 255, 255, 46); }")
        top.addStretch(1)
        top.addWidget(self.heart)
        top.addWidget(self.expand)
        for b in (self.prev, self.play, self.next):
            bottom.addWidget(b)
        right.addLayout(top)
        right.addStretch(1)
        right.addLayout(bottom)
        outer.addLayout(right)

        self.heart.clicked.connect(main.toggle_favorite_current)
        self.expand.clicked.connect(main.exit_mini)
        self.prev.clicked.connect(main.prev_track)
        self.play.clicked.connect(main.toggle_play)
        self.next.clicked.connect(lambda: main.next_track(auto=False))
        self.set_icons(False)
        self.set_heart(False)

    # --- content
    def set_icons(self, playing):
        self.prev.setIcon(make_icon("prev", "#ffffff"))
        self.play.setIcon(make_icon("pause" if playing else "play", "#ffffff"))
        self.next.setIcon(make_icon("next", "#ffffff"))
        self.expand.setIcon(make_icon("expand", "#ffffff"))

    def set_heart(self, fav):
        self.heart.setIcon(make_icon("heart_fill" if fav else "heart", self.accent if fav else "#ffffff"))

    def set_track(self, title, artist, cover_pix, backdrop, href=None):
        self.title.setText(title)
        short = html.escape(self.artist.fontMetrics().elidedText(artist, Qt.TextElideMode.ElideRight, 230))
        self.artist.setText(f'<a href="{html.escape(href)}" style="color: rgba(255,255,255,190); '
                            f'text-decoration: none;">{short}</a>' if href else short)
        self.cover.setPixmap(cover_pix)
        self.backdrop = backdrop
        self._cache = None
        self.update()

    def set_lyric(self, text):
        self.lyric.setText(text)

    def set_next(self, text):
        self.next_label.setText(self.next_label.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, 230))

    def set_progress(self, fraction):
        fraction = max(0.0, min(1.0, fraction))
        if abs(fraction - self.progress) > 0.002:
            self.progress = fraction
            self.update()

    def set_idle_opacity(self, value):
        self.idle_opacity = max(0.3, min(1.0, value))
        if not self._hover:
            self.setWindowOpacity(self.idle_opacity)

    # --- drawing
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = QPainterPath()
        clip.addRoundedRect(0, 0, self.width(), self.height(), 16, 16)
        p.setClipPath(clip)
        if self.backdrop is not None:
            if self._cache is None:
                self._cache = self.backdrop.scaled(
                    self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap((self.width() - self._cache.width()) // 2,
                         (self.height() - self._cache.height()) // 2, self._cache)
        else:
            p.fillRect(self.rect(), QColor("#1b1b20"))
        p.fillRect(self.rect(), QColor(0, 0, 0, 115))
        bar_h = 6 if self._hover else 4
        y = self.height() - bar_h
        p.fillRect(0, y, self.width(), bar_h, QColor(255, 255, 255, 45))
        p.fillRect(0, y, int(self.width() * self.progress), bar_h, QColor(self.accent))
        p.end()

    # --- mouse: drag to move, click/drag the bottom bar to seek, wheel for volume
    def _seek_to(self, x):
        self.main.seek_fraction(max(0.0, min(1.0, x / max(1, self.width()))))

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        pos = e.position().toPoint()
        if pos.y() >= self.height() - self.BAR_ZONE:
            self._seeking = True
            self._seek_to(pos.x())
        else:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._seeking:
            self._seek_to(e.position().toPoint().x())
        elif self._drag is not None and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        if self._drag is not None:
            self.snap()
        self._drag = None
        self._seeking = False

    def mouseDoubleClickEvent(self, e):
        if e.position().toPoint().y() < self.height() - self.BAR_ZONE:
            self.main.exit_mini()

    def wheelEvent(self, e):
        step = 5 if e.angleDelta().y() > 0 else -5
        vol = self.main.volume
        vol.setValue(max(0, min(100, vol.value() + step)))
        QToolTip.showText(e.globalPosition().toPoint(), f"Volume {vol.value()}%", self)

    def enterEvent(self, e):
        self._hover = True
        self._fade_to(1.0)
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self._fade_to(self.idle_opacity)
        self.update()

    def _fade_to(self, value):
        self.fade.stop()
        self.fade.setStartValue(self.windowOpacity())
        self.fade.setEndValue(value)
        self.fade.start()

    def snap(self):
        """Stick neatly to the screen edges when dropped close to them."""
        screen = self.screen() or QApplication.primaryScreen()
        area = screen.availableGeometry()
        g = self.frameGeometry()
        x, y, margin, reach = g.x(), g.y(), 12, 40
        if abs(g.left() - area.left()) < reach:
            x = area.left() + margin
        elif abs(area.right() - g.right()) < reach:
            x = area.right() - g.width() - margin + 1
        if abs(g.top() - area.top()) < reach:
            y = area.top() + margin
        elif abs(area.bottom() - g.bottom()) < reach:
            y = area.bottom() - g.height() - margin + 1
        self.move(x, y)

    def contextMenuEvent(self, e):
        menu = QMenu(self)
        menu.addAction("Back to the full player").triggered.connect(self.main.exit_mini)
        menu.addAction("Close eozMP").triggered.connect(self.main.quit_app)
        menu.exec(e.globalPos())


# ---------------------------------------------------------------- library list, drag & drop, dialogs
EOZ_MIME = "application/x-eozmp-songs"
BACKUP_FILES = {"settings.json": CONFIG_FILE, "playlists.json": PLAYLIST_FILE, "stats.json": STATS_FILE}


def songs_mime(paths):
    md = QMimeData()
    md.setData(EOZ_MIME, QByteArray(json.dumps(paths).encode("utf-8")))
    md.setText("\n".join(paths))
    return md


def paths_from_mime(md):
    if md is None or not md.hasFormat(EOZ_MIME):
        return []
    try:
        return json.loads(bytes(md.data(EOZ_MIME)).decode("utf-8"))
    except Exception:
        return []


def neutral_cover(size, radius, bg, fg):
    """Quiet stand-in for a missing cover: a soft square with a small note."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    shape = QPainterPath()
    shape.addRoundedRect(0, 0, size, size, radius, radius)
    p.fillPath(shape, QColor(bg))
    f = QFont()
    f.setPixelSize(max(6, int(size * 0.5)))
    p.setFont(f)
    p.setPen(QColor(fg))
    p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, "\u266a")
    p.end()
    return pm


def song_tech_info(path):
    out = {"format": Path(path).suffix.upper().lstrip("."), "quality": "", "size": ""}
    try:
        out["size"] = fmt_size(os.path.getsize(path))
    except OSError:
        pass
    try:
        info = getattr(MutagenFile(path), "info", None)
        parts = []
        bitrate = getattr(info, "bitrate", 0) or 0
        if bitrate:
            parts.append(f"{int(round(bitrate / 1000))} kbps")
        rate = getattr(info, "sample_rate", 0) or 0
        if rate:
            parts.append(f"{rate / 1000:g} kHz")
        bits = getattr(info, "bits_per_sample", 0) or 0
        if bits:
            parts.append(f"{bits}-bit")
        ch = getattr(info, "channels", 0) or 0
        if ch:
            parts.append("stereo" if ch == 2 else "mono" if ch == 1 else f"{ch} channels")
        out["quality"] = ", ".join(parts)
    except Exception:
        pass
    return out


class SongTable(QTableWidget):
    """A song list you can drag songs out of (onto playlists or the queue)."""

    def __init__(self, rows, cols, paths_fn):
        super().__init__(rows, cols)
        self.paths_fn = paths_fn
        self.hover_row = -1
        self.setMouseTracking(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)

    def mouseMoveEvent(self, e):
        row = self.rowAt(int(e.position().y()))
        if row != self.hover_row:
            self.hover_row = row
            self.viewport().update()
        super().mouseMoveEvent(e)

    def leaveEvent(self, e):
        self.hover_row = -1
        self.viewport().update()
        super().leaveEvent(e)

    def mimeTypes(self):
        return [EOZ_MIME]

    def mimeData(self, items):
        rows = sorted({it.row() for it in items})
        return songs_mime(self.paths_fn(rows))


class LibraryTree(QTreeWidget):
    """The artist/album list; albums and artists can be dragged onto playlists or the queue."""

    def __init__(self, main):
        super().__init__()
        self.main = main
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)

    def mimeTypes(self):
        return [EOZ_MIME]

    def mimeData(self, items):
        paths = []
        for it in items:
            key = it.data(0, KEY_ROLE)
            if key in self.main.albums:
                paths += self.main.album_paths(key)
            else:
                for k in self.main.artist_album_keys(it.data(0, ARTIST_ROLE)):
                    paths += self.main.album_paths(k)
        return songs_mime(paths)


class TreeRowDelegate(QStyledItemDelegate):
    """Draws library rows: [cover] 1. Album name .......... 2014, with a hover fill and a frame when selected."""

    def __init__(self, main):
        super().__init__(main.tree)
        self.main = main

    def sizeHint(self, option, index):
        compact = self.main.cfg["density"] == "Compact"
        if index.parent().isValid():
            covers = self.main.cfg["album_list_style"] in ("Covers and numbers", "Covers")
            h = (34 if compact else 40) if covers else (26 if compact else 32)
        else:
            h = 28 if compact else 34
        return QSize(120, h)

    def paint(self, painter, option, index):
        m = self.main
        sc = m.scheme
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        r = QRectF(option.rect).adjusted(3, 1.5, -3, -1.5)
        rad = float(max(3, m.radius(8)))
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hover = bool(option.state & QStyle.StateFlag.State_MouseOver)
        if hover and not selected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(sc["hover"]))
            painter.drawRoundedRect(r, rad, rad)
        if selected:
            pen = QPen(QColor(sc["accent"]))
            pen.setWidthF(1.4)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(r.adjusted(0.7, 0.7, -0.7, -0.7), rad, rad)
        text_col, sub_col = QColor(sc["text"]), QColor(sc["sub"])
        x, right = r.left() + 8, r.right() - 8
        font = QFont(option.font)
        title = index.data(Qt.ItemDataRole.DisplayRole) or ""
        center = Qt.AlignmentFlag.AlignVCenter
        if not index.parent().isValid():
            cy, s = r.center().y(), 4.0
            chev = QPainterPath()
            if m.tree.isExpanded(index):
                chev.moveTo(x, cy - s / 2)
                chev.lineTo(x + s, cy + s / 2)
                chev.lineTo(x + 2 * s, cy - s / 2)
            else:
                chev.moveTo(x + s / 2, cy - s)
                chev.lineTo(x + s * 1.5, cy)
                chev.lineTo(x + s / 2, cy + s)
            cpen = QPen(sub_col)
            cpen.setWidthF(1.5)
            cpen.setCapStyle(Qt.PenCapStyle.RoundCap)
            cpen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(cpen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(chev)
            x += 18
            font.setBold(True)
        else:
            style = m.cfg["album_list_style"]
            fm = QFontMetrics(font)
            painter.setFont(font)
            if style in ("Covers and numbers", "Covers"):
                pm = m.tree_thumb(index.data(KEY_ROLE))
                painter.drawPixmap(int(x), int(r.center().y() - pm.height() / 2), pm)
                x += pm.width() + 10
            if style in ("Covers and numbers", "Numbers"):
                nw = fm.horizontalAdvance("00.")
                painter.setPen(sub_col)
                painter.drawText(QRectF(x, r.top(), nw, r.height()), center | Qt.AlignmentFlag.AlignRight,
                                 f"{index.data(NUM_ROLE)}.")
                x += nw + 8
            year = index.data(YEAR_ROLE) or 0
            if year:
                yw = fm.horizontalAdvance(str(year))
                painter.setPen(sub_col)
                painter.drawText(QRectF(right - yw, r.top(), yw, r.height()), center | Qt.AlignmentFlag.AlignRight,
                                 str(year))
                right -= yw + 10
        painter.setFont(font)
        fm = QFontMetrics(font)
        width = max(0, int(right - x))
        painter.setPen(text_col)
        painter.drawText(QRectF(x, r.top(), width, r.height()), center | Qt.AlignmentFlag.AlignLeft,
                         fm.elidedText(title, Qt.TextElideMode.ElideRight, width))
        painter.restore()


class DropButton(QPushButton):
    """A button you can drop songs on (Queue), or that reacts when a drag passes over it (Playlists tab)."""

    def __init__(self, text="", on_drop=None, on_enter=None):
        super().__init__(text)
        self.on_drop = on_drop
        self.on_enter = on_enter
        self.setAcceptDrops(True)

    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat(EOZ_MIME):
            e.acceptProposedAction()
            if self.on_enter:
                self.on_enter()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        if e.mimeData().hasFormat(EOZ_MIME):
            e.acceptProposedAction()

    def dropEvent(self, e):
        paths = paths_from_mime(e.mimeData())
        if paths and self.on_drop:
            self.on_drop(paths)
            e.acceptProposedAction()
        else:
            e.ignore()


class PlaylistDropList(QListWidget):
    """The playlists list: drop songs on a playlist to add them."""

    def __init__(self, main):
        super().__init__()
        self.main = main
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)

    def _target(self, e):
        item = self.itemAt(e.position().toPoint())
        name = item.data(KEY_ROLE) if item is not None else None
        return name if name in self.main.playlists else None

    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat(EOZ_MIME):
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        if e.mimeData().hasFormat(EOZ_MIME) and self._target(e):
            e.acceptProposedAction()
        else:
            e.ignore()

    def dropEvent(self, e):
        name, paths = self._target(e), paths_from_mime(e.mimeData())
        if name and paths:
            self.main.add_to_playlist(name, paths)
            e.acceptProposedAction()
        else:
            e.ignore()


class QueueDelegate(QStyledItemDelegate):
    """Queue rows with a small x on the right to remove the song."""
    X_ZONE = 30

    def __init__(self, view, main):
        super().__init__(view)
        self.view = view
        self.main = main

    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        opt.rect = option.rect.adjusted(0, 0, -self.X_ZONE, 0)   # leave room for the x
        super().paint(painter, opt, index)
        hovered = getattr(self.view, "hover_row", -1) == index.row()
        r = option.rect
        size = 14
        x = r.right() - self.X_ZONE + (self.X_ZONE - size) // 2
        y = r.top() + (r.height() - size) // 2
        color = QColor(self.main.icon_fg)
        color.setAlpha(230 if hovered else 120)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if hovered:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(self.main.scheme["hover"]))
            painter.drawEllipse(QRectF(x - 6, y - 6, size + 12, size + 12))
        pen = QPen(color)
        pen.setWidthF(1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(QPointF(x, y), QPointF(x + size, y + size))
        painter.drawLine(QPointF(x + size, y), QPointF(x, y + size))
        painter.restore()


class QueueList(QListWidget):
    """The queue: drag to reorder, drop songs from anywhere to add them, x to remove one."""

    def __init__(self, main):
        super().__init__()
        self.main = main
        self.hover_row = -1
        self.setMouseTracking(True)
        self.setItemDelegate(QueueDelegate(self, main))

    def _on_x(self, pos):
        index = self.indexAt(pos)
        if not index.isValid():
            return -1
        rect = self.visualRect(index)
        return index.row() if pos.x() >= rect.right() - QueueDelegate.X_ZONE else -1

    def mousePressEvent(self, e):
        row = self._on_x(e.position().toPoint())
        if row >= 0 and e.button() == Qt.MouseButton.LeftButton:
            self.main.remove_queue_row(row)
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        index = self.indexAt(e.position().toPoint())
        row = index.row() if index.isValid() else -1
        if row != self.hover_row:
            self.hover_row = row
            self.viewport().update()
        cursor = Qt.CursorShape.PointingHandCursor if self._on_x(e.position().toPoint()) >= 0 else Qt.CursorShape.ArrowCursor
        self.viewport().setCursor(cursor)
        super().mouseMoveEvent(e)

    def leaveEvent(self, e):
        self.hover_row = -1
        self.viewport().update()
        super().leaveEvent(e)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.main.remove_from_queue()
            return
        super().keyPressEvent(e)

    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat(EOZ_MIME):
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e):
        if e.mimeData().hasFormat(EOZ_MIME):
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e):
        if e.mimeData().hasFormat(EOZ_MIME):
            self.main.queue_add(paths_from_mime(e.mimeData()))
            e.acceptProposedAction()
        else:
            super().dropEvent(e)


class CoverViewer(QDialog):
    """Full-size album cover over a dark backdrop. Click anywhere or press Esc to close."""

    def __init__(self, parent, pix):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        screen = parent.screen() or QApplication.primaryScreen()
        self.setGeometry(screen.geometry())
        area = screen.availableGeometry()
        side = int(min(area.width(), area.height()) * 0.86)
        target = min(side, max(pix.width(), pix.height()) * 2)
        self.pix = pix.scaled(target, target, Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor(0, 0, 0, 215))
        p.drawPixmap((self.width() - self.pix.width()) // 2, (self.height() - self.pix.height()) // 2, self.pix)
        p.end()

    def mousePressEvent(self, event):
        self.accept()


class SongInfoDialog(QDialog):
    def __init__(self, main, path):
        super().__init__(main)
        self.setWindowTitle("Song info")
        self.setMinimumWidth(540)
        t, key = main.track_by_path[path]
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        top.setSpacing(16)
        cover = QLabel()
        cover.setPixmap(main.thumb_pixmap(key, 120, main.radius(10)))
        names = QVBoxLayout()
        title = QLabel(t["title"])
        title.setObjectName("heading2")
        title.setWordWrap(True)
        sub = QLabel(f"{t['artist']}  ·  {t['album']}")
        sub.setObjectName("sub")
        sub.setWordWrap(True)
        names.addStretch(1)
        names.addWidget(title)
        names.addWidget(sub)
        names.addStretch(1)
        top.addWidget(cover)
        top.addLayout(names, 1)
        lay.addLayout(top)
        tech = song_tech_info(path)
        play = main.stats["plays"].get(path, {})
        last = time.strftime("%d %b %Y, %H:%M", time.localtime(play["last"])) if play.get("last") else "Never"
        added = t.get("added", t.get("mtime", 0))
        rows = (
            ("Format", tech["format"]), ("Quality", tech["quality"] or "-"),
            ("Length", fmt_time(t["length"] * 1000)), ("File size", tech["size"] or "-"),
            ("Track", str(t["num"]) if t["num"] != 9999 else "-"), ("Year", str(t["year"]) if t["year"] else "-"),
            ("Genre", t.get("genre") or "-"), ("Plays", str(play.get("count", 0))),
            ("Last played", last), ("Added", time.strftime("%d %b %Y", time.localtime(added)) if added else "-"),
            ("Favorite", "Yes" if path in main.fav_set else "No"), ("File", path),
        )
        form = QFormLayout()
        for label, value in rows:
            v = QLabel(value)
            v.setWordWrap(True)
            v.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            form.addRow(label, v)
        lay.addLayout(form)
        btns = QHBoxLayout()
        show = QPushButton("Show in folder")
        show.clicked.connect(lambda: main.show_in_folder(path))
        close = QPushButton("Close")
        close.setObjectName("primary")
        close.clicked.connect(self.accept)
        btns.addWidget(show)
        btns.addStretch(1)
        btns.addWidget(close)
        lay.addLayout(btns)


class FadeStack(QStackedWidget):
    """The right-hand pages; switching pages does a quick cross-fade."""

    def __init__(self):
        super().__init__()
        self.animate = True
        self.on_resize = None
        self.on_raise = None

    def setCurrentIndex(self, index):
        if (not self.animate or index == self.currentIndex() or not self.isVisible()
                or self.currentWidget() is None):
            super().setCurrentIndex(index)
            return
        snap = self.currentWidget().grab()
        super().setCurrentIndex(index)
        overlay = QLabel(self)
        overlay.setPixmap(snap)
        overlay.setGeometry(0, 0, self.width(), self.height())
        overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        effect = QGraphicsOpacityEffect(overlay)
        overlay.setGraphicsEffect(effect)
        overlay.show()
        overlay.raise_()
        anim = QPropertyAnimation(effect, b"opacity", overlay)
        anim.setDuration(150)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(overlay.deleteLater)
        anim.start()
        if self.on_raise:
            self.on_raise()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.on_resize:
            self.on_resize()


class ClickCatcher(QWidget):
    """Invisible layer that closes the queue panel when you click next to it."""

    def __init__(self, parent, callback):
        super().__init__(parent)
        self.callback = callback
        self.hide()

    def mousePressEvent(self, e):
        self.callback()


class QueueDrawer(QWidget):
    """The queue as a see-through panel sliding in from the right."""

    def __init__(self, main, parent):
        super().__init__(parent)
        self.main = main
        self.setObjectName("drawer")
        self.snapshot = None
        self.anim = QPropertyAnimation(self, b"pos", self)
        self.anim.setDuration(200)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.hide()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        sc = self.main.scheme
        shape = QPainterPath()
        shape.addRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, 14, -0.5), 14, 14)
        p.setClipPath(shape)
        if self.snapshot is not None:
            p.drawPixmap(0, 0, self.snapshot)
        bg = QColor(sc["bg"])
        bg.setAlpha(153)    # about 60 %
        p.fillRect(self.rect(), bg)
        p.setClipping(False)
        pen = QPen(QColor(sc["border"]))
        pen.setWidthF(1.0)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(shape)
        p.end()


class FullPlayer(QWidget):
    """Full-screen player: big cover and controls on the left, lyrics on the right."""

    def __init__(self, main):
        super().__init__(None, Qt.WindowType.Window)
        self.main = main
        self.setWindowTitle("eozMP")
        self.setWindowIcon(app_icon())
        self.backdrop = None
        self._cache = None
        self._last_cursor = QPoint()
        self._idle = 0
        self.has_lyrics = True
        root = QHBoxLayout(self)
        root.setContentsMargins(70, 56, 70, 56)
        root.setSpacing(56)
        self.left = QWidget()
        lv = QVBoxLayout(self.left)
        lv.setSpacing(8)
        self.cover = QLabel()
        self.cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title = QLabel("")
        self.title.setWordWrap(True)
        self.title.setObjectName("fstitle")
        self.artist = QLabel("")
        self.artist.setWordWrap(True)
        self.artist.setObjectName("fsartist")
        self.controls = QWidget()
        cv = QVBoxLayout(self.controls)
        cv.setContentsMargins(0, 8, 0, 0)
        seek_row = QHBoxLayout()
        self.pos_label = QLabel("0:00")
        self.pos_label.setObjectName("fssub")
        self.seek = QSlider(Qt.Orientation.Horizontal)
        self.seek.sliderMoved.connect(lambda v: self.main.player.setPosition(v))
        self.len_label = QLabel("0:00")
        self.len_label.setObjectName("fssub")
        seek_row.addWidget(self.pos_label)
        seek_row.addWidget(self.seek, 1)
        seek_row.addWidget(self.len_label)
        cv.addLayout(seek_row)
        btns = QHBoxLayout()
        btns.addStretch(1)
        self.shuffle = QPushButton()
        self.prev = QPushButton()
        self.play = QPushButton()
        self.next = QPushButton()
        self.repeat = QPushButton()
        self.heart = QPushButton()
        for b in (self.shuffle, self.prev, self.play, self.next, self.repeat, self.heart):
            b.setFixedSize(46, 46)
            b.setIconSize(QSize(22, 22))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            btns.addWidget(b)
        self.play.setObjectName("fsplay")
        self.play.setFixedSize(64, 64)
        self.play.setIconSize(QSize(28, 28))
        btns.addSpacing(18)
        self.vol_btn = QPushButton()
        self.vol_btn.setFixedSize(40, 40)
        self.vol_btn.setIconSize(QSize(20, 20))
        self.vol_btn.clicked.connect(lambda: self.main.toggle_mute())
        self.vol = QSlider(Qt.Orientation.Horizontal)
        self.vol.setRange(0, 100)
        self.vol.setFixedWidth(110)
        self.vol.valueChanged.connect(lambda v: self.main.volume.setValue(v))
        btns.addWidget(self.vol_btn)
        btns.addWidget(self.vol)
        btns.addStretch(1)
        cv.addLayout(btns)
        self.shuffle.clicked.connect(lambda: self.main.shuffle.toggle())
        self.prev.clicked.connect(lambda: self.main.prev_track())
        self.play.clicked.connect(lambda: self.main.toggle_play())
        self.next.clicked.connect(lambda: self.main.next_track(auto=False))
        self.repeat.clicked.connect(lambda: self.main.toggle_repeat())
        self.heart.clicked.connect(lambda: self.main.toggle_favorite_current())
        self.fx = QGraphicsOpacityEffect(self.controls)
        self.fx.setOpacity(1.0)
        self.controls.setGraphicsEffect(self.fx)
        self.fade = QPropertyAnimation(self.fx, b"opacity", self)
        self.fade.setDuration(350)
        lv.addStretch(1)
        lv.addWidget(self.cover, 0, Qt.AlignmentFlag.AlignHCenter)
        lv.addSpacing(10)
        lv.addWidget(self.title)
        lv.addWidget(self.artist)
        lv.addWidget(self.controls)
        lv.addStretch(1)
        root.addWidget(self.left, 5)
        self.right = QWidget()
        self.right_lay = QVBoxLayout(self.right)
        self.right_lay.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self.right, 6)
        self.next_card = QLabel(self)
        self.next_card.setObjectName("fsnext")
        self.next_card.hide()
        self.window_btns = QWidget(self)
        wb = QHBoxLayout(self.window_btns)
        wb.setContentsMargins(0, 0, 0, 0)
        wb.setSpacing(6)
        self.min_btn = QPushButton()
        self.min_btn.setToolTip("Leave fullscreen")
        self.min_btn.clicked.connect(lambda: self.main.exit_fullscreen())
        self.close_btn = QPushButton()
        self.close_btn.setObjectName("fsclose")
        self.close_btn.setToolTip("Close eozMP")
        self.close_btn.clicked.connect(lambda: self.main.quit_app())
        for b in (self.min_btn, self.close_btn):
            b.setFixedSize(40, 40)
            b.setIconSize(QSize(18, 18))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            wb.addWidget(b)
        self.min_btn.setIcon(make_icon("minimize", "#ffffff"))
        self.close_btn.setIcon(make_icon("close", "#ffffff"))
        self.window_btns.adjustSize()
        self.btn_fx = QGraphicsOpacityEffect(self.window_btns)
        self.btn_fx.setOpacity(1.0)
        self.window_btns.setGraphicsEffect(self.btn_fx)
        self.btn_fade = QPropertyAnimation(self.btn_fx, b"opacity", self)
        self.btn_fade.setDuration(350)
        self.idle_timer = QTimer(self)
        self.idle_timer.setInterval(300)
        self.idle_timer.timeout.connect(self._check_idle)
        self.motion_timer = QTimer(self)
        self.motion_timer.setInterval(50)
        self.motion_timer.timeout.connect(self.update)
        self.viz = Visualizer(self, bars=64)
        self.viz.hide()

    def style_for(self, sc):
        self.setStyleSheet(
            "QLabel { color: #ffffff; background: transparent; }"
            f"QLabel#fstitle {{ font-family: '{self.main.display_family}'; font-size: 34px; font-weight: 700; }}"
            "QLabel#fsartist { color: rgba(255, 255, 255, 200); font-size: 20px; }"
            "QLabel#fssub { color: rgba(255, 255, 255, 170); }"
            "QLabel#fsnext { background: rgba(0, 0, 0, 150); border-radius: 12px; padding: 12px 16px;"
            " font-size: 14px; }"
            "QPushButton { background: transparent; border: none; border-radius: 23px; }"
            "QPushButton:hover { background: rgba(255, 255, 255, 36); }"
            f"QPushButton#fsplay {{ background: {sc['accent']}; border-radius: 32px; }}"
            f"QPushButton#fsplay:hover {{ background: {sc['accent_hover']}; }}"
            "QPushButton#fsclose:hover { background: rgba(232, 17, 35, 200); }"
        )

    def cover_side(self):
        if self.has_lyrics:
            return int(min(self.height() * 0.5, self.width() * 0.33))
        return int(min(self.height() * 0.6, self.width() * 0.5))

    def set_lyrics_visible(self, on):
        self.has_lyrics = on
        self.right.setVisible(on)
        self.left.setMaximumWidth(16777215 if not on else int(self.width() * 0.45) or 16777215)

    def set_backdrop(self, pix):
        self.backdrop = pix
        self._cache = None
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        if self.backdrop is not None:
            motion = bool(self.main.cfg["fs_motion"])
            grow = 1.14 if motion else 1.0
            want = QSize(int(self.width() * grow), int(self.height() * grow))
            if self._cache is None or self._cache.size().width() < want.width() - 2:
                self._cache = self.backdrop.scaled(want, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                                   Qt.TransformationMode.SmoothTransformation)
            x = (self.width() - self._cache.width()) / 2
            y = (self.height() - self._cache.height()) / 2
            if motion:   # slow, gentle drift
                t = time.monotonic()
                x += math.sin(t / 9.0) * (self._cache.width() - self.width()) * 0.45
                y += math.cos(t / 13.0) * (self._cache.height() - self.height()) * 0.45
            p.drawPixmap(int(x), int(y), self._cache)
        else:
            p.fillRect(self.rect(), QColor("#111114"))
        p.fillRect(self.rect(), QColor(0, 0, 0, 140))
        p.end()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._cache = None
        self.window_btns.move(self.width() - self.window_btns.width() - 18, 16)
        self.window_btns.raise_()
        self.viz.setGeometry(40, self.height() - 120, self.width() - 80, 100)
        self.main.update_fullscreen()

    def show_next_card(self, text):
        if not text:
            self.next_card.hide()
            return
        self.next_card.setText(text)
        self.next_card.adjustSize()
        self.next_card.move(self.width() - self.next_card.width() - 40,
                            self.height() - self.next_card.height() - 40)
        self.next_card.show()
        self.next_card.raise_()

    # --- auto-hide the controls and the mouse pointer
    def showEvent(self, e):
        super().showEvent(e)
        self._wake()
        self.idle_timer.start()
        if self.main.cfg["fs_motion"]:
            self.motion_timer.start()

    def hideEvent(self, e):
        super().hideEvent(e)
        self.idle_timer.stop()
        self.motion_timer.stop()

    def _wake(self):
        self._idle = 0
        self.unsetCursor()
        for fx, anim in ((self.fx, self.fade), (self.btn_fx, self.btn_fade)):
            if fx.opacity() < 1.0:
                anim.stop()
                anim.setStartValue(fx.opacity())
                anim.setEndValue(1.0)
                anim.start()

    def _check_idle(self):
        pos = QCursor.pos()
        if pos != self._last_cursor:
            self._last_cursor = pos
            self._wake()
            return
        self._idle += 1
        if self._idle == 10:   # about 3 seconds
            self.setCursor(Qt.CursorShape.BlankCursor)
            for fx, anim in ((self.fx, self.fade), (self.btn_fx, self.btn_fade)):
                anim.stop()
                anim.setStartValue(fx.opacity())
                anim.setEndValue(0.0)
                anim.start()

    def keyPressEvent(self, e):
        key = e.key()
        if key in (Qt.Key.Key_Escape, Qt.Key.Key_F11):
            self.main.exit_fullscreen()
        elif key == Qt.Key.Key_Space:
            self.main.toggle_play()
        elif key == Qt.Key.Key_Right:
            self.main.next_track(auto=False)
        elif key == Qt.Key.Key_Left:
            self.main.prev_track()
        else:
            super().keyPressEvent(e)

    def closeEvent(self, e):
        self.main.exit_fullscreen()
        e.accept()


# ---------------------------------------------------------------- main window
class Player(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("eozMP")
        self.cfg = load_config()
        if int(self.cfg.get("cfg_version", 1)) < 2:
            # one-time move to the new album-art lyrics defaults
            if self.cfg.get("lyrics_font") in ("Segoe UI", ""):
                self.cfg["lyrics_font"] = ""
            if int(self.cfg.get("lyrics_size", 26)) == 16:
                self.cfg["lyrics_size"] = 26
            self.cfg["cfg_version"] = 2
            save_config(self.cfg)
        if int(self.cfg.get("cfg_version", 1)) < 3:
            # Times New Roman reads a little small at 10 pt
            if not self.cfg.get("ui_font") and int(self.cfg.get("ui_font_size", 11)) == 10:
                self.cfg["ui_font_size"] = 11
            self.cfg["cfg_version"] = 3
            save_config(self.cfg)
        if int(self.cfg.get("cfg_version", 1)) < 4:
            self.cfg["lyrics_font"] = ""                      # follow the app font again
            if self.cfg.get("album_list_style") in ("Numbers", ""):
                self.cfg["album_list_style"] = "Covers and numbers"
            self.cfg["cfg_version"] = 4
            save_config(self.cfg)
        if self.cfg.get("lyrics_style") == "Apple Music":   # old name
            self.cfg["lyrics_style"] = "Album art"
        self.resize(*self.cfg["win_size"])

        self.workers = set()
        self.albums = {}        # (artist_key, album_key) -> album dict
        self.artists = {}       # artist_key -> display name
        self.tree_albums = {}   # key -> tree item
        self.queue = []         # [(track, album_key)]
        self.qindex = {}        # path -> index in queue
        self.index = -1
        self.current_album = None
        self.cover_cache = {}
        self.search_worker = None
        self.last_done = None
        self.poll_busy = False
        self.all_tracks = []
        self.scanning = False
        self.rescan_pending = False
        self.soul_raw = []      # every file found by the current Soulseek search
        self.soul_view = []     # rows currently shown (each row = list of files)
        self.soul_count_text = ""
        self.searching = False
        self.search_failed = False
        self.dl_rows = []
        self.dl_keys = []
        self.lyric_times = []   # ms timestamps of synced lyric lines
        self.lyric_lines = []
        self.lyric_idx = -1
        self.lyrics_token = ""
        self.pending_seek = 0
        self.prev_page = 0
        self.resumed = False
        self.up_next = []       # songs you queued (play before the rest)
        self.ctx_paths = []     # what plays after them: the library or a playlist
        self.ctx_pos = 0
        self.ctx_kind = ""      # "" = whole library, otherwise the playlist name
        self.track_by_path = {}
        self.playlists = load_playlists()
        self.current_playlist = None
        self.pl_paths = []
        self.stats = load_stats()
        self.fav_set = set(self.stats["favorites"])
        self.history = []        # songs actually played, newest last ("previous" walks back here)
        self.fwd = []            # songs you went back from ("next" walks forward again)
        self.shuffle_played = set()
        self.listen_ms = 0
        self.last_pos = None
        self.listen_path = None
        self.album_accent = None
        self.accent_cache = {}
        self.cover_fetching = set()
        self.cover_batch = None
        self.mini = None
        self.icon_fg = "#ffffff"
        self.vlc_error = ""
        self.quitting = False
        self.tray = None
        self.tray_menu = None
        self.media_filter = None
        self.media_keys_on = False
        self.lyric_watcher = QFileSystemWatcher(self)
        self.lyric_watcher.directoryChanged.connect(self.on_lyric_folder_changed)
        self.lyric_watcher.fileChanged.connect(self.on_lyric_folder_changed)
        self.lyric_wait_path = None
        self.disco_worker = None
        self.disco_rows = []
        self.thumb_cache = {}       # album key -> 160px square cover (None = no cover)
        self.ph_cache = {}          # placeholder pixmaps
        self.backdrop_cache = {}
        self.tree_artists = {}
        self.view_targets = {"artist": {}, "home": {}, "search": {}, "browse": {}}
        self.tree_px = {}
        self.neutral_cache = {}
        self.back_buttons = []
        self.dl_active = 0
        self.genres, self.decades = {}, {}
        self.browse_paths, self.browse_name = [], ""
        self._line_in_item = self._line_out_item = None
        self._fade_on = None
        self.ly_off = 0
        self.lyric_pad = (28, 10)
        self.lyric_hold_until = 0.0
        self.np_phase = 0.0
        self.buf_out = None
        self.nav_back, self.nav_fwd, self.nav_cur = [], [], None
        self._navigating = False
        self.fs = None
        self.fs_active = False
        self.inline_soul_raw, self.inline_soul_view = [], []
        self.inline_soul_worker = None
        self.inline_soul_text = ""
        self.current_artist = None
        self.artist_avatar_key = None
        self.artist_paths = []
        self.artist_top_paths = []
        self.search_paths = []
        self.search_prev_page = 8
        self.song_index = []
        self.thumbs = ThumbLoader()
        self.thumbs.loaded.connect(self.on_thumb_loaded)
        self.thumbs.start()
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.run_search)

        self.player, self.audio, self.engine_name = create_engine(self.cfg["audio_engine"])
        self.audio.setVolume(self.cfg["volume"] / 100)

        self.build_ui()
        self.build_menu()
        self.install_frame_delegates()
        self.install_cover_clicks()
        self.lyrics_viewport = self.lyrics_list.viewport()
        self.time_targets = (self.total_label,)
        self.lyric_resume_timer = QTimer(self)
        self.lyric_resume_timer.setSingleShot(True)
        self.lyric_resume_timer.timeout.connect(self.resume_lyric_follow)
        self.np_timer = QTimer(self)
        self.np_timer.setInterval(140)
        self.np_timer.timeout.connect(self.tick_now_playing)
        self.np_timer.start()
        self.viz_timer = QTimer(self)
        self.viz_timer.setInterval(33)
        self.viz_timer.timeout.connect(self.tick_visualizers)
        QShortcut(QKeySequence("Escape"), self, activated=self.on_escape)
        QApplication.instance().installEventFilter(self)
        self.system_dark = QApplication.palette().color(QPalette.ColorRole.Window).lightness() < 128
        self.scheme = make_scheme(True, ACCENTS["Blue"])
        self.lyric_look = None
        self.lyric_align = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        self.lyrics_immersive = False
        self.display_family = "Segoe UI"
        self.corner = 1.0
        self.cover_px = 220
        self.lyrics_artist = ""
        self.apply_settings()
        self.apply_soulseek_defaults()
        self.apply_equalizer()
        self.refresh_playlist_list()
        self.refresh_queue_view()

        self.connect_engine()

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.poll_downloads)
        self.poll_timer.start(3000)

        # show the cached library instantly, then refresh it in the background
        cached = load_cache()
        if cached:
            try:
                self.build_library(cached)
            except Exception:
                pass
        self.rescan()
        self.setup_tray()
        if self.cfg["media_keys"]:
            self.register_media_keys()

    # ----- helpers
    def keep(self, worker):
        self.workers.add(worker)
        worker.finished.connect(lambda: self.workers.discard(worker))
        worker.start()

    def slskd_ready(self):
        return bool(self.cfg["slskd_url"] and self.cfg["slskd_key"])

    def client(self):
        return Slskd(self.cfg["slskd_url"], self.cfg["slskd_key"])

    # ----- UI
    def build_ui(self):
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(10)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # left: search + artist/album tree
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        brand = QHBoxLayout()
        brand_name = QLabel("eozMP")
        brand_name.setObjectName("brand")
        brand.addWidget(brand_name)
        brand.addStretch(1)
        self.nav_back_btn = QPushButton()
        self.nav_fwd_btn = QPushButton()
        for b, tip, fn in ((self.nav_back_btn, "Back (Alt+Left)", lambda: self.go_back()),
                           (self.nav_fwd_btn, "Forward (Alt+Right)", lambda: self.go_forward())):
            b.setObjectName("transport")
            b.setFixedSize(30, 30)
            b.setIconSize(QSize(16, 16))
            b.setToolTip(tip)
            b.clicked.connect(fn)
            brand.addWidget(b)
        lv.addLayout(brand)
        row = QHBoxLayout()
        row.setSpacing(6)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search")
        self.search.setToolTip("Search your library. Press Enter to also search Soulseek when something's missing.")
        self.search.textChanged.connect(self.apply_filter)
        self.search.textChanged.connect(lambda _t: self.search_timer.start(220))
        self.search.setClearButtonEnabled(True)
        self.search.returnPressed.connect(self.on_enter)
        self.soul_btn = QPushButton()
        self.soul_btn.setToolTip("Search Soulseek")
        self.soul_btn.clicked.connect(self.soulseek_search)
        self.dl_nav_btn = QPushButton()
        self.dl_nav_btn.setToolTip("Downloads")
        self.dl_nav_btn.clicked.connect(lambda: self.open_downloads())
        for b in (self.soul_btn, self.dl_nav_btn):
            b.setObjectName("transport")
            b.setFixedSize(36, 36)
            b.setIconSize(QSize(18, 18))
        row.addWidget(self.search, 1)
        row.addWidget(self.soul_btn)
        row.addWidget(self.dl_nav_btn)
        lv.addLayout(row)
        self.tree = LibraryTree(self)
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(0)
        self.tree.setRootIsDecorated(False)
        self.tree.setUniformRowHeights(False)
        self.tree.setAnimated(True)
        self.tree.setMouseTracking(True)
        self.tree.viewport().setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.tree.setItemDelegate(TreeRowDelegate(self))
        self.tree.itemExpanded.connect(self.on_artist_expanded)
        self.tree.currentItemChanged.connect(self.on_tree_select)
        self.tree.itemClicked.connect(self.on_tree_clicked)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.tree_menu)

        seg_row = QHBoxLayout()
        seg_row.setSpacing(0)
        self.seg_home = QPushButton("Home")
        self.seg_lib = QPushButton("Library")
        self.seg_pl = DropButton("Playlists", on_enter=lambda: self.set_left_view(2))
        self.seg_browse = QPushButton("Browse")
        self.seg_buttons = [self.seg_home, self.seg_lib, self.seg_pl, self.seg_browse]
        for i, b in enumerate(self.seg_buttons):
            b.setObjectName("seg")
            b.setCheckable(True)
            b.clicked.connect(lambda checked=False, i=i: self.set_left_view(i))
            seg_row.addWidget(b)
        seg_row.addStretch(1)
        self.sort_btn = QPushButton()
        self.sort_btn.setObjectName("link")
        self.sort_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sort_btn.setToolTip("Sort artists")
        sort_menu = QMenu(self)
        for mode in ("A-Z", "Recently added", "Most played"):
            sort_menu.addAction(mode).triggered.connect(lambda checked=False, m=mode: self.set_library_sort(m))
        self.sort_btn.setMenu(sort_menu)
        self.sort_btn.setText(self.cfg["library_sort"])
        seg_row.addWidget(self.sort_btn)
        self.seg_lib.setChecked(True)
        lv.addLayout(seg_row)

        self.left_stack = QStackedWidget()
        self.left_stack.addWidget(self.tree)
        pl_panel = QWidget()
        pv = QVBoxLayout(pl_panel)
        pv.setContentsMargins(0, 0, 0, 0)
        self.pl_list = PlaylistDropList(self)
        self.pl_list.itemClicked.connect(self.on_playlist_clicked)
        self.pl_list.currentItemChanged.connect(lambda cur, _p: self.on_playlist_clicked(cur))
        self.pl_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.pl_list.customContextMenuRequested.connect(self.playlist_list_menu)
        pv.addWidget(self.pl_list, 1)
        new_pl = QPushButton("+ New playlist")
        new_pl.clicked.connect(lambda: self.new_playlist(show=True))
        pv.addWidget(new_pl)
        self.left_stack.addWidget(pl_panel)
        self.browse_list = QListWidget()
        self.browse_list.itemClicked.connect(self.on_browse_clicked)
        self.left_stack.addWidget(self.browse_list)
        lv.addWidget(self.left_stack, 1)
        splitter.addWidget(left)

        # right: stacked pages (album view / soulseek results)
        self.stack = FadeStack()
        self.stack.on_resize = self.position_drawer
        self.stack.on_raise = self.raise_drawer
        splitter.addWidget(self.stack)
        splitter.setSizes([340, 760])
        outer.addWidget(splitter, 1)

        # page 0: album
        album_page = QWidget()
        av = QVBoxLayout(album_page)
        head = QHBoxLayout()
        self.cover_label = QLabel()
        self.cover_label.setFixedSize(220, 220)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info = QVBoxLayout()
        self.album_title = QLabel("Pick an album")
        self.album_title.setObjectName("heading")
        self.album_title.setWordWrap(True)
        self.album_sub = QLabel("")
        self.album_sub.setObjectName("sub")
        self.album_sub.setTextFormat(Qt.TextFormat.RichText)
        self.album_sub.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self.album_sub.linkActivated.connect(self.on_link)
        info.addStretch(1)
        info.addWidget(self.album_title)
        info.addWidget(self.album_sub)
        abtns = QHBoxLayout()
        self.album_play_btn = QPushButton(" Play album")
        self.album_play_btn.setObjectName("primary")
        self.album_play_btn.clicked.connect(lambda: self.play_album(shuffle=False))
        self.album_shuffle_btn = QPushButton("Shuffle album")
        self.album_shuffle_btn.clicked.connect(lambda: self.play_album(shuffle=True))
        abtns.addWidget(self.album_play_btn)
        abtns.addWidget(self.album_shuffle_btn)
        abtns.addStretch(1)
        info.addSpacing(6)
        info.addLayout(abtns)
        info.addStretch(1)
        head.addWidget(self.cover_label)
        head.addSpacing(16)
        head.addLayout(info, 1)
        head.setContentsMargins(18, 18, 18, 18)
        self.album_header = BackdropWidget(radius=12)
        self.album_header.setLayout(head)
        av.addWidget(self.album_header)
        self.track_table = SongTable(0, 5, lambda rows: [self.albums[self.current_album]['tracks'][r]['path']
                                                          for r in rows if self.current_album in self.albums
                                                          and r < len(self.albums[self.current_album]['tracks'])])
        self.track_table.setHorizontalHeaderLabels(["#", "", "Title", "Plays", "Length"])
        self.track_table.setIconSize(QSize(16, 16))
        self.track_table.cellClicked.connect(self.on_track_cell_clicked)
        self.track_table.verticalHeader().setVisible(False)
        self.track_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.track_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        th = self.track_table.horizontalHeader()
        th.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        th.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.track_table.setColumnWidth(1, 34)
        th.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        th.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        th.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.track_table.cellDoubleClicked.connect(self.on_track_double_clicked)
        self.track_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.track_table.customContextMenuRequested.connect(self.album_table_menu)
        av.addWidget(self.track_table, 1)
        self.stack.addWidget(album_page)

        # page 1: soulseek results
        soul_page = QWidget()
        sv = QVBoxLayout(soul_page)
        srow = QHBoxLayout()
        self.soul_status = QLabel("")
        self.soul_status.setObjectName("heading3")
        back = self.back_button()
        back.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        self.dl_btn = QPushButton("Download selected")
        self.dl_btn.setObjectName("primary")
        self.dl_btn.clicked.connect(self.download_selected)
        srow.addWidget(back)
        srow.addWidget(self.soul_status, 1)
        disco_btn = QPushButton("Whole discography...")
        disco_btn.setToolTip("Find and download every album by an artist")
        disco_btn.clicked.connect(self.start_discography)
        srow.addWidget(disco_btn)
        srow.addWidget(self.dl_btn)
        sv.addLayout(srow)
        frow = QHBoxLayout()
        self.view_combo = QComboBox()
        self.view_combo.addItems(["Albums", "Files"])
        self.fmt_combo = QComboBox()
        self.fmt_combo.addItems(FORMAT_OPTIONS)
        self.free_check = QCheckBox("Free slots only")
        for w in (QLabel("Show:"), self.view_combo, QLabel("Quality:"),
                  self.fmt_combo, self.free_check):
            frow.addWidget(w)
        frow.addStretch(1)
        sv.addLayout(frow)
        self.view_combo.currentIndexChanged.connect(lambda *_: self.render_soul())
        self.fmt_combo.currentIndexChanged.connect(lambda *_: self.render_soul())
        self.free_check.stateChanged.connect(lambda *_: self.render_soul())
        cols = ["File", "Folder", "User", "Quality", "Size", "Slot / speed"]
        self.soul_table = QTableWidget(0, len(cols))
        self.soul_table.setHorizontalHeaderLabels(cols)
        self.soul_table.verticalHeader().setVisible(False)
        self.soul_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.soul_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.soul_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        sh = self.soul_table.horizontalHeader()
        sh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        sh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for c in (2, 3, 4, 5):
            sh.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self.soul_table.cellDoubleClicked.connect(lambda *_: self.download_selected())
        sv.addWidget(self.soul_table, 1)
        self.stack.addWidget(soul_page)

        # page 2: downloads manager
        dl_page = QWidget()
        dv = QVBoxLayout(dl_page)
        drow = QHBoxLayout()
        self.dl_status = QLabel("Downloads")
        self.dl_status.setObjectName("heading3")
        retry_btn = QPushButton("Retry failed")
        retry_btn.clicked.connect(self.retry_failed)
        clear_btn = QPushButton("Clear finished")
        clear_btn.clicked.connect(self.clear_finished)
        remove_btn = QPushButton("Cancel / remove selected")
        remove_btn.clicked.connect(self.remove_selected_downloads)
        back2 = self.back_button()
        back2.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        drow.addWidget(back2)
        drow.addWidget(self.dl_status, 1)
        for w in (retry_btn, clear_btn, remove_btn):
            drow.addWidget(w)
        dv.addLayout(drow)
        self.dl_table = QTableWidget(0, 4)
        self.dl_table.setHorizontalHeaderLabels(["File", "From user", "Status", "Progress"])
        self.dl_table.verticalHeader().setVisible(False)
        self.dl_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.dl_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.dl_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        dh = self.dl_table.horizontalHeader()
        dh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in (1, 2, 3):
            dh.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        dv.addWidget(self.dl_table, 1)
        self.stack.addWidget(dl_page)

        # page 3: lyrics
        ly_page = LyricsPage()
        self.ly_page = ly_page
        yv = QVBoxLayout(ly_page)
        yrow = QHBoxLayout()
        yrow.setSpacing(14)
        self.lyrics_cover = QLabel()
        self.lyrics_cover.setFixedSize(96, 96)
        titles = QVBoxLayout()
        titles.addStretch(1)
        self.lyrics_title = QLabel("Lyrics")
        self.lyrics_title.setObjectName("heading2")
        self.lyrics_title.setTextFormat(Qt.TextFormat.RichText)
        self.lyrics_title.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self.lyrics_title.linkActivated.connect(self.on_link)
        self.lyrics_title.setWordWrap(True)
        self.lyrics_source = QLabel("")
        self.lyrics_source.setObjectName("sub")
        self.lyrics_source.setTextFormat(Qt.TextFormat.RichText)
        self.lyrics_source.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self.lyrics_source.linkActivated.connect(self.on_link)
        titles.addWidget(self.lyrics_title)
        src_row = QHBoxLayout()
        src_row.setSpacing(8)
        src_row.addWidget(self.lyrics_source)
        fetch_link = QPushButton("Search online")
        fetch_link.setObjectName("link")
        fetch_link.setCursor(Qt.CursorShape.PointingHandCursor)
        fetch_link.setToolTip("Look these lyrics up on lrclib.net")
        fetch_link.clicked.connect(self.fetch_lyrics_online)
        src_row.addWidget(fetch_link)
        add_link = QPushButton("Add manually")
        add_link.setObjectName("link")
        add_link.setCursor(Qt.CursorShape.PointingHandCursor)
        add_link.setToolTip("Open the song's folder so you can save your own lyrics next to it")
        add_link.clicked.connect(self.add_lyrics_manually)
        src_row.addWidget(add_link)
        src_row.addStretch(1)
        titles.addLayout(src_row)
        titles.addStretch(1)
        back3 = self.back_button(light=True)
        back3.clicked.connect(self.toggle_lyrics)
        yrow.addWidget(back3, 0, Qt.AlignmentFlag.AlignTop)
        yrow.addWidget(self.lyrics_cover)
        yrow.addLayout(titles, 1)
        yv.addLayout(yrow)
        self.lyrics_list = QListWidget()
        self.lyrics_list.setObjectName("lyrics")
        self.lyrics_list.setItemDelegate(LyricDelegate(self))
        self.lyrics_list.verticalScrollBar().sliderPressed.connect(self.pause_lyric_follow)
        self.lyrics_list.setWordWrap(True)
        self.lyrics_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.lyrics_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.lyrics_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.lyrics_list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.scroll_anim = QPropertyAnimation(self.lyrics_list.verticalScrollBar(), b"value", self)
        self.scroll_anim.setDuration(260)
        self.scroll_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.line_in = QVariantAnimation(self)
        self.line_in.setDuration(170)
        self.line_in.valueChanged.connect(lambda c: self._paint_line(self._line_in_item, c))
        self.line_out = QVariantAnimation(self)
        self.line_out.setDuration(170)
        self.line_out.valueChanged.connect(lambda c: self._paint_line(self._line_out_item, c))
        self.lyrics_list.itemClicked.connect(self.on_lyric_clicked)
        yv.addWidget(self.lyrics_list, 1)
        self.ly_layout = yv
        self.ly_viz = Visualizer(ly_page, bars=56)
        self.ly_viz.setFixedHeight(70)
        self.ly_viz.hide()
        yv.addWidget(self.ly_viz)
        self.stack.addWidget(ly_page)

        # page 4: (the queue now lives in a side panel; this page stays so page numbers don't change)
        self.stack.addWidget(QWidget())
        self.drawer_scrim = ClickCatcher(self.stack, lambda: self.close_drawer())
        self.drawer = QueueDrawer(self, self.stack)
        dv2 = QVBoxLayout(self.drawer)
        dv2.setContentsMargins(18, 16, 14, 16)
        dv2.setSpacing(6)
        dh = QHBoxLayout()
        self.queue_title = QLabel("Up next")
        self.queue_title.setObjectName("heading2")
        self.drawer_close = QPushButton()
        self.drawer_close.setObjectName("transport")
        self.drawer_close.setFixedSize(30, 30)
        self.drawer_close.setIconSize(QSize(16, 16))
        self.drawer_close.setToolTip("Close (Esc)")
        self.drawer_close.clicked.connect(lambda: self.close_drawer())
        dh.addWidget(self.queue_title, 1)
        dh.addWidget(self.drawer_close)
        dv2.addLayout(dh)
        np_lab = QLabel("Now playing")
        np_lab.setObjectName("heading3")
        dv2.addWidget(np_lab)
        nrow = QHBoxLayout()
        self.drawer_cover = QLabel()
        self.drawer_cover.setFixedSize(48, 48)
        ntext = QVBoxLayout()
        self.drawer_title = QLabel("Nothing playing")
        self.drawer_title.setObjectName("nowplaying")
        self.drawer_artist = QLabel("")
        self.drawer_artist.setObjectName("sub")
        ntext.addWidget(self.drawer_title)
        ntext.addWidget(self.drawer_artist)
        nrow.addWidget(self.drawer_cover)
        nrow.addLayout(ntext, 1)
        dv2.addLayout(nrow)
        dv2.addSpacing(6)
        q_lab = QLabel("Next in queue")
        q_lab.setObjectName("heading3")
        dv2.addWidget(q_lab)
        self.queue_sub = QLabel("")
        self.queue_sub.setObjectName("sub")
        self.queue_sub.setWordWrap(True)
        dv2.addWidget(self.queue_sub)
        self.queue_list = QueueList(self)
        self.queue_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.queue_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.queue_list.model().rowsMoved.connect(self.on_queue_reordered)
        self.queue_list.itemDoubleClicked.connect(self.play_queued_item)
        dv2.addWidget(self.queue_list, 2)
        qbtns = QHBoxLayout()
        clear_btn2 = QPushButton("Clear")
        clear_btn2.clicked.connect(self.clear_queue)
        shuffle_q = QPushButton("Shuffle")
        shuffle_q.clicked.connect(lambda: self.shuffle_queue())
        qbtns.addWidget(shuffle_q)
        qbtns.addWidget(clear_btn2)
        qbtns.addStretch(1)
        dv2.addLayout(qbtns)
        self.drawer_timer = QTimer(self)
        self.drawer_timer.setInterval(600)
        self.drawer_timer.timeout.connect(self.refresh_drawer_snapshot)

        # page 5: playlist
        pl_page = QWidget()
        plv = QVBoxLayout(pl_page)
        phead = QHBoxLayout()
        ptitles = QVBoxLayout()
        self.pl_title = QLabel("Playlist")
        self.pl_title.setObjectName("heading")
        self.pl_title.setWordWrap(True)
        self.pl_sub = QLabel("")
        self.pl_sub.setObjectName("sub")
        ptitles.addWidget(self.pl_title)
        ptitles.addWidget(self.pl_sub)
        play_pl = QPushButton(" Play")
        self.play_pl_btn = play_pl
        play_pl.setObjectName("primary")
        play_pl.clicked.connect(lambda: self.play_playlist(self.current_playlist))
        shuf_pl = QPushButton("Shuffle")
        shuf_pl.clicked.connect(lambda: self.play_playlist(self.current_playlist, shuffle=True))
        ren_pl = QPushButton("Rename")
        self.pl_ren_btn = ren_pl
        ren_pl.clicked.connect(lambda: self.rename_playlist(self.current_playlist))
        del_pl = QPushButton("Delete")
        self.pl_del_btn = del_pl
        del_pl.clicked.connect(lambda: self.delete_playlist(self.current_playlist))
        phead.addLayout(ptitles, 1)
        for w in (play_pl, shuf_pl, ren_pl, del_pl):
            phead.addWidget(w, 0, Qt.AlignmentFlag.AlignTop)
        plv.addLayout(phead)
        self.pl_table = SongTable(0, 5, lambda rows: [self.pl_paths[r] for r in rows if r < len(self.pl_paths)])
        self.pl_table.setHorizontalHeaderLabels(["#", "Title", "Artist", "Album", "Length"])
        self.pl_table.verticalHeader().setVisible(False)
        self.pl_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.pl_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.pl_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        ph = self.pl_table.horizontalHeader()
        ph.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        ph.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        ph.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        ph.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        ph.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.pl_table.cellDoubleClicked.connect(self.on_playlist_row_double_clicked)
        self.pl_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.pl_table.customContextMenuRequested.connect(self.playlist_table_menu)
        plv.addWidget(self.pl_table, 1)
        self.stack.addWidget(pl_page)

        # page 6: listening stats
        st_page = QWidget()
        stv = QVBoxLayout(st_page)
        shead = QHBoxLayout()
        st_title = QLabel("Listening stats")
        st_title.setObjectName("heading")
        self.stats_period = QComboBox()
        self.stats_period.addItems(["Last 7 days", "Last 30 days", "This year", "All time"])
        self.stats_period.setCurrentText("Last 30 days")
        self.stats_period.currentIndexChanged.connect(lambda *_: self.show_stats())
        st_back = self.back_button()
        st_back.clicked.connect(lambda: self.stack.setCurrentIndex(self.prev_page if self.prev_page != 6 else 0))
        shead.addWidget(st_back)
        shead.addWidget(st_title, 1)
        shead.addWidget(self.stats_period)
        stv.addLayout(shead)
        cards = QHBoxLayout()
        self.stat_cards = {}
        for ckey, caption in (("time", "Listening time"), ("plays", "Plays"),
                              ("songs", "Different songs"), ("days", "Days you listened")):
            card = QFrame()
            card.setObjectName("card")
            cl = QVBoxLayout(card)
            num = QLabel("0")
            num.setObjectName("statnum")
            cap = QLabel(caption)
            cap.setObjectName("sub")
            cl.addWidget(num)
            cl.addWidget(cap)
            cards.addWidget(card)
            self.stat_cards[ckey] = num
        stv.addLayout(cards)
        self.stats_hint = QLabel("")
        self.stats_hint.setObjectName("sub")
        stv.addWidget(self.stats_hint)
        tables = QHBoxLayout()
        self.top_songs = self.make_stats_table(["Song", "Artist", "Plays"])
        self.top_artists = self.make_stats_table(["Artist", "Plays"])
        self.top_albums = self.make_stats_table(["Album", "Artist", "Plays"])
        for caption, table in (("Top songs", self.top_songs), ("Top artists", self.top_artists),
                               ("Top albums", self.top_albums)):
            col = QVBoxLayout()
            lab = QLabel(caption)
            lab.setObjectName("heading3")
            col.addWidget(lab)
            col.addWidget(table, 1)
            tables.addLayout(col, 1)
        stv.addLayout(tables, 1)
        self.stack.addWidget(st_page)

        # page 7: artist
        ar_page = QWidget()
        arv = QVBoxLayout(ar_page)
        self.artist_header = BackdropWidget(radius=12)
        ah = QHBoxLayout(self.artist_header)
        ah.setContentsMargins(18, 18, 18, 18)
        ah.setSpacing(18)
        self.artist_avatar = QLabel()
        self.artist_avatar.setFixedSize(120, 120)
        at = QVBoxLayout()
        self.artist_title = QLabel("")
        self.artist_title.setObjectName("heading")
        self.artist_title.setWordWrap(True)
        self.artist_sub = QLabel("")
        self.artist_sub.setObjectName("sub")
        abt = QHBoxLayout()
        self.artist_play_btn = QPushButton(" Play all")
        self.artist_play_btn.setObjectName("primary")
        self.artist_play_btn.clicked.connect(lambda: self.play_artist(shuffle=False))
        art_shuf = QPushButton("Shuffle")
        art_shuf.clicked.connect(lambda: self.play_artist(shuffle=True))
        abt.addWidget(self.artist_play_btn)
        abt.addWidget(art_shuf)
        abt.addStretch(1)
        at.addStretch(1)
        at.addWidget(self.artist_title)
        at.addWidget(self.artist_sub)
        at.addSpacing(6)
        at.addLayout(abt)
        at.addStretch(1)
        ah.addWidget(self.artist_avatar)
        ah.addLayout(at, 1)
        arv.addWidget(self.artist_header)
        abody = QHBoxLayout()
        gcol = QVBoxLayout()
        glab = QLabel("Albums")
        glab.setObjectName("heading3")
        self.artist_grid = self.make_tile_list(140, wrap=True)
        gcol.addWidget(glab)
        gcol.addWidget(self.artist_grid, 1)
        tcol = QVBoxLayout()
        tlab = QLabel("Most played")
        tlab.setObjectName("heading3")
        self.artist_top = SongTable(0, 3, lambda rows: [self.artist_top_paths[r] for r in rows
                                                         if r < len(self.artist_top_paths)])
        self.artist_top.setHorizontalHeaderLabels(["Song", "Album", "Plays"])
        self.artist_top.verticalHeader().setVisible(False)
        self.artist_top.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.artist_top.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        ath = self.artist_top.horizontalHeader()
        ath.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        ath.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        ath.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.artist_top.cellDoubleClicked.connect(
            lambda r, _c: self.play_paths(self.artist_top_paths, self.artists.get(self.current_artist, ""), start=r))
        tcol.addWidget(tlab)
        tcol.addWidget(self.artist_top, 1)
        abody.addLayout(gcol, 3)
        abody.addLayout(tcol, 2)
        arv.addLayout(abody, 1)
        self.stack.addWidget(ar_page)

        # page 8: home
        home = QWidget()
        hv = QVBoxLayout(home)
        hv.setContentsMargins(4, 4, 4, 4)
        self.home_title = QLabel("Welcome")
        self.home_title.setObjectName("heading")
        self.home_sub = QLabel("")
        self.home_sub.setObjectName("sub")
        hv.addWidget(self.home_title)
        hv.addWidget(self.home_sub)
        hv.addSpacing(8)
        self.home_rows = {}
        for row_key, caption in (("played", "Recently played"), ("added", "Recently added"),
                                 ("favorites", "Favorites")):
            lab = QLabel(caption)
            lab.setObjectName("heading3")
            lst = self.make_tile_list(120, wrap=False)
            hv.addWidget(lab)
            hv.addWidget(lst)
            hv.addSpacing(6)
            self.home_rows[row_key] = (lab, lst)
        hv.addStretch(1)
        home_scroll = QScrollArea()
        home_scroll.setWidgetResizable(True)
        home_scroll.setFrameShape(QFrame.Shape.NoFrame)
        home_scroll.setWidget(home)
        self.stack.addWidget(home_scroll)

        # page 9: search results
        sr = QWidget()
        srv = QVBoxLayout(sr)
        self.search_title = QLabel("")
        self.search_title.setObjectName("heading2")
        search_hint = QLabel("Press Enter to also look on Soulseek.")
        search_hint.setObjectName("sub")
        srv.addWidget(self.search_title)
        srv.addWidget(search_hint)
        self.search_sections = {}
        for sec_key, caption, size in (("artists", "Artists", 84), ("albums", "Albums", 104)):
            lab = QLabel(caption)
            lab.setObjectName("heading3")
            lst = self.make_tile_list(size, wrap=False)
            srv.addWidget(lab)
            srv.addWidget(lst)
            self.search_sections[sec_key] = (lab, lst)
        songs_lab = QLabel("Songs")
        songs_lab.setObjectName("heading3")
        self.search_songs = SongTable(0, 4, lambda rows: [self.search_paths[r] for r in rows
                                                           if r < len(self.search_paths)])
        self.search_songs.setHorizontalHeaderLabels(["Title", "Artist", "Album", "Length"])
        self.search_songs.verticalHeader().setVisible(False)
        self.search_songs.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.search_songs.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        ssh = self.search_songs.horizontalHeader()
        for c in range(3):
            ssh.setSectionResizeMode(c, QHeaderView.ResizeMode.Stretch)
        ssh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.search_songs.cellDoubleClicked.connect(
            lambda r, _c: self.play_from_library(self.qindex[self.search_paths[r]])
            if r < len(self.search_paths) and self.search_paths[r] in self.qindex else None)
        self.search_songs.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.search_songs.customContextMenuRequested.connect(self.search_songs_menu)
        self.search_sections["songs"] = (songs_lab, self.search_songs)
        srv.addWidget(songs_lab)
        srv.addWidget(self.search_songs, 1)
        soul_row = QHBoxLayout()
        soul_lab = QLabel("From Soulseek")
        soul_lab.setObjectName("heading3")
        self.search_soul_status = QLabel("")
        self.search_soul_status.setObjectName("sub")
        self.search_soul_btn = QPushButton("Search Soulseek too")
        self.search_soul_btn.clicked.connect(lambda: self.search_soulseek_inline())
        self.search_soul_dl = QPushButton("Download selected")
        self.search_soul_dl.setObjectName("primary")
        self.search_soul_dl.clicked.connect(lambda: self.download_inline_selected())
        self.search_soul_dl.hide()
        soul_row.addWidget(soul_lab)
        soul_row.addWidget(self.search_soul_status, 1)
        soul_row.addWidget(self.search_soul_btn)
        soul_row.addWidget(self.search_soul_dl)
        srv.addLayout(soul_row)
        self.search_soul_table = QTableWidget(0, 5)
        self.search_soul_table.setHorizontalHeaderLabels(["Album / folder", "From user", "Tracks", "Quality", "Size"])
        self.search_soul_table.verticalHeader().setVisible(False)
        self.search_soul_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.search_soul_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.search_soul_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        sth = self.search_soul_table.horizontalHeader()
        sth.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in (1, 2, 3, 4):
            sth.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self.search_soul_table.setMaximumHeight(240)
        self.search_soul_table.cellDoubleClicked.connect(lambda r, _c: self.download_inline_rows([r]))
        self.search_soul_table.hide()
        srv.addWidget(self.search_soul_table)
        self.stack.addWidget(sr)

        # page 10: browse (a genre or a decade)
        br_page = QWidget()
        brv = QVBoxLayout(br_page)
        bhead = QHBoxLayout()
        btitles = QVBoxLayout()
        self.browse_title = QLabel("")
        self.browse_title.setObjectName("heading")
        self.browse_sub = QLabel("")
        self.browse_sub.setObjectName("sub")
        btitles.addWidget(self.browse_title)
        btitles.addWidget(self.browse_sub)
        self.browse_play_btn = QPushButton(" Play all")
        self.browse_play_btn.setObjectName("primary")
        self.browse_play_btn.clicked.connect(lambda: self.play_paths(self.browse_paths, self.browse_name))
        bshuf = QPushButton("Shuffle")
        bshuf.clicked.connect(lambda: self.play_paths(self.browse_paths, self.browse_name, shuffle=True))
        bhead.addLayout(btitles, 1)
        bhead.addWidget(self.browse_play_btn, 0, Qt.AlignmentFlag.AlignTop)
        bhead.addWidget(bshuf, 0, Qt.AlignmentFlag.AlignTop)
        brv.addLayout(bhead)
        self.browse_grid = self.make_tile_list(130, wrap=True)
        brv.addWidget(self.browse_grid, 1)
        self.stack.addWidget(br_page)

        # now playing + controls
        np_row = QHBoxLayout()
        self.np_cover = QLabel()
        self.np_cover.setFixedSize(56, 56)
        self.now_playing = QLabel("Nothing playing")
        self.now_playing.setObjectName("nowplaying")
        self.now_playing.setTextFormat(Qt.TextFormat.RichText)
        self.now_playing.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self.now_playing.linkActivated.connect(self.on_link)
        self.lyric_line = QLabel("")
        self.lyric_line.setObjectName("lyricline")
        np_text = QVBoxLayout()
        np_text.addWidget(self.now_playing)
        np_text.addWidget(self.lyric_line)
        self.fav_btn = QPushButton()
        self.fav_btn.setObjectName("transport")
        self.fav_btn.setFixedSize(40, 40)
        self.fav_btn.setIconSize(QSize(22, 22))
        self.fav_btn.clicked.connect(self.toggle_favorite_current)
        np_row.addWidget(self.np_cover)
        np_row.addLayout(np_text, 1)
        np_row.addWidget(self.fav_btn)
        outer.addLayout(np_row)

        seek_row = QHBoxLayout()
        self.time_label = QLabel("0:00")
        self.time_label.setObjectName("sub")
        self.seek = QSlider(Qt.Orientation.Horizontal)
        self.seek.setRange(0, 0)
        self.seek.sliderMoved.connect(lambda v: self.player.setPosition(v))
        self.total_label = QLabel("0:00")
        self.total_label.setObjectName("sub")
        self.total_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.total_label.setToolTip("Click to switch between song length and time left")
        seek_row.addWidget(self.time_label)
        seek_row.addWidget(self.seek, 1)
        seek_row.addWidget(self.total_label)
        outer.addLayout(seek_row)

        controls = QHBoxLayout()
        self.prev_btn = QPushButton()
        self.play_btn = QPushButton()
        self.next_btn = QPushButton()
        for b, size, icon, tip in ((self.prev_btn, 40, 20, "Previous (Ctrl+Left)"),
                                   (self.play_btn, 46, 22, "Play (Ctrl+P)"),
                                   (self.next_btn, 40, 20, "Next (Ctrl+Right)")):
            b.setFixedSize(size, size)
            b.setIconSize(QSize(icon, icon))
            b.setToolTip(tip)
        self.prev_btn.setObjectName("transport")
        self.play_btn.setObjectName("play")
        self.next_btn.setObjectName("transport")
        self.prev_btn.clicked.connect(self.prev_track)
        self.play_btn.clicked.connect(self.toggle_play)
        self.next_btn.clicked.connect(lambda: self.next_track(auto=False))
        self.shuffle = QPushButton()
        self.shuffle.setCheckable(True)
        self.shuffle.setChecked(bool(self.cfg["shuffle_on"]))
        self.shuffle.toggled.connect(self.on_shuffle_toggled)
        self.repeat_btn = QPushButton()
        self.repeat_btn.clicked.connect(self.toggle_repeat)
        for b in (self.shuffle, self.repeat_btn):
            b.setObjectName("transport")
            b.setFixedSize(40, 40)
            b.setIconSize(QSize(20, 20))
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(self.cfg["volume"])
        self.volume.setFixedWidth(120)
        self.volume.valueChanged.connect(self.set_volume)
        self.lyrics_btn = QPushButton("Lyrics")
        self.lyrics_btn.setObjectName("transport")
        self.lyrics_btn.clicked.connect(self.toggle_lyrics)
        self.queue_btn = DropButton("Queue", on_drop=lambda paths: self.queue_add(paths))
        self.queue_btn.setToolTip("Up next (drop songs here to queue them)")
        self.queue_btn.setObjectName("transport")
        self.queue_btn.clicked.connect(self.toggle_queue)
        for w in (self.prev_btn, self.play_btn, self.next_btn, self.shuffle, self.repeat_btn,
                  self.lyrics_btn, self.queue_btn):
            controls.addWidget(w)
        controls.addStretch(1)
        self.mute_btn = QPushButton()
        self.mute_btn.setFixedSize(40, 40)
        self.mute_btn.setIconSize(QSize(20, 20))
        self.mute_btn.setObjectName("transport")
        self.mute_btn.setToolTip("Mute / unmute (Ctrl+M)")
        self.mute_btn.clicked.connect(self.toggle_mute)
        self.eq_btn = QPushButton("EQ")
        self.eq_btn.setObjectName("transport")
        self.eq_btn.setToolTip("Equalizer (Ctrl+E)")
        self.eq_btn.clicked.connect(self.open_equalizer)
        self.mini_btn = QPushButton()
        self.mini_btn.setObjectName("transport")
        self.mini_btn.setFixedSize(40, 40)
        self.mini_btn.setIconSize(QSize(20, 20))
        self.mini_btn.setToolTip("Mini player (Ctrl+Shift+M)")
        self.mini_btn.clicked.connect(self.toggle_mini)
        self.vol_label = QLabel(f"{self.cfg['volume']}%")
        self.vol_label.setObjectName("sub")
        self.vol_label.setMinimumWidth(44)
        self.volume.sliderMoved.connect(
            lambda v: QToolTip.showText(QCursor.pos(), f"{v}%", self.volume))
        controls.addWidget(self.eq_btn)
        controls.addWidget(self.mini_btn)
        self.fs_btn = QPushButton()
        self.fs_btn.setObjectName("transport")
        self.fs_btn.setFixedSize(40, 40)
        self.fs_btn.setIconSize(QSize(20, 20))
        self.fs_btn.setToolTip("Fullscreen player (F11)")
        self.fs_btn.clicked.connect(lambda: self.toggle_fullscreen())
        controls.addWidget(self.fs_btn)
        controls.addWidget(self.mute_btn)
        controls.addWidget(self.volume)
        controls.addWidget(self.vol_label)
        outer.addLayout(controls)

        self.setCentralWidget(central)

    def build_menu(self):
        lib = self.menuBar().addMenu("&Library")
        for text, fn in (
            ("Add music folder...", self.add_folder),
            ("Rescan library", self.rescan),
            ("Remove all folders", self.clear_folders),
            ("Find missing covers online", self.start_cover_batch),
            ("Organize downloads now", self.organize_now),
            ("Back up eozMP...", self.backup_data),
            ("Restore from backup...", self.restore_data),
        ):
            act = QAction(text, self)
            act.triggered.connect(fn)
            lib.addAction(act)

        play = self   # these shortcuts work everywhere; they are listed under Help > Keyboard shortcuts
        for text, key, fn in (
            ("Play / Pause", "Ctrl+P", lambda: self.toggle_play()),
            ("Play / Pause (anywhere you are not typing)", "Space", lambda: self.toggle_play()),
            ("Next song", "Ctrl+Right", lambda: self.next_track(auto=False)),
            ("Previous song", "Ctrl+Left", lambda: self.prev_track()),
            ("Volume up", "Ctrl+Up", lambda: self.volume.setValue(self.volume.value() + 5)),
            ("Volume down", "Ctrl+Down", lambda: self.volume.setValue(self.volume.value() - 5)),
            ("Show / hide lyrics", "Ctrl+L", lambda: self.toggle_lyrics()),
            ("Show / hide queue", "Ctrl+U", lambda: self.toggle_queue()),
            ("Mute / unmute", "Ctrl+M", lambda: self.toggle_mute()),
            ("Fullscreen player", "F11", lambda: self.toggle_fullscreen()),
            ("Go back", "Alt+Left", lambda: self.go_back()),
            ("Go forward", "Alt+Right", lambda: self.go_forward()),
            ("Like / unlike song", "Ctrl+D", lambda: self.toggle_favorite_current()),
            ("Equalizer...", "Ctrl+E", lambda: self.open_equalizer()),
            ("Mini player", "Ctrl+Shift+M", lambda: self.toggle_mini()),
            ("Search", "Ctrl+F", lambda: self.search.setFocus()),
            ("Home", "Ctrl+H", lambda: self.show_home()),
        ):
            act = QAction(text, self)
            act.setShortcut(key)
            act.triggered.connect(fn)
            play.addAction(act)

        pls = self.menuBar().addMenu("&Playlists")
        act = QAction("New playlist...", self)
        act.setShortcut("Ctrl+N")
        act.triggered.connect(lambda: self.new_playlist(show=True))
        pls.addAction(act)
        act = QAction("Show my playlists", self)
        act.triggered.connect(lambda: self.set_left_view(2))
        pls.addAction(act)

        soul = self.menuBar().addMenu("&Soulseek")
        act = QAction("Settings...", self)
        act.triggered.connect(lambda: self.open_settings("Soulseek"))
        soul.addAction(act)

        stats = self.menuBar().addAction("S&tats")
        stats.triggered.connect(lambda: self.open_stats())
        prefs = self.menuBar().addAction("P&references")
        prefs.setShortcut("Ctrl+,")
        prefs.triggered.connect(lambda: self.open_settings())

        hlp = self.menuBar().addMenu("&Help")
        act = QAction("Keyboard shortcuts", self)
        act.setShortcut("F1")
        act.triggered.connect(lambda: self.show_shortcuts())
        hlp.addAction(act)
        act = QAction("About eozMP", self)
        act.triggered.connect(lambda: QMessageBox.about(
            self, "eozMP", "eozMP - eren's definitely (not) sketchy music player, customize and enjoy your music.\n\n"
            "Copyright (C) 2026 Eren. Free software under the GNU General Public License v3."))
        hlp.addAction(act)

    # ----- library
    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose your music folder")
        if folder and folder not in self.cfg["folders"]:
            self.cfg["folders"].append(folder)
            save_config(self.cfg)
            self.rescan()

    def clear_folders(self):
        self.cfg["folders"] = []
        save_config(self.cfg)
        self.rescan()

    def rescan(self):
        if self.scanning:
            self.rescan_pending = True
            return
        folders = list(self.cfg["folders"])
        dl = self.cfg.get("downloads_dir")
        if dl and dl not in folders:
            folders.append(dl)
        self.scanning = True
        self.statusBar().showMessage("Scanning library...")
        old = list(self.all_tracks)

        def job():
            tracks = scan_folders(folders, old)
            save_cache(tracks)
            return tracks

        w = Worker(job)
        w.ok.connect(self.on_scan_done)
        w.fail.connect(self.on_scan_failed)
        self.keep(w)

    def on_scan_done(self, tracks):
        self.scanning = False
        self.build_library(tracks)
        if self.rescan_pending:
            self.rescan_pending = False
            self.rescan()

    def on_scan_failed(self, msg):
        self.scanning = False
        self.statusBar().showMessage(f"Scan failed: {msg}")

    def build_library(self, tracks):
        self.all_tracks = tracks
        playing = None
        if 0 <= self.index < len(self.queue):
            playing = self.queue[self.index][0]["path"]
        expanded = {
            self.tree.topLevelItem(i).text(0)
            for i in range(self.tree.topLevelItemCount())
            if self.tree.topLevelItem(i).isExpanded()
        }
        self.albums, self.artists, self.cover_cache = {}, {}, {}
        group = bool(self.cfg["group_featured"])
        split = bool(self.cfg["split_collabs"])
        keep = {k.strip().lower() for k in self.cfg["keep_together"] if k.strip()}
        for t in tracks:
            raw = t.get("artist_raw")
            if raw is not None:
                t["artist"] = (main_artist(raw, split, keep) if group
                               else (raw.strip() or "Unknown Artist"))
            akey, alkey = t["artist"].lower(), t["album"].lower()
            self.artists.setdefault(akey, t["artist"])
            alb = self.albums.setdefault(
                (akey, alkey),
                {"artist": self.artists[akey], "album": t["album"], "tracks": []},
            )
            alb["tracks"].append(t)

        for alb in self.albums.values():
            alb["tracks"].sort(key=lambda t: (t["disc"], t["num"], t["title"].lower()))
            years = [t["year"] for t in alb["tracks"] if t["year"]]
            alb["year"] = min(years) if years else 0
            alb["search"] = [
                f"{alb['artist']} {alb['album']} {t['title']}".lower() for t in alb["tracks"]
            ]
        self.genres, self.decades = {}, {}
        for key, alb in self.albums.items():
            names = set()
            for t in alb["tracks"]:
                for g in re.split(r"\s*[;,]\s*|\s+/\s+", t.get("genre") or ""):
                    if g.strip():
                        names.add(g.strip())
            for g in names:
                entry = self.genres.setdefault(g.lower(), {"name": g, "albums": []})
                if key not in entry["albums"]:
                    entry["albums"].append(key)
            if alb["year"]:
                self.decades.setdefault(f"{alb['year'] // 10 * 10}s", []).append(key)

        ignore_the = bool(self.cfg["ignore_the"])

        def artist_sort(k):
            return k[4:] if ignore_the and k.startswith("the ") else k

        mode = self.cfg.get("library_sort", "A-Z")
        added, plays = {}, {}
        play_counts = self.stats["plays"]
        for (akey, _alkey), alb in self.albums.items():
            for t in alb["tracks"]:
                added[akey] = max(added.get(akey, 0), t.get("added", t.get("mtime", 0)))
                plays[akey] = plays.get(akey, 0) + play_counts.get(t["path"], {}).get("count", 0)
        if mode == "Recently added":
            artist_order = sorted(self.artists, key=lambda k: (-added.get(k, 0), artist_sort(k)))
        elif mode == "Most played":
            artist_order = sorted(self.artists, key=lambda k: (-plays.get(k, 0), artist_sort(k)))
        else:
            artist_order = sorted(self.artists, key=artist_sort)
        self.tree_artists = {}

        self.tree.blockSignals(True)
        self.tree.clear()
        self.tree_albums = {}
        self.queue, self.qindex = [], {}
        for akey in artist_order:
            a_item = QTreeWidgetItem([self.artists[akey]])
            a_item.setData(0, ARTIST_ROLE, akey)
            self.tree_artists[akey] = a_item
            bold = a_item.font(0)
            bold.setBold(True)
            a_item.setFont(0, bold)
            self.tree.addTopLevelItem(a_item)
            keys = [k for k in self.albums if k[0] == akey]
            keys.sort(key=lambda k: (self.albums[k]["year"] or 9999, k[1]))
            for number, key in enumerate(keys, start=1):
                alb = self.albums[key]
                al_item = QTreeWidgetItem([alb["album"]])
                al_item.setData(0, NUM_ROLE, number)
                al_item.setData(0, YEAR_ROLE, alb["year"] or 0)
                al_item.setToolTip(0, f"{alb['album']} ({alb['year']})" if alb["year"] else alb["album"])
                al_item.setData(0, KEY_ROLE, key)
                a_item.addChild(al_item)
                self.tree_albums[key] = al_item
                if self.list_covers():
                    al_item.setIcon(0, self.thumb_icon(key, 28, 6, request=False))
                for t in alb["tracks"]:
                    self.qindex[t["path"]] = len(self.queue)
                    self.queue.append((t, key))
        for i in range(self.tree.topLevelItemCount()):
            a_item = self.tree.topLevelItem(i)
            if a_item.text(0) in expanded:
                a_item.setExpanded(True)
        self.index = self.qindex.get(playing, -1) if playing else -1
        self.track_by_path = {t["path"]: (t, key) for t, key in self.queue}
        self.song_index = [(f"{t['title']} {t['artist']} {t['album']}".lower(), t["path"]) for t, _k in self.queue]
        if self.list_covers():
            for akey, a_item in self.tree_artists.items():
                a_item.setIcon(0, self.artist_icon(akey, 28))
        missing = [k for k in self.albums if k not in self.thumb_cache]
        self.thumbs.clear()
        self.thumbs.add([self.thumb_job(k) for k in missing])
        self.refresh_context()
        if self.current_album in self.tree_albums:
            item = self.tree_albums[self.current_album]
            item.parent().setExpanded(True)
            self.tree.setCurrentItem(item)
        self.tree.blockSignals(False)

        self.statusBar().showMessage(
            f"{len(tracks)} tracks - {len(self.artists)} artists - {len(self.albums)} albums"
            if tracks else "No music yet - use Library > Add music folder..."
        )
        self.apply_filter()
        if self.current_album in self.albums:
            self.show_album(self.current_album, switch=False)
        else:
            self.current_album = None
        self.refresh_playlist_list()
        if self.current_playlist in self.playlists and self.stack.currentIndex() == 5:
            self.show_playlist(self.current_playlist, switch=False)
        if not self.resumed and self.queue:
            self.resumed = True
            self.restore_queue()
            self.restore_last()
        if self.left_stack.currentIndex() == 2:
            self.refresh_browse_list()
        idx = self.stack.currentIndex()
        if idx == 8 or (idx == 0 and self.current_album is None):
            self.show_home()
        elif idx == 7 and self.current_artist in self.artists:
            self.show_artist(self.current_artist, switch=False)
        self.refresh_queue_view()

    def visible_album_count(self):
        n = 0
        for item in self.tree_albums.values():
            if not item.isHidden():
                n += 1
        return n

    def apply_filter(self):
        text = self.search.text().strip().lower()
        for i in range(self.tree.topLevelItemCount()):
            a_item = self.tree.topLevelItem(i)
            any_album = False
            for j in range(a_item.childCount()):
                al_item = a_item.child(j)
                alb = self.albums.get(al_item.data(0, KEY_ROLE))
                match = bool(alb) and (not text or any(text in s for s in alb["search"]))
                al_item.setHidden(not match)
                any_album = any_album or match
            a_item.setHidden(not any_album)
            if text:
                a_item.setExpanded(any_album)

    def on_enter(self):
        text = self.search.text().strip()
        if len(text) < 2:
            return
        self.search_timer.stop()
        self.run_search()
        if self.slskd_ready():
            self.search_soulseek_inline()
        else:
            self.statusBar().showMessage("Set up Soulseek in Preferences to search it too.", 6000)

    # ----- album page
    def cover_for(self, key):
        if key in self.cover_cache:
            return self.cover_cache[key]
        pix = None
        tracks = self.albums[key]["tracks"]
        candidates = [embedded_cover(t["path"]) for t in tracks[:3]]
        candidates.append(folder_cover(tracks[0]["path"]))
        candidates.append(read_cached_cover(self.albums[key]["artist"], self.albums[key]["album"]))
        for data in candidates:
            if data:
                p = QPixmap()
                if p.loadFromData(data):
                    pix = p
                    break
        self.cover_cache[key] = pix
        return pix

    def on_tree_select(self, item, _prev):
        if item is None:
            return
        key = item.data(0, KEY_ROLE)
        if key in self.albums:
            self.show_album(key)
        else:
            akey = item.data(0, ARTIST_ROLE)
            if akey in self.artists:
                self.show_artist(akey)

    def show_album(self, key, switch=True):
        alb = self.albums[key]
        self.current_album = key
        self.set_cover(self.cover_label, key, self.cover_px, self.radius(14))
        self.maybe_fetch_cover(key)
        total = sum(t["length"] for t in alb["tracks"])
        year = f" - {alb['year']}" if alb["year"] else ""
        self.album_title.setText(alb["album"])
        self.album_sub.setText(
            self.link(f"artist:{key[0]}", alb["artist"], "#ffffff", bold=True)
            + html.escape(year) + "<br>"
            + html.escape(f"{len(alb['tracks'])} tracks - {fmt_time(total * 1000)}")
        )
        self.album_header.set_backdrop(self.backdrop_for(key))
        self.track_table.setRowCount(len(alb["tracks"]))
        plays = self.stats["plays"]
        for r, t in enumerate(alb["tracks"]):
            num = str(t["num"]) if t["num"] != 9999 else ""
            count = plays.get(t["path"], {}).get("count", 0)
            vals = (num, "", t["title"], str(count) if count else "", fmt_time(t["length"] * 1000))
            for c, val in enumerate(vals):
                self.track_table.setItem(r, c, QTableWidgetItem(val))
        self.refresh_album_hearts()
        if switch:
            self.stack.setCurrentIndex(0)
            self.nav_note(("album", key))
        if 0 <= self.index < len(self.queue):
            cur, ckey = self.queue[self.index]
            if ckey == key:
                for r, t in enumerate(alb["tracks"]):
                    if t["path"] == cur["path"]:
                        self.track_table.selectRow(r)
                        break

    def on_track_cell_clicked(self, row, col):
        if col != 1 or self.current_album is None:
            return
        tracks = self.albums[self.current_album]["tracks"]
        if row < len(tracks):
            path = tracks[row]["path"]
            self.set_favorite([path], path not in self.fav_set)

    def refresh_album_hearts(self):
        if self.current_album not in self.albums:
            return
        for r, t in enumerate(self.albums[self.current_album]["tracks"]):
            item = self.track_table.item(r, 1)
            if item is None:
                continue
            fav = t["path"] in self.fav_set
            item.setIcon(make_icon("heart_fill" if fav else "heart",
                                   self.scheme["accent"] if fav else self.scheme["sub"]))
            item.setToolTip("Remove from Favorites" if fav else "Add to Favorites")

    def on_track_double_clicked(self, row, col):
        if self.current_album is None or col == 1:
            return
        track = self.albums[self.current_album]["tracks"][row]
        idx = self.qindex.get(track["path"])
        if idx is not None:
            self.play_from_library(idx)

    # ----- playback
    def play_index(self, idx, autoplay=True, start_pos=0, record=True):
        if not self.queue:
            return
        self.finalize_listen()
        self.index = idx % len(self.queue)
        track, key = self.queue[self.index]
        if record:
            if not self.history or self.history[-1] != track["path"]:
                self.history.append(track["path"])
                del self.history[:-500]
            self.fwd.clear()
        self.listen_path = track["path"]
        self.pending_seek = start_pos
        self.player.setSource(QUrl.fromLocalFile(track["path"]))
        if autoplay:
            self.player.play()
        self.set_now_playing(track)
        self.set_cover(self.np_cover, key, 56, self.radius(8))
        if self.current_album == key:
            for r, t in enumerate(self.albums[key]["tracks"]):
                if t["path"] == track["path"]:
                    self.track_table.selectRow(r)
                    break
        self.load_lyrics(track)
        self.update_heart()
        self.update_album_accent(key)
        self.update_mini()
        self.maybe_fetch_cover(key)
        self.update_drawer()
        self.update_fullscreen()
        self.update_tray()

    def toggle_play(self):
        state = self.player.playbackState()
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        elif self.player.source().isEmpty():
            if self.up_next:
                self.next_track()
            elif self.current_album is not None:
                first_track = self.albums[self.current_album]["tracks"][0]
                self.play_from_library(self.qindex[first_track["path"]])
            else:
                self.play_from_library(0)
        else:
            self.player.play()

    def next_track(self, auto=False):
        if not self.queue:
            return
        # 0) after going back, "next" walks forward through what you already heard
        while self.fwd:
            path = self.fwd.pop()
            idx = self.qindex.get(path)
            if idx is not None:
                self.history.append(path)
                if path in self.ctx_paths:
                    self.ctx_pos = self.ctx_paths.index(path)
                self.play_index(idx, record=False)
                return
        # 1) songs you queued always go first
        while self.up_next:
            path = self.up_next.pop(0)
            idx = self.qindex.get(path)
            if idx is not None:
                self.refresh_queue_view()
                self.play_index(idx)
                return
        self.refresh_queue_view()
        # 2) then the library / playlist you were playing from
        self.ensure_context()
        n = len(self.ctx_paths)
        if n == 0:
            return
        if self.shuffle.isChecked():
            current = self.current_path()
            if current:
                self.shuffle_played.add(current)
            self.ctx_pos = pick_shuffle(self.ctx_paths, self.shuffle_played, avoid=current)
            self.shuffle_played.add(self.ctx_paths[self.ctx_pos])
        elif self.ctx_pos + 1 >= n:
            if auto and self.cfg["repeat_mode"] != "all":
                self.player.stop()
                return
            self.ctx_pos = 0
        else:
            self.ctx_pos += 1
        self.play_ctx()

    def prev_track(self):
        """Never random: go back to the song you actually heard before."""
        if not self.queue:
            return
        if self.player.position() > 3000:
            self.player.setPosition(0)
            return
        if len(self.history) >= 2:
            current = self.history.pop()
            path = self.history[-1]
            idx = self.qindex.get(path)
            if idx is None:
                self.history.append(current)
                self.player.setPosition(0)
                return
            self.fwd.append(current)
            if path in self.ctx_paths:
                self.ctx_pos = self.ctx_paths.index(path)
            self.play_index(idx, record=False)
            return
        # nothing earlier in the history: step back through the list itself (in order)
        self.ensure_context()
        current = self.current_path()
        if not self.ctx_paths or current not in self.ctx_paths:
            self.player.setPosition(0)
            return
        pos = self.ctx_paths.index(current)
        if pos == 0:
            self.player.setPosition(0)
            return
        self.ctx_pos = pos - 1
        target = self.ctx_paths[self.ctx_pos]
        idx = self.qindex.get(target)
        if idx is None:
            self.player.setPosition(0)
            return
        self.fwd.append(current)
        self.history = [target]
        self.play_index(idx, record=False)

    # ----- play context (what plays after the queue) and the queue itself
    def set_library_context(self, idx):
        self.ctx_paths = [t["path"] for t, _ in self.queue]
        self.ctx_kind = ""
        self.ctx_pos = max(0, min(idx, len(self.ctx_paths) - 1)) if self.ctx_paths else 0
        self.shuffle_played = set()

    def play_from_library(self, idx):
        if not self.queue:
            return
        idx = idx % len(self.queue)
        self.set_library_context(idx)
        self.play_index(idx)

    def ensure_context(self):
        if not self.ctx_paths and self.queue:
            self.set_library_context(max(self.index, 0))

    def refresh_context(self):
        """Library was rebuilt: keep the context valid and keep our place in it."""
        anchor = self.ctx_paths[self.ctx_pos] if 0 <= self.ctx_pos < len(self.ctx_paths) else None
        if self.ctx_kind:
            self.ctx_paths = [p for p in self.ctx_paths if p in self.qindex]
        elif self.ctx_paths:
            self.ctx_paths = [t["path"] for t, _ in self.queue]
        self.history = [h for h in self.history if h in self.qindex]
        self.fwd = [f for f in self.fwd if f in self.qindex]
        if anchor in self.ctx_paths:
            self.ctx_pos = self.ctx_paths.index(anchor)
        else:
            self.ctx_pos = min(self.ctx_pos, max(0, len(self.ctx_paths) - 1))

    def play_ctx(self):
        n = len(self.ctx_paths)
        for _ in range(n):
            idx = self.qindex.get(self.ctx_paths[self.ctx_pos])
            if idx is not None:
                self.play_index(idx)
                return
            self.ctx_pos = (self.ctx_pos + 1) % n

    def toggle_page(self, page):
        if self.stack.currentIndex() == page:
            self.stack.setCurrentIndex(self.prev_page)
        else:
            self.prev_page = self.stack.currentIndex()
            self.stack.setCurrentIndex(page)
            if page == 3:
                self.nav_note(("lyrics",))

    def toggle_queue(self):
        if self.drawer.isVisible():
            self.close_drawer()
        else:
            self.open_drawer()

    def queue_add(self, paths, play_next=False):
        paths = [p for p in paths if p in self.qindex]
        if not paths:
            return
        if play_next:
            self.up_next[0:0] = paths
        else:
            self.up_next.extend(paths)
        self.refresh_queue_view()
        what = "Playing next" if play_next else "Added to queue"
        self.statusBar().showMessage(f"{what}: {len(paths)} song(s)")

    def refresh_queue_view(self):
        self.up_next = [p for p in self.up_next if p in self.track_by_path]
        self.queue_list.clear()
        for path in self.up_next:
            t, _ = self.track_by_path[path]
            item = QListWidgetItem(f"{t['title']}  -  {t['artist']}")
            item.setData(KEY_ROLE, path)
            self.queue_list.addItem(item)
        n = len(self.up_next)
        self.queue_btn.setText(f"Queue ({n})" if n else "Queue")
        after = f"\"{self.ctx_kind}\"" if self.ctx_kind else "your library"
        self.queue_sub.setText(
            (f"{n} song{'s' if n != 1 else ''}  ·  {self.queue_length_text()}  -  drag to reorder. "
             if n else "Nothing queued. ")
            + f"After the queue, playback continues with {after}."
        )
        self.update_mini_next()
        self.update_drawer()

    def on_queue_reordered(self, *_args):
        self.up_next = [
            self.queue_list.item(i).data(KEY_ROLE) for i in range(self.queue_list.count())
        ]

    def remove_from_queue(self):
        rows = sorted({i.row() for i in self.queue_list.selectedIndexes()}, reverse=True)
        for r in rows:
            if r < len(self.up_next):
                del self.up_next[r]
        self.refresh_queue_view()

    def remove_queue_row(self, row):
        if 0 <= row < len(self.up_next):
            del self.up_next[row]
            self.refresh_queue_view()

    def clear_queue(self):
        self.up_next = []
        self.refresh_queue_view()

    def play_queued_item(self, item):
        row = self.queue_list.row(item)
        if 0 <= row < len(self.up_next):
            path = self.up_next.pop(row)
            self.refresh_queue_view()
            idx = self.qindex.get(path)
            if idx is not None:
                self.play_index(idx)

    def restore_queue(self):
        if self.cfg["resume"]:
            self.up_next = [p for p in self.cfg.get("queue", []) if p in self.qindex]

    def set_volume(self, value):
        self.audio.setVolume(value / 100)
        self.cfg["volume"] = value
        save_config(self.cfg)
        if value and self.audio.isMuted():
            self.audio.setMuted(False)
        self.update_mute_icon()

    def toggle_mute(self):
        self.audio.setMuted(not self.audio.isMuted())
        self.update_mute_icon()

    def update_mute_icon(self):
        v = self.volume.value()
        muted = self.audio.isMuted()
        kind = "vol_mute" if (muted or v == 0) else ("vol_low" if v < 50 else "vol_high")
        self.mute_btn.setIcon(make_icon(kind, self.icon_fg))
        self.vol_label.setText("Muted" if muted else f"{v}%")
        if self.fs_active and self.fs is not None:
            self.fs.vol.blockSignals(True)
            self.fs.vol.setValue(v)
            self.fs.vol.blockSignals(False)
            self.fs.vol_btn.setIcon(make_icon(kind, "#ffffff"))

    def on_position(self, pos):
        if not self.seek.isSliderDown():
            self.seek.setValue(pos)
        self.time_label.setText(fmt_time(pos))
        if self.cfg["show_remaining"]:
            self.update_total_labels(pos)
        self.update_lyric_position(pos)
        # listening stats: count only time actually played (seeking doesn't count)
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState and self.last_pos is not None:
            step = pos - self.last_pos
            if 0 < step < 2000:
                self.listen_ms += step
        self.last_pos = pos
        if self.mini is not None and self.mini.isVisible():
            dur = self.seek.maximum()
            self.mini.set_progress(pos / dur if dur else 0)
        if self.fs_active and self.fs is not None:
            self.update_fs_position(pos)

    def on_duration(self, dur):
        self.seek.setRange(0, dur)
        self.update_total_labels(self.player.position())

    def time_text(self, pos):
        dur = self.seek.maximum()
        if self.cfg["show_remaining"] and dur:
            return "-" + fmt_time(max(0, dur - pos))
        return fmt_time(dur)

    def update_total_labels(self, pos):
        text = self.time_text(pos)
        self.total_label.setText(text)
        if self.fs_active and self.fs is not None:
            self.fs.len_label.setText(text)

    def toggle_remaining(self):
        self.cfg["show_remaining"] = not self.cfg["show_remaining"]
        save_config(self.cfg)
        self.update_total_labels(self.player.position())

    def on_status(self, status):
        ready = (QMediaPlayer.MediaStatus.LoadedMedia, QMediaPlayer.MediaStatus.BufferedMedia)
        if status in ready and self.pending_seek:
            self.player.setPosition(self.pending_seek)
            self.pending_seek = 0
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self.cfg["repeat_mode"] == "one" and self.current_path():
                self.finalize_listen()
                self.listen_path = self.current_path()
                self.player.setPosition(0)
                self.player.play()
            elif self.cfg["autoplay_next"]:
                self.next_track(auto=True)
            else:
                self.player.stop()

    def on_state(self, state):
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.play_btn.setIcon(make_icon("pause" if playing else "play", self.scheme["on_accent"]))
        self.play_btn.setToolTip("Pause (Ctrl+P)" if playing else "Play (Ctrl+P)")
        if self.mini is not None:
            self.mini.set_icons(playing)
        self.update_tray()
        self.update_fullscreen()

    # ----- settings
    def open_settings(self, tab=None):
        dlg = PreferencesDialog(self.cfg, self, tab)
        if not dlg.exec():
            return False
        self.apply_prefs(dlg.values())
        return True

    def apply_prefs(self, values):
        old = dict(self.cfg)
        self.cfg.update(values)
        save_config(self.cfg)
        self.apply_settings()
        self.apply_soulseek_defaults()
        self.apply_equalizer()
        if old["media_keys"] != self.cfg["media_keys"]:
            if self.cfg["media_keys"]:
                self.register_media_keys()
            else:
                self.unregister_media_keys()
        if self.mini is not None:
            self.mini.set_idle_opacity(int(self.cfg["mini_opacity"]) / 100)
        if old["audio_engine"] != self.cfg["audio_engine"]:
            self.vlc_error = ""
            self.switch_engine(self.cfg["audio_engine"])
        if any(old[k] != self.cfg[k] for k in ("slskd_url", "slskd_key", "downloads_dir")):
            self.last_done = None
        if old["folders"] != self.cfg["folders"] or old["downloads_dir"] != self.cfg["downloads_dir"]:
            self.rescan()
        elif (old["group_featured"] != self.cfg["group_featured"]
              or old["ignore_the"] != self.cfg["ignore_the"]
              or old["album_list_style"] != self.cfg["album_list_style"]
              or old["split_collabs"] != self.cfg["split_collabs"]
              or old["keep_together"] != self.cfg["keep_together"]):
            self.build_library(self.all_tracks)
        if (not old["lyrics_online"] and self.cfg["lyrics_online"]
                and 0 <= self.index < len(self.queue) and not self.lyric_lines):
            self.load_lyrics(self.queue[self.index][0])

    def radius(self, r):
        return int(round(r * self.corner))

    def apply_settings(self):
        app = QApplication.instance()
        if self.cfg["ui_font"] == SYSTEM_FONT_TAG:
            ui = QFont(SYSTEM_FONT_FAMILY)
        elif self.cfg["ui_font"]:
            ui = QFont(self.cfg["ui_font"])
        else:
            ui = pick_ui_font() or QFont(app.font())
        ui.setPointSize(int(self.cfg["ui_font_size"]))
        app.setFont(ui)
        self.display_family = ui.family()     # headings follow the app font
        self.corner = CORNER_FACTORS.get(self.cfg["corner_style"], 1.0)
        self.cover_px = COVER_SIZES.get(self.cfg["cover_size"], 220)
        self.cover_label.setFixedSize(self.cover_px, self.cover_px)
        self.stack.animate = bool(self.cfg["page_fade"])
        if self.fs is not None:
            self.fs.style_for(self.scheme) if self.fs_active else None
        self.lyric_line.setVisible(bool(self.cfg["show_lyric_line"]))
        if self.cfg["accent"] == ALBUM_ART_ACCENT and self.current_key() is not None:
            self.album_accent = self.accent_for_key(self.current_key())
        self.refresh_colors()
        if self.current_album in self.albums:
            self.show_album(self.current_album, switch=False)

    def refresh_colors(self):
        """Re-colour everything (theme, accent, icons, covers). Runs on song change in album-art mode."""
        app = QApplication.instance()
        self.scheme = apply_look(
            app, self.cfg["theme"], self.accent_hex(), self.system_dark,
            style_tokens(self.cfg, self.display_family),
        )
        self.apply_lyrics_look()
        self.refresh_icons()
        self.album_header.setStyleSheet(header_qss(self.scheme))
        self.artist_header.setStyleSheet(header_qss(self.scheme))
        if self.list_covers():
            for k, item in self.tree_albums.items():
                if self.thumb_cache.get(k) is None:
                    item.setIcon(0, self.thumb_icon(k, 28, 6, request=False))
            for ak, item in self.tree_artists.items():
                item.setIcon(0, self.artist_icon(ak, 28))
        self.refresh_album_hearts()
        self.tree_px.clear()
        self.neutral_cache.clear()
        self.tree.viewport().update()
        key = self.current_key()
        self.set_cover(self.np_cover, key, 56, self.radius(8))
        self.set_cover(self.lyrics_cover, key, 96, self.radius(10))
        self.update_lyrics_backdrop(key)
        if self.current_album not in self.albums:
            self.set_cover(self.cover_label, None, self.cover_px, self.radius(14))
        elif self.cover_for(self.current_album) is None:   # placeholder uses the accent
            self.set_cover(self.cover_label, self.current_album, self.cover_px, self.radius(14))
        self.update_mini()

    def refresh_icons(self):
        self.icon_fg = "#ffffff" if self.scheme.get("dark", True) else self.scheme["text"]
        self.prev_btn.setIcon(make_icon("prev", self.icon_fg))
        self.next_btn.setIcon(make_icon("next", self.icon_fg))
        playing = self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        self.play_btn.setIcon(make_icon("pause" if playing else "play", self.scheme["on_accent"]))
        self.play_pl_btn.setIcon(make_icon("play", self.scheme["on_accent"]))
        self.album_play_btn.setIcon(make_icon("play", self.scheme["on_accent"]))
        self.artist_play_btn.setIcon(make_icon("play", self.scheme["on_accent"]))
        self.mini_btn.setIcon(make_icon("mini", self.icon_fg))
        self.browse_play_btn.setIcon(make_icon("play", self.scheme["on_accent"]))
        self.soul_btn.setIcon(make_icon("search", self.icon_fg))
        for btn, light in self.back_buttons:
            btn.setIcon(make_icon("back", "#ffffff" if (light and self.lyrics_immersive) else self.icon_fg))
        self.update_downloads_badge()
        self.update_mode_buttons()
        self.update_mute_icon()
        self.update_heart()
        self.nav_back_btn.setIcon(make_icon("back", self.icon_fg))
        self.nav_fwd_btn.setIcon(make_icon("forward", self.icon_fg))
        self.drawer_close.setIcon(make_icon("close", self.icon_fg))
        self.fs_btn.setIcon(make_icon("fullscreen", self.icon_fg))
        self.update_nav_buttons()
        if 0 <= self.index < len(self.queue):
            self.set_now_playing(self.queue[self.index][0])
        self.set_lyrics_header()

    def apply_lyrics_look(self):
        apple = self.cfg["lyrics_style"] != "Classic"
        immersive = apple or self.fs_active   # "Album art" style (and fullscreen) paint the blurred cover
        family = self.cfg.get("lyrics_font") or self.display_family
        if family == SYSTEM_FONT_TAG:
            family = SYSTEM_FONT_FAMILY
        size = int(round(int(self.cfg["lyrics_size"]) * (1.3 if self.fs_active else 1.0)))
        weight = LYRIC_WEIGHTS.get(self.cfg["lyrics_weight"], QFont.Weight.Bold)
        base = QFont(family)
        base.setPointSize(size)
        base.setWeight(weight)
        big = QFont(family)
        big.setPointSizeF(size * 1.3)
        big.setWeight(QFont.Weight.ExtraBold if self.cfg["lyrics_weight"] == "Heavy" else QFont.Weight.Bold)
        full = QColor("#ffffff") if immersive else QColor(self.scheme["text"])
        active = QColor(full) if apple else QColor(self.scheme["accent"])
        dim = QColor(full)
        dim.setAlpha(int(255 * int(self.cfg["lyrics_dim"]) / 100))
        self.lyric_look = (base, big, active, dim, full)
        if self.cfg["lyrics_align"] == "Center":
            self.lyric_align = Qt.AlignmentFlag.AlignCenter
        else:
            self.lyric_align = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        self.lyrics_immersive = immersive
        self.lyrics_list.setFont(base)
        self.lyrics_list.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff if immersive else Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.ly_page.setStyleSheet(lyrics_page_qss(apple, immersive))
        self.lyric_pad = (28, 10) if apple else (14, 8)
        self.set_lyrics_fade(bool(self.cfg["lyrics_fade"]))
        if getattr(self, "ly_viz", None) is not None:
            self.setup_visualizer()
        gap = "• • •" if apple else "♪"
        for i in range(len(self.lyric_lines)):
            item = self.lyrics_list.item(i + self.ly_off)
            if item is None:
                continue
            item.setTextAlignment(self.lyric_align)
            item.setText(self.lyric_lines[i] or gap)
        self.restyle_lyrics()

    def update_lyrics_backdrop(self, key):
        if not self.lyrics_immersive:
            self.ly_page.set_backdrop(None)
            return
        self.ly_page.set_backdrop(self.backdrop_for(key))

    def set_cover(self, label, key, size, radius):
        pix = self.cover_for(key) if key in self.albums else None
        label.setPixmap(
            rounded_pixmap(pix, size, radius) if pix
            else placeholder_cover(size, radius, self.scheme["accent"])
        )

    def style_lyric_item(self, item, active, synced):
        base, big, active_col, dim, full = self.lyric_look
        classic = self.cfg["lyrics_style"] == "Classic"
        item.setFont(big if (classic and active) else base)
        if active:
            item.setForeground(active_col)
        else:
            item.setForeground(dim if synced else full)

    def restyle_lyrics(self):
        synced = bool(self.lyric_times)
        for i in range(len(self.lyric_lines)):
            item = self.lyrics_list.item(i + self.ly_off)
            if item is not None:
                self.style_lyric_item(item, synced and i == self.lyric_idx, synced)
        self.lyrics_list.doItemsLayout()

    def pause_lyric_follow(self):
        """You scrolled the lyrics yourself: stop following for a few seconds."""
        self.lyric_hold_until = time.monotonic() + 4.0
        self.scroll_anim.stop()
        self.lyric_resume_timer.start(4000)

    def resume_lyric_follow(self):
        self.lyric_hold_until = 0.0
        item = self.lyrics_list.item(self.lyric_idx + self.ly_off) if 0 <= self.lyric_idx < len(self.lyric_lines) else None
        if item is not None:
            self.scroll_anim.setDuration(600)
            self.scroll_lyrics_to(item)
            self.scroll_anim.setDuration(260)

    def scroll_lyrics_to(self, item):
        if time.monotonic() < self.lyric_hold_until:
            return
        bar = self.lyrics_list.verticalScrollBar()
        rect = self.lyrics_list.visualItemRect(item)
        anchor = 0.5   # the current line always sits in the middle
        target = bar.value() + rect.center().y() - int(self.lyrics_list.viewport().height() * anchor)
        target = max(bar.minimum(), min(bar.maximum(), target))
        self.scroll_anim.stop()
        self.scroll_anim.setStartValue(bar.value())
        self.scroll_anim.setEndValue(target)
        self.scroll_anim.start()

    def apply_soulseek_defaults(self):
        self.view_combo.setCurrentText(self.cfg["soul_view"])
        self.fmt_combo.setCurrentText(self.cfg["soul_quality"])
        self.free_check.setChecked(bool(self.cfg["soul_free_only"]))

    def restore_last(self):
        if not self.cfg["resume"]:
            return
        idx = self.qindex.get(self.cfg.get("last_path"))
        if idx is None:
            return
        key = self.queue[idx][1]
        item = self.tree_albums.get(key)
        if item is not None:
            item.parent().setExpanded(True)
            self.tree.setCurrentItem(item)
        self.set_library_context(idx)
        self.play_index(idx, autoplay=False, start_pos=int(self.cfg.get("last_pos", 0)))

    def closeEvent(self, event):
        if (self.cfg["close_to_tray"] and not self.quitting and self.tray is not None
                and self.tray.isVisible()):
            event.ignore()
            self.hide()
            if not self.cfg.get("tray_hint_shown"):
                self.cfg["tray_hint_shown"] = True
                save_config(self.cfg)
                self.tray.showMessage("eozMP is still playing",
                                      "It's in the system tray. Right-click the icon to quit.",
                                      app_icon(), 4000)
            return
        try:
            if 0 <= self.index < len(self.queue):
                self.cfg["last_path"] = self.queue[self.index][0]["path"]
                self.cfg["last_pos"] = int(self.player.position())
            self.cfg["win_size"] = [self.width(), self.height()]
            self.cfg["queue"] = list(self.up_next)
            if self.mini is not None:
                if self.mini.isVisible():
                    self.cfg["mini_pos"] = [self.mini.x(), self.mini.y()]
                self.mini.close()
            save_config(self.cfg)
            self.finalize_listen()
            if self.cover_batch is not None:
                self.cover_batch.stop()
                self.cover_batch.wait(2000)
            self.thumbs.stop()
            self.thumbs.wait(2000)
            if self.fs is not None:
                self.fs.hide()
        except Exception:
            pass
        try:
            self.player.stop()
        except Exception:
            pass
        try:
            self.unregister_media_keys()
            if self.tray is not None:
                self.tray.hide()
        except Exception:
            pass
        super().closeEvent(event)
        QTimer.singleShot(0, QApplication.instance().quit)

    # ----- library list: covers, sorting, one artist open
    def thumb_job(self, key):
        alb = self.albums[key]
        return (key, [t["path"] for t in alb["tracks"][:3]], alb["artist"], alb["album"])

    def placeholder(self, size, radius):
        ck = (size, radius, self.scheme["accent"])
        if ck not in self.ph_cache:
            self.ph_cache[ck] = placeholder_cover(size, radius, self.scheme["accent"])
        return self.ph_cache[ck]

    def thumb_pixmap(self, key, size, radius, request=True):
        if key in self.thumb_cache:
            pix = self.thumb_cache[key]
            return rounded_pixmap(pix, size, radius) if pix is not None else self.placeholder(size, radius)
        if request and key in self.albums:
            self.thumbs.add([self.thumb_job(key)], front=True)
        return self.placeholder(size, radius)

    def thumb_icon(self, key, size, radius, request=True):
        return static_icon(self.thumb_pixmap(key, size, radius, request))

    def install_frame_delegates(self):
        for table in (self.track_table, self.pl_table, self.soul_table, self.dl_table,
                      self.artist_top, self.search_songs, self.search_soul_table):
            table.setItemDelegate(FrameDelegate(table, lambda: self.scheme["accent"],
                                                lambda: self.scheme["hover"],
                                                lambda: self.current_path(), lambda: self.np_phase))
        self.track_table.number_col = True
        self.pl_table.number_col = True

    def list_covers(self):
        return False   # covers in the library list are drawn by TreeRowDelegate

    def artist_cover_key(self, akey):
        keys = [k for k in self.albums if k[0] == akey]
        keys.sort(key=lambda k: (self.albums[k]["year"] or 9999, k[1]))
        for k in keys:
            if self.thumb_cache.get(k) is not None:
                return k
        return keys[0] if keys else None

    def artist_pixmap(self, akey, size):
        key = self.artist_cover_key(akey)
        if key is not None and self.thumb_cache.get(key) is not None:
            return rounded_pixmap(self.thumb_cache[key], size, size // 2)
        return avatar_pixmap(self.artists.get(akey, "?"), size, self.scheme["raised"], self.scheme["text"])

    def artist_icon(self, akey, size):
        return static_icon(self.artist_pixmap(akey, size))

    def on_thumb_loaded(self, key, data):
        pix = None
        if data:
            img = QPixmap()
            if img.loadFromData(data):
                pix = rounded_pixmap(img, 160, 0)
        self.thumb_cache[key] = pix
        self.tree_px.pop(key, None)
        if key in self.tree_albums:
            self.tree.viewport().update()
        item = self.tree_albums.get(key)
        if item is not None and self.list_covers():
            item.setIcon(0, self.thumb_icon(key, 28, 6, request=False))
        a_item = self.tree_artists.get(key[0])
        if a_item is not None and pix is not None and self.list_covers():
            a_item.setIcon(0, self.artist_icon(key[0], 28))
        for view in self.view_targets.values():
            for target, size, radius, circle in view.get(key, []):
                try:
                    if circle:
                        target.setIcon(self.artist_icon(key[0], size))
                    else:
                        target.setIcon(self.thumb_icon(key, size, radius, request=False))
                except RuntimeError:
                    pass
        if self.stack.currentIndex() == 7 and key == self.artist_avatar_key:
            self.artist_avatar.setPixmap(self.artist_pixmap(self.current_artist, 120))

    def set_library_sort(self, mode):
        self.cfg["library_sort"] = mode
        save_config(self.cfg)
        self.sort_btn.setText(mode)
        self.build_library(self.all_tracks)

    def on_artist_expanded(self, item):
        if item.parent() is not None or self.search.text().strip():
            return
        for i in range(self.tree.topLevelItemCount()):
            other = self.tree.topLevelItem(i)
            if other is not item and other.isExpanded():
                other.setExpanded(False)

    def backdrop_for(self, key):
        pix = self.cover_for(key) if key in self.albums else None
        ck = (key, None if pix is not None else self.scheme["accent"])
        if ck not in self.backdrop_cache:
            if len(self.backdrop_cache) > 24:
                self.backdrop_cache.clear()
            self.backdrop_cache[ck] = make_backdrop(pix, self.scheme["accent"])
        return self.backdrop_cache[ck]

    # ----- playing a list of songs (artist, album, search...)
    def play_paths(self, paths, name, start=0, shuffle=False):
        paths = [p for p in paths if p in self.qindex]
        if not paths:
            return
        if shuffle:
            random.shuffle(paths)
            start = 0
        self.ctx_paths, self.ctx_kind = paths, name or "list"
        self.ctx_pos = max(0, min(start, len(paths) - 1))
        self.shuffle_played = set()
        self.play_index(self.qindex[paths[self.ctx_pos]])
        self.refresh_queue_view()

    # ----- tiles (artist page, home, search)
    def make_tile_list(self, size, wrap):
        lst = QListWidget()
        lst.setObjectName("tiles")
        lst.setViewMode(QListWidget.ViewMode.IconMode)
        lst.setIconSize(QSize(size, size))
        lst.setGridSize(QSize(size + 24, size + 56))
        lst.setMovement(QListWidget.Movement.Static)
        lst.setResizeMode(QListWidget.ResizeMode.Adjust)
        lst.setWordWrap(True)
        lst.setUniformItemSizes(True)
        lst.setTextElideMode(Qt.TextElideMode.ElideRight)
        lst.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        lst.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        if not wrap:
            lst.setFlow(QListWidget.Flow.LeftToRight)
            lst.setWrapping(False)
            lst.setFixedHeight(size + 80)
            lst.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        lst.itemClicked.connect(self.on_tile_clicked)
        lst.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        lst.customContextMenuRequested.connect(lambda pos, l=lst: self.tile_menu(l, pos))
        return lst

    def add_tile(self, lst, view, kind, value, text, size, radius=None):
        item = QListWidgetItem(text)
        item.setData(KEY_ROLE, (kind, value))
        item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        item.setToolTip(text.replace("\n", " - "))
        r = self.radius(10) if radius is None else radius
        if kind == "artist":
            item.setIcon(self.artist_icon(value, size))
            key = self.artist_cover_key(value)
            if key is not None:
                self.view_targets[view].setdefault(key, []).append((item, size, r, True))
                if key not in self.thumb_cache:
                    self.thumbs.add([self.thumb_job(key)], front=True)
        else:
            key = value if kind == "album" else self.track_by_path[value][1]
            item.setIcon(self.thumb_icon(key, size, r))
            self.view_targets[view].setdefault(key, []).append((item, size, r, False))
        lst.addItem(item)

    def on_tile_clicked(self, item):
        kind, value = item.data(KEY_ROLE)
        if kind == "album" and value in self.albums:
            self.open_album(value)
        elif kind == "artist" and value in self.artists:
            self.show_artist(value)
        elif kind == "song" and value in self.qindex:
            lst = item.listWidget()
            songs = [lst.item(i).data(KEY_ROLE)[1] for i in range(lst.count())]
            self.play_paths(songs, "Favorites", start=lst.row(item))

    def tile_menu(self, lst, pos):
        item = lst.itemAt(pos)
        if item is None:
            return
        kind, value = item.data(KEY_ROLE)
        if kind == "album":
            paths = self.album_paths(value)
        elif kind == "artist":
            paths = [t["path"] for k in self.artist_album_keys(value) for t in self.albums[k]["tracks"]]
        else:
            paths = [value]
        if paths:
            self.track_menu(lst.viewport().mapToGlobal(pos), paths,
                            play_cb=lambda: self.play_paths(paths, item.text().split("\n")[0]))

    def open_album(self, key):
        item = self.tree_albums.get(key)
        if item is not None:
            self.set_left_view(1)
            item.parent().setExpanded(True)
            self.tree.blockSignals(True)
            self.tree.setCurrentItem(item)
            self.tree.blockSignals(False)
            self.tree.scrollToItem(item)
        self.show_album(key)

    # ----- artist page
    def artist_album_keys(self, akey):
        keys = [k for k in self.albums if k[0] == akey]
        keys.sort(key=lambda k: (self.albums[k]["year"] or 9999, k[1]))
        return keys

    def show_artist(self, akey, switch=True):
        self.current_artist = akey
        keys = self.artist_album_keys(akey)
        tracks = [t for k in keys for t in self.albums[k]["tracks"]]
        self.artist_paths = [t["path"] for t in tracks]
        plays = self.stats["plays"]
        total_plays = sum(plays.get(p, {}).get("count", 0) for p in self.artist_paths)
        sub = f"{len(keys)} album{'s' if len(keys) != 1 else ''}  ·  {len(tracks)} songs"
        if total_plays:
            sub += f"  ·  {total_plays} plays"
        self.artist_title.setText(self.artists[akey])
        self.artist_sub.setText(sub)
        self.artist_avatar_key = self.artist_cover_key(akey)
        self.artist_avatar.setPixmap(self.artist_pixmap(akey, 120))
        self.artist_header.set_backdrop(self.backdrop_for(self.artist_avatar_key))
        self.view_targets["artist"] = {}
        self.artist_grid.clear()
        for k in keys:
            alb = self.albums[k]
            text = alb["album"] + (f"\n{alb['year']}" if alb["year"] else "")
            self.add_tile(self.artist_grid, "artist", "album", k, text, 140)
        top = sorted((p for p in self.artist_paths if plays.get(p, {}).get("count")),
                     key=lambda p: -plays[p]["count"])[:10]
        if not top:
            top = self.artist_paths[:10]
        self.artist_top_paths = top
        self.artist_top.setRowCount(len(top))
        for r, path in enumerate(top):
            t = self.track_by_path[path][0]
            count = plays.get(path, {}).get("count", 0)
            for c, val in enumerate((t["title"], t["album"], str(count) if count else "")):
                self.artist_top.setItem(r, c, QTableWidgetItem(val))
        if switch:
            self.stack.setCurrentIndex(7)
            self.nav_note(("artist", akey))

    def play_artist(self, shuffle=False):
        if self.current_artist in self.artists:
            self.play_paths(self.artist_paths, self.artists[self.current_artist], shuffle=shuffle)

    # ----- home
    def show_home(self, switch=True):
        hour = time.localtime().tm_hour
        greet = ("Good night" if hour < 5 else "Good morning" if hour < 12
                 else "Good afternoon" if hour < 18 else "Good evening")
        self.home_title.setText(greet)
        if self.albums:
            self.home_sub.setText(f"{len(self.queue)} songs  ·  {len(self.artists)} artists  ·  "
                                  f"{len(self.albums)} albums in your library")
        else:
            self.home_sub.setText("Add your music from Library > Add music folder...")
        self.view_targets["home"] = {}
        # recently played albums
        played, seen = [], set()
        for _ts, path, _secs in reversed(self.stats["events"]):
            hit = self.track_by_path.get(path)
            if hit and hit[1] not in seen:
                seen.add(hit[1])
                played.append(hit[1])
                if len(played) >= 18:
                    break
        added = sorted(self.albums, key=lambda k: -max(t.get("added", t.get("mtime", 0))
                                                       for t in self.albums[k]["tracks"]))[:18]
        favs = [p for p in reversed(self.stats["favorites"]) if p in self.track_by_path][:24]
        rows = {"played": [("album", k) for k in played], "added": [("album", k) for k in added],
                "favorites": [("song", p) for p in favs]}
        for row_key, items in rows.items():
            lab, lst = self.home_rows[row_key]
            lst.clear()
            for kind, value in items:
                if kind == "album":
                    alb = self.albums[value]
                    text = f"{alb['album']}\n{alb['artist']}"
                else:
                    t = self.track_by_path[value][0]
                    text = f"{t['title']}\n{t['artist']}"
                self.add_tile(lst, "home", kind, value, text, 120)
            lab.setVisible(bool(items))
            lst.setVisible(bool(items))
        if switch:
            self.stack.setCurrentIndex(8)
            self.left_stack.setCurrentIndex(0)
            self.mark_tab(0)
            self.nav_note(("home",))

    # ----- search
    def run_search(self):
        text = self.search.text().strip()
        words = text.lower().split()
        if len(text) < 2:
            if self.stack.currentIndex() == 9:
                back = self.search_prev_page if self.search_prev_page != 9 else 8
                if back == 8:
                    self.show_home()
                else:
                    self.stack.setCurrentIndex(back)
            return
        if self.stack.currentIndex() != 9:
            self.search_prev_page = self.stack.currentIndex()
        if text != self.inline_soul_text:
            self.reset_inline_soul()

        def hit(s):
            return all(w in s for w in words)

        artists = [a for a, name in self.artists.items() if hit(name.lower())][:12]
        albums = [k for k, alb in self.albums.items() if hit(f"{alb['artist']} {alb['album']}".lower())][:18]
        songs = [path for s, path in self.song_index if hit(s)][:150]
        self.view_targets["search"] = {}
        lab, lst = self.search_sections["artists"]
        lst.clear()
        for a in artists:
            self.add_tile(lst, "search", "artist", a, self.artists[a], 84)
        lab.setVisible(bool(artists))
        lst.setVisible(bool(artists))
        lab, lst = self.search_sections["albums"]
        lst.clear()
        for k in albums:
            alb = self.albums[k]
            self.add_tile(lst, "search", "album", k, f"{alb['album']}\n{alb['artist']}", 104)
        lab.setVisible(bool(albums))
        lst.setVisible(bool(albums))
        self.search_paths = songs
        self.search_songs.setRowCount(len(songs))
        for r, path in enumerate(songs):
            t = self.track_by_path[path][0]
            for c, val in enumerate((t["title"], t["artist"], t["album"], fmt_time(t["length"] * 1000))):
                self.search_songs.setItem(r, c, QTableWidgetItem(val))
        lab, _tbl = self.search_sections["songs"]
        lab.setVisible(bool(songs))
        self.search_songs.setVisible(bool(songs))
        found = len(artists) + len(albums) + len(songs)
        self.search_title.setText(f'Results for "{text}"' if found else f'Nothing in your library for "{text}"')
        self.stack.setCurrentIndex(9)

    def search_songs_menu(self, pos):
        row = self.search_songs.rowAt(pos.y())
        if row < 0:
            return
        sel = sorted({i.row() for i in self.search_songs.selectedIndexes()})
        if row not in sel:
            sel = [row]
        paths = [self.search_paths[r] for r in sel if r < len(self.search_paths)]
        if paths:
            self.track_menu(self.search_songs.viewport().mapToGlobal(pos), paths,
                            play_cb=lambda: self.play_from_library(self.qindex[paths[0]]))

    # ----- organize Soulseek downloads
    def organize_target(self):
        root = self.cfg["organize_root"].strip()
        if root:
            return root
        return self.cfg["folders"][0] if self.cfg["folders"] else self.cfg["downloads_dir"]

    def after_downloads_finished(self):
        if not (self.cfg["organize_downloads"] and self.cfg["downloads_dir"]):
            self.rescan()
            return
        self.organize_now(quiet=True)

    def organize_now(self, quiet=False):
        src = self.cfg["downloads_dir"]
        dest = self.organize_target()
        if not src or not os.path.isdir(src):
            if not quiet:
                self.statusBar().showMessage("Set your slskd downloads folder first (Preferences > Soulseek).")
            return
        group = bool(self.cfg["group_featured"])
        w = Worker(lambda: organize_downloads(src, dest, group))

        def done(n):
            if n or not quiet:
                self.statusBar().showMessage(f"Organized {n} song(s) into Artist / Album folders.", 8000)
            self.rescan()

        w.ok.connect(done)
        w.fail.connect(lambda m: (self.statusBar().showMessage(f"Couldn't organize downloads: {m}"), self.rescan()))
        self.keep(w)

    # ----- library rows (drawn by TreeRowDelegate)
    def tree_thumb(self, key):
        px = self.tree_px.get(key)
        if px is not None:
            return px
        pix = self.thumb_cache.get(key)
        radius = max(2, self.radius(6))
        if pix is None:
            ck = (28, radius, self.scheme["raised"])
            if ck not in self.neutral_cache:
                self.neutral_cache[ck] = neutral_cover(28, radius, self.scheme["raised"], self.scheme["sub"])
            return self.neutral_cache[ck]
        px = rounded_pixmap(pix, 28, radius)
        self.tree_px[key] = px
        return px

    def back_button(self, light=False):
        b = QPushButton()
        b.setObjectName("transport")
        b.setFixedSize(34, 34)
        b.setIconSize(QSize(18, 18))
        b.setToolTip("Back")
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_buttons.append((b, light))
        return b

    def update_downloads_badge(self):
        self.dl_nav_btn.setIcon(badge_icon("download", self.icon_fg, self.dl_active,
                                           self.scheme["accent"], self.scheme["on_accent"]))
        self.dl_nav_btn.setToolTip(f"Downloads ({self.dl_active} active)" if self.dl_active else "Downloads")

    # ----- shuffle / repeat
    def on_shuffle_toggled(self, on):
        self.cfg["shuffle_on"] = bool(on)
        save_config(self.cfg)
        self.update_mode_buttons()
        self.update_mini_next()

    def toggle_repeat(self):
        order = ["off", "all", "one"]
        mode = self.cfg["repeat_mode"] if self.cfg["repeat_mode"] in order else "off"
        self.cfg["repeat_mode"] = order[(order.index(mode) + 1) % 3]
        save_config(self.cfg)
        self.update_mode_buttons()
        self.update_mini_next()

    def update_mode_buttons(self):
        on = self.shuffle.isChecked()
        self.shuffle.setIcon(make_icon("shuffle", self.scheme["accent"] if on else self.icon_fg))
        self.shuffle.setToolTip("Shuffle: on" if on else "Shuffle: off")
        mode = self.cfg["repeat_mode"]
        self.repeat_btn.setIcon(make_icon("repeat_one" if mode == "one" else "repeat",
                                          self.scheme["accent"] if mode != "off" else self.icon_fg))
        self.repeat_btn.setToolTip({"all": "Repeat: all", "one": "Repeat: this song"}.get(mode, "Repeat: off"))
        self.update_fullscreen()

    # ----- browse by genre / decade
    def refresh_browse_list(self):
        self.browse_list.clear()

        def add(text, data=None):
            item = QListWidgetItem(text)
            if data is None:
                item.setFlags(Qt.ItemFlag.NoItemFlags)
            else:
                item.setData(KEY_ROLE, data)
            self.browse_list.addItem(item)

        add("GENRES")
        for gk in sorted(self.genres, key=lambda k: self.genres[k]["name"].lower()):
            g = self.genres[gk]
            add(f"{g['name']}   ({len(g['albums'])})", ("genre", gk))
        if not self.genres:
            add("No genre tags found in your music yet.")
        add("DECADES")
        for dk in sorted(self.decades, reverse=True):
            add(f"{dk}   ({len(self.decades[dk])})", ("decade", dk))

    def on_browse_clicked(self, item):
        data = item.data(KEY_ROLE)
        if data:
            self.show_browse(*data)

    def show_browse(self, kind, value):
        if kind == "genre":
            keys = list(self.genres.get(value, {}).get("albums", []))
            title = self.genres.get(value, {}).get("name", value)
        else:
            keys = list(self.decades.get(value, []))
            title = f"The {value}"
        keys = [k for k in keys if k in self.albums]
        keys.sort(key=lambda k: (self.albums[k]["artist"].lower(), self.albums[k]["year"] or 9999))
        self.browse_paths = [p for k in keys for p in self.album_paths(k)]
        self.browse_name = title
        self.browse_title.setText(title)
        self.browse_sub.setText(f"{len(keys)} albums  ·  {len(self.browse_paths)} songs")
        self.view_targets["browse"] = {}
        self.browse_grid.clear()
        for k in keys:
            alb = self.albums[k]
            self.add_tile(self.browse_grid, "browse", "album", k, f"{alb['album']}\n{alb['artist']}", 130)
        self.stack.setCurrentIndex(10)
        self.nav_note(("browse", kind, value))

    # ----- covers you can click, song info, folders
    def install_cover_clicks(self):
        self.cover_targets = (self.cover_label, self.np_cover, self.lyrics_cover, self.artist_avatar)
        for lab in self.cover_targets:
            lab.setCursor(Qt.CursorShape.PointingHandCursor)
            lab.setToolTip("Click to see the cover full size")

    def eventFilter(self, obj, event):
        etype = event.type()
        if etype == QEvent.Type.Resize and obj is getattr(self, "lyrics_list", None):
            QTimer.singleShot(0, self.resize_lyric_spacers)
        elif etype == QEvent.Type.Wheel and obj is getattr(self, "lyrics_viewport", None):
            self.pause_lyric_follow()
        elif etype == QEvent.Type.MouseButtonRelease and obj in getattr(self, "time_targets", ()):
            self.toggle_remaining()
            return True
        if etype == QEvent.Type.MouseButtonPress and event.button() in (Qt.MouseButton.BackButton,
                                                                         Qt.MouseButton.ForwardButton):
            if event.button() == Qt.MouseButton.BackButton:
                self.go_back()
            else:
                self.go_forward()
            return True
        if (etype == QEvent.Type.MouseButtonRelease and getattr(self, "cover_targets", None)
                and obj in self.cover_targets):
            if obj is self.cover_label:
                key = self.current_album
            elif obj is self.artist_avatar:
                key = self.artist_avatar_key
            else:
                key = self.current_key()
            self.show_cover_viewer(key)
            return True
        return super().eventFilter(obj, event)

    def show_cover_viewer(self, key):
        pix = self.cover_for(key) if key in self.albums else None
        if pix is None:
            self.statusBar().showMessage("There's no cover for this album yet.", 5000)
            return
        CoverViewer(self, pix).exec()

    def show_song_info(self, path):
        if path in self.track_by_path:
            SongInfoDialog(self, path).exec()

    def show_in_folder(self, path):
        if sys.platform == "win32":
            subprocess.Popen(f'explorer /select,"{os.path.normpath(path)}"')
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(path)))

    # ----- keyboard shortcuts help
    def show_shortcuts(self):
        rows = []
        for top in self.menuBar().actions():
            menu = top.menu()
            for act in (menu.actions() if menu else [top]):
                key = act.shortcut().toString(QKeySequence.SequenceFormat.NativeText)
                if key:
                    rows.append((act.text().replace("&", ""), key))
        for act in self.actions():
            key = act.shortcut().toString(QKeySequence.SequenceFormat.NativeText)
            if key:
                rows.append((act.text().replace("&", ""), key))
        rows += [("Play/pause, next, previous (anywhere)", "Keyboard media keys"),
                 ("Go back / forward", "Mouse side buttons"),
                 ("Close the queue panel or fullscreen", "Esc"),
                 ("Mini player: volume", "Mouse wheel"),
                 ("Mini player: jump in the song", "Click the bottom bar"),
                 ("Mini player: back to the full player", "Double-click"),
                 ("Lyrics: jump to a line", "Click the line")]
        dlg = QDialog(self)
        dlg.setWindowTitle("Keyboard shortcuts")
        dlg.resize(520, 560)
        lay = QVBoxLayout(dlg)
        table = QTableWidget(len(rows), 2)
        table.setHorizontalHeaderLabels(["Action", "Shortcut"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        for r, (what, key) in enumerate(rows):
            table.setItem(r, 0, QTableWidgetItem(what))
            table.setItem(r, 1, QTableWidgetItem(key))
        lay.addWidget(table)
        ok = QPushButton("Close")
        ok.clicked.connect(dlg.accept)
        lay.addWidget(ok, 0, Qt.AlignmentFlag.AlignRight)
        dlg.exec()

    # ----- backup / restore
    def backup_data(self):
        save_config(self.cfg)
        save_stats(self.stats)
        save_playlists(self.playlists)
        default = os.path.join(os.path.expanduser("~"), f"eozMP-backup-{time.strftime('%Y-%m-%d')}.zip")
        path, _ = QFileDialog.getSaveFileName(self, "Back up eozMP", default, "eozMP backup (*.zip)")
        if not path:
            return
        try:
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
                for name, src in BACKUP_FILES.items():
                    if src.exists():
                        z.write(src, name)
                if LYRICS_DIR.exists():
                    for f in LYRICS_DIR.glob("*.json"):
                        z.write(f, f"lyrics/{f.name}")
            self.statusBar().showMessage(f"Backup saved: {path}", 10000)
        except Exception as e:
            QMessageBox.warning(self, "Backup", f"Couldn't save the backup:\n{e}")

    def restore_data(self):
        path, _ = QFileDialog.getOpenFileName(self, "Restore eozMP backup", os.path.expanduser("~"),
                                              "eozMP backup (*.zip)")
        if not path:
            return
        answer = QMessageBox.question(
            self, "Restore backup",
            "Replace your current settings, playlists, favorites and listening stats with this backup?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            with zipfile.ZipFile(path) as z:
                names = z.namelist()
                if not any(n in names for n in BACKUP_FILES):
                    raise ValueError("This doesn't look like an eozMP backup.")
                for name, dst in BACKUP_FILES.items():
                    if name in names:
                        dst.write_bytes(z.read(name))
                LYRICS_DIR.mkdir(exist_ok=True)
                for n in names:
                    if n.startswith("lyrics/") and n.endswith(".json"):
                        (LYRICS_DIR / os.path.basename(n)).write_bytes(z.read(n))
        except Exception as e:
            QMessageBox.warning(self, "Restore", f"Couldn't restore:\n{e}")
            return
        self.cfg = load_config()
        self.playlists = load_playlists()
        self.stats = load_stats()
        self.fav_set = set(self.stats["favorites"])
        self.shuffle.setChecked(bool(self.cfg["shuffle_on"]))
        self.apply_settings()
        self.apply_soulseek_defaults()
        self.refresh_playlist_list()
        self.rescan()
        self.statusBar().showMessage("Backup restored.", 8000)

    # ----- clickable names
    @staticmethod
    def link(href, text, color, bold=False):
        weight = "font-weight: 600; " if bold else ""
        return (f'<a href="{html.escape(href)}" style="color: {color}; {weight}text-decoration: none;">'
                f'{html.escape(text)}</a>')

    def on_link(self, href):
        kind, _, value = href.partition(":")
        value = urllib.parse.unquote(value)
        if kind == "artist" and value in self.artists:
            self.leave_overlays()
            self.show_artist(value)
            self.mark_tab(1)
        elif kind == "album" and value in self.track_by_path:
            self.leave_overlays()
            self.open_album(self.track_by_path[value][1])

    def leave_overlays(self):
        if self.fs_active:
            self.exit_fullscreen()
        if self.mini is not None and self.mini.isVisible():
            self.exit_mini()
        if self.drawer.isVisible():
            self.close_drawer()

    def set_now_playing(self, track):
        col = self.scheme["text"]
        akey = urllib.parse.quote(track["artist"].lower())
        path = urllib.parse.quote(track["path"])
        sep = html.escape("  -  ")
        self.now_playing.setText(
            self.link(f"album:{path}", track["title"], col) + sep
            + self.link(f"artist:{akey}", track["artist"], col) + sep
            + self.link(f"album:{path}", track["album"], col))

    def set_lyrics_header(self):
        path = getattr(self, "lyrics_path", None)
        if not path or path not in self.track_by_path:
            return
        t = self.track_by_path[path][0]
        light = "#ffffff" if self.lyrics_immersive else self.scheme["text"]
        soft = "rgba(255, 255, 255, 200)" if self.lyrics_immersive else self.scheme["sub"]
        self.lyrics_title.setText(self.link(f"album:{urllib.parse.quote(path)}", t["title"], light))
        info = getattr(self, "lyrics_info", "")
        if getattr(self, "lyrics_info_path", None) != path:
            info = ""
        self.lyrics_source.setText(
            self.link(f"artist:{urllib.parse.quote(t['artist'].lower())}", t["artist"], soft)
            + (html.escape(f"  •  {info}") if info else ""))

    # ----- back / forward history
    def nav_note(self, entry):
        if self._navigating or entry == self.nav_cur:
            return
        if self.nav_cur is not None:
            self.nav_back.append(self.nav_cur)
            del self.nav_back[:-60]
        self.nav_cur = entry
        self.nav_fwd.clear()
        self.update_nav_buttons()

    def update_nav_buttons(self):
        self.nav_back_btn.setEnabled(bool(self.nav_back))
        self.nav_fwd_btn.setEnabled(bool(self.nav_fwd))

    def go_back(self):
        while self.nav_back:
            entry = self.nav_back.pop()
            if self.open_nav(entry):
                if self.nav_cur is not None:
                    self.nav_fwd.append(self.nav_cur)
                self.nav_cur = entry
                break
        self.update_nav_buttons()

    def go_forward(self):
        while self.nav_fwd:
            entry = self.nav_fwd.pop()
            if self.open_nav(entry):
                if self.nav_cur is not None:
                    self.nav_back.append(self.nav_cur)
                self.nav_cur = entry
                break
        self.update_nav_buttons()

    def open_nav(self, entry):
        """Show a page from the history. Returns False if it no longer exists."""
        kind = entry[0]
        self._navigating = True
        try:
            if kind == "album" and entry[1] in self.albums:
                self.open_album(entry[1])
            elif kind == "artist" and entry[1] in self.artists:
                self.show_artist(entry[1])
            elif kind == "home":
                self.show_home()
            elif kind == "playlist" and entry[1] in self.playlists:
                self.show_playlist(entry[1])
            elif kind == "browse":
                self.show_browse(entry[1], entry[2])
            elif kind == "stats":
                self.open_stats()
            elif kind == "lyrics":
                self.stack.setCurrentIndex(3)
            elif kind == "soulseek":
                self.stack.setCurrentIndex(1)
            elif kind == "downloads":
                self.stack.setCurrentIndex(2)
            else:
                return False
            return True
        finally:
            self._navigating = False

    def open_downloads(self):
        self.stack.setCurrentIndex(2)
        self.nav_note(("downloads",))

    def on_escape(self):
        if self.drawer.isVisible():
            self.close_drawer()

    # ----- queue side panel
    def drawer_geometry(self):
        w = min(420, max(320, int(self.stack.width() * 0.36)))
        return self.stack.width() - w, 0, w, self.stack.height()

    def open_drawer(self):
        x, y, w, h = self.drawer_geometry()
        self.drawer.setGeometry(self.stack.width(), y, w, h)
        self.drawer_scrim.setGeometry(0, 0, self.stack.width(), self.stack.height())
        self.refresh_drawer_snapshot(final_x=x)
        self.drawer_scrim.show()
        self.drawer.show()
        self.raise_drawer()
        self.update_drawer()
        self.drawer.anim.stop()
        try:
            self.drawer.anim.finished.disconnect()
        except Exception:
            pass
        self.drawer.anim.setStartValue(QPoint(self.stack.width(), y))
        self.drawer.anim.setEndValue(QPoint(x, y))
        self.drawer.anim.start()
        self.drawer_timer.start()

    def close_drawer(self):
        if not self.drawer.isVisible():
            return
        self.drawer_timer.stop()
        self.drawer_scrim.hide()
        self.drawer.anim.stop()
        try:
            self.drawer.anim.finished.disconnect()
        except Exception:
            pass
        self.drawer.anim.setStartValue(self.drawer.pos())
        self.drawer.anim.setEndValue(QPoint(self.stack.width(), self.drawer.y()))
        self.drawer.anim.finished.connect(self.drawer.hide)
        self.drawer.anim.start()

    def position_drawer(self):
        if getattr(self, "drawer", None) is not None and self.drawer.isVisible():
            x, y, w, h = self.drawer_geometry()
            self.drawer.setGeometry(x, y, w, h)
            self.drawer_scrim.setGeometry(0, 0, self.stack.width(), self.stack.height())
            self.refresh_drawer_snapshot()

    def raise_drawer(self):
        if getattr(self, "drawer", None) is not None and self.drawer.isVisible():
            self.drawer_scrim.raise_()
            self.drawer.raise_()

    def refresh_drawer_snapshot(self, final_x=None):
        page = self.stack.currentWidget()
        if page is None or (not self.drawer.isVisible() and final_x is None):
            return
        x = final_x if final_x is not None else self.drawer.x()
        w, h = self.drawer.width(), self.drawer.height()
        if w <= 0 or h <= 0:
            return
        shot = page.grab(QRect(x, 0, w, h))
        if shot.isNull():
            return
        small = shot.scaled(max(1, w // 12), max(1, h // 12), Qt.AspectRatioMode.IgnoreAspectRatio,
                            Qt.TransformationMode.SmoothTransformation)
        self.drawer.snapshot = small.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation)
        self.drawer.update()

    def update_drawer(self):
        if not self.drawer.isVisible():
            return
        if 0 <= self.index < len(self.queue):
            t, key = self.queue[self.index]
            self.drawer_title.setText(t["title"])
            self.drawer_artist.setText(f"{t['artist']}  ·  {t['album']}")
            self.drawer_cover.setPixmap(self.thumb_pixmap(key, 48, self.radius(8)))
        else:
            self.drawer_title.setText("Nothing playing")
            self.drawer_artist.setText("")
            self.drawer_cover.setPixmap(self.placeholder(48, self.radius(8)))

    # ----- Soulseek inside the search page
    def reset_inline_soul(self):
        if self.inline_soul_worker is not None:
            self.inline_soul_worker.stop()
            for sig in (self.inline_soul_worker.results, self.inline_soul_worker.failed,
                        self.inline_soul_worker.finished_search):
                try:
                    sig.disconnect()
                except Exception:
                    pass
            self.inline_soul_worker = None
        self.inline_soul_raw, self.inline_soul_view = [], []
        self.inline_soul_text = self.search.text().strip()
        self.search_soul_table.setRowCount(0)
        self.search_soul_table.hide()
        self.search_soul_dl.hide()
        self.search_soul_status.setText("")

    def search_soulseek_inline(self):
        text = self.search.text().strip()
        if len(text) < 2:
            return
        if not self.slskd_ready():
            self.statusBar().showMessage("Set up your slskd connection first.")
            if not self.open_settings("Soulseek") or not self.slskd_ready():
                return
        self.reset_inline_soul()
        self.inline_soul_text = text
        self.search_soul_status.setText("Searching Soulseek... (about 30 seconds)")
        w = SearchWorker(self.client(), text)
        w.results.connect(self.show_inline_soul)
        w.failed.connect(lambda m: self.search_soul_status.setText(f"Soulseek error: {m}"))
        w.finished_search.connect(lambda: self.search_soul_status.setText(
            f"{len(self.inline_soul_view)} albums found" if self.inline_soul_view else "Nothing found on Soulseek."))
        self.inline_soul_worker = w
        self.keep(w)

    def show_inline_soul(self, rows):
        self.inline_soul_raw = rows
        rows = [r for r in rows if passes_filters(r, self.cfg["soul_quality"], bool(self.cfg["soul_free_only"]))]
        self.inline_soul_view = group_by_folder(rows)[:40]
        table = self.search_soul_table
        table.setRowCount(len(self.inline_soul_view))
        for r, group in enumerate(self.inline_soul_view):
            top = group[0]
            _name, folder = split_path(top["filename"])
            vals = (folder.split("/")[-1] or folder, top["username"], str(len(group)),
                    quality_text(group), fmt_size(sum(f["size"] for f in group)))
            for c, v in enumerate(vals):
                table.setItem(r, c, QTableWidgetItem(v))
        table.setVisible(bool(self.inline_soul_view))
        self.search_soul_dl.setVisible(bool(self.inline_soul_view))
        self.search_soul_status.setText(f"{len(self.inline_soul_view)} albums so far...")

    def download_inline_selected(self):
        rows = sorted({i.row() for i in self.search_soul_table.selectedIndexes()})
        if not rows:
            self.statusBar().showMessage("Select one or more Soulseek results first.")
            return
        self.download_inline_rows(rows)

    def download_inline_rows(self, rows):
        files = [f for r in rows if r < len(self.inline_soul_view) for f in self.inline_soul_view[r]]
        if files:
            self.enqueue_downloads(files)

    # ----- fullscreen player
    def toggle_fullscreen(self):
        if self.fs_active:
            self.exit_fullscreen()
        else:
            self.enter_fullscreen()

    def enter_fullscreen(self):
        if self.fs_active:
            return
        if self.fs is None:
            self.fs = FullPlayer(self)
        if self.drawer.isVisible():
            self.close_drawer()
        self.fs_active = True
        self.fs.right_lay.addWidget(self.lyrics_list)   # borrow the live lyrics list
        self.apply_lyrics_look()
        self.fs.style_for(self.scheme)
        if self.fs not in self.time_targets:
            self.time_targets = (self.total_label, self.fs.len_label)
        screen = self.screen() or QApplication.primaryScreen()
        self.fs.setGeometry(screen.geometry())
        self.fs.showFullScreen()
        self.fs.activateWindow()
        self.update_fullscreen()
        QTimer.singleShot(80, self.resize_lyric_spacers)

    def exit_fullscreen(self):
        if not self.fs_active:
            return
        self.fs_active = False
        self.ly_layout.insertWidget(1, self.lyrics_list, 1)   # give the lyrics list back to the lyrics page
        QTimer.singleShot(80, self.resize_lyric_spacers)
        if self.fs is not None:
            self.fs.hide()
        self.apply_lyrics_look()
        self.activateWindow()

    def update_fullscreen(self):
        fs = self.fs
        if not self.fs_active or fs is None:
            return
        sc = self.scheme
        key = self.current_key()
        if 0 <= self.index < len(self.queue):
            t = self.queue[self.index][0]
            fs.title.setText(t["title"])
            fs.artist.setText(f"{t['artist']}  ·  {t['album']}")
        else:
            fs.title.setText("Nothing playing")
            fs.artist.setText("")
        fs.set_lyrics_visible(bool(self.lyric_lines))
        side = max(120, fs.cover_side())
        pix = self.cover_for(key) if key in self.albums else None
        fs.cover.setPixmap(rounded_pixmap(pix, side, 18) if pix is not None
                           else placeholder_cover(side, 18, sc["accent"]))
        fs.set_backdrop(self.backdrop_for(key))
        playing = self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        fs.play.setIcon(make_icon("pause" if playing else "play", sc["on_accent"]))
        fs.prev.setIcon(make_icon("prev", "#ffffff"))
        fs.next.setIcon(make_icon("next", "#ffffff"))
        fs.shuffle.setIcon(make_icon("shuffle", sc["accent"] if self.shuffle.isChecked() else "#ffffff"))
        mode = self.cfg["repeat_mode"]
        fs.repeat.setIcon(make_icon("repeat_one" if mode == "one" else "repeat",
                                    sc["accent"] if mode != "off" else "#ffffff"))
        path = self.current_path()
        fav = bool(path) and path in self.fav_set
        fs.heart.setIcon(make_icon("heart_fill" if fav else "heart", sc["accent"] if fav else "#ffffff"))
        fs.seek.setRange(0, self.seek.maximum())
        fs.len_label.setText(self.time_text(self.player.position()))
        fs.len_label.setCursor(Qt.CursorShape.PointingHandCursor)
        fs.vol.blockSignals(True)
        fs.vol.setValue(self.volume.value())
        fs.vol.blockSignals(False)
        v = self.volume.value()
        kind = "vol_mute" if (self.audio.isMuted() or v == 0) else ("vol_low" if v < 50 else "vol_high")
        fs.vol_btn.setIcon(make_icon(kind, "#ffffff"))
        if self.cfg["fs_motion"] and not fs.motion_timer.isActive():
            fs.motion_timer.start()
        elif not self.cfg["fs_motion"]:
            fs.motion_timer.stop()
        self.setup_visualizer()
        fs.show_next_card("")

    def update_fs_position(self, pos):
        fs = self.fs
        dur = self.seek.maximum()
        if fs.seek.maximum() != dur:
            fs.seek.setRange(0, dur)
        fs.len_label.setText(self.time_text(pos))
        if not fs.seek.isSliderDown():
            fs.seek.setValue(pos)
        fs.pos_label.setText(fmt_time(pos))
        remaining = dur - pos
        if dur and 0 < remaining <= 15000 and self.cfg["repeat_mode"] != "one":
            text = self.peek_next()
            if text.startswith("Next: ") and not fs.next_card.isVisible():
                fs.show_next_card("Up next\n" + text[len("Next: "):])
        elif fs.next_card.isVisible():
            fs.show_next_card("")

    # ----- song-list "now playing" bars
    def tick_now_playing(self):
        if self.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            return
        self.np_phase += 0.55
        page = self.stack.currentIndex()
        table = {0: self.track_table, 5: self.pl_table, 7: self.artist_top, 9: self.search_songs}.get(page)
        if table is not None and table.isVisible():
            table.viewport().update()

    # ----- queue extras
    def queue_length_text(self):
        secs = sum(self.track_by_path[p][0]["length"] for p in self.up_next if p in self.track_by_path)
        return fmt_time(secs * 1000) if secs < 3600 else f"{int(secs // 3600)} h {int(secs % 3600 // 60)} min"

    def shuffle_queue(self):
        if len(self.up_next) > 1:
            random.shuffle(self.up_next)
            self.refresh_queue_view()

    # ----- visualizer
    def visualizers(self):
        out = []
        style = self.cfg["visualizer"]
        if style == "Off":
            return out
        if self.fs_active and self.fs is not None:
            out.append(self.fs.viz)
        elif self.stack.currentIndex() == 3:
            out.append(self.ly_viz)
        return out

    def setup_visualizer(self):
        style = self.cfg["visualizer"]
        on = style != "Off"
        can = (on and QAudioBufferOutput is not None and isinstance(self.player, QMediaPlayer)
               and hasattr(self.player, "setAudioBufferOutput"))
        if can and self.buf_out is None:
            self.buf_out = QAudioBufferOutput(self)
            self.buf_out.audioBufferReceived.connect(self.on_audio_buffer)
            self.player.setAudioBufferOutput(self.buf_out)
        elif not can and self.buf_out is not None:
            try:
                self.player.setAudioBufferOutput(None)
            except Exception:
                pass
            self.buf_out = None
        light = self.lyrics_immersive or self.fs_active
        for viz, visible in ((self.ly_viz, can), (getattr(self.fs, "viz", None), can)):
            if viz is None:
                continue
            viz.style = style if style != "Off" else "Bars"
            viz.color = QColor(255, 255, 255, 150) if (light or viz is not self.ly_viz) else QColor(self.scheme["accent"])
            viz.setVisible(visible)
        if can:
            self.viz_timer.start()
        else:
            self.viz_timer.stop()

    def tick_visualizers(self):
        for viz in self.visualizers():
            viz.tick()

    def on_audio_buffer(self, buf):
        targets = self.visualizers()
        if not targets:
            return
        try:
            fmt = buf.format()
            channels = max(1, fmt.channelCount())
            size = buf.byteCount()
            if size <= 0:
                return
            raw = buf.constData().asstring(size)
            sf = fmt.sampleFormat()
            n = len(targets[0].levels)
            if np is not None:
                S = QAudioFormat.SampleFormat
                dtype, scale, shift = {S.Int16: (np.int16, 32768.0, 0.0), S.Int32: (np.int32, 2147483648.0, 0.0),
                                       S.Float: (np.float32, 1.0, 0.0), S.UInt8: (np.uint8, 128.0, 128.0)}.get(
                    sf, (None, 1.0, 0.0))
                if dtype is None:
                    return
                data = (np.frombuffer(raw, dtype=dtype).astype(np.float32) - shift) / scale
                usable = len(data) - len(data) % channels
                mono = data[:usable].reshape(-1, channels).mean(axis=1)
                levels = spectrum_levels(mono[-2048:], n)
            else:
                levels = loudness_levels(raw, sf, channels, n)
            for viz in targets:
                viz.feed(levels)
        except Exception:
            pass

    # ----- small helpers
    def connect_engine(self):
        p = self.player
        p.positionChanged.connect(self.on_position)
        p.durationChanged.connect(self.on_duration)
        p.mediaStatusChanged.connect(self.on_status)
        p.playbackStateChanged.connect(self.on_state)
        p.errorOccurred.connect(self.on_player_error)
        if isinstance(p, VlcEngine):
            p.failed.connect(self.on_engine_failed)
        self.buf_out = None
        self.setup_visualizer()

    def on_player_error(self, _err, msg):
        self.statusBar().showMessage(f"Can't play this file: {msg}")

    def on_engine_failed(self, why):
        if self.engine_name != "VLC":
            return
        self.vlc_error = why
        self.switch_engine(
            "Qt (built-in)",
            notice=f"VLC couldn't play ({why}). Switched to the built-in engine - the equalizer needs VLC.",
            force_play=True)

    def switch_engine(self, choice, notice="", force_play=False):
        """Swap the audio engine on the fly and carry on with the same song."""
        old = self.player
        src = old.source()
        pos = old.position() if not src.isEmpty() else 0
        playing = old.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        for sig in (old.positionChanged, old.durationChanged, old.mediaStatusChanged,
                    old.playbackStateChanged, old.errorOccurred):
            try:
                sig.disconnect()
            except Exception:
                pass
        try:
            if isinstance(old, VlcEngine):
                old.failed.disconnect()
                old.shutdown()
            else:
                old.stop()
        except Exception:
            pass
        old.deleteLater()
        self.player, self.audio, self.engine_name = create_engine(choice)
        self.audio.setVolume(self.volume.value() / 100)
        self.connect_engine()
        self.apply_equalizer()
        if not src.isEmpty():
            self.pending_seek = pos
            self.player.setSource(src)
            if playing or force_play:
                self.player.play()
        self.refresh_icons()
        if not notice:
            if self.engine_name == "VLC":
                notice = "Now playing through VLC - the equalizer is available."
            else:
                why = ENGINE_ERROR or ("" if vlc is not None else VLC_STATUS)
                notice = "Now using the built-in engine." + (f" ({why})" if why else "")
        self.statusBar().showMessage(notice, 12000)

    def set_lyric_line(self, text):
        """The current lyric under the song title (bottom bar and mini player)."""
        self.lyric_line.setText(text)
        if self.mini is not None:
            self.mini.set_lyric(text)

    def current_key(self):
        return self.queue[self.index][1] if 0 <= self.index < len(self.queue) else None

    def current_path(self):
        return self.queue[self.index][0]["path"] if 0 <= self.index < len(self.queue) else None

    def quit_app(self):
        self.quitting = True
        if self.fs_active:
            self.exit_fullscreen()
        if self.mini is not None:
            self.mini.hide()
        self.close()
        QApplication.instance().quit()

    # ----- colours from the album art
    def accent_hex(self):
        if self.cfg["accent"] == ALBUM_ART_ACCENT:
            return self.album_accent or ACCENTS["Blue"]
        if self.cfg["accent"] == CUSTOM_ACCENT:
            c = QColor(self.cfg["accent_custom"])
            return c.name() if c.isValid() else ACCENTS["Blue"]
        return ACCENTS.get(self.cfg["accent"], ACCENTS["Blue"])

    def accent_for_key(self, key):
        if key in self.accent_cache:
            return self.accent_cache[key]
        pix = self.cover_for(key) if key in self.albums else None
        color = accent_from_pixmap(pix) if pix is not None else None
        self.accent_cache[key] = color or ACCENTS["Blue"]
        return self.accent_cache[key]

    def update_album_accent(self, key):
        if self.cfg["accent"] != ALBUM_ART_ACCENT or key is None:
            return
        new = self.accent_for_key(key)
        if new != self.album_accent:
            self.album_accent = new
            self.refresh_colors()

    # ----- favorites
    def update_heart(self):
        path = self.current_path()
        fav = bool(path) and path in self.fav_set
        color = self.scheme["accent"] if fav else self.icon_fg
        self.fav_btn.setIcon(make_icon("heart_fill" if fav else "heart", color))
        self.fav_btn.setToolTip("Remove from Favorites (Ctrl+D)" if fav else "Add to Favorites (Ctrl+D)")
        self.fav_btn.setEnabled(path is not None)
        self.update_fullscreen()
        if self.mini is not None:
            self.mini.accent = self.scheme["accent"]
            self.mini.set_heart(fav)

    def set_favorite(self, paths, on):
        favs = self.stats["favorites"]
        changed = 0
        for path in paths:
            if on and path not in self.fav_set:
                favs.append(path)
                self.fav_set.add(path)
                changed += 1
            elif not on and path in self.fav_set:
                favs.remove(path)
                self.fav_set.discard(path)
                changed += 1
        if not changed:
            return
        save_stats(self.stats)
        self.update_heart()
        self.refresh_album_hearts()
        self.refresh_playlist_list()
        if self.current_playlist == SMART_FAV and self.stack.currentIndex() == 5:
            self.show_playlist(SMART_FAV, switch=False)
        what = "Added to" if on else "Removed from"
        self.statusBar().showMessage(f"{what} Favorites: {changed} song(s)")

    def toggle_favorite_current(self):
        path = self.current_path()
        if path:
            self.set_favorite([path], path not in self.fav_set)

    # ----- listening stats
    def finalize_listen(self):
        path, ms = self.listen_path, self.listen_ms
        self.listen_ms, self.last_pos = 0, None
        if not path:
            return
        hit = self.track_by_path.get(path)
        length_ms = hit[0]["length"] * 1000 if hit and hit[0]["length"] else 60000
        if ms >= min(30000, length_ms * 0.5):
            record_play(self.stats, path, ms / 1000)
            save_stats(self.stats)
            if hit and hit[1] == self.current_album and self.current_album in self.albums:
                for r, t in enumerate(self.albums[self.current_album]["tracks"]):
                    if t["path"] == path and self.track_table.item(r, 3) is not None:
                        self.track_table.item(r, 3).setText(str(self.stats["plays"][path]["count"]))

    def make_stats_table(self, headers):
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        hh = table.horizontalHeader()
        for c in range(len(headers)):
            hh.setSectionResizeMode(
                c, QHeaderView.ResizeMode.ResizeToContents if c == len(headers) - 1
                else QHeaderView.ResizeMode.Stretch)
        return table

    @staticmethod
    def fill_table(table, rows):
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                table.setItem(r, c, QTableWidgetItem(str(val)))

    def open_stats(self):
        if self.stack.currentIndex() != 6:
            self.prev_page = self.stack.currentIndex()
        self.show_stats()
        self.stack.setCurrentIndex(6)
        self.nav_note(("stats",))

    def show_stats(self):
        now = time.time()
        year_start = time.mktime((time.localtime().tm_year, 1, 1, 0, 0, 0, 0, 0, -1))
        since = {"Last 7 days": now - 7 * 86400, "Last 30 days": now - 30 * 86400,
                 "This year": year_start}.get(self.stats_period.currentText(), 0)
        info = {p: (t["title"], t["artist"], t["album"]) for p, (t, _k) in self.track_by_path.items()}
        st = summarize_stats(self.stats, info, since)
        secs = st["seconds"]
        self.stat_cards["time"].setText(f"{secs / 3600:.1f} h" if secs >= 3600 else f"{int(secs // 60)} min")
        self.stat_cards["plays"].setText(str(st["plays"]))
        self.stat_cards["songs"].setText(str(st["distinct"]))
        self.stat_cards["days"].setText(str(st["days"]))
        self.fill_table(self.top_songs, [(info[p][0], info[p][1], n) for p, n in st["songs"]])
        self.fill_table(self.top_artists, [(a, n) for a, n in st["artists"]])
        self.fill_table(self.top_albums, [(al, ar, n) for (ar, al), n in st["albums"]])
        self.stats_hint.setText(
            "" if st["plays"] else
            "Nothing here yet. A song counts as played after 30 seconds (or half of it, if it's short).")

    # ----- album covers from the internet
    def maybe_fetch_cover(self, key):
        if not self.cfg["covers_auto"] or key not in self.albums or key in self.cover_fetching:
            return
        alb = self.albums[key]
        if alb["album"] == "Unknown Album" or alb["artist"] == "Unknown Artist":
            return
        if self.cover_for(key) is not None:
            return
        miss_key = f"{alb['artist']}|{alb['album']}".lower()
        if time.time() - self.stats["cover_misses"].get(miss_key, 0) < 30 * 86400:
            return
        self.cover_fetching.add(key)
        folder = os.path.dirname(alb["tracks"][0]["path"]) if self.cfg["covers_to_folder"] else None
        artist, album = alb["artist"], alb["album"]
        w = Worker(lambda: download_cover(artist, album, folder))
        w.ok.connect(lambda ok: self.on_cover_fetched(key, miss_key, ok))
        w.fail.connect(lambda _m: self.cover_fetching.discard(key))
        self.keep(w)

    def on_cover_fetched(self, key, miss_key, ok):
        self.cover_fetching.discard(key)
        if ok:
            self.cover_found(key)
        else:
            self.stats["cover_misses"][miss_key] = time.time()
            save_stats(self.stats)

    def cover_found(self, key):
        self.cover_cache.pop(key, None)
        self.thumb_cache.pop(key, None)
        for ck in [ck for ck in self.backdrop_cache if ck[0] == key]:
            del self.backdrop_cache[ck]
        if key in self.albums:
            self.thumbs.add([self.thumb_job(key)], front=True)
        self.accent_cache.pop(key, None)
        if self.current_album == key:
            self.set_cover(self.cover_label, key, self.cover_px, self.radius(14))
        if self.current_key() == key:
            self.set_cover(self.np_cover, key, 56, self.radius(8))
            self.set_cover(self.lyrics_cover, key, 96, self.radius(10))
            self.update_lyrics_backdrop(key)
            self.update_mini()
            self.update_album_accent(key)

    def start_cover_batch(self):
        if self.cover_batch is not None and self.cover_batch.isRunning():
            self.statusBar().showMessage("Already looking for covers...")
            return
        jobs = [(k, a["artist"], a["album"], a["tracks"][0]["path"]) for k, a in self.albums.items()
                if a["album"] != "Unknown Album" and a["artist"] != "Unknown Artist"]
        if not jobs:
            self.statusBar().showMessage("No albums to check.")
            return
        batch = CoverBatch(jobs, bool(self.cfg["covers_to_folder"]))
        batch.progress.connect(lambda m: self.statusBar().showMessage(m))
        batch.found.connect(self.cover_found)
        batch.done.connect(lambda n: self.on_cover_batch_done(batch, n))
        self.cover_batch = batch
        batch.start()
        self.statusBar().showMessage("Looking for missing covers in the background...")

    def on_cover_batch_done(self, batch, found):
        for miss in batch.missed:
            self.stats["cover_misses"][miss] = time.time()
        save_stats(self.stats)
        self.statusBar().showMessage(f"Cover search finished: found {found} new cover(s).")

    # ----- mini player
    def toggle_mini(self):
        if self.mini is not None and self.mini.isVisible():
            self.exit_mini()
        else:
            self.enter_mini()

    def enter_mini(self):
        if self.mini is None:
            self.mini = MiniPlayer(self)
        self.update_mini()
        self.mini.set_icons(self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState)
        pos = self.cfg.get("mini_pos") or []
        if len(pos) == 2:
            self.mini.move(int(pos[0]), int(pos[1]))
        else:
            area = QApplication.primaryScreen().availableGeometry()
            self.mini.move(area.right() - self.mini.width() - 24, area.bottom() - self.mini.height() - 24)
        self.mini.setWindowOpacity(max(0.3, int(self.cfg["mini_opacity"]) / 100))
        self.mini.show()
        self.hide()

    def exit_mini(self):
        if self.mini is not None:
            self.cfg["mini_pos"] = [self.mini.x(), self.mini.y()]
            save_config(self.cfg)
            self.mini.hide()
        self.show()
        self.raise_()
        self.activateWindow()

    def update_mini(self):
        if self.mini is None:
            return
        key = self.current_key()
        pix = self.cover_for(key) if key in self.albums else None
        cover = (rounded_pixmap(pix, 72, self.radius(10)) if pix
                 else placeholder_cover(72, self.radius(10), self.scheme["accent"]))
        self.mini.accent = self.scheme["accent"]
        if 0 <= self.index < len(self.queue):
            t = self.queue[self.index][0]
            self.mini.set_track(t["title"], t["artist"], cover, self.backdrop_for(key),
                                href="artist:" + urllib.parse.quote(t["artist"].lower()))
        else:
            self.mini.set_track("Nothing playing", "", cover, self.backdrop_for(None))
        self.mini.lyric.setVisible(bool(self.cfg["show_lyric_line"]))
        self.mini.set_lyric(self.lyric_line.text())
        path = self.current_path()
        self.mini.set_heart(bool(path) and path in self.fav_set)
        self.mini.set_idle_opacity(int(self.cfg["mini_opacity"]) / 100)
        self.update_mini_next()

    def update_mini_next(self):
        if self.mini is not None:
            self.mini.set_next(self.peek_next())

    def peek_next(self):
        """What 'next' would play, for the mini player."""
        if self.cfg["repeat_mode"] == "one":
            return "Repeating this song"
        if self.fwd:
            path = self.fwd[-1]
        elif self.up_next:
            path = self.up_next[0]
        elif self.shuffle.isChecked():
            return "Next: a random song (shuffle is on)"
        else:
            n = len(self.ctx_paths)
            if not n:
                return ""
            pos = self.ctx_pos + 1
            if pos >= n:
                return "That's the last song"
            path = self.ctx_paths[pos]
        hit = self.track_by_path.get(path)
        return f"Next: {hit[0]['title']}  -  {hit[0]['artist']}" if hit else ""

    def seek_fraction(self, fraction):
        dur = self.seek.maximum()
        if dur > 0:
            self.player.setPosition(int(dur * fraction))

    # ----- album buttons
    def play_album(self, shuffle=False):
        key = self.current_album
        paths = [p for p in self.album_paths(key) if p in self.qindex]
        if not paths:
            return
        if shuffle:
            random.shuffle(paths)
            self.ctx_paths, self.ctx_kind, self.ctx_pos = paths, self.albums[key]["album"], 0
            self.shuffle_played = set()
            self.play_index(self.qindex[paths[0]])
            self.refresh_queue_view()
        else:
            self.play_from_library(self.qindex[paths[0]])

    # ----- your own lyrics
    def add_lyrics_manually(self):
        path = self.current_path()
        if not path:
            self.statusBar().showMessage("Play a song first, then add its lyrics.")
            return
        stem = os.path.splitext(os.path.basename(path))[0]
        QApplication.clipboard().setText(stem + ".txt")
        folder = os.path.dirname(path)
        if sys.platform == "win32":
            subprocess.Popen(f'explorer /select,"{os.path.normpath(path)}"')
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
        self.lyric_wait_path = path
        if folder not in self.lyric_watcher.directories():
            self.lyric_watcher.addPath(folder)
        self.statusBar().showMessage(
            f'Save your lyrics in that folder as "{stem}.txt" (the name is copied - just paste it), '
            f'or "{stem}.lrc" for synced lyrics. They show up as soon as you save.', 20000)

    def on_lyric_folder_changed(self, _changed):
        path = self.lyric_wait_path
        if not path or path != self.current_path():
            return
        stem = os.path.splitext(path)[0]
        for ext in (".lrc", ".txt"):
            f = stem + ext
            if os.path.exists(f) and f not in self.lyric_watcher.files():
                self.lyric_watcher.addPath(f)
        QTimer.singleShot(400, lambda: self.reload_lyrics_if_current(path))

    def reload_lyrics_if_current(self, path):
        if path == self.current_path():
            self.load_lyrics(self.queue[self.index][0])

    # ----- tray icon
    def setup_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(app_icon(), self)
        menu = QMenu(self)
        self.tray_now = menu.addAction("Nothing playing")
        self.tray_now.setEnabled(False)
        menu.addSeparator()
        self.tray_play = menu.addAction("Play")
        self.tray_play.triggered.connect(lambda: self.toggle_play())
        menu.addAction("Next").triggered.connect(lambda: self.next_track(auto=False))
        menu.addAction("Previous").triggered.connect(lambda: self.prev_track())
        menu.addSeparator()
        menu.addAction("Show eozMP").triggered.connect(lambda: self.show_main())
        menu.addAction("Mini player").triggered.connect(lambda: self.toggle_mini())
        menu.addSeparator()
        menu.addAction("Quit eozMP").triggered.connect(lambda: self.quit_app())
        self.tray.setContextMenu(menu)
        self.tray_menu = menu
        self.tray.setToolTip("eozMP")
        self.tray.activated.connect(self.on_tray_activated)
        self.tray.show()
        self.update_tray()

    def on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick):
            self.show_main()

    def show_main(self):
        if self.mini is not None and self.mini.isVisible():
            self.exit_mini()
        else:
            self.showNormal()
            self.raise_()
            self.activateWindow()

    def update_tray(self):
        if self.tray is None:
            return
        playing = self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        self.tray_play.setText("Pause" if playing else "Play")
        if 0 <= self.index < len(self.queue):
            t = self.queue[self.index][0]
            text = f"{t['title']} - {t['artist']}"
            self.tray_now.setText(text if len(text) < 60 else text[:57] + "...")
            self.tray.setToolTip(f"eozMP\n{text}"[:120])

    # ----- keyboard media keys
    def register_media_keys(self):
        if sys.platform != "win32" or self.media_keys_on:
            return
        import ctypes
        if self.media_filter is None:
            self.media_filter = MediaKeyFilter(self.on_media_key)
            QApplication.instance().installNativeEventFilter(self.media_filter)
        got = 0
        for hid, vk in MEDIA_KEYS.items():
            if ctypes.windll.user32.RegisterHotKey(None, hid, 0x4000, vk):   # MOD_NOREPEAT
                got += 1
        self.media_keys_on = True
        if not got:
            self.statusBar().showMessage("Another app is already using the media keys.", 8000)

    def unregister_media_keys(self):
        if sys.platform != "win32" or not self.media_keys_on:
            return
        import ctypes
        for hid in MEDIA_KEYS:
            ctypes.windll.user32.UnregisterHotKey(None, hid)
        self.media_keys_on = False

    def on_media_key(self, hid):
        vk = MEDIA_KEYS.get(hid)
        if vk == 0xB3:
            self.toggle_play()
        elif vk == 0xB0:
            self.next_track(auto=False)
        elif vk == 0xB1:
            self.prev_track()
        elif vk == 0xB2:
            self.player.pause()

    # ----- whole discography from Soulseek
    def start_discography(self):
        if not self.slskd_ready():
            self.statusBar().showMessage("Set up your slskd connection first.")
            if not self.open_settings("Soulseek") or not self.slskd_ready():
                return
        artist, ok = QInputDialog.getText(
            self, "Whole discography", "Artist name:", QLineEdit.EchoMode.Normal, self.search.text().strip())
        artist = artist.strip()
        if not ok or not artist:
            return
        if self.disco_worker is not None:
            self.disco_worker.stop()
            for sig in (self.disco_worker.results, self.disco_worker.failed,
                        self.disco_worker.finished_search):
                try:
                    sig.disconnect()
                except Exception:
                    pass
        self.disco_rows = []
        self.statusBar().showMessage(f"Searching Soulseek for everything by {artist}... (about 30 seconds)", 35000)
        w = SearchWorker(self.client(), artist)
        w.results.connect(lambda rows: setattr(self, "disco_rows", rows))
        w.failed.connect(lambda m: self.statusBar().showMessage(f"Soulseek error: {m}"))
        w.finished_search.connect(lambda: self.show_discography(artist))
        self.disco_worker = w
        self.keep(w)

    def show_discography(self, artist):
        picks = pick_discography(self.disco_rows, artist)
        if not picks:
            self.statusBar().showMessage(f"Couldn't find albums by {artist} on Soulseek right now.")
            return
        a = _norm(artist)
        owned = {album_key(alb["album"], artist) for alb in self.albums.values() if _norm(alb["artist"]) == a}
        dlg = DiscographyDialog(self, artist, picks, owned)
        if dlg.exec():
            files = [f for pk in dlg.selected() for f in pk["files"]]
            if files:
                self.enqueue_downloads(files)

    # ----- equalizer
    def apply_equalizer(self):
        if self.engine_name != "VLC":
            return
        try:
            self.player.set_equalizer(
                bool(self.cfg["eq_enabled"]), float(self.cfg["eq_preamp"]),
                [float(x) for x in self.cfg["eq_bands"]])
        except Exception:
            pass

    def open_equalizer(self):
        EqualizerDialog(self).exec()

    # ----- playlists and right-click menus
    def set_left_view(self, tab):
        """Tabs: 0 Home, 1 Library, 2 Playlists, 3 Browse."""
        self.left_stack.setCurrentIndex({0: 0, 1: 0, 2: 1, 3: 2}.get(tab, 0))
        self.mark_tab(tab)
        if tab == 0:
            self.show_home()
        elif tab == 3:
            self.refresh_browse_list()

    def mark_tab(self, tab):
        for i, b in enumerate(self.seg_buttons):
            b.setChecked(i == tab)
        self.sort_btn.setVisible(tab in (0, 1))

    def on_tree_clicked(self, item, _col):
        if item.parent() is None:
            item.setExpanded(not item.isExpanded())
            akey = item.data(0, ARTIST_ROLE)
            if akey in self.artists and not (self.stack.currentIndex() == 7 and self.current_artist == akey):
                self.show_artist(akey)
        else:
            key = item.data(0, KEY_ROLE)
            if key in self.albums and not (self.stack.currentIndex() == 0 and self.current_album == key):
                self.show_album(key)
        self.mark_tab(1)

    def album_paths(self, key):
        return [t["path"] for t in self.albums[key]["tracks"]] if key in self.albums else []

    def track_menu(self, global_pos, paths, play_cb=None, extra=()):
        if not paths:
            return
        menu = QMenu(self)
        if play_cb:
            menu.addAction("Play").triggered.connect(lambda: play_cb())
        menu.addAction("Play next").triggered.connect(lambda: self.queue_add(paths, True))
        menu.addAction("Add to queue").triggered.connect(lambda: self.queue_add(paths))
        all_fav = all(p in self.fav_set for p in paths)
        menu.addAction("Remove from Favorites" if all_fav else "Add to Favorites").triggered.connect(
            lambda: self.set_favorite(paths, not all_fav))
        if len(paths) == 1:
            menu.addAction("Song info...").triggered.connect(lambda: self.show_song_info(paths[0]))
            menu.addAction("Show in folder").triggered.connect(lambda: self.show_in_folder(paths[0]))
        sub = menu.addMenu("Add to playlist")
        for name in self.playlists:
            sub.addAction(name).triggered.connect(
                lambda checked=False, n=name: self.add_to_playlist(n, paths))
        if self.playlists:
            sub.addSeparator()
        sub.addAction("New playlist...").triggered.connect(lambda: self.new_playlist(paths))
        if extra:
            menu.addSeparator()
            for text, cb in extra:
                menu.addAction(text).triggered.connect(lambda checked=False, f=cb: f())
        menu.exec(global_pos)

    def tree_menu(self, pos):
        item = self.tree.itemAt(pos)
        if item is None:
            return
        key = item.data(0, KEY_ROLE)
        if key in self.albums:
            paths = self.album_paths(key)
        else:  # an artist row: every album under it
            paths = []
            for i in range(item.childCount()):
                paths += self.album_paths(item.child(i).data(0, KEY_ROLE))
        if not paths:
            return
        self.track_menu(
            self.tree.viewport().mapToGlobal(pos), paths,
            play_cb=lambda: self.play_from_library(self.qindex[paths[0]]),
        )

    def album_table_menu(self, pos):
        row = self.track_table.rowAt(pos.y())
        if row < 0 or self.current_album is None:
            return
        sel = sorted({i.row() for i in self.track_table.selectedIndexes()})
        if row not in sel:
            sel = [row]
        tracks = self.albums[self.current_album]["tracks"]
        paths = [tracks[r]["path"] for r in sel if r < len(tracks)]
        if not paths:
            return
        self.track_menu(
            self.track_table.viewport().mapToGlobal(pos), paths,
            play_cb=lambda: self.play_from_library(self.qindex[paths[0]]),
        )

    def refresh_playlist_list(self, select=None):
        keep = select or self.current_playlist
        self.pl_list.blockSignals(True)
        self.pl_list.clear()

        def add(text, name=None):
            item = QListWidgetItem(text)
            if name is None:
                item.setFlags(Qt.ItemFlag.NoItemFlags)
            else:
                item.setData(KEY_ROLE, name)
            self.pl_list.addItem(item)
            if name is not None and name == keep:
                self.pl_list.setCurrentItem(item)

        for name, paths in self.playlists.items():
            add(f"{name}   ({len(paths)})", name)
        if not self.playlists:
            add("No playlists yet.\nRight-click songs > Add to playlist,\nor press + New playlist.")
        self.pl_list.blockSignals(False)

    def playlist_source(self, name):
        """The song paths of a playlist; smart playlists are worked out on the fly."""
        if name == SMART_FAV:
            return list(reversed(self.stats["favorites"]))
        if name == SMART_MOST:
            plays = self.stats["plays"]
            ranked = sorted((p for p in plays if plays[p].get("count")),
                            key=lambda p: (-plays[p]["count"], -plays[p]["last"]))
            return ranked[:100]
        if name == SMART_ADDED:
            newest = sorted(self.all_tracks, key=lambda t: -t.get("added", t.get("mtime", 0)))
            return [t["path"] for t in newest[:100]]
        if name == SMART_RECENT:
            seen, out = set(), []
            for _ts, path, _secs in reversed(self.stats["events"]):
                if path not in seen:
                    seen.add(path)
                    out.append(path)
                    if len(out) >= 100:
                        break
            return out
        return self.playlists.get(name, [])

    def playlist_row_actions(self, name, sel, paths):
        if name in SMART_PLAYLISTS:
            return []
        return [
            ("Move up", lambda: self.move_in_playlist(name, sel, -1)),
            ("Move down", lambda: self.move_in_playlist(name, sel, 1)),
            ("Remove from playlist", lambda: self.remove_from_playlist(name, paths)),
        ]

    def on_playlist_clicked(self, item):
        if item is None:
            return
        name = item.data(KEY_ROLE)
        if name in self.playlists or name in SMART_PLAYLISTS:
            self.show_playlist(name)

    def playlist_tracks(self, name):
        return [self.track_by_path[p] for p in self.playlist_source(name) if p in self.track_by_path]

    def show_playlist(self, name, switch=True):
        self.current_playlist = name
        tracks = self.playlist_tracks(name)
        self.pl_paths = [t["path"] for t, _ in tracks]
        total = sum(t["length"] for t, _ in tracks)
        missing = len(self.playlist_source(name)) - len(tracks)
        sub = f"{len(tracks)} songs - {fmt_time(total * 1000)}"
        if missing:
            sub += f"  ({missing} not found in your library right now)"
        self.pl_title.setText(name)
        self.pl_ren_btn.setEnabled(name not in SMART_PLAYLISTS)
        self.pl_del_btn.setEnabled(name not in SMART_PLAYLISTS)
        self.pl_sub.setText(sub)
        self.pl_table.clearSelection()
        self.pl_table.setRowCount(len(tracks))
        for r, (t, _key) in enumerate(tracks):
            vals = (str(r + 1), t["title"], t["artist"], t["album"], fmt_time(t["length"] * 1000))
            for c, v in enumerate(vals):
                self.pl_table.setItem(r, c, QTableWidgetItem(v))
        if switch:
            self.stack.setCurrentIndex(5)
            self.nav_note(("playlist", name))

    def on_playlist_row_double_clicked(self, row, _col):
        if self.current_playlist is not None:
            self.play_playlist(self.current_playlist, start=row)

    def play_playlist(self, name, start=0, shuffle=False):
        if name is None:
            return
        paths = [t["path"] for t, _ in self.playlist_tracks(name)]
        if not paths:
            self.statusBar().showMessage("That playlist has no songs yet.")
            return
        if shuffle:
            random.shuffle(paths)
            start = 0
        self.ctx_paths, self.ctx_kind = paths, name
        self.shuffle_played = set()
        self.ctx_pos = max(0, min(start, len(paths) - 1))
        self.play_index(self.qindex[paths[self.ctx_pos]])
        self.refresh_queue_view()

    def unique_playlist_name(self, name):
        taken = set(self.playlists) | set(SMART_PLAYLISTS)
        if name not in taken:
            return name
        n = 2
        while f"{name} ({n})" in taken:
            n += 1
        return f"{name} ({n})"

    def new_playlist(self, paths=None, show=False):
        name, ok = QInputDialog.getText(self, "New playlist", "Playlist name:")
        name = name.strip()
        if not ok or not name:
            return
        name = self.unique_playlist_name(name)
        self.playlists[name] = []
        save_playlists(self.playlists)
        if paths:
            self.add_to_playlist(name, paths)
        self.refresh_playlist_list(select=name)
        if show:
            self.set_left_view(2)
            self.show_playlist(name)

    def add_to_playlist(self, name, paths):
        lst = self.playlists.setdefault(name, [])
        added = 0
        for p in paths:
            if p not in lst:
                lst.append(p)
                added += 1
        save_playlists(self.playlists)
        self.refresh_playlist_list()
        if self.current_playlist == name and self.stack.currentIndex() == 5:
            self.show_playlist(name, switch=False)
        dupes = len(paths) - added
        msg = f'Added {added} song(s) to "{name}"'
        if dupes:
            msg += f" ({dupes} already in it)"
        self.statusBar().showMessage(msg)

    def rename_playlist(self, name):
        if name not in self.playlists:
            return
        new, ok = QInputDialog.getText(
            self, "Rename playlist", "New name:", QLineEdit.EchoMode.Normal, name)
        new = new.strip()
        if not ok or not new or new == name:
            return
        new = self.unique_playlist_name(new)
        self.playlists = {(new if k == name else k): v for k, v in self.playlists.items()}
        save_playlists(self.playlists)
        if self.current_playlist == name:
            self.current_playlist = new
        if self.ctx_kind == name:
            self.ctx_kind = new
        self.refresh_playlist_list(select=new)
        if self.current_playlist == new:
            self.show_playlist(new, switch=False)

    def delete_playlist(self, name):
        if name not in self.playlists:
            return
        answer = QMessageBox.question(
            self, "Delete playlist", f'Delete the playlist "{name}"? (Your songs are not deleted.)')
        if answer != QMessageBox.StandardButton.Yes:
            return
        del self.playlists[name]
        save_playlists(self.playlists)
        if self.current_playlist == name:
            self.current_playlist = None
            if self.stack.currentIndex() == 5:
                self.stack.setCurrentIndex(0)
        self.refresh_playlist_list()

    def remove_from_playlist(self, name, paths):
        if name == SMART_FAV:
            self.set_favorite(paths, False)
            return
        if name not in self.playlists:
            return
        gone = set(paths)
        self.playlists[name] = [p for p in self.playlists.get(name, []) if p not in gone]
        save_playlists(self.playlists)
        self.refresh_playlist_list()
        self.show_playlist(name, switch=False)

    def move_in_playlist(self, name, rows, delta):
        if name not in self.playlists:
            return
        order = list(self.pl_paths)
        if not order:
            return
        chosen = {order[r] for r in rows if r < len(order)}
        seq = range(len(order)) if delta < 0 else range(len(order) - 1, -1, -1)
        for i in seq:
            j = i + delta
            if order[i] in chosen and 0 <= j < len(order) and order[j] not in chosen:
                order[i], order[j] = order[j], order[i]
        present = set(order)
        rest = [p for p in self.playlists.get(name, []) if p not in present]
        self.playlists[name] = order + rest
        save_playlists(self.playlists)
        self.show_playlist(name, switch=False)
        sm = self.pl_table.selectionModel()
        flags = QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
        for r, p in enumerate(self.pl_paths):
            if p in chosen:
                sm.select(self.pl_table.model().index(r, 0), flags)

    def playlist_table_menu(self, pos):
        row = self.pl_table.rowAt(pos.y())
        name = self.current_playlist
        if row < 0 or name is None:
            return
        sel = sorted({i.row() for i in self.pl_table.selectedIndexes()})
        if row not in sel:
            sel = [row]
        paths = [self.pl_paths[r] for r in sel if r < len(self.pl_paths)]
        self.track_menu(
            self.pl_table.viewport().mapToGlobal(pos), paths,
            play_cb=lambda: self.play_playlist(name, start=sel[0]),
            extra=self.playlist_row_actions(name, sel, paths),
        )

    def playlist_list_menu(self, pos):
        item = self.pl_list.itemAt(pos)
        if item is None:
            return
        name = item.data(KEY_ROLE)
        if name not in self.playlists and name not in SMART_PLAYLISTS:
            return
        menu = QMenu(self)
        menu.addAction("Play").triggered.connect(lambda: self.play_playlist(name))
        menu.addAction("Shuffle").triggered.connect(lambda: self.play_playlist(name, shuffle=True))
        if name in self.playlists:
            menu.addSeparator()
            menu.addAction("Rename...").triggered.connect(lambda: self.rename_playlist(name))
            menu.addAction("Delete").triggered.connect(lambda: self.delete_playlist(name))
        menu.exec(self.pl_list.viewport().mapToGlobal(pos))

    # ----- lyrics
    def toggle_lyrics(self):
        self.toggle_page(3)

    def lyric_spacer(self):
        item = QListWidgetItem("")
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        item.setData(KEY_ROLE, "spacer")
        item.setSizeHint(QSize(10, max(40, self.lyrics_list.viewport().height() // 2)))
        return item

    def resize_lyric_spacers(self):
        h = max(40, self.lyrics_list.viewport().height() // 2)
        for row in (0, self.lyrics_list.count() - 1):
            item = self.lyrics_list.item(row)
            if item is not None and item.data(KEY_ROLE) == "spacer":
                item.setSizeHint(QSize(10, h))
        self.lyrics_list.doItemsLayout()
        if 0 <= self.lyric_idx < len(self.lyric_lines):
            item = self.lyrics_list.item(self.lyric_idx + self.ly_off)
            if item is not None:
                bar = self.lyrics_list.verticalScrollBar()
                rect = self.lyrics_list.visualItemRect(item)
                bar.setValue(bar.value() + rect.center().y() - self.lyrics_list.viewport().height() // 2)

    def clear_lyrics(self, message=""):
        self.lyrics_list.clear()
        self.ly_off = 0
        self.lyric_times, self.lyric_lines, self.lyric_idx = [], [], -1
        self.set_lyric_line("")
        if message:
            item = QListWidgetItem(message)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            item.setFont(self.lyric_look[0])
            item.setForeground(QColor(self.scheme["sub"]))
            self.lyrics_list.addItem(item)
        self.update_fullscreen()

    def fetch_lyrics_online(self):
        if 0 <= self.index < len(self.queue):
            self.load_lyrics(self.queue[self.index][0], force_online=True)

    def load_lyrics(self, track, force_online=False):
        token = track["path"]
        self.lyrics_token = token
        self.lyrics_artist = track["artist"]
        self.lyrics_path = track["path"]
        self.set_lyrics_header()
        lkey = (track["artist"].lower(), track["album"].lower())
        self.set_cover(self.lyrics_cover, lkey, 96, self.radius(10))
        self.update_lyrics_backdrop(lkey)
        self.clear_lyrics("Looking for lyrics...")
        online = bool(self.cfg["lyrics_online"] or force_online)
        save = bool(self.cfg["lyrics_save_lrc"])
        w = Worker(lambda: get_lyrics(track, online, save, force_online))
        w.ok.connect(lambda res: self.on_lyrics(token, res))
        w.fail.connect(lambda m: self.on_lyrics(token, {"text": "", "error": m}))
        self.keep(w)

    def on_lyrics(self, token, res):
        if token != self.lyrics_token:
            return  # an older song's answer arriving late
        text = res.get("text", "")
        if not text.strip():
            if res.get("instrumental"):
                msg = "Instrumental - no lyrics."
            elif res.get("error"):
                msg = f"Couldn't get lyrics ({res['error']})"
            elif not self.cfg["lyrics_online"]:
                msg = "No lyrics found.\nOnline lookup is off (Preferences > Lyrics)."
            else:
                msg = "No lyrics found."
            self.clear_lyrics(msg)
            return
        synced, lines = parse_lrc(text)
        self.lyrics_list.clear()
        self.lyric_times, self.lyric_lines, self.lyric_idx = [], [], -1
        self.ly_off = 1 if synced else 0
        if synced:
            self.lyrics_list.addItem(self.lyric_spacer())
        for ms, line in lines:
            gap = "♪" if self.cfg["lyrics_style"] == "Classic" else "• • •"
            item = QListWidgetItem(line if line else gap)
            item.setTextAlignment(self.lyric_align)
            self.style_lyric_item(item, False, synced)
            self.lyrics_list.addItem(item)
            self.lyric_lines.append(line)
            if synced:
                self.lyric_times.append(ms)
        if synced:
            self.lyrics_list.addItem(self.lyric_spacer())
        kind = "synced" if synced else "plain text"
        self.lyrics_info = f"{res.get('source', '')}  ({kind})"
        self.lyrics_info_path = self.lyrics_path
        self.set_lyrics_header()
        self.update_fullscreen()
        self.lyrics_list.doItemsLayout()
        if synced:
            self.update_lyric_position(self.player.position())

    def update_lyric_position(self, pos):
        times = self.lyric_times
        if not times:
            return
        i = bisect.bisect_right(times, pos + 200) - 1
        if i == self.lyric_idx:
            return
        old = self.lyric_idx
        self.lyric_idx = i
        count = len(self.lyric_lines)
        off = self.ly_off
        animate = bool(self.cfg["lyrics_animate"])
        _base, _big, active_col, dim, _full = self.lyric_look
        for anim, item in ((self.line_in, self._line_in_item), (self.line_out, self._line_out_item)):
            if anim.state() == QVariantAnimation.State.Running:
                anim.stop()
                self._paint_line(item, anim.endValue())
        if 0 <= old < count:
            item = self.lyrics_list.item(old + off)
            self.style_lyric_item(item, False, True)
            if animate:
                self._line_out_item = item
                item.setForeground(QColor(active_col))
                self.line_out.setStartValue(QColor(active_col))
                self.line_out.setEndValue(QColor(dim))
                self.line_out.start()
        if 0 <= i < count:
            item = self.lyrics_list.item(i + off)
            self.style_lyric_item(item, True, True)
            if animate:
                self._line_in_item = item
                item.setForeground(QColor(dim))
                self.line_in.setStartValue(QColor(dim))
                self.line_in.setEndValue(QColor(active_col))
                self.line_in.start()
            if self.cfg["lyrics_style"] == "Classic":
                self.lyrics_list.doItemsLayout()   # the current line got bigger
            self.scroll_lyrics_to(item)
            self.set_lyric_line(self.lyric_lines[i] or "♪")
        else:
            self.set_lyric_line("")

    @staticmethod
    def _paint_line(item, color):
        if item is None or color is None:
            return
        try:
            item.setForeground(color)
        except RuntimeError:
            pass

    def set_lyrics_fade(self, on):
        if on == self._fade_on:
            return
        self._fade_on = on
        if on:
            effect = QGraphicsOpacityEffect(self.lyrics_list)
            grad = QLinearGradient(0, 0, 0, 1)
            grad.setCoordinateMode(QGradient.CoordinateMode.ObjectBoundingMode)
            grad.setColorAt(0.0, QColor(0, 0, 0, 0))
            grad.setColorAt(0.16, QColor(0, 0, 0, 255))
            grad.setColorAt(0.84, QColor(0, 0, 0, 255))
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            effect.setOpacityMask(QBrush(grad))
            self.lyrics_list.setGraphicsEffect(effect)
        else:
            self.lyrics_list.setGraphicsEffect(None)

    def on_lyric_clicked(self, item):
        row = self.lyrics_list.row(item) - self.ly_off
        if 0 <= row < len(self.lyric_times):
            self.player.setPosition(self.lyric_times[row])

    # ----- soulseek
    def soulseek_search(self):
        text = self.search.text().strip()
        if not text:
            self.statusBar().showMessage("Type what you're looking for first.")
            return
        if not self.slskd_ready():
            self.statusBar().showMessage("Set up your slskd connection first.")
            if not self.open_settings("Soulseek") or not self.slskd_ready():
                return
        if self.search_worker is not None:
            self.search_worker.stop()
            for sig in (self.search_worker.results, self.search_worker.failed,
                        self.search_worker.finished_search):
                try:
                    sig.disconnect()
                except Exception:
                    pass
        self.soul_raw = []
        self.searching = True
        self.search_failed = False
        self.render_soul()
        self.soul_status.setText(f'Searching Soulseek for "{text}"...')
        self.stack.setCurrentIndex(1)
        self.nav_note(("soulseek",))
        w = SearchWorker(self.client(), text)
        w.results.connect(self.show_soul_results)
        w.failed.connect(self.on_search_failed)
        w.finished_search.connect(self.on_search_finished)
        self.search_worker = w
        self.keep(w)

    def on_search_failed(self, msg):
        self.searching = False
        self.search_failed = True
        self.soul_status.setText(f"Soulseek error: {msg}")

    def on_search_finished(self):
        self.searching = False
        if not self.search_failed:
            self.update_soul_status()

    def show_soul_results(self, rows):
        self.soul_raw = rows
        self.render_soul()

    def update_soul_status(self):
        if not self.soul_raw:
            self.soul_status.setText(
                "Searching Soulseek..." if self.searching else "No results found on Soulseek."
            )
            return
        prefix = "Searching... " if self.searching else ""
        hint = "" if self.searching else " - select and press Download"
        self.soul_status.setText(f"{prefix}{self.soul_count_text}{hint}")

    def render_soul(self):
        fmt = self.fmt_combo.currentText()
        free_only = self.free_check.isChecked()
        rows = [r for r in self.soul_raw if passes_filters(r, fmt, free_only)]
        albums_mode = self.view_combo.currentText() == "Albums"

        # remember what is selected so new results don't wipe the selection
        selected = set()
        for idx in self.soul_table.selectedIndexes():
            if idx.row() < len(self.soul_view):
                g = self.soul_view[idx.row()]
                selected.add((g[0]["username"], g[0]["filename"]))

        if albums_mode:
            self.soul_view = group_by_folder(rows)
            headers = ["Album folder", "Location", "User", "Quality", "Size", "Slot / speed"]
            unit = "albums"
        else:
            self.soul_view = [[r] for r in rows]
            headers = ["File", "Folder", "User", "Quality", "Size", "Slot / speed"]
            unit = "files"
        self.soul_count_text = (
            f"{len(self.soul_view)} {unit} shown ({len(self.soul_raw)} files found)"
        )

        self.soul_table.setHorizontalHeaderLabels(headers)
        self.soul_table.clearSelection()
        self.soul_table.setRowCount(len(self.soul_view))
        sm = self.soul_table.selectionModel()
        flags = QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
        for r, group in enumerate(self.soul_view):
            top = group[0]
            name, folder = split_path(top["filename"])
            parts = folder.split("/")
            if albums_mode:
                name = f"{parts[-1]}  ({len(group)} tracks)"
                where = "/".join(parts[-3:-1])
            else:
                where = "/".join(parts[-2:])
            size = sum(f["size"] for f in group)
            slot = "Free slot" if top["free"] else f"Queue {top['queue']}"
            if top["speed"]:
                slot += f" - {top['speed'] / 1024:.0f} KB/s"
            vals = (name, where, top["username"], quality_text(group), fmt_size(size), slot)
            for c, v in enumerate(vals):
                self.soul_table.setItem(r, c, QTableWidgetItem(v))
            if (top["username"], top["filename"]) in selected:
                sm.select(self.soul_table.model().index(r, 0), flags)
        self.update_soul_status()

    def run_job(self, job, ok_msg):
        w = Worker(job)

        def done(n):
            self.statusBar().showMessage(ok_msg.format(n=n))
            self.poll_downloads()

        w.ok.connect(done)
        w.fail.connect(lambda m: self.statusBar().showMessage(f"Failed: {m}"))
        self.keep(w)

    def download_selected(self):
        rows = sorted({i.row() for i in self.soul_table.selectedIndexes()})
        files = [f for r in rows if r < len(self.soul_view) for f in self.soul_view[r]]
        if not files:
            self.statusBar().showMessage("Select one or more results first.")
            return
        if len(files) > 40:
            answer = QMessageBox.question(
                self, "Download many files?", f"This will queue {len(files)} files. Continue?"
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.enqueue_downloads(files)

    def enqueue_downloads(self, files):
        by_user = {}
        for f in files:
            by_user.setdefault(f["username"], []).append({"filename": f["filename"], "size": f["size"]})
        count = len(files)
        client = self.client()

        def job():
            for user, items in by_user.items():
                client.call("POST", f"/transfers/downloads/{urllib.parse.quote(user, safe='')}", items)
            return count

        self.run_job(
            job,
            "Queued {n} file(s). Watch them on the Downloads page - finished files "
            "appear in your library by themselves.",
        )

    # ----- downloads manager
    def poll_downloads(self):
        if not self.slskd_ready() or self.poll_busy:
            return
        self.poll_busy = True
        client = self.client()
        w = Worker(lambda: client.call("GET", "/transfers/downloads", timeout=8))
        w.ok.connect(self.on_downloads)
        w.fail.connect(lambda _m: None)
        w.finished.connect(lambda: setattr(self, "poll_busy", False))
        self.keep(w)

    def on_downloads(self, data):
        rows = []
        for user in data or []:
            uname = user.get("username", "")
            for d in user.get("directories", []) or []:
                for f in d.get("files", []) or []:
                    rows.append({
                        "username": f.get("username") or uname,
                        "id": f.get("id", ""),
                        "filename": f.get("filename", ""),
                        "size": f.get("size", 0),
                        "status": parse_state(f.get("state", "")),
                        "percent": float(f.get("percentComplete") or 0),
                    })
        rank = {"Downloading": 0, "Starting": 1, "Waiting in queue": 2}

        def sort_key(r):
            s = r["status"]
            if s in rank:
                n = rank[s]
            else:
                n = 3 if s.startswith("Failed") else 4
            return (n, r["username"], r["filename"])

        rows.sort(key=sort_key)
        self.dl_rows = rows
        done = sum(1 for r in rows if r["status"] == "Finished")
        failed = sum(1 for r in rows if r["status"].startswith("Failed"))
        active = len(rows) - done - failed

        self.render_downloads()
        self.dl_status.setText(f"{active} active - {done} finished - {failed} failed")
        self.dl_active = active
        self.update_downloads_badge()
        if active:
            self.statusBar().showMessage(f"Soulseek: {active} downloading, {done} finished")
        if self.last_done is not None and done > self.last_done:
            self.after_downloads_finished()
        self.last_done = done

    @staticmethod
    def dl_values(row):
        name, _ = split_path(row["filename"])
        pct = "100%" if row["status"] == "Finished" else f"{row['percent']:.0f}%"
        return (name, row["username"], row["status"], pct)

    def render_downloads(self):
        rows = self.dl_rows
        keys = [(r["username"], r["id"]) for r in rows]
        if keys == self.dl_keys:
            # same rows: just update the text so the selection is kept
            for r, row in enumerate(rows):
                for c, v in enumerate(self.dl_values(row)):
                    item = self.dl_table.item(r, c)
                    if item is not None:
                        item.setText(v)
            return
        prev = self.dl_keys
        selected = {prev[i.row()] for i in self.dl_table.selectedIndexes() if i.row() < len(prev)}
        self.dl_table.clearSelection()
        self.dl_table.setRowCount(len(rows))
        sm = self.dl_table.selectionModel()
        flags = QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
        for r, row in enumerate(rows):
            for c, v in enumerate(self.dl_values(row)):
                self.dl_table.setItem(r, c, QTableWidgetItem(v))
            if keys[r] in selected:
                sm.select(self.dl_table.model().index(r, 0), flags)
        self.dl_keys = keys

    def retry_failed(self):
        failed = [r for r in self.dl_rows if r["status"].startswith("Failed")]
        if not failed:
            self.statusBar().showMessage("No failed downloads.")
            return
        client = self.client()

        def job():
            for r in failed:
                u = urllib.parse.quote(r["username"], safe="")
                try:
                    client.call("DELETE", f"/transfers/downloads/{u}/{r['id']}?remove=true")
                except Exception:
                    pass
                client.call(
                    "POST", f"/transfers/downloads/{u}",
                    [{"filename": r["filename"], "size": r["size"]}],
                )
            return len(failed)

        self.run_job(job, "Retrying {n} download(s).")

    def remove_downloads(self, targets, message):
        if not targets:
            self.statusBar().showMessage("Nothing to remove.")
            return
        client = self.client()

        def job():
            n = 0
            for r in targets:
                u = urllib.parse.quote(r["username"], safe="")
                try:
                    client.call("DELETE", f"/transfers/downloads/{u}/{r['id']}")  # cancel
                except Exception:
                    pass
                try:
                    client.call("DELETE", f"/transfers/downloads/{u}/{r['id']}?remove=true")
                    n += 1
                except Exception:
                    pass
            return n

        self.run_job(job, message)

    def clear_finished(self):
        done = [r for r in self.dl_rows if r["status"] == "Finished"]
        self.remove_downloads(done, "Cleared {n} finished download(s).")

    def remove_selected_downloads(self):
        sel = sorted({i.row() for i in self.dl_table.selectedIndexes()})
        targets = [self.dl_rows[r] for r in sel if r < len(self.dl_rows)]
        self.remove_downloads(targets, "Removed {n} download(s).")


if __name__ == "__main__":
    if sys.platform == "win32":
        try:  # so the taskbar shows the eozMP icon instead of Python's
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("eozMP.Player.1")
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setApplicationName("eozMP")
    app.setWindowIcon(app_icon())
    SYSTEM_FONT_FAMILY = app.font().family()
    app.setStyle("Fusion")
    app.setQuitOnLastWindowClosed(False)
    ui_font = pick_ui_font()
    if ui_font is not None:
        app.setFont(ui_font)
    win = Player()
    win.show()
    sys.exit(app.exec())
