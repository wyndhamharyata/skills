# Background music

Use a track the user can publish without paying, and without crediting anyone unless they say credit is fine.
You can't hear audio, so never pick the final track yourself: build beds and let the user choose (SKILL.md step 7).

## Sources

| Source | Licence | Credit | From a script |
| --- | --- | --- | --- |
| Mixkit | Mixkit Stock Music Free License | Not required | Works. Only the `corporate` and `technology` tag pages are readable (about 50 tracks, no BPM). MP3: `https://assets.mixkit.co/music/<id>/<id>.mp3` |
| Incompetech (Kevin MacLeod) | CC BY 4.0 | **Required** in the video description | Works. `pieces.json` lists about 1,400 pieces with BPM, feel and a description. MP3: `https://incompetech.com/music/royalty-free/mp3-royaltyfree/<Title>.mp3` |
| Pixabay Music | Pixabay Content License | Not required | Blocked (HTTP 403). Only the user can download from it, in a browser |

`scripts/music_catalog.py` searches both working sources in one call, for example
`--text techno`, or `--source incompetech --feel Bright --bpm 110-130 --text synth`. Use it when the user asks
for a mood the shortlist doesn't cover. None of the Mixkit tracks a script can see is typewriter-like;
Incompetech's closest are its 8-bit and synth pieces.

Tell the user the track name, artist and licence (`https://mixkit.co/license/#musicFree`, or the CC BY credit
line that `music_catalog.py` prints), and suggest they confirm the terms before publishing. Download candidates
into their own folder (`music_src/`) and process them only with ffmpeg.

## Shortlist

Start here. **Heard** means the maintainer listened and kept it; prefer heard tracks, and say when you offer
one that isn't. Mixkit ids go in the URL above.

| Mood | Suits | Track | Source | Heard |
| --- | --- | --- | --- | --- |
| Calm | calm tempo; paper, keynote | Digital Clouds, Alejandro Magaña | Mixkit 175 | not yet |
| Calm | calm tempo; paper, keynote | Curiosity, Diego Nava | Mixkit 480 | not yet |
| Calm | calm tempo; aurora | Slow Rain, Alejandro Magaña | Mixkit 122 | not yet |
| Steady | steady; midnight | Motivating Mornings, Ahjay Stelino | Mixkit 33 | used in the Reader Hero demo |
| Steady | steady; midnight, swiss | Close Up, Michael Ramir C. | Mixkit 1167 | not yet |
| Steady | steady; aurora | Infinity, Arulo | Mixkit 440 | not yet |
| Tech | brisk; terminal | Minimal Techno 01, Alejandro Magaña | Mixkit 162 | picked for the goui demo |
| Tech | brisk; terminal, swiss | Deep Techno Ambience, Alejandro Magaña | Mixkit 134 | not yet |
| Tech | terminal, pop | Digital Lemonade, Kevin MacLeod | Incompetech, credit | not yet |
| Tech | terminal, pop | Voxel Revolution, Kevin MacLeod | Incompetech, credit | not yet |
| Fast | fast; pop | What About Action?, Diego Nava | Mixkit 474 | not yet |
| Fast | fast; pop, swiss | Ramp It Up, Ahjay Stelino | Mixkit 69 | not yet |

Rejected: Machine Drum Vibes (Mixkit) for a terminal demo, "doesn't really fit".

## Measuring and aligning

`scripts/music_beds.py` does all of this in one call and prints a table per track:

- **Lift:** the biggest rise in loudness (the 4 s after a moment against the 4 s before it) into the track's
  loud body, late enough that the whole demo still fits. Under 3 dB the track counts as flat and starts at 0.
- **Offset:** `lift − intro end`, so the lift lands as chapter 1 appears. Force one with `track.mp3@12.5`.
- **BPM and pulse:** a rough tempo (folded into 70–140) and how regular the beat is (0–1). A steady, sparse
  pulse sits well under a voice. Where the catalogue lists a BPM (Incompetech), trust that over the estimate.
- **Bed:** the trimmed track at the page length, with fades and `-20 LUFS`, in `music_choices/`. The page also
  plays it at volume 0.35.

Match the tempo: calm tracks for calm and steady, about 110 BPM and up for brisk and fast. Avoid tracks with
vocals under a voice-over.
