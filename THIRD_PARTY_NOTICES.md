# Third-party notices

eozMP (GPL-3.0) is built on these open-source projects. Each keeps its own license.

| Project | What eozMP uses it for | License |
| --- | --- | --- |
| [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) | Windows, buttons, audio playback | GPL v3 (or commercial) |
| [Qt 6](https://www.qt.io/) | The toolkit under PyQt6 | LGPL v3 / GPL |
| [mutagen](https://github.com/quodlibet/mutagen) | Reading song tags, covers and lyrics | GPL-2.0-or-later |
| [NumPy](https://numpy.org/) | Visualizer spectrum (optional) | BSD-3-Clause |
| [python-vlc](https://github.com/oaubert/python-vlc) | Talking to VLC for the equalizer (optional) | LGPL-2.1-or-later |
| [VLC / libVLC](https://www.videolan.org/) | Optional audio engine (installed separately) | LGPL-2.1-or-later |
| [PyInstaller](https://pyinstaller.org/) | Building `eozMP.exe` | GPL-2.0 with bootloader exception |
| [segno](https://github.com/heuer/segno) | The phone remote's QR code | BSD-3-Clause |
| [PyWinRT](https://github.com/pywinrt/pywinrt) | Windows media controls (lock screen, volume flyout) | MIT |

## Included in the installer

The installer (`eozMP-Setup-x.y.exe`, built with [Inno Setup](https://jrsoftware.org/isinfo.php)) also carries
these separate programs, unchanged. Their licenses are installed next to them.

| Program | What for | License |
| --- | --- | --- |
| [slskd](https://github.com/slskd/slskd) 0.26.1 | Talking to the Soulseek network | AGPL-3.0 (source: github.com/slskd/slskd) |
| [fpcalc / Chromaprint](https://github.com/acoustid/chromaprint) 1.6.1 | Recognising songs by their sound for *Fix tags* | LGPL-2.1-or-later (uses FFmpeg, LGPL) |
| [VLC](https://www.videolan.org/) | Optional: only downloaded from videolan.org during setup if you tick it | GPL-2.0-or-later |

## Separate programs and online services

eozMP does not include these; it talks to them while running.

- **slskd** and the **Soulseek** network: slskd comes with the installer but runs as its own program.
- **lrclib.net**: free synced-lyrics database.
- **Apple iTunes Search API**, **MusicBrainz** and the **Cover Art Archive**: finding missing album covers.
  Album artwork belongs to its respective rights holders.
- **AcoustID** (optional, your own key): recognising songs by their sound.
- **Last.fm** (optional, your own key): scrobbling and similar artists.
- **Google Translate** (unofficial free endpoint) and **MyMemory**: translating lyrics.
- **GitHub**: checking for a newer eozMP.
