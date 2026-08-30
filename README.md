# HeartMuLa Studio

HeartMuLa Studio is a standalone Windows desktop app for local HeartMuLa song
creation, lyric timing, cover art, stem extraction, multitrack editing, sound
effects, and lyric-video rendering.

## Download

Run [HeartMuLa Studio.exe](HeartMuLa%20Studio.exe). Model checkpoints are not
included; place the required HeartMuLa files in `ckpt\` as described in
[`studio/README.md`](studio/README.md).

## Resulting song

[![Watch the resulting song](https://img.youtube.com/vi/NQxVi77k3Hs/hqdefault.jpg)](https://youtu.be/NQxVi77k3Hs)

Listen to the resulting song on [YouTube](https://youtu.be/NQxVi77k3Hs).

## App screenshots

![HeartMuLa create screen](studio/docs/screenshots/01-create.jpg)
![Prompt entry](studio/docs/screenshots/02-prompt.png)
![Written song](studio/docs/screenshots/03-written-song.png)
![Custom editor](studio/docs/screenshots/04-custom.png)
![Advanced options](studio/docs/screenshots/05-options.png)
![Effects generation](studio/docs/screenshots/06-effects.png)
![Song library](studio/docs/screenshots/07-library.png)
![Lyric synchronization](studio/docs/screenshots/08-sync.png)
![Song ready](studio/docs/screenshots/09-ready.png)
![Effects ready](studio/docs/screenshots/10-effects-ready.png)
![Multitrack Studio](studio/docs/screenshots/11-multitrack.png)
![Video Studio landscape](studio/docs/screenshots/12-video-landscape.png)
![Video Studio portrait](studio/docs/screenshots/13-video-portrait.png)
![Video Studio controls](studio/docs/screenshots/14-video-controls.png)
![Video rendering](studio/docs/screenshots/15-video-render.png)

## Privacy

No personal API keys are included. Optional writing-provider keys are stored in
the local, ignored Studio vault and must never be committed.

## Source

The complete application source is in [`studio/`](studio/README.md), including
the desktop UI, sidecar services, multitrack editor, video studio, screenshots,
and build documentation.
