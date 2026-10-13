// demo.config.js — everything the page shows. Times are in seconds.
// Worked example: "Reader Hero", a web-novel reader recorded on a Mac (app window + Finder).
window.DEMO = {
  brand: {name: 'Reader Hero', tag: 'Web novel reader', accent: '#22A863', accentHi: '#5FE3A1', bg: '#050C09', muted: '#A0B5AA'},
  // logo: 'logo.png',   // optional; without it a monogram of the first letter is drawn

  stage: {w: 1920, h: 1248},          // match the recording's aspect (3600x2338 → 1920x1248)
  frame: {type: 'mac', aspect: 1782 / 2180, title: 'Reader Hero'},   // 'mac' | 'phone' | 'none'; aspect = clip width / height

  intro: {
    title: 'Meet Reader Hero',
    sub: 'Read long web novels without losing the thread.',
    cutouts: ['covers/a.png', 'covers/b.png', 'covers/c.png', 'covers/d.png', 'covers/e.png', 'covers/f.png'],
    cutoutWidth: 240,
    end: 5.4,                         // chapter 1 starts here
  },

  // Steps: ['hold', clipTime, seconds] | ['play', fromClipTime, toClipTime, rate?]
  // Cams:  [clipTime, offsetSeconds, scale, focusX, focusY, easeSeconds]   focus is 0–1 inside the app frame
  // Chips: [clipTime, offsetSeconds, text, endClipTime?]
  chapters: [
    {label: 'Open', title: 'Your Mac’s PDF reader', clip: '01-library-open.mp4',
      body: 'Double-click any PDF in Finder. Reader Hero adds it to your library and opens it, ready to read.',
      steps: [['hold', 0, .5], ['play', 0, 3], ['hold', 3, .5], ['play', 3, 7.8], ['hold', 7.8, .6]],
      cams: [[2.75, 0, 1.6, .5, .92, .5], [3.35, 0, 1.55, 0, .18, .8], [5, 0, 1.45, .32, .42, 1.6]],
      chips: [[.3, 0, 'Double-click any PDF in Finder', 2.9], [3, 0, 'Added to your library, then opened']]},
    {label: 'Reading', title: 'Set up the page your way', clip: '02-text-settings.mp4',
      body: 'Theme, warmth, font, size and spacing live in one menu. The page changes as you tap.',
      steps: [['hold', 0, .5], ['play', 0, 8.6], ['hold', 8.6, .6], ['play', 8.6, 13.167], ['hold', 13.167, .6]],
      cams: [[.15, 0, 1.75, .8, .33, .9], [7.85, 0, 1.12, .55, .45, .7], [10.2, 0, 1.8, .8, .28, .8], [12.6, 0, 1.3, .65, .4, .6]],
      chips: [[3.3, 0, 'Size 16 → 21 px, line spacing 1.8 → 2.0', 7.6], [8, 0, 'Light or dark, warm or cool']]},
    {label: 'Summaries', title: 'Catch up in seconds', clip: '03-summaries.mp4',
      body: 'Read a summary of each chapter, check who’s who, or summarise just the part you’ve read.',
      steps: [['hold', 0, .4], ['play', 0, 7.75], ['hold', 7.75, 1.4], ['play', 7.75, 14.875], ['hold', 14.875, .8]],
      cams: [[.6, 0, 1.2, 0, .42, .9], [7.4, 0, 1.3, 0, .34, .6], [7.75, 1.4, 1.1, .5, .45, .6], [9.3, 0, 1.2, 0, .56, .8], [10.9, 0, 1.28, 0, .45, .9]],
      chips: [[.8, 0, 'A summary for every chapter', 6.8], [7.4, 0, 'Terms: who’s who, and where they appear', 9.1], [10.9, 0, 'Stops at your current page, so no spoilers']]},
    {label: 'Covers', title: 'Every book, looking right', clip: '04-book-cover.mp4',
      body: 'See progress, format and length at a glance, and swap in any cover from your files.',
      steps: [['hold', 0, .4], ['play', 0, 7.05], ['hold', 7.05, .9], ['play', 7.05, 11.35], ['hold', 11.35, .6]],
      cams: [[.9, 0, 1.4, .5, .48, .8], [4, 0, 1.12, .5, .52, .5], [5.95, 0, 1.45, .5, .42, .7], [7.7, 0, 1, .5, .5, .6], [8.4, 0, 1.6, .3, .26, .9]],
      chips: [[1, 0, 'Progress, format and length at a glance', 3.9], [6, 0, 'Pick any image as the cover', 7.7], [8.5, 0, 'The new cover shows up in your library']]},
  ],

  // Extra windows that play alongside a chapter, e.g. Finder for an "open from the OS" moment.
  // The overlay clip must start at the same source second as the chapter clip so both share clip time.
  // rect = [left, top, width] in stage px; push = [clipTime, seconds, extraScale]; outAt = clip time it fades away.
  overlays: [
    {clip: '00-finder.mp4', chapter: 0, rect: [850, 300, 900], aspect: 1784 / 1176, origin: '0 71%', push: [.2, 1.9, .1], outAt: 2.75},
  ],

  outro: {title: 'Reader Hero', sub: 'Read more. Remember all of it.', hold: 6},
  // duration: 90,                    // optional fixed length; extra time goes to the outro
  music: {src: 'music.m4a', volume: .35},
};
