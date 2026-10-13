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

Paths are relative to this skill's folder. **Run these scripts; don't rebuild them.** Each one makes a decision
(a crop, a cut, a zoom, a check) that a model would otherwise work out from images, more slowly and less
reliably. If a script's suggestion is wrong, change the one value and say why in `NOTES.md`; don't re-derive it.

| Step | Script | What it does |
| --- | --- | --- |
| 1 | `scripts/find_windows.py` | Finds every window on screen, its content crop below the title bar, and the Dock or other windows covering an edge |
| 1 | `scripts/contact_sheet.py` | Time-labelled frame grids; `--crop` to one window; `--grid` adds 0.1 gridlines |
| 1 | `scripts/activity.py` | Change per sample in a region: idle spans, and when something happens there; `--ref` times a pop-up |
| 3 | `scripts/suggest_cuts.py` | Turns a chapter's rough source range into segments: trims idle, speeds up long continuous change, keeps margins; `--clips` writes them into `clips.json` |
| 3 | `scripts/cut_clips.py` | `--preview` shows every clip's start, middle and end before cutting; then cuts; `--map`/`--list` convert source time ↔ clip time |
| 3 | `scripts/cursor_track.py` | Cursor position and changed areas per sample in the cut clips, for the camera tools |
| 4 | `scripts/cutout.py` | Background-removed PNG of a UI element for the intro |
| 5 | `scripts/make_config.py` | Builds `page/demo.config.js` from `clips.json`, `work/page.json` and `work/chapters/*.json`, and lists the claims in `work/claims.md` |
| 5 | `scripts/render.mjs --auto-cams --write` | Camera moves from the cursor traces, framed for the chosen style, written into the config |
| 5 | `scripts/render.mjs --lint` | Config errors, overlapping or clipped text, overlays hidden by captions, the Loom spot, and the cursor leaving the view. Seconds, no images |
| 5 | `scripts/check_claims.py` | Reads the text on screen at each claim's time (macOS text recognition) and flags numbers and words that aren't there |
| 6 | `scripts/render.mjs --stills auto` | Renders the moments worth checking and writes one labelled sheet per chapter (`--chapter n` for one) |
| 6 | `scripts/render.mjs` | `--timeline` for chapter times, `--stills … --style all` for the look sheet, `--out` for the MP4 |
| 7 | `scripts/music_beds.py` | `--style`/`--tempo` picks shortlist tracks, downloads them and writes one bed per track, aligned to chapter 1 |
| 7 | `scripts/music_catalog.py`, `scripts/add_music.py` | Search for a specific mood; mux the chosen bed into the MP4 |

| Reference | Read it for |
| --- | --- |
| `references/subagents.md` | The briefs for parallel work: analysis window, chapter, cut-outs, music, stills check |
| `references/page-config.md` | Config fields, timing and camera semantics, framing rules |
| `references/styles.md` | The 7 styles and 4 tempos, what each suits, and their quirks |
| `references/music.md` | Music sources, licences and the shortlist |

`assets/demo-template.html` is the page engine (copy it to `page/index.html`, never edit content into it), and
`assets/example.config.js` is a worked config to read when something in a generated config is unclear.

Requirements: ffmpeg, ImageMagick (`magick`), Python 3 with Pillow, and Node with `playwright-core`
(`cd render && npm init -y && npm i playwright-core`). Chromium comes from `$CHROME_PATH`, Playwright's cache or
Google Chrome. If none is found, run `npx playwright install chromium-headless-shell`. Run `scripts/doctor.sh`
first; it lists anything missing with the command to install it.

## Workflow

### 0. Budget, folder, helpers and notes

- **One hour by default**, from the start to the first MP4, unless the user sets another limit. Checkpoints:
  chapter plan sent by about 15 min, clips cut by 25, look chosen by 35, first MP4 by 50. At each, send the user
  one line: where you are and what's next. If a checkpoint slips, say so and take the simpler path.
- **The project folder** goes where the user says. Otherwise put it next to the recording, named
  `<product>-demo-<YYYY-MM-DD>` with no spaces, and never inside a git repository unless the user asks. It holds
  `page/`, `output/`, `render/` and `work/`.
- **Context is the cost.** Every step re-reads the whole conversation, and every image you open stays in it. If the
  conversation already holds a lot of unrelated work, suggest a new session with only the recording path.
- **Ask with the question tool** when the harness has one (`question` in OpenCode, `AskUserQuestion` in Claude Code):
  the plan, the look and the music, each with options. Users answer "ask me" to long question lists in text.
- **Use subagents for the image-heavy work** when the harness can start them (Claude Code, OpenCode). You talk
  to the user, keep `NOTES.md`, `work/page.json` and the config, and decide. Subagents run the briefs in
  `references/subagents.md` in parallel and send back text or JSON files. Without subagents, run the same briefs
  yourself, one after another.
- **Keep `NOTES.md`** from step 1 onward and update it after every decision:

  ```md
  # Demo notes
  - Recording: <path>, <W×H>, <duration> s, <fps> fps
  - Crop: <W:H:X:Y> from find_windows.py (left out: <e.g. the Dock on the right edge>)
  - Other windows: <name> <crop>
  - Beats: <source s> <what happens>, one line each; mark dead air
  - Outside the app: <source s> <Finder / file picker / notification / other app>: overlay or cut, and why
  - Chapters: <clip> src <a–b>: <the action> at clip <t>
  - Look: <style> / <tempo>. Music: <track> at offset <s>, or "beds in music_choices/, waiting for the user"
  - Open: <questions for the user>
  - Next: <the next step, exactly>
  ```

- **Resuming.** On "continue", or in a new session, read `NOTES.md` and start at `Next:`.

### 1. Understand the recording (steps 1–2 together: about 15 min)

1. `ffprobe` the file, then `find_windows.py <recording>`. It gives the app's content crop, every other window's
   crop, and any edge the Dock or another window covers.
2. Make **one** 1 frame/s sheet of the whole screen and look at it: which window is the app and roughly what
   happens when. Every window `find_windows.py` found besides the app is a place where part of the story may happen.
3. Start the **analysis** briefs in parallel, one per time window of the recording (2–3). Each runs `activity.py`
   on the app **and on every other window's crop**, so a click in Finder or a file picker shows up as activity
   there, not as something to notice in an image.
4. **Budget:** at most 5 close-up sheets across the whole step, each with several timestamps and cropped to the
   region in question, and each settling a cut range or which chapters exist. Don't read on-screen labels here.
   A fact that only changes wording ("double-clicked or dragged?") goes to the user in the plan.
5. Stop when every candidate chapter has a source range and the clip time of its action.

### 2. Plan chapters, and confirm

Pick 3–6 chapters. Each is one feature the viewer should remember, with a one-word **label**, a short **title**, a
one-sentence **body**, a rough source range and 1–3 **chips**. Copy states only what is visible. About 45 s of
usable footage gives a page of about 65 s at the steady tempo, 48 s at fast and 73 s at calm.

Then ask the user, with the question tool, before cutting. The plan always has these three parts:

1. **Chapters:** label, what it shows, source range.
2. **Outside the app:** every moment in another window, file picker, share sheet, notification or the desktop,
   each marked *overlay* or *cut* with a reason. A moment that starts or completes a feature ("double-click a PDF
   and it opens here", "choose your own cover") is an overlay by default. Never leave this part out; write "none"
   if there are none. Leaving Finder out has been the most common miss.
3. **Questions:** wording facts and anything you'd otherwise investigate.

### 3. Cut the clips

1. For each chapter, `suggest_cuts.py <recording> --crop … --range a-b [--drop …] --clips clips.json --name <clip>`
   writes its segments. Overlay clips get their own `crop` and the same first source second as their chapter, plus
   an `"overlay"` key (see `make_config.py`).
2. `cut_clips.py clips.json --preview` and look at the one sheet: every tile edge is the app, every middle tile
   shows the chapter's action, no pop-ups. Fix and re-run until it's right, then cut.
3. `cursor_track.py page/0*.mp4 --out work/cursor`.

### 4. Cut-outs (a subagent, alongside step 5)

`cutout.py` pulls 4–7 recognisable UI pieces from a clean frame: covers, cards, a key button, app icons. Similar
shapes (width ÷ height about 1.3–1.8), and `intro.cutoutWidth` so the row spans about 60–70% of the stage.

### 5. Build the page

1. Copy `assets/demo-template.html` to `page/index.html`, and write `work/page.json` (brand, accent, style, tempo,
   frame type, intro, outro and the chapter order; format in `make_config.py`).
2. Run one **chapter** brief per chapter, in parallel. Each writes `work/chapters/<clip>.json`.
3. `make_config.py <project>` builds `page/demo.config.js` and `work/claims.md`.
4. `render.mjs ../page/index.html --auto-cams --write` sets the camera from the cursor traces.
5. `render.mjs ../page/index.html --lint` and `check_claims.py work/claims.md`. Fix every ERROR and MISSING line
   before any still: move a cam, an overlay's `at`, or fix the caption to what the screen says.
6. **Pick the look with the user**, unless they named one: `render.mjs … --stills <mid-chapter t> --style all
   --stills-dir ../looks`, recommend one or two from `references/styles.md`, and ask with the question tool for a
   style and a tempo. After a style change, run `--auto-cams --write` and `--lint` again: zooms depend on the style.

### 6. Check with stills, then render

1. Run one **stills** brief per chapter in parallel (`render.mjs … --stills auto --chapter <n>`), and look at
   `sheet_00-intro-outro.jpg` yourself. Render one still first so the clip frames get extracted once.
2. Fix the config, then re-run `--lint` and only the stills that changed.
3. `render.mjs ../page/index.html --out ../output/demo-silent.mp4`, in the background while the music beds are
   built. Spot-check about 12 frames of the MP4 in one montage.

### 7. Music

You can't hear audio. `music_beds.py --style <style> --tempo <tempo> --duration <page duration> --intro-end
<chapter 1 start> --out music_choices` picks shortlist tracks, downloads them and builds aligned beds (both numbers
from `--timeline`). For a mood the user named, add tracks from `music_catalog.py` instead.

If the user **asked you to add music**, mux the best match and offer the other beds as one-command swaps. If you're
only **offering** music, ask with the question tool which bed to use. Mux with `add_music.py --track … --offset
<from the table> --duration … --page-out page/music.m4a --video-in output/demo-silent.mp4 --video-out
output/demo.mp4`, and add `music: {src: 'music.m4a', volume: .35}` to `work/page.json` and the config. Re-run the
beds and the mux whenever the tempo changes. For an Incompetech track, give the credit line `music_catalog.py` prints.

### 8. Hand over

Tell the user, briefly, with **absolute paths** in backticks (they copy them into `open` and `cp`):
- the MP4 and the page, and the specs;
- the style and tempo, and that they're one line each in the config (or **S** and **T** live);
- how to record: open the page in Chrome, **F** full screen, **C** camera spot, **Space** play, **M** music.
  Loom only captures the music if computer audio is on;
- what was cut or sped up, which moments outside the app became overlays, and any claims to verify;
- how to adjust: edit `work/` or the config, then `--lint` and stills;
- the folder's size, and an offer to delete `page/frames/`, `work/` and `looks/` (rebuilt when needed).

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
- Keep the user's raw recording untouched. All outputs go in the project folder.
- ffmpeg builds may lack `drawtext`, and ImageMagick may have no default font (`unable to read font`).
  Label images with Pillow (`contact_sheet.py` does) or pass `-font /path/to/font.ttf`.
