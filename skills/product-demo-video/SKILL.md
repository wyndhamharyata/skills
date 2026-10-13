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
| `scripts/cursor_track.py` | Rough cursor position per sample in cut clips, as JSON for `render.mjs --check-cams` |
| `assets/demo-template.html` | The page engine. Copy it to `page/index.html`; never edit content into it |
| `assets/example.config.js` | A complete worked config. Copy it to `page/demo.config.js` and rewrite it |
| `scripts/render.mjs` | Headless Chromium render to MP4, `--stills t1,t2` for checks, `--timeline` for chapter times; `--style`/`--tempo` override the config, and `--stills … --style all` makes a labelled sheet of every style; `--check-cams <dir>` lists times the cursor is outside the camera view |
| `scripts/music_catalog.py` | Searches Mixkit and Incompetech (title, feel, BPM) and prints direct MP3 links |
| `scripts/music_beds.py` | Measures candidate tracks, aligns each one's lift with chapter 1, and writes one bed per track for the user to choose |
| `scripts/add_music.py` | Trims, fades and normalises the chosen track; writes `page/music.m4a`; muxes it into the MP4 |
| `references/page-config.md` | Every config field, timing and camera semantics, and framing rules. **Read it before writing the config** |
| `references/styles.md` | The 7 styles and 4 tempos: layouts, what each suits, quirks, and how to choose with the user |
| `references/music.md` | Free-to-use music sources, licences, and how to pick and align a track |
| `references/subagents.md` | Briefs for the parallel work: crop, analysis window, chapter, cut-outs, music, stills check |

Requirements: ffmpeg, ImageMagick (`magick`), Python 3 with Pillow, and Node with `playwright-core`
(`cd render && npm init -y && npm i playwright-core`). Chromium comes from `$CHROME_PATH`, Playwright's cache or
Google Chrome. If none is found, run `npx playwright install chromium-headless-shell`. Run `scripts/doctor.sh`
first; it lists anything missing with the command to install it.

## Workflow

### 0. Budget, helpers and notes

- **One hour by default**, from the start to the first MP4, unless the user sets another limit. Checkpoints:
  chapter plan sent by about 15 min, clips cut by 25, look chosen by 35, first MP4 by 50. At each, send the user
  one line: where you are and what's next. If a checkpoint slips, say so and take the simpler path: fewer
  close-ups, the recommended style, no extra cut-out rounds. A revision round after the hand-over gets about 20 min.
  A run with no limit once took two hours and never finished, almost all of it in step 1.
- **Context is the cost.** Every step re-reads the whole conversation, and every image you open stays in it. A demo
  built at the end of a long, unrelated session costs several times more than in a fresh one. If the conversation
  already holds a lot of other work, say so once and suggest a new session with only the recording path.
- **Use subagents for the image-heavy work** when the harness can start them (Claude Code, OpenCode). You talk
  to the user, keep `NOTES.md` and `demo.config.js`, and make the decisions. Subagents analyse frames, check
  chapters and review stills in parallel, from the briefs in `references/subagents.md`, and send back text. They
  can't ask the user, so their questions come back to you to batch. Give analysis and review to a model that reads
  images well; cutting, rendering and muxing can go to a cheaper, faster one. Without subagents, run the same
  briefs yourself, one after another.
- **Keep `demo/NOTES.md`** from step 1 onward and update it after every decision:

  ```md
  # Demo notes
  - Recording: <path>, <W×H>, <duration> s, <fps> fps
  - Crop: <W:H:X:Y>, checked with --preview (left out: <e.g. the Dock on the right edge>)
  - Beats: <source s> <what happens>, one line each; mark dead air
  - Outside the app: <source s> <Finder / file picker / notification / other app>: overlay or cut, and why
  - Chapters: <clip> src <a–b>: <the action> at clip <t>
  - Claims: <chip or caption text> -> <clip> at <t>, where it's visible
  - Look: <style> / <tempo>. Music: <track> at offset <s>, or "beds in music_choices/, waiting for the user"
  - Open: <questions for the user>
  - Next: <the next step, exactly>
  ```

- **Resuming.** On "continue", or in a new session, read `NOTES.md` and start at `Next:`. If a session stops
  answering, the user can start a fresh one pointed at `NOTES.md` and lose nothing.

### 1. Understand the recording (steps 1–2 together: about 15 min)

1. `ffprobe` the file for size, duration and frame rate. Mac screen recordings are often variable frame rate at
   Retina size, such as 3600×2338.
2. Make **one** 1 frame/s sheet of the whole screen and look at it yourself: which window is the app, what else
   is on screen, roughly what happens when.
3. Start in parallel (`references/subagents.md`):
   - one **crop** brief: exact bounds of the app's content area, and of any window an overlay needs;
   - two or three **analysis** briefs, one per time window of the recording: a beat list, dead air, pop-ups and
     every moment outside the app.
4. **Budget:** at most 5 close-up sheets across the whole step, each with several timestamps (`--times`) and
   cropped to the region in question. A close-up has to settle a cut range, a crop or which chapters exist.
   Don't read labels for captions yet; step 5 reads them from the cut clips. A fact that only changes wording
   ("double-clicked or dragged?", "what is this button called?") goes to the user in the plan, not into more frames.
5. Stop when every candidate chapter has a source range and the clip time of its action.
6. **Outside the app.** Write every moment outside the app window into `NOTES.md` with a decision. Finder, a file
   picker, a share sheet and a notification are often the feature itself ("double-click a PDF and it opens here",
   "choose your own cover"), so a moment that starts or completes a feature becomes an **overlay clip** by default.
   Desktop blips and unrelated apps are cut. Cropping out the Finder open was missed twice, once after the user
   had asked for it.

### 2. Plan chapters, and confirm

Pick 3–6 chapters. Each is one feature the viewer should remember. Give each:
- a one-word **label** (it's also the step and the outro pill), a short **title** and a one-sentence **body**;
- source segments `[start, end, speed]`: cut dead air and mistakes, speed scrolling and waiting up 1.5–2×, and keep
  clicks and results at 1×;
- 1–3 **chips** stating what's on screen.

Write copy only from what is visible (counts changing, labels, dialogs). Don't invent capabilities. Let the content
set the length: about 45 s of usable footage gives a page of about 65 s at the steady tempo, about 48 s at fast and
about 73 s at calm. If the user asks for a fixed length and the footage is short, say so, and offer a calmer tempo,
longer holds or `duration`.

Then send the user **one** short message and wait for the answer before cutting: the chapters (label, what it
shows, source range), what's left out (each moment outside the app, and why), and your wording questions. This is
the cheapest point to catch a missing feature; after the render it costs a whole revision round.

### 3. Cut the clips

Write `clips.json` (format in `cut_clips.py`'s docstring). **Before cutting**, run `cut_clips.py clips.json --preview`
and look at the one sheet it writes: the start, middle and end of every clip, cropped. Every tile edge must be the
app (no Dock, menu bar or other window), every middle tile should show the chapter's action, and no tile may show a
pop-up or another app. Fix the crop or the ranges first. Then cut, and **check every cut boundary** with one sheet
at 0.1–0.25 s around each. Pop-ups and glitches often last longer than they first appear, and a cut needs margin.
Overlay clips get their own `crop` and must start at the same source second as their chapter's clip.

Then trace the cursor in every chapter clip; it takes seconds and reads no images:
`cursor_track.py page/0*.mp4 --out work/cursor`.

### 4. Cut-outs (background removal; a subagent can do this alongside step 5)

Use `cutout.py` to pull 4–7 recognisable UI pieces from a clean frame for the intro: covers, cards, a key button,
app icons. Measure one cleanly, reuse the grid pitch for its siblings. Pick pieces of a similar shape (width ÷
height about 1.3–1.8), and set `intro.cutoutWidth` so the row spans about 60–70% of the stage width. Check them all
in one montage on a dark background.

### 5. Build the page

Copy `assets/demo-template.html` → `page/index.html` and `assets/example.config.js` → `page/demo.config.js`, and
fill in brand accent, stage, frame, overlays and outro yourself. Follow `references/page-config.md`.

Run one **chapter** brief per chapter, in parallel. Each reads its cut clip, its cursor trace and one grid sheet,
and returns that chapter's steps, cams and chips, plus every claim with the clip time where it's visible. Merge
them into the config, and write the claims into `NOTES.md`. Write all timings for the `steady` tempo; the other
tempos scale them.

Then check the camera against the cursor, before any stills (no images, a few seconds):
`node render.mjs ../page/index.html --check-cams ../work/cursor`. Fix every `OUTSIDE` line by moving the cam
or adding one. Treat `edge` lines as a warning when the action is at that spot. The tracker can mistake a spinner
or a playing video for the cursor, so look at a still before changing a cam you believe is right.

**Pick the look with the user.** Unless they already named a style and tempo, render one mid-chapter moment in
every style (`render.mjs … --stills <t> --style all --stills-dir ../looks`), show them `looks/sheet_t_<t>.jpg`,
recommend one or two styles from `references/styles.md`, and ask about pace (calm, steady, brisk or fast). If they
want music, start the **music** brief now; it only needs the page length, which `--timeline` gives once the tempo
is set.

### 6. Check with stills, then render

1. `node <skill>/scripts/render.mjs ../page/index.html --timeline` (from `render/`) prints chapter times. Render one
   still first so the clip frames get extracted once; parallel renders then reuse them.
2. Run one **stills** brief per chapter, in parallel. Each renders that chapter's moments (first zoom, every hold,
   every overlay hand-off, and every chip at its start) into one montage, and checks that:
   - no zoom cuts the start of text lines, and the action is in view (in Pop, inside the cropped panel);
   - the hold shows the intended state, not one frame early;
   - overlays and chips don't cover the caption or each other;
   - every chip and caption claim is visible on screen at its time;
   - the Loom spot (`--cam`) doesn't hide anything important.
   Check the intro and outro yourself in one montage.
3. Fix the config and re-check only the stills that changed. Stills take seconds; a full render about 1.5 min per
   minute of video.
4. Full render: `node render.mjs ../page/index.html --out ../output/demo-silent.mp4`, in the background while the
   music beds are built. Spot-check about 12 frames of the MP4 in one montage.

### 7. Music

You can't hear audio. Follow `references/music.md`:

1. Take 3–5 candidates for the chosen style and tempo: first from the heard shortlist in `music.md`, then, for a
   specific mood the user asked for, from `music_catalog.py`.
2. Download them into `music_src/` and build one bed each:
   `music_beds.py --duration <page duration> --intro-end <chapter 1 start> --out music_choices music_src/*.mp3`.
3. If the user **asked you to add music**, that's consent: mux the best match and hand over the other beds as
   one-command swaps. If you're only **offering** music, give them `music_choices/` and the table, and mux only
   the one they pick.
4. Mux: `add_music.py --track … --offset <from the table> --duration … --page-out page/music.m4a --video-in output/demo-silent.mp4 --video-out output/demo.mp4`,
   and add `music: {src: 'music.m4a', volume: .35}` to the config so the live page plays it too.

Re-run the beds and the mux whenever the tempo changes, because the length changes. For an Incompetech track,
give the user the credit line `music_catalog.py` prints.

### 8. Hand over

Tell the user, briefly:
- the MP4 path and specs, and the page path;
- the style and tempo used, and that they're one line each in the config (or **S** and **T** to try others live);
- how to record: open the page in Chrome, **F** full screen, **C** camera spot, **Space** play, **M** music.
  Loom only captures the music if computer audio is on;
- what was cut or sped up, which moments outside the app became overlays, and any copy claims to verify;
- how to adjust: edit `demo.config.js`, then re-run stills or the render;
- the project folder's size (`du -sh demo`), and an offer to delete `page/frames/`, `work/` and `looks/`. They
  are only working files, and `render.mjs` rebuilds the frames when needed.

Set `Next:` in `NOTES.md` to "done", and offer to open Finder on the folder.

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
