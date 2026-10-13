// Render the demo page to an MP4, or to a few stills for checking framing.
//
//   node render.mjs page/index.html --out output/demo-silent.mp4
//   node render.mjs page/index.html --stills 2.5,9,23.4 --stills-dir stills
//   node render.mjs page/index.html --stills 9,20 --style all      # every style, labelled, plus one sheet per moment
//   node render.mjs page/index.html --timeline --tempo fast        # chapter times for a tempo
//   node render.mjs page/index.html --stills 9 --cam               # show the Loom camera spot in stills
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
page.on('pageerror', e => console.error('page error:', e.message));
page.on('console', m => m.type() === 'warning' && console.error('page warning:', m.text()));

async function open(style, render) {
  const query = [look(style, TEMPO), render].filter(Boolean).join('&');
  await page.goto(`file://${pageFile}${query ? '?' + query : ''}`);
  return page.evaluate(() => ({clips: window.__clips, timeline: window.__timeline(), styles: window.__styles,
    stage: [document.getElementById('stage').offsetWidth, document.getElementById('stage').offsetHeight]}));
}

const info = await open(STYLE === 'all' ? null : STYLE);
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

const stills = opt('--stills');
if (stills) {
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
