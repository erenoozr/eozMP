"""Builds eozmp_lang.py: every interface text of musicplayer.py, machine-translated into the UI languages.

Run from the eozMP folder:  python tools/make_translations.py
Texts already translated are kept (and hand fixes in tools/overrides.json always win), so re-running only
translates new texts. Uses the same free Google endpoint as the lyric translation.
"""
import ast
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "musicplayer.py"
OUT = ROOT / "eozmp_lang.py"
OVERRIDES = Path(__file__).resolve().parent / "overrides.json"
LANGS = ["tr", "es", "de", "fr", "pt", "ru", "ar", "zh-CN", "hi", "ja", "id"]
SKIP_RE = re.compile(r"^(Ctrl|Alt|Shift|F\d|Esc|Space|Media|Meta)\b|^[A-Z0-9_]+$|^\W*$|^Segoe|^Times New Roman$")
PH_RE = re.compile(r"\{\d+\}")


# names and technical strings that stay as they are in every language
KEEP = {"Soulseek", "&Soulseek", "Apple Music", "Arial", "Georgia", "Fusion", "Liberation Serif", "DejaVu Serif",
        "Times New Roman", "Qt", "Preamp", "MP3 320k+", "Soulseek Guide.txt", "eozMP", "MYMEMORY WARNING",
        "AcoustID", "Last.fm", "Last.fm...",
        "eozMP - eren's definitely (not) sketchy music player.",   # the hidden tagline stays English
        # tag field names read from files (APE, WMA, MP4, Matroska); never shown
        "Album Artist", "AlbumArtist", "album artist", "Author", "Date", "Disc", "DiscNumber",
        "Cover Art (Front)", "Cover Art (Back)", "Cover Art (Other)", "not a Matroska file",
        "Various Artists",
        # UPnP / HTTP field names and an internal error text; never shown
        "Channel", "DesiredVolume", "Master", "SetVolume", "bytes */{0}", "not an http address",
        # font and folder names, and the kana table and Greek "Ou" used to read lyrics in Latin letters; never shown
        "Helvetica Neue", "Pictures", "Ou",
        "a i u e o ka ki ku ke ko ga gi gu ge go sa shi su se so za ji zu ze zo ta chi tsu te to da ji zu de do "
        "na ni nu ne no ha hi fu he ho ba bi bu be bo pa pi pu pe po ma mi mu me mo ya yu yo ra ri ru re ro "
        "wa wi we o n a i u e o vu"}   # a compilation's album artist: a name, like any other artist
TECH_RE = re.compile(r"^[\w\-{}.]*:(?!\s|$)|^\S*[/|]\S*$|^/|^\{0\}\.|rgba\(|font-|^color:|^explorer |"
                     r"^[\w-]+-[A-Z][\w-]*$|^[A-Z]{2,}\{0\}$|^eozMP(/|-backup)|^release|^\d+px|^M-SEARCH|\?v=|@\w|=\w+=")


def literal_ok(s):
    if s in KEEP or TECH_RE.search(s):
        return False
    s = s.replace("&", "") if re.search(r"&\w", s) else s     # "&Library" is a menu title
    if not re.search(r"[A-Za-z]{2}", s) or "\\" in s or "<" in s or s.startswith(("http", "#", "-"))             or re.match(r"Q[A-Z]", s):                          # Qt stylesheets ("QLabel { ... }")
        return False
    if "_" in s or SKIP_RE.search(s.strip()):
        return False
    if s == s.lower() and " " not in s.strip():     # keys like "album", "off"
        return False
    return " " in s.strip() or s[:1].isupper()


def collect():
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    inside_f, docs = set(), set()
    for n in ast.walk(tree):
        if isinstance(n, ast.JoinedStr):
            inside_f.update(id(v) for v in n.values)
        if isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.Module)) and n.body:
            first = n.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                docs.add(id(first.value))
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "KEEP_TOGETHER" for t in n.targets):
            inside_f.update(id(c) for c in ast.walk(n.value))       # band names
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "MOOD_WORDS" for t in n.targets):
            for v in n.value.values:
                inside_f.update(id(c) for c in ast.walk(v))          # genre keywords
    texts = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in inside_f and id(n) not in docs:
            if literal_ok(n.value):
                count = iter(range(99))   # "Retrying {n} download(s)." is filled in with .format(n=...)
                texts.add(re.sub(r"\{[a-z]\w*\}", lambda m: "{%d}" % next(count), n.value))
        elif isinstance(n, ast.JoinedStr):
            parts, k = [], 0
            for v in n.values:
                if isinstance(v, ast.Constant):
                    parts.append(str(v.value).replace("{", "{{").replace("}", "}}"))
                else:
                    parts.append("{%d}" % k)
                    k += 1
            tpl = "".join(parts)
            lit = "".join(str(v.value) for v in n.values if isinstance(v, ast.Constant))
            if k and tpl not in KEEP and not TECH_RE.search(tpl) and re.search(r"[A-Za-z]{3}", lit) and "<" not in tpl and "\\" not in tpl and "_" not in lit \
                    and not tpl.startswith(("http", "{0}/")) and not re.match(r"Q[A-Z]", tpl):
                texts.add(tpl)
    return sorted(texts)


def gtx(text, lang):
    url = ("https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=" + lang
           + "&dt=t&q=" + urllib.parse.quote(text))
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "eozMP-translations"})
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read().decode("utf-8"))
            return "".join(seg[0] for seg in data[0] if seg and seg[0])
        except Exception:
            time.sleep(2 + attempt * 3)
    return None


BRANDS = ["Soulseek", "slskd", "eozMP", "MusicBrainz", "VLC", "lrclib.net", "AcoustID", "Last.fm", "ReplayGain", "Eren Özer"]   # never translated


def prep(s):
    """Strip menu accelerators (&File) and hide brand names behind {9x} placeholders before translating."""
    accel = bool(re.search(r"&\w", s)) and not re.search(r"\s&\s", s)
    s = s.replace("&", "") if accel else s
    for i, b in enumerate(BRANDS):
        s = s.replace(b, "{%d}" % (90 + i))
    return s, accel


def unprep(t, accel):
    for i, b in enumerate(BRANDS):
        t = t.replace("{%d}" % (90 + i), b)
    return ("&" + t) if accel else t


def valid(src, out):
    return out and sorted(PH_RE.findall(src)) == sorted(PH_RE.findall(out))


def translate_lang(lang, todo):
    """Translates in batches of single lines (one request = many texts); falls back to one by one."""
    res = {}
    single = [s for s in todo if "\n" not in s]
    multi = [s for s in todo if "\n" in s]
    batches = [single[i:i + 40] for i in range(0, len(single), 40)]

    def run_batch(batch):
        clean = [prep(s) for s in batch]
        out = gtx("\n".join(c for c, _ in clean), lang)
        lines = out.split("\n") if out else []
        got = {}
        if len(lines) == len(batch):
            for s, (c, accel), line in zip(batch, clean, lines):
                t = line.strip()
                if valid(c, t):
                    got[s] = unprep(t, accel)
        for s, (c, accel) in zip(batch, clean):     # anything the batch mangled: one at a time
            if s not in got:
                t = gtx(c, lang)
                if valid(c, t):
                    got[s] = unprep(t.strip(), accel)
        return got

    def run_one(s):
        c, accel = prep(s)
        t = gtx(c, lang)
        return {s: unprep(t.strip(), accel)} if valid(c, t) else {}

    with ThreadPoolExecutor(max_workers=4) as pool:
        for got in pool.map(run_batch, batches):
            res.update(got)
        for got in pool.map(run_one, multi):
            res.update(got)
    return res


def main():
    texts = collect()
    print(len(texts), "interface texts")
    old = {}
    if OUT.exists():
        ns = {}
        exec(OUT.read_text(encoding="utf-8"), ns)
        old = ns.get("LANG", {})
    over = json.loads(OVERRIDES.read_text(encoding="utf-8")) if OVERRIDES.exists() else {}
    table = {}
    for lang in LANGS:
        have = {k: v for k, v in old.get(lang, {}).items()
                if k in texts and all(b in v for b in BRANDS if b in k)}    # re-do mangled brand names
        todo = [t for t in texts if t not in have]
        print(f"{lang}: {len(have)} kept, translating {len(todo)}...", flush=True)
        have.update(translate_lang(lang, todo))
        have.update({k: v for k, v in over.get(lang, {}).items()})
        table[lang] = dict(sorted(have.items()))
        print(f"{lang}: {len(table[lang])} / {len(texts)} done", flush=True)
    OUT.write_text("# Generated by tools/make_translations.py - edit tools/overrides.json instead.\n"
                   "LANG = " + json.dumps(table, ensure_ascii=False, indent=0) + "\n", encoding="utf-8",
                   newline="\n")   # Windows would write CRLF
    print("wrote", OUT)


if __name__ == "__main__":
    if "--list" in sys.argv:
        for t in collect():
            print(repr(t))
    else:
        main()
