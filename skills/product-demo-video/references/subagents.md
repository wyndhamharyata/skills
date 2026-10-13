# Subagent briefs

Each brief is self-contained: a subagent starts with no memory of the conversation. Copy the shared rules and one
brief, fill in every `<…>`, and start the independent ones in the same turn so they run in parallel. Without
subagents, run the briefs yourself, one after another.

What comes back is text. Merge it into `NOTES.md` or `demo.config.js` yourself. Only the main agent writes those
two files, and only the main agent talks to the user.

## Shared rules (paste at the top of every brief)

```
You are helping build a product demo video with the product-demo-video skill at <skill dir>.
Project: <demo dir>. Recording: <recording path> (<W×H>, <duration> s). Don't modify the recording.
- Write files only under <demo dir>/work/<task>/. Don't edit page/demo.config.js or NOTES.md.
- You can't ask the user anything. Put open questions in your reply under "Questions".
- Images: at most <n> image reads. Answer each question with one montage of several timestamps
  (contact_sheet.py --times … --crop …), cropped to the region in question. Never open single full-size frames.
- Reply in text only, at most 40 lines, in the format below. No logs, no file listings.
- Stop when you can fill in the format. You have about <minutes> minutes.
```

## Crop (step 1)

```
Task: find the crop for the app and for every window an overlay may need. Image budget: 3.
1. Sample pixels along one row and one column with Python + Pillow where each window edge meets the wallpaper.
   Use the content area below the title bar; the page draws its own frame.
2. The Dock, the menu bar or another window can overlap the app's edge. Make one sheet of the crop at 3
   timestamps spread over the recording and check that every edge is the app.
Reply:
App crop: W:H:X:Y (aspect W/H = …), left out: …
Other windows: <name> crop W:H:X:Y, visible from <s> to <s>
Questions: …
```

## Analysis window (step 1; one per time window)

```
Task: a beat list for source seconds <a>–<b>. The app is at crop <W:H:X:Y> (approximate is fine).
Image budget: 3.
1. One 0.5 s sheet of <a>–<b> cropped to the app (contact_sheet.py --start <a> --end <b> --step .5 --crop …).
2. activity.py on the app region for idle spans. For a suspected pop-up, use --ref on a thin strip at the
   screen bottom (Dock) or top-right (notifications) for exact times.
3. At most 2 close-up sheets, only to settle where an action starts or ends.
Don't read on-screen text for captions; that comes later from the cut clips.
Reply:
Beats: <source s> <what the user does or what appears>, one line each
Dead air: <a–b>, …
Outside the app: <source s> <Finder, file picker, share sheet, notification, other app, desktop>: <what happens>
Feature candidates: <one line each, with source range>
Questions: …
```

## Chapter (step 5; one per chapter)

```
Task: write the timeline, camera and chips for chapter "<label>": <one-line description of the feature>.
Clip: <demo dir>/page/<clip>.mp4 (<duration> s, clip time starts at 0). Cursor trace: work/cursor/<clip>.json.
Read references/page-config.md (Timeline, Camera, Chips) first. Image budget: 3.
1. Read the cursor trace for where the action is over time.
2. One grid sheet of the clip at 6–10 moments (contact_sheet.py <clip> --times … --grid --width 450).
3. Steps: holds on results so they can be read (0.4–1.4 s), play the rest; speed up only scrolling or waiting.
   Cams: frame where the cursor is working, at scale 1.1–1.3 for wide panels and 1.5–1.8 for a control or a
   line of text. A text panel wider than the view uses fx 0. Keep the cursor inside the view.
4. Chips (1–3, under about 45 characters) and the caption body state only what is visible. Read the labels.
Reply:
steps: [...]
cams: [...]
chips: [...]
title / body: …
Claims: <text> -> visible at clip <t> (<what shows it>)
Questions: …
```

## Cut-outs (step 4)

```
Task: 4–7 intro cut-outs for <product>: <what to pull, e.g. book covers from the library grid>.
Source frame: <recording> at <s> s. Image budget: 3.
Use cutout.py. Measure one piece cleanly and reuse the grid pitch for the others. Pick pieces of a similar shape
(width ÷ height about 1.3–1.8). Save them to work/cutouts/, then check them in one montage on a dark background.
Reply:
Files: work/cutouts/<name>.png (W×H), …
cutoutWidth: <px, so the row spans 60–70% of a 1920 px stage>
Questions: …
```

## Music candidates (step 5, once the tempo is set)

```
Task: 3–5 music beds for a <style> / <tempo> demo, <mood the user asked for, if any>.
Page length <duration> s, chapter 1 starts at <intro end> s. No images needed.
Read references/music.md. Take candidates from its shortlist first (prefer "heard"), then from music_catalog.py.
Download into <demo dir>/music_src/ (process only with ffmpeg), then:
music_beds.py --duration <duration> --intro-end <intro end> --out <demo dir>/music_choices <demo dir>/music_src/*.mp3
Reply:
The table music_beds.py printed, then one line per bed: why it suits, licence, credit line if any.
Your best match and why.
```

## Stills check (step 6; one per chapter)

```
Task: check chapter "<label>" (page time <start>–<end>) in <style> / <tempo>. Image budget: 2.
From <demo dir>/render run render.mjs ../page/index.html --stills <times> --cam --stills-dir ../work/stills-<n>
for: the first zoom, every hold, every overlay hand-off, and each chip at its start (<times>). Put them in one
montage (magick montage … -tile 3x -geometry 640x416+3+3) and check that:
- no zoom cuts the start of text lines, and the action and cursor are in view;
- each hold shows the intended state, not one frame early;
- overlays and chips don't cover the caption or each other;
- each of these claims is visible at its time: <claims from NOTES.md>;
- the Loom spot doesn't hide anything important.
Reply:
OK, or one line per problem: page <t> / clip <t>: <problem> -> <suggested config change>
```
