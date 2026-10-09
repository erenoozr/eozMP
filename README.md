<p align="center">
  <img src="eozMP_logo.png" width="128" alt="eozMP logo">
</p>

<h1 align="center">eozMP</h1>
<p align="center"><i>eren's definitely (not) sketchy music player — customize and enjoy your music.</i></p>

eozMP is a desktop music player for Windows. It organizes your music by artist and album, shows covers and
synced lyrics, and can find and download music through Soulseek.

## Features

- **Your library, tidy:** Artist → Album, with covers, numbers and years; collaborations filed under the first artist
- **Lyrics:** synced lyrics that follow the song (from `.lrc` files, the song's tags or lrclib.net), or add your own
- **Fullscreen player:** big cover and controls on the left, lyrics on the right, over a moving blurred background
- **Mini player:** small always-on-top window with the lyric line, seek bar and volume
- **Playlists, queue panel, favorites, shuffle and repeat** (previous always goes back to the song you heard)
- **Browse** by genre and decade, **search** artists / albums / songs, **listening stats**
- **Soulseek** (through slskd): search, download albums or whole discographies, auto-organize downloads
- **Make it yours:** themes, accent colors (even from the album cover), fonts, lyric styles, visualizer, equalizer (VLC)
- Media keys, system tray, drag and drop, backup and restore

## Download

Get `eozMP.exe` from the [latest release](../../releases/latest) and double-click it.
Windows may show a blue *"Windows protected your PC"* box because the app is new and unsigned:
click **More info → Run anyway**.

## Build it yourself

1. Install [Python](https://www.python.org/downloads/) and tick **Add Python to PATH** in the installer.
2. Download this repository (green **Code** button → **Download ZIP**) and extract it.
3. Double-click **`build_exe.bat`**. It installs everything and puts `eozMP.exe` on your Desktop.

Or run it straight from the source:

```
pip install -r requirements.txt
python musicplayer.py
```

## How to use it

Everything — first start, the queue, lyrics, fullscreen, **logging in to Soulseek with slskd**, settings and
troubleshooting — is in the **[User Manual](MANUAL.md)**.

## License

eozMP is free software, released under the **GNU General Public License v3.0** (see [LICENSE](LICENSE)).
You can use, change and share it; if you share a changed version, it must stay under the same license with its
source code available. It uses other open-source projects, listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

<img width="1075" height="889" alt="homepage" src="https://github.com/user-attachments/assets/0d0d5050-0438-4dd2-9207-d529d66931b9" />
<img width="1062" height="877" alt="appmain" src="https://github.com/user-attachments/assets/aecd3b5f-5e5a-4067-84e3-a015d527d243" />
<img width="1918" height="1198" alt="fullscreen" src="https://github.com/user-attachments/assets/bc772921-a652-45c8-b138-87b9246d7294" />
<img width="1072" height="886" alt="lyrics" src="https://github.com/user-attachments/assets/d4350764-ed26-418a-a082-f33348372c0e" />
<img width="543" height="210" alt="miniplayer" src="https://github.com/user-attachments/assets/cbb69bc0-6f03-4cc5-be0e-f46e4df8fbc4" />
<img width="1070" height="887" alt="search" src="https://github.com/user-attachments/assets/fa97ecab-344b-452f-af4a-f684c0c0be16" />
<img width="1067" height="959" alt="searchsoulseek" src="https://github.com/user-attachments/assets/fb0b1c7f-486f-47d2-8c85-baa722deb36e" />


## Disclaimer

eozMP is not affiliated with Soulseek, slskd, VLC, Apple, MusicBrainz or lrclib. Soulseek is a file-sharing
network: only download music you have the right to download. The software comes with no warranty.
