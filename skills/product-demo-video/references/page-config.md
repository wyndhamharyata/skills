# Page config reference (`demo.config.js`)

The page (`assets/demo-template.html`, copied to `page/index.html`) reads `window.DEMO` from
`demo.config.js` in the same folder. `assets/example.config.js` is a complete, working example.
Paths inside the config are relative to the page folder.

## Look

| Field | Values |
| --- | --- |
| `style` | `midnight` (default), `paper`, `aurora`, `keynote`, `swiss`, `pop`, `terminal` |
| `tempo` | `calm`, `steady` (default), `brisk`, `fast`, or `{preset, …overrides}` |
| `brand` | `{name, tag, accent, logo?}`. `accent` is a hex colour that every style uses; `logo` is an image path (without one, a letter monogram is drawn) |
| `stamp` | Pop only: the round sticker text (default "Live demo"), or `false` to hide it |

What each style and tempo does, and how to choose with the user: `styles.md`.

## Stage and frame

- `stage: {w, h}` is the size of the screen the page is played on. 1920×1248 suits a MacBook screen and
  1920×1080 suits 16:9. Every style is designed at 1920×1248 and scaled to fit, and the background fills any
  extra space.
- `frame.type`: `mac` (title bar with traffic lights), `phone` (bezel and island), `none` (plain rounded frame).
  Some styles override this: Keynote drops the title bar, Pop always outlines, and Terminal uses an editor pane.
- `frame.aspect` is the clip's width ÷ height, the crop size from `clips.json`. The style sizes and places the
  frame from it. Measure it from the crop; don't round it.
- `frame.title` is the title-bar text (default: the brand name).

## Timeline

Every chapter plays one clip. Its `steps` list builds that chapter's part of the timeline:

- `['hold', c, seconds]` freezes on clip time `c`. Use holds so a result, or a caption, gets read. 0.4–1.4 s is typical.
- `['play', from, to, rate]` plays clip time `from`→`to`. `rate` is optional (default 1); 1.5–2 speeds through scrolling.

Chapter 1 starts at `intro.end`. Each chapter starts when the previous one ends, and the outro then holds for
`outro.hold` seconds. `duration` (optional) fixes the total length and gives any extra time to the outro.

**Write timings for the `steady` tempo.** Other tempos scale the hold lengths, hold offsets, play rates,
camera ease times, `intro.end` and the default outro hold, but never clip times. Run
`render.mjs --timeline [--tempo x]` for the actual chapter times.

Holds and plays use **clip time**, meaning seconds inside the cut clip and not in the source recording.
`cut_clips.py clips.json --map <clip> <sourceSecond>` converts between the two. `--list` shows every segment's range.

## Camera

`cams: [clipTime, offset, scale, fx, fy, ease]` moves a camera *inside* the app frame. The frame stays put, so
the captions are never covered.

- `clipTime` must be a time that is on the chapter's timeline: inside a `play` range, or exactly a `hold` time.
  `offset` shifts the move in steady-tempo seconds, for example to start it partway through a hold.
- `scale` 1 = whole clip. 1.1–1.3 for wide panels, 1.5–1.8 for a control or a short line of text. Brisk and
  Fast push in a little further.
- `fx, fy` are the focus point as fractions of the clip (0–1). Read them off a `contact_sheet.py --grid` sheet.
  The view is clamped so it never shows past the clip's edge.
- Each chapter starts zoomed out, and the camera returns to scale 1 for the outro.
- Aim the camera where the cursor is working, not where the layout looks interesting. `cursor_track.py` traces
  the cursor in the cut clips, and `render.mjs --check-cams work/cursor` lists every moment it leaves the view.
- In Pop, the recording may be cropped to fill the panel. The camera never zooms out past that, so `fx`, `fy`
  also choose which part of the clip shows.

Framing rules that matter in review:
- **Text panels wider than the view:** use `fx: 0` (left-aligned) so lines keep their first words. Centring cuts both ends.
- **Moments when a panel opens or the page changes:** check a still just *after* the change. The camera eases over `ease` seconds and can land late.
- Keep zoom at 1.2 or less on anything whose meaning is the whole layout (a library grid, a dialog with buttons on both sides).

## Chips

`[clipTime, offset, text, endClipTime?]` shows a chip from that moment until `endClipTime`, or until the chapter ends.
Keep each chip under about 45 characters, make it state what the viewer is seeing, and don't let two chips in a
chapter overlap in time: they share one spot.

## Intro and outro

- `intro.title`, `intro.sub`. `intro.highlight` is the part of the title that Pop underlines (default: the brand name).
- `intro.cutouts`: PNG cutouts (background removed, made with `cutout.py`) that animate in above the title, such as
  book covers, product cards or app icons. Each style arranges them its own way. 4–7 work best, at
  `intro.cutoutWidth` px (default 240). Leave the list empty for a title-only intro.
- `intro.end`: when chapter 1 starts (default 5.4 s at steady).
- `intro.command`: Terminal only, the command typed above the title (default `open <brand-name>`).
- `outro`: `{title, sub, hold?}`. The outro shows the logo, title, sub and one pill per chapter label.

## Overlays (second windows)

Use an overlay when part of the story happens outside the app, for example opening a file from Finder, a share sheet,
a notification or a browser tab. The overlay is its own cropped clip that floats above the app frame and fades away at `outAt`.

```js
overlays: [{clip: '00-finder.mp4', chapter: 0, at: [.44, .475], width: 900, aspect: 1784 / 1176,
            origin: '0 71%', push: [.2, 1.9, .1], outAt: 2.75}]
```

- The overlay clip **must start at the same source second** as its chapter's clip. They share clip time, so the
  double-click in Finder and the app's reaction stay in sync.
- `at` = the overlay's centre as fractions of the app frame, so it follows the frame in every style. `width` is
  in design px (height comes from `aspect`). It is kept on screen, but it can cover the caption in styles whose
  caption sits beside the app. Check an overlay still in the chosen style.
- `origin` + `push` = a slow push-in toward the important row: [startClipTime, seconds, extraScale].
- `outAt` = clip time when the app takes over. The overlay slides back and fades out.

## Music

`music: {src: 'music.m4a', volume: .35}` plays in sync with the timeline (seeking, pausing). **M** toggles it.
0.35 keeps it under a voice-over. Omit `music` for none. Make the file with `add_music.py`, using the duration
and intro end that `--timeline` prints for the chosen tempo.

## Keys (live page)

Space play/pause · S next style · T next tempo · F full screen · C camera spot · M music · R restart ·
←/→ 5 s · click the stage = play/pause. S and T are for trying looks; put the final choice in the config.
