// Render the demo page to an MP4, or to a few stills for checking framing.
//
//   node render.mjs page/index.html --out output/demo-silent.mp4
//   node render.mjs page/index.html --stills 2.5,9,23.4 --stills-dir stills
//   node render.mjs page/index.html --stills 9,20 --style all      # every style, labelled, plus one sheet per moment
//   node render.mjs page/index.html --timeline --tempo fast        # chapter times for a tempo
//   node render.mjs page/index.html --stills 9 --cam               # show the Loom camera spot in stills
//   node render.mjs page/index.html --lint                         # config, layout and camera problems, before any still
//   node render.mjs page/index.html --auto-cams --write            # camera moves from the cursor traces, written into the config
//   node render.mjs page/index.html --stills auto [--chapter 2]    # the moments worth checking, one labelled sheet per chapter
//   node render.mjs page/index.html --check-cams ../work/cursor    # times the cursor is outside the camera view
//
// --lint, --auto-cams and --check-cams read cursor traces from ../work/cursor (cursor_track.py) unless given a folder.
//
// --style and --tempo override the config (styles: midnight paper aurora keynote swiss pop terminal;
// tempos: calm steady brisk fast). Run it from a directory where `npm i playwright-core` has been done
// (it is resolved from the current directory). Browser: $CHROME_PATH, else Playwright's cached Chromium,
// else Google Chrome. Clip frames are extracted once to <page dir>/frames/<id>/ and reused until the clip changes.
import {createRequire} from 'node:module';
import {spawn, execFileSync} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';

const require = createRequire(path.join(process.cwd(), 'noop.js'));
const {chromium} = require('playwright-core');

const argv = process.argv.slice(2);
const opt = (k, d) => (argv.includes(k) ? argv[argv.indexOf(k) + 1] : d);
const pageFile = path.resolve(argv.find(a => a.endsWith('.html')) || 'page/index.html');
const PAGE = path.dirname(pageFile);
const FPS = +opt('--fps', 30);
const STYLE = opt('--style'), TEMPO = opt('--tempo');

function findBrowser() {
  if (process.env.CHROME_PATH) return process.env.CHROME_PATH;
  for (const root of [path.join(os.homedir(), 'Library/Caches/ms-playwright'), path.join(os.homedir(), '.cache/ms-playwright')]) {
    if (!fs.existsSync(root)) continue;
    for (const prefix of ['chromium_headless_shell-', 'chromium-']) {
      const dir = fs.readdirSync(root).filter(d => d.startsWith(prefix)).sort().pop();
      if (!dir) continue;
      for (const rel of ['chrome-headless-shell-mac-arm64/chrome-headless-shell', 'chrome-headless-shell-mac-x64/chrome-headless-shell',
        'chrome-headless-shell-linux64/chrome-headless-shell', 'chrome-mac/Chromium.app/Contents/MacOS/Chromium',
        'chrome-mac-arm64/Chromium.app/Contents/MacOS/Chromium', 'chrome-linux/chrome', 'chrome-linux64/chrome']) {
        const p = path.join(root, dir, rel);
        if (fs.existsSync(p)) return p;
      }
    }
  }
  const mac = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
  if (fs.existsSync(mac)) return mac;
  throw new Error('No Chromium found. Set CHROME_PATH or run: npx playwright install chromium-headless-shell');
}

function extractFrames(clips) {
  const counts = {};
  for (const {id, src} of clips) {
    const file = path.resolve(PAGE, src);
    const dir = path.join(PAGE, 'frames', id);
    const stamp = path.join(dir, '.src');
    const key = `${file}|${fs.statSync(file).mtimeMs}|${FPS}`;
    if (!fs.existsSync(stamp) || fs.readFileSync(stamp, 'utf8') !== key) {
      fs.rmSync(dir, {recursive: true, force: true});
      fs.mkdirSync(dir, {recursive: true});
      execFileSync('ffmpeg', ['-v', 'error', '-i', file, '-vf', `fps=${FPS},scale='min(1600,iw)':-2`, '-q:v', '3', path.join(dir, '%05d.jpg')]);
      fs.writeFileSync(stamp, key);
    }
    counts[id] = fs.readdirSync(dir).filter(f => f.endsWith('.jpg')).length;
  }
  return counts;
}

const look = (style, tempo) => [style && `style=${style}`, tempo && `tempo=${tempo}`, argv.includes('--cam') && !!opt('--stills') && 'cam'].filter(Boolean).join('&');

const browser = await chromium.launch({executablePath: findBrowser()});
const page = await browser.newPage({viewport: {width: 1920, height: 1248}});
const pageErrors = [];
page.on('pageerror', e => { pageErrors.push(e.message); console.error('page error:', e.message); });
page.on('console', m => m.type() === 'warning' && console.error('page warning:', m.text()));

async function open(style, render) {
  const query = [look(style, TEMPO), render].filter(Boolean).join('&');
  await page.goto(`file://${pageFile}${query ? '?' + query : ''}`);
  return page.evaluate(() => ({clips: window.__clips, timeline: window.__timeline(), styles: window.__styles,
    stage: [document.getElementById('stage').offsetWidth, document.getElementById('stage').offsetHeight]}));
}

let info;
try { info = await open(STYLE === 'all' ? null : STYLE); }
catch (e) {
  if (!pageErrors.length) throw e;
  console.error('The page did not load. Fix demo.config.js:\n  ' + pageErrors.join('\n  '));
  process.exit(1);
}

const clipName = p => path.basename(p).replace(/\.[^.]+$/, '');
const slug = s => s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
function loadTraces(dir) {
  // Cursor traces from cursor_track.py: <dir>/<clip name>.json, one per chapter clip, in clip time.
  const traces = {};
  for (const f of fs.existsSync(dir) ? fs.readdirSync(dir) : []) if (f.endsWith('.json')) traces[f.slice(0, -5)] = JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8'));
  return traces;
}
const traceDir = flag => path.resolve(opt(flag) && !opt(flag).startsWith('--') ? opt(flag) : path.join(PAGE, '..', 'work', 'cursor'));
const near = (tr, c) => { let best = null; for (const p of tr.samples) if (p[1] !== null && Math.abs(p[0] - c) <= .3 && (!best || Math.abs(p[0] - c) < Math.abs(best[0] - c))) best = p; return best; };

async function checkCams(traces) {
  const MARGIN = .03, issues = [];
  for (let t = info.timeline.intro; t < info.timeline.outro; t += .2) {
    const v = await page.evaluate(x => window.__view(x), t);
    const tr = v && traces[clipName(v.clip)];
    if (!v || !tr || v.overlay) continue;
    const p = near(tr, v.c);
    if (!p) continue;
    const [, fx, fy, how] = p;
    const out = fx < v.x0 || fx > v.x1 || fy < v.y0 || fy > v.y1;
    // Near a view edge that is also the clip's edge isn't a framing problem.
    const edge = !out && ((v.x0 > .001 && fx < v.x0 + MARGIN) || (v.x1 < .999 && fx > v.x1 - MARGIN) || (v.y0 > .001 && fy < v.y0 + MARGIN) || (v.y1 < .999 && fy > v.y1 - MARGIN));
    if (!out && !edge) continue;
    // A parked cursor (not moving) outside the view matters less than one that is doing something.
    const last = issues[issues.length - 1], kind = out ? (how === 'held' ? 'parked' : 'OUTSIDE') : 'edge';
    if (last && last.chapter === v.chapter && last.kind === kind && t - last.t1 < .45) { last.t1 = t; last.c1 = v.c; continue; }
    issues.push({chapter: v.chapter, kind, t0: t, t1: t, c0: v.c, c1: v.c, at: `${fx.toFixed(2)},${fy.toFixed(2)}`,
      view: `x ${v.x0.toFixed(2)}–${v.x1.toFixed(2)}, y ${v.y0.toFixed(2)}–${v.y1.toFixed(2)}`});
  }
  // A cursor that flicks past for one sample is faster than any camera; only a stay outside is an error.
  return issues.map(i => ({level: i.kind === 'OUTSIDE' && i.t1 - i.t0 >= .35 ? 'error' : 'warn',
    text: `cursor ${{OUTSIDE: 'outside', parked: 'parked outside', edge: 'at the edge of'}[i.kind]} the view: ${i.chapter} clip ${i.c0.toFixed(2)}–${i.c1.toFixed(2)} (page ${i.t0.toFixed(1)}–${i.t1.toFixed(1)}), cursor ${i.at}, view ${i.view}`}));
}

async function autoCams(traces) {
  // One window per hold and about 2 s of play; frame the cursor and whatever changed in it, then keep only real moves.
  const geo = await page.evaluate(() => window.__geometry()), chs = await page.evaluate(() => window.__chapters());
  const MAX = +opt('--max-zoom', 2.4), [lw, lh] = geo.lensOverVideo, base = Math.max(1, geo.minScale);
  const clamp = x => Math.max(0, Math.min(1, x));
  return chs.map(ch => {
    const tr = traces[clipName(ch.clip)];
    if (!tr) return {label: ch.label, clip: ch.clip, cams: null};
    const wins = [], holdLen = {};
    for (const st of ch.steps) {
      if (st[0] === 'hold') { wins.push({c0: st[1] - .3, c1: st[1] + .3, at: st[1], off: 0, hold: true}); holdLen[st[1]] = st[2]; continue; }
      const [, a, b, rate = 1] = st, n = Math.max(1, Math.round((b - a) / (2 * rate)));
      for (let k = 0; k < n; k++) {
        const c0 = a + (b - a) * k / n;
        wins.push({c0, c1: a + (b - a) * (k + 1) / n, at: k ? +c0.toFixed(2) : a, off: k ? -.3 : (holdLen[a] ?? 0) - .3});
      }
    }
    const cams = [];
    let cur = {S: base, fx: .5, fy: .5};
    wins.forEach((w, i) => {
      // A moving cursor is the action; a parked one only counts when nothing else changes.
      const inWin = tr.samples.filter(p => p[1] !== null && p[0] >= w.c0 - .2 && p[0] <= w.c1 + .2);
      const boxes = (tr.changes || []).filter(b => b[0] >= w.c0 && b[0] <= w.c1 && (b[3] - b[1]) * (b[4] - b[2]) < .5);
      const big = (tr.changes || []).some(b => b[0] >= w.c0 && b[0] <= w.c1 && (b[3] - b[1]) * (b[4] - b[2]) >= .5);
      const moving = inWin.filter(p => p[3] === 'seen'), pts = moving.length || boxes.length ? moving : inWin;
      const mid = list => list.length ? list.reduce((a, p) => a + p, 0) / list.length : .5;
      let t;
      if (big) t = {S: base, fx: mid(pts.map(p => p[1])), fy: mid(pts.map(p => p[2]))};   // most of the screen changes: as wide as the style allows
      else if (pts.length || boxes.length) {
        let x0 = 1, y0 = 1, x1 = 0, y1 = 0;
        for (const p of pts) { x0 = Math.min(x0, p[1]); x1 = Math.max(x1, p[1]); y0 = Math.min(y0, p[2]); y1 = Math.max(y1, p[2]); }
        for (const b of boxes) { x0 = Math.min(x0, b[1]); y0 = Math.min(y0, b[2]); x1 = Math.max(x1, b[3]); y1 = Math.max(y1, b[4]); }
        const bw = Math.max(x1 - x0 + .12, .2), bh = Math.max(y1 - y0 + .12, .2);
        let S = Math.max(Math.min(lw / bw, lh / bh, MAX), base);
        if (S < 1.08) S = 1;
        t = {S, fx: clamp((x0 + x1) / 2), fy: clamp((y0 + y1) / 2)};
      }
      if (!t || (t.S <= 1.001 && cur.S <= 1.001)) return;
      if (Math.abs(t.S - cur.S) < .15 && Math.abs(t.fx - cur.fx) < .08 && Math.abs(t.fy - cur.fy) < .08) return;
      const off = i === 0 ? 0 : w.off;
      cams.push([w.at, +off.toFixed(2), +(1 + (t.S - 1) / geo.zoom).toFixed(2), +t.fx.toFixed(2), +t.fy.toFixed(2), w.hold ? .6 : .8]);
      cur = t;
    });
    return {label: ch.label, clip: ch.clip, cams};
  });
}

function writeCams(file, list) {
  // Replaces each chapter's `cams: [...]` in order; needs exactly one per chapter (make_config.py writes them).
  const src = fs.readFileSync(file, 'utf8'), starts = [], re = /\bcams\s*:\s*\[/g;
  for (let m; (m = re.exec(src));) starts.push(m.index);
  if (starts.length !== list.length) return `found ${starts.length} "cams:" entries for ${list.length} chapters; paste the lines by hand`;
  let out = '', last = 0;
  starts.forEach((start, i) => {
    let j = src.indexOf('[', start), depth = 0;
    for (; j < src.length; j++) { if (src[j] === '[') depth++; else if (src[j] === ']' && --depth === 0) break; }
    out += src.slice(last, start) + (list[i] ? `cams: ${JSON.stringify(list[i])}` : src.slice(start, j + 1));
    last = j + 1;
  });
  fs.copyFileSync(file, file + '.bak');
  fs.writeFileSync(file, out + src.slice(last));
  return null;
}

async function lint() {
  const found = [];
  const add = (level, text) => found.push({level, text});
  // Clip times past the end of a clip, and overlays that don't start with their chapter.
  const dur = {};
  for (const c of info.clips) dur[c.src] = +execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path.resolve(PAGE, c.src)]).toString().trim();
  const chs = await page.evaluate(() => window.__chapters());
  for (const ch of chs) {
    const d = dur[ch.clip], times = [...ch.steps.flatMap(s => s[0] === 'hold' ? [s[1]] : [s[1], s[2]]), ...ch.cams.map(c => c.c), ...ch.chips.map(c => c.c)];
    const late = Math.max(...times);
    if (d && late > d + .05) add('error', `${ch.label}: clip time ${late} is past the end of ${ch.clip} (${d.toFixed(2)} s)`);
  }
  const clipsJson = path.join(PAGE, '..', 'clips.json');
  if (fs.existsSync(clipsJson)) {
    const cj = JSON.parse(fs.readFileSync(clipsJson, 'utf8')).clips || {};
    for (const ch of chs) for (const o of ch.overlays) {
      const a = cj[clipName(ch.clip)], b = cj[clipName(o.clip)];
      if (a && b && Math.abs(a.segments[0][0] - b.segments[0][0]) > .05)
        add('error', `${ch.label}: overlay ${o.clip} starts at source ${b.segments[0][0]} s but its chapter at ${a.segments[0][0]} s; they must match`);
    }
  }
  // Layout, sampled through the whole page.
  const runs = [];
  for (let t = 0; t < info.timeline.duration; t += .25) {
    for (const f of await page.evaluate(x => window.__lint(x), t)) {
      const key = `${f.level}|${f.kind}|${f.what}`, last = runs.find(r => r.key === key && t - r.t1 < .6);
      if (last) last.t1 = t; else runs.push({key, ...f, t0: t, t1: t});
    }
  }
  for (const r of runs) add(r.level, `${r.kind}: ${r.what} (page ${r.t0.toFixed(1)}–${r.t1.toFixed(1)})`);
  const traces = loadTraces(traceDir('--lint'));
  if (Object.keys(traces).length) found.push(...await checkCams(traces));
  else add('warn', 'no cursor traces, so the camera was not checked (run cursor_track.py)');
  return found;
}

if (argv.includes('--check-cams')) {
  const traces = loadTraces(traceDir('--check-cams'));
  if (!Object.keys(traces).length) throw new Error(`no cursor traces in ${traceDir('--check-cams')}; run cursor_track.py first`);
  const issues = await checkCams(traces);
  if (!issues.length) console.log('cursor stays inside the camera view');
  for (const i of issues) console.log(`${i.level === 'error' ? 'OUTSIDE' : 'edge   '} ${i.text}`);
  await browser.close();
  process.exit(0);
}
if (argv.includes('--auto-cams')) {
  const traces = loadTraces(traceDir('--auto-cams'));
  if (!Object.keys(traces).length) throw new Error(`no cursor traces in ${traceDir('--auto-cams')}; run cursor_track.py first`);
  const result = await autoCams(traces);
  for (const r of result) console.log(r.cams ? `${r.label}: cams: ${JSON.stringify(r.cams)},` : `${r.label}: no trace for ${r.clip}; run cursor_track.py on it`);
  if (argv.includes('--write')) {
    const problem = writeCams(path.join(PAGE, 'demo.config.js'), result.map(r => r.cams));
    if (problem) console.log(problem);
    else {
      console.log('written to demo.config.js (previous version in demo.config.js.bak)');
      info = await open(STYLE, null);
      const issues = await checkCams(traces);
      console.log(issues.length ? issues.map(i => `${i.level === 'error' ? 'OUTSIDE' : 'edge   '} ${i.text}`).join('\n') : 'cursor stays inside the camera view');
    }
  }
  await browser.close();
  process.exit(0);
}
if (argv.includes('--lint')) {
  const found = await lint();
  const errors = found.filter(f => f.level === 'error'), warns = found.filter(f => f.level === 'warn');
  for (const f of [...errors, ...warns]) console.log(`${f.level === 'error' ? 'ERROR' : 'warn '} ${f.text}`);
  console.log(`lint: ${errors.length} errors, ${warns.length} warnings${errors.length ? '' : ' - ready for stills'}`);
  await browser.close();
  process.exit(errors.length ? 1 : 0);
}
if (argv.includes('--timeline')) {
  const tl = info.timeline;
  console.log(`style ${tl.style} · tempo ${tl.tempo}`);
  console.log(`${'intro'.padEnd(14)} 0.00 – ${tl.intro.toFixed(2)}`);
  for (const c of tl.chapters) console.log(`${c.label.padEnd(14)} ${c.start.toFixed(2)} – ${c.end.toFixed(2)}`);
  console.log(`${'outro'.padEnd(14)} ${tl.outro.toFixed(2)} – ${tl.duration.toFixed(2)}`);
  console.log(`duration       ${tl.duration}`);
  await browser.close();
  process.exit(0);
}

await page.setViewportSize({width: info.stage[0], height: info.stage[1]});
const counts = extractFrames(info.clips);
const frames = 'render=' + Object.entries(counts).map(([k, v]) => `${k}:${v}`).join(',') + `&fps=${FPS}`;

async function autoMoments(only) {
  // The moments worth checking: each chapter's start, every settled zoom, every hold, every chip, every overlay hand-off.
  const chs = await page.evaluate(() => window.__chapters()), tl = info.timeline, groups = [];
  if (!only) groups.push({name: '00-intro-outro', items: [{t: tl.intro * .75, why: 'intro'}, {t: Math.min(tl.duration - .2, tl.outro + 1.5), why: 'outro'}]});
  chs.forEach((ch, i) => {
    if (only && only !== i + 1) return;
    const items = [{t: ch.g0 + .5, why: 'start'}, ...ch.cams.map(c => ({t: c.settled, why: `zoom @${c.c}`})),
      ...ch.holds.map(h => ({t: (h.g0 + h.g1) / 2, why: `hold @${h.c}`})), ...ch.chips.map(c => ({t: c.g + .45, why: `chip "${c.text.slice(0, 22)}"`})),
      ...ch.overlays.flatMap(o => [{t: o.gOut - .3, why: 'overlay out'}, {t: o.gOut + .8, why: 'after overlay'}])];
    const kept = [];
    for (const it of items.map(x => ({...x, t: Math.min(x.t, ch.g1 - .05)})).sort((x, y) => x.t - y.t)) {
      const last = kept[kept.length - 1];
      if (last && it.t - last.t < .35) last.why += ` + ${it.why}`; else kept.push(it);
    }
    groups.push({name: `${String(i + 1).padStart(2, '0')}-${slug(ch.label)}`, items: kept});
  });
  return groups;
}

const stills = opt('--stills');
if (stills === 'auto') {
  if (STYLE === 'all') throw new Error('--stills auto needs one style');
  const out = path.resolve(opt('--stills-dir', 'stills'));
  fs.mkdirSync(out, {recursive: true});
  await open(STYLE, frames);
  await page.waitForFunction(() => window.__ready && window.__ready());
  const font = ['/System/Library/Fonts/Helvetica.ttc', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'].find(f => fs.existsSync(f));
  for (const g of await autoMoments(opt('--chapter') ? +opt('--chapter') : 0)) {
    const args = ['montage', ...(font ? ['-font', font] : []), '-pointsize', '20', '-fill', 'white', '-background', '#222'];
    for (const it of g.items) {
      const file = path.join(out, `${g.name}_${it.t.toFixed(2)}.jpg`);
      await page.evaluate(t => window.__renderAt(t), it.t);
      await page.screenshot({path: file, type: 'jpeg', quality: 80});
      args.push('-label', `${it.t.toFixed(2)} s  ${it.why}`, file);
    }
    const sheet = path.join(out, `sheet_${g.name}.jpg`);
    fs.rmSync(sheet, {force: true});
    try { execFileSync('magick', [...args, '-tile', '3x', '-geometry', '640x416+4+4', sheet], {stdio: 'ignore'}); } catch {}
    console.log(fs.existsSync(sheet) ? `${sheet}  (${g.items.length} moments)` : `montage failed for ${g.name}; stills are in ${out}`);
  }
} else if (stills) {
  const out = path.resolve(opt('--stills-dir', 'stills'));
  fs.mkdirSync(out, {recursive: true});
  for (const style of STYLE === 'all' ? info.styles : [STYLE]) {
    await open(style, frames + (STYLE === 'all' ? '&badge' : ''));
    await page.waitForFunction(() => window.__ready && window.__ready());
    for (const s of stills.split(',').map(Number)) {
      await page.evaluate(t => window.__renderAt(t), s);
      const name = `${style ? style + '_' : ''}t_${s.toFixed(2).padStart(6, '0')}.jpg`;
      await page.screenshot({path: path.join(out, name), type: 'jpeg', quality: 80});
    }
  }
  if (STYLE === 'all') {
    // One comparison sheet per moment, styles in reading order, for showing the user.
    for (const s of stills.split(',').map(Number)) {
      const t = s.toFixed(2).padStart(6, '0'), sheet = path.join(out, `sheet_t_${t}.jpg`);
      // ImageMagick exits non-zero when it has no default font, even though the sheet is written.
      const font = ['/System/Library/Fonts/Helvetica.ttc', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'].find(f => fs.existsSync(f));
      fs.rmSync(sheet, {force: true});
      try {
        execFileSync('magick', ['montage', ...(font ? ['-font', font] : []), ...info.styles.map(st => path.join(out, `${st}_t_${t}.jpg`)),
          '-tile', '3x', '-geometry', '960x624+6+6', '-background', '#222', sheet], {stdio: 'ignore'});
      } catch {}
      if (fs.existsSync(sheet)) console.log('sheet ->', sheet);
      else console.error('magick montage failed; the separate stills are still in', out);
    }
  }
  console.log('stills ->', out);
} else {
  if (STYLE === 'all') throw new Error('--style all only works with --stills');
  await open(STYLE, frames);
  await page.waitForFunction(() => window.__ready && window.__ready());
  const outFile = path.resolve(opt('--out', 'output/demo-silent.mp4'));
  fs.mkdirSync(path.dirname(outFile), {recursive: true});
  // libx264 with yuv420p needs even sides, so an odd stage loses its last pixel row or column.
  const ff = spawn('ffmpeg', ['-v', 'error', '-y', '-f', 'image2pipe', '-c:v', 'mjpeg', '-framerate', String(FPS), '-i', '-',
    '-vf', 'crop=trunc(iw/2)*2:trunc(ih/2)*2',
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', outFile], {stdio: ['pipe', 'inherit', 'inherit']});
  const dur = info.timeline.duration, total = Math.round(dur * FPS);
  for (let f = 0; f < total; f++) {
    await page.evaluate(t => window.__renderAt(t), f / FPS);
    const buf = await page.screenshot({type: 'jpeg', quality: 95});
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    if (f % 300 === 0) console.log(`frame ${f}/${total}`);
  }
  ff.stdin.end();
  await new Promise(r => ff.on('close', r));
  console.log('done ->', outFile, `${dur}s`, `(${info.timeline.style}, ${info.timeline.tempo})`);
}
await browser.close();
