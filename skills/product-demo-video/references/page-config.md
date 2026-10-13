# Page config reference (`demo.config.js`)

The page (`assets/demo-template.html`, copied to `page/index.html`) reads `window.DEMO` from
`demo.config.js` in the same folder. `assets/example.config.js` is a complete, working example.
Paths inside the config are relative to the page folder.

## Layout

The 1920-wide stage has a fixed left column and the product on the right:

| Area | Position | Notes |
| --- | --- | --- |
| Brand + chapter steps | x 120, y 84–200 | Steps fill as each chapter plays |
| Caption | x 120–800, y 300 | eyebrow `01 LABEL`, title (70px), body (29px) |
| Chips | under the caption | one short claim at a time, check-mark bullet |
| App frame | centred on x ≈ 1354 | sized from `frame.aspect` to fill the height |
| Loom camera spot | bottom-left circle | press **C** to preview where the bubble sits; keep it clear |

`stage` should match the recording's aspect (a 3600×2338 Mac capture → 1920×1248; a 16:9 capture → 1920×1080).

`frame.type`: `mac` (title bar with traffic lights), `phone` (bezel and island, for simulator or phone recordings), `none`.
`frame.aspect` is the clip's width ÷ height. The page computes the frame size from it.

## Timeline

Every chapter plays one clip. Its `steps` list builds the chapter's part of the timeline:

- `['hold', c, seconds]` freezes on clip time `c`. Use holds so a result, or a caption, gets read. 0.4–1.4 s is typical.
- `['play', from, to, rate]` plays clip time `from`→`to`. `rate` is optional (default 1); 1.5–2 speeds through scrolling.

Chapter 1 starts at `intro.end`. Each chapter starts when the previous one ends. The outro then holds for `outro.hold` seconds.
`duration` (optional) fixes the total length and gives any extra time to the outro.

Holds and plays use **clip time**, meaning seconds inside the cut clip and not in the source recording.
`cut_clips.py clips.json --map <clip> <sourceSecond>` converts between the two. `--list` shows every segment's range.

## Camera

`cams: [clipTime, offset, scale, fx, fy, ease]` move a camera *inside* the app frame. The frame stays put, so the
captions are never covered.

- `clipTime` must be a time that is on the chapter's timeline: inside a `play` range, or exactly a `hold` time.
  `offset` shifts the move in page seconds, for example to start it partway through a hold.
- `scale` 1 = whole frame. 1.1–1.3 for wide panels, 1.5–1.8 for a control or a short line of text.
- `fx, fy` are the focus point as fractions of the frame (0–1). Read them off a `contact_sheet.py --grid` sheet.
  The view is clamped so it never shows past the frame edge.
- Each chapter starts zoomed out, and the camera returns to scale 1 for the outro.

Framing rules that matter in review:
- **Text panels wider than the view:** use `fx: 0` (left-aligned) so lines keep their first words. Centring cuts both ends.
- **Moments when a panel opens or the page changes:** check a still just *after* the change. The camera eases over `ease` seconds and can land late.
- Keep zoom at 1.2 or less on anything whose meaning is the whole layout (a library grid, a dialog with buttons on both sides).

## Chips

`[clipTime, offset, text, endClipTime?]` shows a chip from that moment until `endClipTime`, or until the chapter ends.
Keep each chip under about 45 characters, make it state what the viewer is seeing, and avoid overlapping two chips.

## Intro and outro

- `intro.cutouts`: PNG cutouts (background removed, made with `cutout.py`) that fan in above the title, such as book covers,
  product cards or app icons. 4–7 work best. Leave the list empty for a title-only intro.
- `outro`: logo, title, sub and one pill per chapter label.

## Overlays (second windows)

Use an overlay when part of the story happens outside the app, for example opening a file from Finder, a share sheet,
a notification or a browser tab. The overlay is its own cropped clip that floats above the app frame and fades away at `outAt`.

```js
overlays: [{clip: '00-finder.mp4', chapter: 0, rect: [850, 300, 900], aspect: 1784 / 1176,
            origin: '0 71%', push: [.2, 1.9, .1], outAt: 2.75}]
```

- The overlay clip **must start at the same source second** as its chapter's clip. They share clip time, so the
  double-click in Finder and the app's reaction stay in sync.
- `rect` = [left, top, width] in stage px (height comes from `aspect`). Keep `left` ≥ 840 so it never overlaps the caption.
- `origin` + `push` = a slow push-in toward the important row: [startClipTime, seconds, extraScale].
  Use an `origin` x of 0 so the window grows rightward, away from the caption.
- `outAt` = clip time when the app takes over. The overlay slides back and fades out over 0.45 s.

## Music

`music: {src: 'music.m4a', volume: .35}` plays in sync with the timeline (seeking, pausing). **M** toggles it.
0.35 keeps it under a voice-over. Omit `music` for none. Make the file with `add_music.py`.

## Keys (live page)

Space play/pause · F full screen · C camera spot · M music · R restart · ←/→ 5 s · click stage = play/pause.
