---
name: product-demo-video
description: Turn a raw screen recording (Mac app, web app or phone simulator) into a polished product demo, meaning an auto-advancing webpage with chapter captions, camera zooms and cut-out UI that the user narrates over in Loom, plus a rendered H.264 MP4 and optional free background music. Seven looks (dark, editorial, gradient, keynote, Swiss, playful, terminal/code-editor) and four tempos from calm to fast. Use this whenever someone wants to edit, trim, cut dead air from, speed up, zoom into or "make a demo/promo/walkthrough video" from a screen recording (.mov or .mp4), wants something like a polished launch or feature video, or mentions recording Loom over a demo page, even if they don't say "skill" or "webpage".
metadata:
  short-description: Turn a screen recording into an auto-playing product demo page (7 styles, 4 tempos) to narrate in Loom, plus an MP4 with music.
compatibility: Needs ffmpeg, ImageMagick 7, Python 3 with Pillow, Node 18+ with playwright-core, and Chromium or Google Chrome. Run scripts/doctor.sh to check.
---

# Product demo video from a screen recording

The result is a branded stage: chapter steps, a caption and short "chips" sit beside the product, which plays
inside a Mac window, phone or editor pane while a camera eases in on what the user is doing. There's an intro
(title, plus cut-out UI) and an outro. The page plays automatically, so the user can record a Loom with their
face and voice on top. The same page renders, frame-exact, to an MP4.

Two settings change the feel without touching the content. The **style** sets the look and layout (seven,
from a dark launch look to a code-editor look). The **tempo** sets the pace, from calm to fast. Let the user
choose both from stills of their own footage (step 5).

This approach exists because the obvious one, ffmpeg zoompan with highlight boxes drawn over the UI, looked
amateur and was rejected. Captions beside the product, plus a camera that frames the action, look like a real
launch video. Don't draw rectangles or labels over the UI.

## Tools in this skill

Paths are relative to this skill's folder. Work in a project folder next to the recording,
such as `<project>/demo/`, with `page/`, `output/` and `render/` inside it.

| Script | What it does |
| --- | --- |
| `scripts/contact_sheet.py` | Time-labelled frame grids; `--crop` to one window; `--grid` adds 0.1 gridlines to read focus points |
| `scripts/activity.py` | Change per sample; lists idle spans (dead air); `--ref` shows when a pop-up (Dock, notification) appears and leaves |
| `scripts/cut_clips.py` | Cuts cropped clips from `clips.json` (segments with speed); `--preview` shows every clip's start, middle and end before cutting; `--map`/`--list` convert source time ↔ clip time |
| `scripts/cutout.py` | Background-removed PNG of a UI element (rounded alpha) for the intro |
| `assets/demo-template.html` | The page engine. Copy it to `page/index.html`; never edit content into it |
| `assets/example.config.js` | A complete worked config. Copy it to `page/demo.config.js` and rewrite it |
| `scripts/render.mjs` | Headless Chromium render to MP4, `--stills t1,t2` for checks, `--timeline` for chapter times; `--style`/`--tempo` override the config, and `--stills … --style all` makes a labelled sheet of every style |
| `scripts/music_catalog.py` | Searches Mixkit and Incompetech (title, feel, BPM) and prints direct MP3 links |
| `scripts/music_beds.py` | Measures candidate tracks, aligns each one's lift with chapter 1, and writes one bed per track for the user to choose |
| `scripts/add_music.py` | Trims, fades and normalises the chosen track; writes `page/music.m4a`; muxes it into the MP4 |
| `references/page-config.md` | Every config field, timing and camera semantics, and framing rules. **Read it before writing the config** |
| `references/styles.md` | The 7 styles and 4 tempos: layouts, what each suits, quirks, and how to choose with the user |
| `references/music.md` | Free-to-use music sources, licences, and how to pick and align a track |

Requirements: ffmpeg, ImageMagick (`magick`), Python 3 with Pillow, and Node with `playwright-core`
(`cd render && npm init -y && npm i playwright-core`). Chromium comes from `$CHROME_PATH`, Playwright's cache or
Google Chrome. If none is found, run `npx playwright install chromium-headless-shell`. Run `scripts/doctor.sh`
first; it lists anything missing with the command to install it.

## Workflow

### 0. Start clean and keep notes

- **Context is the cost.** Every step re-reads the whole conversation, so a demo built at the end of a long,
  unrelated session costs several times more than the same demo in a fresh one. If the conversation already
  holds a lot of other work, say so once and suggest a new session with only the recording path. Carry on if
  the user would rather stay.
- **Keep `demo/NOTES.md`** from step 1 onward, and update it after every decision. A new session reads it first
  instead of analysing the recording again. Keep it short:

  ```md
  # Demo notes
  - Recording: <path>, <W×H>, <duration> s, <fps> fps
  - Crop: <W:H:X:Y>, checked with --preview (left out: <e.g. the Dock on the right edge>)
  - Beats: <source s> <what happens>, one line each; mark dead air and other apps
  - Chapters: <clip> src <a–b>: <the action> at clip <t>
  - Look: <style> / <tempo>. Music: <track> at offset <s>, or "beds in music_choices/, waiting for the user"
  - Open: <claims to confirm, questions for the user>
  ```

### 1. Understand the recording (don't skip; every later step depends on it)

1. `ffprobe` the file for its size, duration and frame rate. Mac screen recordings are often variable frame rate at
   Retina size, such as 3600×2338.
2. Make a 1 frame/s sheet of the whole screen, then a 0.5 s sheet cropped to the app. Write down a beat list:
   what the user does and when (clicks, panels opening, results appearing), and what's dead air or a mistake.
3. Find exact window bounds by sampling pixels along a row and a column (Python + Pillow) where the window
   edge meets the wallpaper. Use the content area below the title bar; the page draws its own frame. The Dock or
   another window can overlap the app's edge, so confirm the crop with `cut_clips.py --preview` (step 3).
4. Look outside the app too. If the story starts or ends in the OS (double-clicking a file in Finder, a share
   sheet, a notification), that moment is often the point, for example "it's your system PDF reader". Keep it as
   an **overlay clip** instead of cropping it away. Cropping it out was a real miss.
5. Run `activity.py` on the app region for idle spans. On suspicious moments, run `--ref` on a thin strip at
   the screen bottom (Dock) or top-right (notifications) to get exact pop-up start and end times.

### 2. Plan chapters

Pick 3–5 chapters. Each is one feature the viewer should remember. Give each:
- a one-word **label** (it's also the step and the outro pill), a short **title** and a one-sentence **body**;
- source segments `[start, end, speed]`: cut dead air and mistakes, speed scrolling and waiting up 1.5–2×, and keep
  clicks and results at 1×;
- 1–3 **chips** stating what's on screen.

Write copy only from what is visible in the recording (counts changing, labels, dialogs). Don't invent
capabilities, and ask the user to check claims like "no spoilers" or "works offline". Prefer plain words.
Let the content set the length: about 45 s of usable footage gives a page of about 65 s at the steady tempo,
about 48 s at fast and about 73 s at calm. If the user asks for a fixed length (for example 90 s) and the footage
is short, say so, and offer a calmer tempo, longer holds or `duration`.

### 3. Cut the clips

Write `clips.json` (format in `cut_clips.py`'s docstring), and for each chapter write the clip time of its key
action in `NOTES.md`. **Before cutting**, run `cut_clips.py clips.json --preview` and look at the one sheet it
writes: the start, middle and end of every clip, cropped. Every tile edge must be the app (no Dock, menu bar
or other window), every middle tile should show the chapter's action, and no tile may show a pop-up or another
app. Fix the crop or the ranges first; one sheet is far cheaper than re-cutting six clips. Then cut, and
**check every cut boundary** with a sheet at 0.1–0.25 s around it. Pop-ups and glitches often last longer than they first appear, and a cut needs
margin. Overlay clips (for example Finder) get their own `crop` and must start at the same source second as
their chapter's clip.

### 4. Cut-outs (background removal)

Use `cutout.py` to pull 4–7 recognisable UI pieces from a clean frame for the intro: covers, cards, a key
button, app icons. Measure one cleanly, reuse the grid pitch for its siblings. Pick pieces of a similar shape
(width ÷ height about 1.3–1.8) so the row reads evenly, and set `intro.cutoutWidth` so the row spans about
60–70% of the stage width. Check them all in one montage on a dark background before using them.

### 5. Build the page

Copy `assets/demo-template.html` → `page/index.html` and `assets/example.config.js` → `page/demo.config.js`.
Then rewrite the config: brand accent taken from the product, stage size, frame type and aspect, chapters,
steps, cams, chips, overlays and outro. Follow `references/page-config.md`. Read camera focus points from
`contact_sheet.py --times … --crop … --grid` sheets of the cut clips, not from guesses. Write all timings for
the `steady` tempo; the other tempos scale them.

**Pick the look with the user.** Unless they already named a style and tempo, render one mid-chapter moment
in every style (`render.mjs … --stills <t> --style all --stills-dir ../looks`), show them
`looks/sheet_t_<t>.jpg`, and recommend one or two styles from `references/styles.md` for their product and
audience. Then ask about pace: calm, steady, brisk or fast. Put both in the config. The template is the same
for every look, so changing either later is one line and a re-render.

### 6. Check with stills, then render

1. `node <skill>/scripts/render.mjs ../page/index.html --timeline` (from `render/`) prints chapter times.
2. Render 8–14 stills at the important moments in the chosen style and tempo: each chapter's first zoom, every
   hold, every overlay hand-off, intro and outro. Times come from `--timeline`, which changes with the tempo.
   Make one montage and look at it. Check that:
   - no zoom cuts the start of text lines (in Pop, also that the cropped panel shows the action);
   - the hold shows the intended state (not one frame early);
   - overlays and chips don't cover the caption or each other;
   - chips match what's on screen;
   - the Loom spot (`--cam` on stills, or **C** live) doesn't hide anything important.
3. Fix the config and re-check only the stills that changed. Stills take seconds; a full render takes about
   1.5 min per minute of video.
4. Full render: `node render.mjs ../page/index.html --out ../output/demo-silent.mp4`. Spot-check about 12 frames
   of the MP4 in one montage.

### 7. Music (when asked, or offer it)

You can't hear audio, so the user picks the track. Follow `references/music.md`:

1. Take 3–5 candidates for the chosen style and tempo: first from the heard shortlist in `music.md`, then, for
   a specific mood the user asked for, from `music_catalog.py`.
2. Download them into `music_src/` and build one bed each:
   `music_beds.py --duration <page duration> --intro-end <chapter 1 start> --out music_choices music_src/*.mp3`.
   Both numbers come from `--timeline` for the chosen tempo. Each bed starts where its lift lands on chapter 1.
3. Give the user the `music_choices/` folder and the table it printed, and ask which one. Don't mux before they
   choose, and record the candidates in `NOTES.md`.
4. Mux the chosen one:
   `add_music.py --track … --offset <from the table> --duration … --page-out page/music.m4a --video-in output/demo-silent.mp4 --video-out output/demo.mp4`,
   and add `music: {src: 'music.m4a', volume: .35}` to the config so the live page plays it too.

Re-run the beds and the mux whenever the tempo changes, because the length changes. For an Incompetech track,
give the user the credit line `music_catalog.py` prints.

### 8. Hand over

Tell the user, briefly:
- the MP4 path and specs, and the page path;
- the style and tempo used, and that they're one line each in the config (or **S** and **T** to try others live);
- how to record: open the page in Chrome, **F** full screen, **C** camera spot, **Space** play, **M** music.
  Loom only captures the music if computer audio is on;
- what was cut or sped up, and any copy claims to verify;
- how to adjust: edit `demo.config.js`, then re-run stills or the render.

Offer to open Finder on the folder.

## Working style

- Users of this skill usually want results fast and get frustrated by long loops. Check with stills before any
  full render. Never re-render the whole video to test one framing change.
- Report in plain words: what the viewer will see, not filter names.
- **Every image you look at stays in the conversation** and is re-read on every later turn. Answer each visual
  question with one montage, not separate frames. Crop to the region in question (`--crop`) instead of reading
  a whole stage, and don't open an image again once you've described it in `NOTES.md`.
- Keep tool output short: tables and one-line results, not logs or long directory listings.
- When a still looks wrong, find which element paints it before changing the config. A frame that is right on
  its own but wrong after other frames is a page bug, not a stale render; fix it in the template.
- Keep the user's raw recording untouched. All outputs go in the project's `demo/` folder.
- ffmpeg builds may lack `drawtext`, and ImageMagick may have no default font (`unable to read font`).
  Label images with Pillow (`contact_sheet.py` does) or pass `-font /path/to/font.ttf`.
