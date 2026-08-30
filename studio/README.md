# HeartMuLa Studio

A standalone Windows studio for the open-weight [HeartMuLa](https://github.com/HeartMuLa/heartlib) model. Songs are written locally on your GPU. Cloud API keys are optional and never required to generate audio.

![Create a song](docs/screenshots/01-create.jpg)

HeartMuLa uses separate comma-separated style tags and tagged lyrics. **Generate Lyrics** / **Optimize** can draft lyrics when Writing is enabled in KEYS. **Create song** runs the local HeartMuLa worker. The WAV is saved under the song title, not `song.wav`.

![Library](docs/screenshots/02-library.jpg)

![Playing a song](docs/screenshots/03-playing.jpg)

The library holds every local generation with cover, seed, and details. Timed lyrics scroll on the card when you have synced them.

![Karaoke lyrics](docs/screenshots/04-karaoke.png)

![Regenerate cover](docs/screenshots/05-cover.png)

Cover art is local SD 1.5 by default (1:1). Optional visual direction stays in the popup. Cloud image keys, when added later, stay opt-in.

![Video Studio](docs/screenshots/06-video-studio.jpg)

**Make video** opens the local Video Studio (16:9 or 9:16 lyric visualizer + MP4). Cloud video keys are a later opt-in, not a replacement.

![Effects library](docs/screenshots/11-effects.jpg)

**Effects** is the local Stable Audio SFX library (rain, thunder, hits). Generate, preview, then **Add to Studio**.

![Native Studio](docs/screenshots/07-studio.jpg)

**Studio** is the clip timeline: original mix plus Vocals / Drums / Bass / Other, Mute/Solo, This Lane / All, fades, stereo placement, sixteen selectable region effects, and export. Effects include echo, reverb, auto-pan, tremolo, filters, telephone, saturation, stereo widening, dynamics, and leveling; see `editor.md` for the complete guide. **Export custom mix** becomes the song you hear in Library and Make video; the dry original is kept beside it.

![System drawer](docs/screenshots/08-system.jpg)

![API Keys drawer](docs/screenshots/09-keys.jpg)

![Generation log](docs/screenshots/10-logs.jpg)

Left rail: **LOGS**, **KEYS** (vaulted cloud helpers, Enable per category), **SYSTEM** (VRAM, models, stems, SFX, lyric sync).

More screenshots can drop into `docs/screenshots/`.

## What is local vs optional cloud

| Always local | Optional (KEYS tab) |
|---|---|
| HeartMuLa song generation | Writing: titles, Generate Lyrics, Optimize |
| Stem split (Demucs) | Cloud covers (not wired yet; local SD 1.5 is default) |
| Cover thumbnails (SD 1.5) | Cloud video (not wired yet; local Video Studio is default) |
| Sound effects, lyric sync, Studio mix | — |

Optional Writing helpers stay off until you enable them in KEYS. See [docs/api-keys.md](docs/api-keys.md).

## Current stack

- Tauri 2 + React desktop host. Closing the app kills the Python sidecar and GPU worker tree.
- Sidecar on `127.0.0.1:7784`: queue, cancel, library, Studio bounce, Video Studio.
- HeartMuLa 3B on a single RTX 3090. The app unloads the model before codec decoding to keep VRAM use manageable.
- Native Studio: clip timeline, This Lane / All lanes, fades, library drops, titled WAV export.

## Setup

```text
Setup HeartMuLa Studio.bat
```

Creates the local Python runtimes and installs the HeartMuLa dependencies. The checkpoints are already expected in the parent folder's `ckpt\` directory:

```text
..\ckpt\
├── HeartMuLa-oss-3B\
├── HeartCodec-oss\
├── tokenizer.json
└── gen_config.json
```

Optional:

- `Setup Lyrics Sync.bat` — WhisperX word timing (`models/lyrics`)
- `Setup Sound Effects.bat` — Stable Audio 3 Small SFX (see `MODEL_DOWNLOADS.md`)

Launch `HeartMuLa Studio.exe` or `Launch HeartMuLa Studio.bat`.

Set `HEARTMULA_MODEL_ROOT` if the checkpoints live somewhere else.

## Song actions

From each row’s `…` menu: Studio, Make video, edit details, regenerate cover, sync lyrics, extract stems, playlists / workspaces, download WAV / MP3 / FLAC, open the song folder (selects the titled WAV), delete.

MP3 is LAME V0; FLAC is compression 8. Both embed title, artist, album, genre, year, track, comment, and cover when present.

## Multitrack Studio

Top **Studio** tab, or **Open in Studio** on a song. Four Demucs stems plus the original mix as reference. Clip edit, razor, This Lane / All, fades, SFX from Effects, export mix to the last audible clip.

## Development

```powershell
py -3.11 -m venv python\venv
python\venv\Scripts\python.exe -m pip install -r python\requirements.txt
npm install
npm run tauri dev
```

Use one instance. Port `7784`.

## License note

This studio uses the HeartMuLa project and its Apache 2.0 license. Review the upstream model terms before commercial use.

