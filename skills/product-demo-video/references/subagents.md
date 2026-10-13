# Subagent briefs

Each brief is self-contained: a subagent starts with no memory of the conversation. Copy the shared rules and one
brief, fill in every `<…>`, and start the independent ones in the same turn so they run in parallel. Without
subagents, run the briefs yourself, one after another.

What comes back is text, or a JSON file under `work/` that a script reads (chapter briefs write
`work/chapters/<clip>.json` for `make_config.py`). Only the main agent writes `NOTES.md`, `work/page.json` and the
config, and only the main agent talks to the user.

## Shared rules (paste at the top of every brief)

```
You are helping build a product demo video with the product-demo-video skill at <skill dir>.
Project: <project>. Recording: <recording path> (<W×H>, <duration> s). Don't modify the recording.
- Write files only under <project>/work/. Don't edit page/demo.config.js, work/page.json or NOTES.md.
- Use the skill's scripts for anything they cover; don't write your own pixel sampling or timing code.
- You can't ask the user anything. Put open questions in your reply under "Questions".
- Images: at most <n> image reads. Answer each question with one montage of several timestamps
  (contact_sheet.py --times … --crop …), cropped to the region in question. Never open single full-size frames.
- Reply in at most 40 lines, in the format below. No logs, no file listings.
- Stop when you can fill in the format. You have about <minutes> minutes.
```

## Analysis window (step 1; one per time window)

```
Task: a beat list for source seconds <a>–<b>. The app is at crop <app crop>. Other windows (from find_windows.py):
<name> at <crop>, … Image budget: 3.
1. activity.py --crop <app crop> --start <a> --end <b> --quiet, and the same for every other window's crop.
   Activity in another window is a moment outside the app: report it whatever it looks like.
2. One 0.5 s sheet of <a>–<b> cropped to the app (contact_sheet.py --start <a> --end <b> --step .5 --crop … --width 240).
3. At most 2 close-up sheets (cropped, several --times), only to settle where an action starts or ends, or what
   happened in another window.
Don't read on-screen text for captions; that comes later from the cut clips.
Reply:
Beats: <source s> <what the user does or what appears>, one line each
Dead air: <a–b>, …
Outside the app: <source s> <window or dialog>: <what happens>   (or "none")
Feature candidates: <one line each, with source range>
Questions: …
```

## Chapter (step 5; one per chapter)

```
Task: the caption, timeline and chips for chapter "<label>": <one-line description of the feature>.
Clip: <project>/page/<clip>.mp4 (<duration> s, clip time starts at 0). Image budget: 3.
Read references/page-config.md (Timeline and Chips) first. The camera is set later by render.mjs --auto-cams.
1. One grid sheet of the clip at 6–10 moments (contact_sheet.py <clip> --times … --width 450).
2. Steps: holds on results so they can be read (0.4–1.4 s), play the rest; speed up only scrolling or waiting.
3. Chips (1–3, under about 45 characters) and the body state only what is visible.
4. Every number or on-screen label you use goes in "claims" with the clip time where it is visible. If you
   couldn't read it clearly, leave it out of the copy; never guess a number.
Write <project>/work/chapters/<clip>.json:
{"label": "…", "title": "…", "body": "…", "steps": [...], "chips": [[clipTime, 0, "text"], ...],
 "claims": [["356 pages · 847 KB", 4.0], ...]}
Reply: the file path, then one line per claim, then Questions.
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

## Music candidates (step 7)

```
Task: music beds for a <style> / <tempo> demo<, mood: …>. Page length <duration> s, chapter 1 starts at <intro end> s.
No images. From <project>: music_beds.py --style <style> --tempo <tempo> --duration <duration> --intro-end <intro end>
--out music_choices --src music_src
For a named mood, first find 2–3 tracks with music_catalog.py, download them into music_src/ and pass them as
arguments instead of --style/--tempo.
Reply: the table music_beds.py printed, one line per bed (why it suits, licence, credit line if any), and your best match.
```

## Stills check (step 6; one per chapter)

```
Task: check chapter <n> "<label>" in <style> / <tempo>. Image budget: 2.
From <project>/render: node <skill>/scripts/render.mjs ../page/index.html --stills auto --chapter <n> --cam
--stills-dir ../work/stills-<n>. Look at the sheet it prints (each tile is labelled with its time and why it's there):
- the action is in view and no zoom cuts the start of text lines;
- each hold shows the intended state, not one frame early;
- each chip and caption claim is what the screen shows at that moment;
- the Loom spot doesn't hide anything important.
--lint has already checked overlaps and the cursor, so don't re-check those by eye.
Reply:
OK, or one line per problem: page <t> / clip <t>: <problem> -> <suggested change to work/chapters/<clip>.json or the config>
```
