# Styles and tempos

The page has 7 styles (look and layout) and 4 tempos (pace). They are independent: any style works at any
tempo, and both are one line in `demo.config.js`. The footage, captions and camera moves stay the same.

```js
style: 'terminal',
tempo: 'brisk',            // or {preset: 'brisk', rate: 1} to override one setting
```

The live page cycles them with **S** and **T**, and `?style=pop&tempo=fast` in the URL overrides the config.

## Choosing with the user

Don't guess. After the clips are cut and a first config exists, render one moment in every style and show the
sheet:

```sh
node render.mjs ../page/index.html --stills <a mid-chapter second> --style all --stills-dir ../looks
```

This writes `looks/sheet_t_<time>.jpg`, with every style labelled, in the user's own footage. Recommend one or
two from the table below, and let the user pick. Then ask about pace, using the tempo table.

## Styles

| Style | Layout | Look | Good for |
| --- | --- | --- | --- |
| `midnight` | Text left, app right | Dark, soft glow in the brand colour, Mac window | Most launch and feature videos (the default) |
| `paper` | App left, text right, chapter tabs in a header row | Warm off-white, serif headlines, thin rules | Reading, writing and content apps; calm products |
| `aurora` | Headline centred on top, app centred below it, description left, callouts right | Blurred brand-colour gradient, frosted glass, app tilted back in 3D | Consumer launches, social posts |
| `keynote` | App centred, headline left, callouts right | Black, no title bar, almost no decoration | One hero feature, phone apps, talks |
| `swiss` | Colour band on top with a huge chapter number; app overlaps it on the right | Solid brand colour, black callouts, strict grid | B2B tools, step-by-step walkthroughs |
| `pop` | Recording fills a big outlined panel; caption is a tilted card on top | Thick outlines, hard shadows, stickers, "Live demo" stamp | Indie and Product Hunt launches, playful brands |
| `terminal` | Three editor panes: chapters as a file list, app in the middle, captions in a terminal | Monospace, status bar, block cursor, grid and scanlines | Developer tools, CLIs, APIs, technical audiences |

Every style takes its colours from `brand.accent` (Aurora builds its whole gradient from it). Pick an accent
that reads on both dark and light backgrounds; very light accents wash out in Paper and Swiss.

### How each style handles the recording's shape

`frame.aspect` (clip width ÷ height) decides the frame. Tall means under about 1.15 (a narrow Mac window or a
phone); wide means a typical browser or full-screen capture.

- **midnight, paper, aurora, keynote, swiss** draw the frame at the clip's exact shape, inside an area that
  suits the style. Wide recordings get a wider area, and the captions move to make room. Aurora and Keynote
  put the headline across the top for wide recordings.
- **pop** fills its big panel with the recording and *crops* it, unless the recording is a phone or very
  tall, in which case it shows the whole frame on the right. When it crops, the camera focus (`fx`, `fy`)
  decides which part is visible, so check every Pop chapter's stills.
- **terminal** keeps its pane size and centres the recording inside it, with dark bars where the shapes
  differ. Wide recordings move the terminal under the app.

### Things to know

- **Loom camera spot.** Most styles keep the bottom-left corner clear for the Loom bubble. Paper, Pop and
  Terminal keep the bottom-right clear instead, because their text is on the left. **C** shows the spot.
- **Pop** always has some recording under the Loom bubble, because the recording fills the frame. Keep the
  camera focus away from the bottom-right during Pop chapters. `stamp: 'New'` changes the sticker text, and
  `stamp: false` hides it.
- **Aurora and Keynote** hide the app for the outro and centre the closing card.
- **Terminal** types the intro title out, with `intro.command` (default `open <brand-name>`) above it.
- `intro.highlight` (default: the brand name) is the part of the intro title that Pop underlines.
- With no `intro.cutouts`, every style moves the intro title up to fill the space.

## Tempos

| Tempo | Holds | Clip speed | Camera and text | Between chapters | Default outro | Reader Hero example |
| --- | --- | --- | --- | --- | --- | --- |
| `calm` | ×1.5 | ×1 | Slower, smaller zooms | Slow cross-fade | 7 s | 73 s |
| `steady` | ×1 | ×1 | As written | Cross-fade | 6 s | 67 s |
| `brisk` | ×0.7 | ×1.15 | Quicker, slight overshoot on captions and chips | Next chapter slides in | 5 s | 57 s |
| `fast` | ×0.5 | ×1.3 | Snappy, bigger zooms, bouncy captions | Quick zoom-through | 4 s | 48 s |

Write every timing in the config for **steady**: the tempo scales holds, hold offsets, play rates, camera ease
times and the intro. Clip times (the first number in `steps`, `cams` and `chips`) are never scaled, so cams
and chips stay on the same frames at every tempo.

Choosing:
- **calm** for narrated walkthroughs, onboarding and audiences who need to read the screen.
- **steady** for most demos with a voice-over.
- **brisk** for launch videos where the narration is short.
- **fast** for social clips and teasers, usually with music and little or no narration. At ×1.3, typing and
  cursor moves look quick, so cut long typing in `clips.json` rather than relying on speed alone.

To change one setting and keep the rest of a preset, use an object, e.g.
`tempo: {preset: 'fast', rate: 1}` (fast, but clips at normal speed). The fields are `hold`, `rate`,
`ease`, `text` (caption animation time), `swap` (seconds between chapters), `transition`
(`fade`, `slide` or `zoom`), `intro`, `outro`, `zoom` (camera push-in strength) and `bounce`
(0 = none, 1 = strong overshoot).

The page's length changes with the tempo. Always read it from `render.mjs --timeline` before trimming music.
