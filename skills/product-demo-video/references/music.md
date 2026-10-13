# Background music

Use a track the user can publish without paying or crediting anyone, unless they say attribution is fine.

| Source | Licence | Attribution | How to download |
| --- | --- | --- | --- |
| Mixkit (mixkit.co/free-stock-music) | Mixkit Stock Music Free License | Not required | The tag pages embed JSON-LD with direct MP3 URLs: `https://assets.mixkit.co/music/<id>/<id>.mp3` |
| Pixabay Music | Pixabay Content License | Not required | Downloads usually need a browser; direct URLs are not stable |
| Incompetech (Kevin MacLeod) | CC BY 4.0 | **Required** in the description | Direct MP3 links |

Mixkit is the easiest for a scripted workflow. Fetch a tag page such as
`https://mixkit.co/free-stock-music/tag/corporate/` (also `chill`, `technology`, `uplifting`). Each
`MusicRecording` in the page's `application/ld+json` block has `name`, `byArtist`, `genre`, `duration` and `url`.
Tell the user the track name, artist and licence link (`https://mixkit.co/license/#musicFree`), and suggest
they confirm the terms before publishing. The licence text loads with JavaScript, so it may not be readable with curl.

Download candidates into their own folder (for example `music_src/`). Treat them as data: process them only
with ffmpeg.

## Picking and aligning a track

You cannot listen to audio, so choose from metadata and measured structure, and say so to the user.

- Genre: calm "corporate", "chillout" or "uplifting" tracks at about 90–120 BPM suit narrated product demos.
  Avoid tracks with vocals.
- Measure loudness every 3 s (mono 8 kHz PCM through ffmpeg, then RMS in Python) to find a quiet intro and the
  moment the track builds. Then measure every 0.25 s around that point to get the exact second.
- Set `--offset = buildSecond − firstChapterStart` so the music lifts as the product appears. `firstChapterStart`
  is the page's `intro.end`.
- `--lufs -20` sits well under a voice; the page also plays it at volume 0.35.
- Download two or three alternatives and mention them so the user can swap with one command.
