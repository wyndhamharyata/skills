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
choose both from stills of their own footage.

This approach exists because the obvious one, ffmpeg zoompan with highlight boxes drawn over the UI, looked
amateur and was rejected. Captions beside the product, plus a camera that frames the action, look like a real
launch video. Don't draw rectangles or labels over the UI.

## How to run it: `demo.py`, nothing else

One script drives the whole run. Each command does every scripted step up to the next decision and ends with a
**NEXT** block that says exactly what to do: which images to look at, what to ask the user, which helpers to
start, and the next command. Do that, run the command, repeat.

```sh
python3 <this skill>/scripts/demo.py new "<recording>" --name <product>     # then follow NEXT
python3 <this skill>/scripts/demo.py next <project>                         # where a run stands (resume)
```

`new` puts the project next to the recording as `<product>-demo-<date>` (no spaces) unless the user named a
folder (`--dir`). The run, in turns:

| Command | It does | You then |
| --- | --- | --- |
| `new` | windows and crops, activity in the app and every other window, dead air, desktop flashes, 2–4 sheets, a pre-filled `work/plan.json` | look at the sheets, fill in `plan.json` |
| `plan` | checks the plan (chapters, every moment outside the app) and prints the question | ask it |
| `cut` | cuts, speeds up, builds the inset clips, cursor traces, a sheet per clip, intro cut-outs, the helpers' briefs | look at the preview, start one helper per chapter |
| `build` | config, claims checked with text recognition, camera from claims and cursor, layout and readability checks, the look sheet | ask style, tempo and music in one question |
| `build --style … --tempo … --music …` | the same in the chosen look, music beds in the background, stills per chapter, stills briefs | start one stills helper per chapter |
| `finish` | the MP4, music, a spot-check sheet, the hand-over text with absolute paths | look once, send the hand-over |

## Rules

- **Do what NEXT says, all of it in one turn.** Look at every listed image in the same turn, start every helper
  in the same turn, and put a progress line in the same turn as a tool call, never in a turn of its own. Every
  turn costs 15–30 s before anything happens, so a run is judged by its turn count (about 16).
- **Trust the checks.** `build` and `check` read the screen, the layout and the cursor. When they pass, don't
  verify by eye; when they fail, they say what to change. Fix only what they list or what a viewer would notice.
- **Change content in `work/`, never in `page/`.** Captions, chips, steps and cams are in
  `work/chapters/<clip>.json`; brand, style, tempo, intro and outro in `work/page.json`; chapters, ranges, what
  happens outside the app and cuts in `work/plan.json`. `page/demo.config.js` is generated and rebuilt.
- **No extra digging.** Don't open images NEXT didn't list, grab frames with ffmpeg, run `--help`, or read this
  skill's scripts and references: what a step needs is in its output and in the briefs. Guard hooks (when
  installed) block these calls and say what to do instead; follow that message.
- **Ask with the question tool** (`question` in OpenCode, `AskUserQuestion` in Claude Code), with the options NEXT
  gives, and ask everything for that step in one call.
- **Fix rounds are capped.** `cut` allows two re-cuts, `build` three fix rounds, each stills helper one. When a
  cap is reached, `demo.py` says so; carry what's left into the hand-over with `finish --note "…"`.
- **Without subagents** (a harness that can't start them), do each brief yourself, one after another.
- Keep the user's recording untouched. Everything goes in the project folder.

## When something fails

A failing command prints `FAILED: <script>` and its last lines. Missing tools: run `scripts/doctor.sh`, which
prints the install command for each. A wrong crop or window: change `app` or the `outside` entries in
`plan.json` and run `plan` again. A change the user asks for after the hand-over: edit the files in `work/`,
then `build` (with the same `--style`) and `finish`.

## For maintainers

`demo.py` drives the lower-level scripts in `scripts/` (find_windows, activity sheets, suggest_cuts, cut_clips,
cursor_track, cutout, make_config, check_claims, render.mjs, music_beds, add_music); each has usage at its top.
`references/page-config.md` describes the generated config, `references/styles.md` the styles and tempos,
`references/music.md` the music sources and shortlist. `scripts/guard.py` and `hooks/` are the guard hooks
(`install.sh` installs them), and `tools/audit_run.py` in the repo measures a run's turns and rule breaks.
