# eozMP — User Manual

eozMP is a music player for Windows that organizes your songs by artist and album, shows covers and synced lyrics,
and can find and download music through Soulseek. This manual takes you from an empty PC to a working player,
step by step.

**Contents:** [What you need](#what-you-need) · [Installing](#installing-eozmp) · [First start](#first-start-adding-your-music) ·
[Finding your way around](#finding-your-way-around) · [Playing music](#playing-music) ·
[Lyrics, mini player and fullscreen](#lyrics-mini-player-and-fullscreen) ·
[Playlists, Browse, Search, Home and Stats](#playlists-browse-search-home-and-stats) ·
[Soulseek](#soulseek-logging-in-and-downloading) · [Preferences](#making-it-yours-preferences) ·
[Optional extras](#optional-extras-vlc-equalizer-and-visualizer) · [Backups and updates](#backups-updates-and-your-data) ·
[Troubleshooting](#troubleshooting) · [Shortcuts](#keyboard-and-mouse-shortcuts)

## What you need

| Item | Needed? | Where it comes from |
| --- | --- | --- |
| A Windows 10 or 11 PC | Yes | |
| `eozMP.exe` | Yes | The [latest release](../../releases/latest) of this repository |
| Your music files (mp3, flac, m4a, wav, ogg and more) | Yes | Your own folders |
| An internet connection | For lyrics and covers | |
| Python 3 | Only to build eozMP yourself | [python.org/downloads](https://www.python.org/downloads/) |
| slskd (a small Soulseek program) | Only for Soulseek | [github.com/slskd/slskd](https://github.com/slskd/slskd/releases) |
| VLC | Only for the equalizer | [videolan.org](https://www.videolan.org/) |

A Soulseek account is free. slskd creates it for you the first time it connects (see the Soulseek section).

## Installing eozMP

### The easy way: download the exe

1. Open the [latest release](../../releases/latest) and download **eozMP.exe** under *Assets*.
2. Put it wherever you like (for example on your Desktop) and double-click it.
3. If Windows shows a blue **Windows protected your PC** box, click **More info**, then **Run anyway**.
   This happens because the app is new and unsigned.

### Building it yourself

1. Install Python from [python.org/downloads](https://www.python.org/downloads/). On the first installer screen,
   tick **Add Python to PATH**, then click **Install Now**.
2. On this repository's page, click the green **Code** button → **Download ZIP**, and extract it.
3. Double-click **build_exe.bat**. A black window installs everything eozMP uses (PyQt6, mutagen, numpy,
   PyInstaller and python-vlc), then builds the app. The first time takes a few minutes.
4. When it says **Done!**, `eozMP.exe` is on your Desktop (and in the `dist` folder).

To run it straight from the source instead: open the extracted folder, click the address bar, type `cmd`,
press Enter, then run:

```
pip install -r requirements.txt
python musicplayer.py
```

The build command `build_exe.bat` runs, if you ever want to type it yourself:

```
python -m PyInstaller --noconfirm --onefile --windowed --name eozMP --icon eozMP.ico musicplayer.py
```

## First start: adding your music

Tell eozMP where your music is, and it builds your library by itself.

1. In the top menu, click **Library → Add music folder...** and pick the folder that holds your music.
   Subfolders are included.
2. Wait while it scans. The first scan reads every file, so a big library can take a minute or two;
   after that, starting is quick.
3. Your library appears on the left as **Artist → Album**. Songs with "feat." and collaborations
   ("A, B", "A & B", "A x B") are filed under the first artist.
4. Missing album covers are looked up online automatically (iTunes, then MusicBrainz).

To add more folders or remove one later, open **Preferences → Library**.

## Finding your way around

The window has four parts: the top menu, the left panel, the main area on the right, and the bottom bar.

| Part | What's there |
| --- | --- |
| Top menu | **Library** (folders, rescan, covers, organize downloads, backup), **Playlists**, **Soulseek**, **Stats**, **Preferences**, **Help** |
| Left panel, top | The eozMP name with **back / forward arrows**, the **Search** box, a **Soulseek search** icon and a **Downloads** icon (it shows a number while files download) |
| Left panel, tabs | **Home**, **Library** (artists and albums), **Playlists**, **Browse** (genres and decades), plus a **Sort** link (A-Z, Recently added, Most played) |
| Main area | The page you opened: home, an album, an artist, a playlist, lyrics, search results, stats, Soulseek or downloads |
| Bottom bar | The cover and song name (click the title or album to open the album, the artist to open their page), the current lyric line, the heart, and the progress bar |
| Bottom controls | Previous, play/pause, next, shuffle, repeat, Lyrics, Queue, EQ, mini player, fullscreen, mute and volume |

Two small tricks: click the song length under the progress bar to switch to **time left**, and click any album
cover to see it full size.

## Playing music

Double-click any song to play it; eozMP then carries on through the rest of the album and your library.

- **Albums and artists:** an album page has **Play album** and **Shuffle album**; an artist page has **Play all**
  and **Shuffle**. Click an artist's name anywhere to open their page.
- **Right-click** a song, album or artist for: Play, Play next, Add to queue, Add to / Remove from Favorites,
  Add to playlist, Song info and Show in folder.
- **Drag and drop:** drag songs, albums or artists onto a playlist (in the Playlists tab) or onto the **Queue** button.
- **Shuffle** picks songs at random without repeats until everything has played once. **Previous** always goes
  back to the song you actually heard.
- **Repeat** cycles through off, repeat all (the list starts over) and repeat one (the same song again).
- **Favorites:** click the heart next to the song (or press Ctrl+D). Your favorites show on the Home page.

### The queue panel

Click **Queue** (or press Ctrl+U) and a see-through panel slides in from the right.

- It shows **Now playing** and the songs you queued, which always play before the rest.
- Drag songs to reorder them. Click the **x** on a song to remove it, or select songs and press Delete.
- **Shuffle** mixes up the queue; **Clear** empties it.
- Click next to the panel, press Esc or click Queue again to close it.

### Keeps playing in the background

Closing the window keeps eozMP playing in the **system tray** (the small icons near the clock). Right-click the
tray icon for controls or **Quit eozMP**. Your keyboard's play/pause, next and previous keys work even when eozMP
isn't the active window.

## Lyrics, mini player and fullscreen

### Lyrics

Click **Lyrics** (or press Ctrl+L). Synced lyrics follow the song, with the current line kept in the middle.

- eozMP looks for lyrics in this order: a `.lrc` or `.txt` file next to the song, lyrics inside the song file,
  then the free lrclib.net database.
- **Search online** (next to the source text) looks the song up again. **Add manually** opens the song's folder
  and copies the right file name: save your lyrics there as a `.txt` (or a synced `.lrc`) file and they appear as
  soon as you save.
- Click a line to jump to that moment. Scroll yourself and the lyrics stop following for a few seconds, then
  glide back.

### Mini player

Click the mini player button (or press Ctrl+Shift+M) for a small window that stays on top of everything.

- Drag it anywhere; near a screen edge it snaps into place.
- Click or drag along its bottom bar to jump in the song; scroll the mouse wheel over it to change the volume.
- Double-click it (or use its expand button) to go back to the full player. Right-click for **Close eozMP**.

### Fullscreen player

Click the fullscreen button (or press F11). The cover and controls are on the left, the lyrics on the right, over
a slowly moving blurred background.

- The controls and mouse pointer fade after about 3 seconds without movement; move the mouse to bring them back.
- Top right: **–** leaves fullscreen, **✕** closes eozMP completely. Esc also leaves fullscreen.
- Space pauses; the Left and Right arrow keys skip. In the last 15 seconds of a song, an **Up next** card shows
  what comes next.

## Playlists, Browse, Search, Home and Stats

- **Playlists:** open the Playlists tab and click **+ New playlist** (or press Ctrl+N). Add songs by
  right-clicking them (**Add to playlist**) or by dragging them onto the playlist's name. On a playlist's page you
  can Play, Shuffle, Rename and Delete; right-click a song to move it up or down or remove it.
- **Browse:** the Browse tab lists your genres and decades. Click one to see its albums, with **Play all** and
  **Shuffle**. Genres come from your songs' tags.
- **Search:** type in the Search box (Ctrl+F). Results show as Artists, Albums and Songs. Press **Enter** to also
  search Soulseek (see the next section).
- **Home:** Recently played, Recently added and your Favorites as rows of covers. Open it with the Home tab or Ctrl+H.
- **Stats:** click **Stats** in the top menu for listening time, plays, top songs, artists and albums for the last
  7 days, 30 days, this year or all time. A song counts as played after 30 seconds, or half of it if it's short.
- **Back and forward:** the arrows at the top left (or Alt+Left / Alt+Right, or your mouse's side buttons) take you
  through the pages you visited.

## Soulseek: logging in and downloading

eozMP talks to Soulseek through **slskd**, a small free program that runs in the background and holds your
Soulseek login. You set it up once; after that, just keep slskd running whenever you want to use Soulseek.

### 1. Get slskd

1. Go to [github.com/slskd/slskd/releases](https://github.com/slskd/slskd/releases) and scroll to **Assets** under
   the newest release.
2. Download the file whose name ends in **win-x64.zip**. Do not pick "Source code": it has no program in it.
3. Right-click the zip, choose **Extract All**, and open the extracted folder.
4. Double-click **slskd.exe**. A black window opens; leave it open, that is slskd running.
5. In your browser, go to `localhost:5030` and log in with username `slskd` and password `slskd`.

### 2. Log in to Soulseek (the settings file)

1. Press **Windows key + R**, type `%localappdata%\slskd` and press Enter.
2. Right-click **slskd.yml**, choose **Open with → Notepad**.
3. Go to the very bottom of the file and paste this, then change the parts described below:

```yaml
soulseek:
  username: "mymusic_7391"
  password: "PickAPassword123"

directories:
  downloads: C:\Users\YOURNAME\Music\Soulseek

web:
  authentication:
    username: slskd
    password: slskd
    api_keys:
      eozmp:
        key: PUT-ANY-LONG-RANDOM-TEXT-HERE-1234
        role: readwrite
        cidr: 0.0.0.0/0,::/0
```

- **username / password (under soulseek):** make up a Soulseek name with some random numbers so nobody else has
  it, and a password with only letters and numbers. The account is created automatically the first time slskd
  connects; there is no separate sign-up.
- **downloads:** the folder where downloaded music should go. Replace `YOURNAME` with your Windows user name.
- **key:** type 20 or more random letters and numbers, like a password. eozMP needs this same text later, so copy
  it somewhere.
- Use spaces, never the Tab key, and keep the spacing exactly as shown. The words `soulseek:`, `directories:` and
  `web:` must each appear only once without a `#` in front.

4. Save (Ctrl+S), close the slskd window, and start `slskd.exe` again.
5. Refresh `localhost:5030`: it should say you're connected to Soulseek. If it says the server rejected your login,
   that username is taken; pick another one in the file and restart slskd.

### 3. Connect eozMP

1. In eozMP, open **Preferences → Soulseek**.
2. Fill in: slskd address `http://localhost:5030`, the **API key** (the long text from the file) and the
   **downloads folder** (the same folder as in the file).
3. Click **Test connection**. "Connected to slskd." means it works. Click **OK**.

### 4. Finding and downloading music

- **From the search box:** type an artist or album and press **Enter**. Under your library results, a
  **From Soulseek** section fills in after about 30 seconds, grouped by album with quality and size. Double-click a
  row, or select rows and click **Download selected**.
- **The Soulseek page:** click the Soulseek search icon next to the search box for a full results page with
  filters: Albums or Files, quality (lossless only, MP3 320k+), and free slots only.
- **Whole discography:** on the Soulseek page, click **Whole discography...** and type an artist. eozMP picks the
  best copy of every album; albums you already have come unticked.
- **Downloads:** the Downloads icon (with its number badge) shows progress. You can retry failed downloads, clear
  finished ones, or cancel.
- **Tidy library:** finished downloads are moved into your first music folder as `Artist / Album / 01 - Title` and
  show up in your library by themselves. You can turn this off or pick another folder in Preferences → Soulseek;
  **Library → Organize downloads now** tidies files you already have.

Soulseek is a file-sharing network. Only download music you're allowed to have.

## Making it yours: Preferences

Click **Preferences** in the top menu (or press Ctrl+,). **Apply** shows a change without closing the window.

| Tab | What you can change |
| --- | --- |
| General | Reopen on the song where you stopped, keep playing the next song, show the current lyric line under the song title, keep playing in the tray when you close the window, use the keyboard's media keys |
| Appearance | Theme (System, Dark, Light), accent color (presets, colors from each album cover, or any custom color by hex code or color picker), corners, spacing, album cover size, how albums look in the left list, fade between pages, app font (Times New Roman, the system font or any font) and text size, mini player opacity |
| Library | Music folders, group featured artists, put collaborations under the first artist, names that should never be split (such as Simon & Garfunkel), ignore "The" when sorting, find missing covers online, save found covers into album folders |
| Lyrics | Style (Album art or Classic), alignment, font, weight, size, brightness of the other lines, fade at the edges, smooth line changes, soft shadow, online lookup, save found lyrics next to songs |
| Audio | Audio engine (built-in or VLC), visualizer (Off, Bars, Wave), moving fullscreen background, open the equalizer |
| Soulseek | slskd address, API key and downloads folder, Test connection, default results view and quality filter, free slots only, organizing finished downloads |

## Optional extras: VLC, equalizer and visualizer

These are optional; eozMP works fully without them.

- **VLC engine and equalizer:** install VLC from [videolan.org](https://www.videolan.org/) (the normal 64-bit
  version). Then open **Preferences → Audio**, set the engine to **Automatic (VLC if installed)** and click OK.
  Press **EQ** (or Ctrl+E) for a 10-band equalizer with presets. If VLC can't play on your PC, eozMP switches back
  to the built-in engine by itself and tells you why.
- **Visualizer:** in **Preferences → Audio**, choose **Bars** or **Wave**. It shows at the bottom of the lyrics page
  and the fullscreen player. It works with the built-in engine (not VLC).

## Backups, updates and your data

- **Back up:** **Library → Back up eozMP...** saves your settings, playlists, favorites, listening stats and saved
  lyrics into one `.zip` file. **Library → Restore from backup...** loads them back, for example on a new PC.
- **Updating:** download the newest `eozMP.exe` from the [releases](../../releases) and replace the old one
  (or download the new source and run `build_exe.bat` again). Your settings, playlists and stats are kept.
- **Your music files** are never changed, except when you allow it: organizing Soulseek downloads, saving lyrics
  next to songs, or saving found covers into album folders.

eozMP keeps its own data in your user folder (`C:\Users\YOURNAME`):

| File or folder | What it holds |
| --- | --- |
| `.simple_music_player.json` | Your settings |
| `.simple_music_player_playlists.json` | Your playlists |
| `.simple_music_player_stats.json` | Favorites and listening stats |
| `.simple_music_player_cache.json` | The library list (makes starting fast) |
| `.simple_music_player_lyrics` | Lyrics found online |
| `.simple_music_player_covers` | Covers found online |

## Troubleshooting

| Problem | What to do |
| --- | --- |
| `build_exe.bat` says Python was not found | Reinstall Python and tick **Add Python to PATH** on the first screen |
| Blue "Windows protected your PC" box | Click **More info**, then **Run anyway** |
| Songs don't play or there's no sound | Preferences → Audio → set the engine to **Qt (built-in)**; check the volume isn't on Muted |
| The library is empty | Library → Add music folder; then Library → Rescan library |
| An artist is split up or grouped wrongly | Preferences → Library: collaborations, featured artists and the "never split" list |
| No lyrics | Click **Search online**, or **Add manually**; check online lookup is on in Preferences → Lyrics |
| Soulseek: "Can't reach slskd" | Start `slskd.exe` (the black window must stay open) and check the address is `http://localhost:5030` |
| Soulseek: HTTP 401 or 403 | The API key in eozMP doesn't match the `key:` line in `slskd.yml` |
| Soulseek: login rejected | That username is taken; change it in `slskd.yml` and restart slskd |
| Downloads don't show up in the library | Check the downloads folder in Preferences → Soulseek, then Library → Organize downloads now |
| Media keys do nothing | Another app (for example a browser playing music) has them; close it and restart eozMP |
| No visualizer | It needs the built-in engine; if you build it yourself, run `pip install -U PyQt6 numpy` and rebuild |
| The window closed but music still plays | eozMP is in the system tray; right-click its icon → Quit eozMP |

## Keyboard and mouse shortcuts

The same list is inside the app under **Help → Keyboard shortcuts** (F1).

| Action | Shortcut |
| --- | --- |
| Play / pause | Space (when not typing) or Ctrl+P |
| Next / previous song | Ctrl+Right / Ctrl+Left |
| Volume up / down | Ctrl+Up / Ctrl+Down |
| Mute | Ctrl+M |
| Lyrics | Ctrl+L |
| Queue panel | Ctrl+U |
| Search | Ctrl+F |
| Home | Ctrl+H |
| Like / unlike the song | Ctrl+D |
| Equalizer | Ctrl+E |
| Mini player | Ctrl+Shift+M |
| Fullscreen player | F11 |
| Back / forward | Alt+Left / Alt+Right, or the mouse side buttons |
| New playlist | Ctrl+N |
| Preferences | Ctrl+, |
| Close the queue panel or fullscreen | Esc |
| Play / pause, next, previous from anywhere | Your keyboard's media keys |
| Mini player: volume / jump in song / back to full player | Mouse wheel / click the bottom bar / double-click |
| Lyrics: jump to a line | Click the line |
