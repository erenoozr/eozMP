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

## Separate programs and online services

eozMP does not include these; it talks to them while running.

- **slskd** and the **Soulseek** network: a separate program you install yourself (see the manual).
- **lrclib.net**: free synced-lyrics database.
- **Apple iTunes Search API**, **MusicBrainz** and the **Cover Art Archive**: finding missing album covers.
  Album artwork belongs to its respective rights holders.
