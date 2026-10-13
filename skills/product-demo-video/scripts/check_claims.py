#!/usr/bin/env python3
"""Check that every caption/chip claim is actually readable on screen, using OCR.

  check_claims.py demo/NOTES.md                                  # lines like: - "356 pages" -> page/05-details.mp4 at 2.4
  check_claims.py --claim "356 pages|page/05-details.mp4|2.4" --claim "All 35|page/06-picker.mp4|3"

NOTES.md lines: `- "<text>" -> <clip> at <t>` (quotes optional, `at 2.4 s` also fine); clip paths
are relative to the NOTES.md folder. --claim paths are relative to the current folder.
Grabs frames at t-0.3, t, t+0.3, OCRs them and checks that every number in the claim and most of
its words (4+ letters) are on screen. Verdicts: OK, CHECK (numbers or words weak), MISSING (a number
is not on screen; exit code 1). Wrong numbers are listed with the OCR lines that hold nearby text.
OCR: macOS Vision (Swift helper compiled once into ~/.cache/product-demo-video/ocr), else tesseract.
--json writes every verdict with the claim's box on screen (clip fractions), which render.mjs uses to aim
the camera (--auto-cams) and to check the viewer can see it (--lint). Normally run by demo.py.
Needs ffmpeg.
"""
import argparse, hashlib, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

SWIFT = r"""
import Foundation
import ImageIO
import Vision
for path in CommandLine.arguments.dropFirst() {
    guard let src = CGImageSourceCreateWithURL(URL(fileURLWithPath: path) as CFURL, nil),
          let cg = CGImageSourceCreateImageAtIndex(src, 0, nil) else { continue }
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.usesLanguageCorrection = false
    try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
    for obs in req.results ?? [] {
        // x0 y0 x1 y1 (0-1, top-left origin), a tab, then the text
        if let top = obs.topCandidates(1).first {
            let b = obs.boundingBox
            print(String(format: "%.4f %.4f %.4f %.4f\t", b.minX, 1 - b.maxY, b.maxX, 1 - b.minY) + top.string)
        }
    }
    print("\u{1E}")
}
"""

CACHE = Path.home() / ".cache/product-demo-video/ocr"
NUM = re.compile(r"[+-]?\d+(?:\.\d+)?%?")
WORD = re.compile(r"[^\W\d_]{4,}")


def build_vision():
    if sys.platform != "darwin" or not shutil.which("swiftc"):
        return None
    tag = hashlib.sha1(SWIFT.encode()).hexdigest()[:10]
    exe = CACHE / f"ocr-{tag}"
    if exe.exists():
        return [str(exe)]
    CACHE.mkdir(parents=True, exist_ok=True)
    src = CACHE / f"ocr-{tag}.swift"
    src.write_text(SWIFT)
    r = subprocess.run(["swiftc", "-O", str(src), "-o", str(exe)], capture_output=True, text=True)
    return [str(exe)] if r.returncode == 0 else None


def ocr_engine():
    # Returns one list per image of (text, box): box is [x0, y0, x1, y1] in 0-1 image fractions, or None (tesseract).
    vision = build_vision()
    if vision:
        def run(pngs):
            out = subprocess.run(vision + pngs, capture_output=True, text=True).stdout
            pages = []
            for page in out.split("\x1e")[:len(pngs)]:
                items = []
                for line in page.strip("\n").splitlines():
                    box, _, text = line.partition("\t")
                    items.append((text, [float(v) for v in box.split()]))
                pages.append(items)
            return pages
        return run
    if shutil.which("tesseract"):
        def tess(pngs):
            return [[(l, None) for l in subprocess.run(["tesseract", p, "-", "--psm", "11"], capture_output=True,
                                                       text=True).stdout.splitlines()] for p in pngs]
        return tess
    return None


def norm(s):
    s = s.replace("\u2212", "-").replace("\u2013", "-").replace("\u2014", "-")
    for sp in "\u2009\u202f\u00a0\u200a":
        s = s.replace(sp, " ")
    s = re.sub(r"(?<=\d),(?=\d{3}\b)", "", s)
    return re.sub(r"(?<=\d),(?=\d)", ".", s)  # decimal comma: 1,8 MB


def numbers(s):
    return {n.lstrip("+") for n in NUM.findall(norm(s))}


def parse_notes(path):
    base = Path(path).parent
    pat = re.compile(r'^\s*[-*]\s*"?(.+?)"?\s*->\s*(\S+)\s+at\s+([\d.]+)\s*s?\b')
    claims = []
    for line in Path(path).read_text().splitlines():
        m = pat.match(line)
        if m:
            # Clip paths are relative to the notes file, or to its parent (work/claims.md from make_config.py).
            clip = next((c for c in (base / m[2], base.parent / m[2]) if c.exists()), base / m[2])
            claims.append((m[1].strip(), str(clip), m[2], float(m[3])))
    return claims


def frames(clip, t, tmp):
    pngs = []
    for i, dt in enumerate((-0.3, 0, 0.3)):
        out = os.path.join(tmp, f"{abs(hash((clip, t)))}_{i}.png")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0, t + dt):.3f}", "-i", clip,
                        "-frames:v", "1", "-vf", "scale=2000:-2:flags=lanczos", out], check=True)
        if os.path.exists(out):
            pngs.append(out)
    return pngs


def check(text, lines):
    screen = norm(" \n".join(lines))
    have_nums = numbers(screen) | {n.rstrip("%") for n in numbers(screen)}
    nums = numbers(text)
    miss_nums = [n for n in nums if n not in have_nums]
    words = claim_words(text)
    low = screen.lower()
    found = [w for w in words if w in low]
    frac = len(found) / len(words) if words else 1
    if miss_nums:
        verdict = "MISSING"
    elif frac >= 0.6:
        verdict = "OK"
    else:
        verdict = "CHECK"
    near = []
    for ln in lines:
        l = norm(ln).lower()
        hit = any(w in l for w in words) or any(close(n, numbers(l)) for n in miss_nums)
        if hit and ln.strip() not in near:
            near.append(ln.strip())
    return verdict, miss_nums, near, frac


def claim_words(text):
    # Words of 4+ letters; a claim made only of short words ("PDF", "Dark") checks those instead.
    words = WORD.findall(text) or re.findall(r"[^\W\d_]{2,}", text)
    return {w.lower().removesuffix("s") if len(w) > 3 else w.lower() for w in words}


def locate(text, items):
    # The box around the screen lines that carry the claim: for each number its best line, else the lines with
    # most of its words.
    nums, words = numbers(text), claim_words(text)
    def score(t):
        l = norm(t).lower()
        return 2 * len(nums & numbers(l)) + sum(w in l for w in words)
    picked = []
    for n in nums:
        best = max((it for it in items if it[1] and n in numbers(it[0])), key=lambda it: score(it[0]), default=None)
        if best and best not in picked:
            picked.append(best)
    if not nums:
        need = max(1, (len(words) + 1) // 2)
        picked = [it for it in items if it[1] and score(it[0]) >= need]
        if not picked:
            best = max((it for it in items if it[1]), key=lambda it: score(it[0]), default=None)
            picked = [best] if best and score(best[0]) else []
    if not picked:
        return None, 0
    boxes = [it[1] for it in picked]
    return ([round(min(b[0] for b in boxes), 4), round(min(b[1] for b in boxes), 4),
             round(max(b[2] for b in boxes), 4), round(max(b[3] for b in boxes), 4)], sum(score(it[0]) for it in picked))


def close(n, have):
    a = n.rstrip("%")
    for h in have:
        b = h.rstrip("%")
        if len(a) == len(b) and sum(x != y for x, y in zip(a, b)) <= 1:
            return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("notes", nargs="?", help="NOTES.md with '- \"text\" -> clip at t' lines")
    ap.add_argument("--claim", action="append", default=[], help="text|clip|t (repeatable)")
    ap.add_argument("--json", help="also write the verdicts and each claim's box on screen (clip fractions) here")
    ap.add_argument("--quiet", action="store_true", help="don't print OK lines")
    a = ap.parse_args()

    claims = parse_notes(a.notes) if a.notes else []
    for c in a.claim:
        text, clip, t = c.rsplit("|", 2)
        claims.append((text, clip, clip, float(t)))
    if not claims:
        ap.error("no claims found")
    ocr = ocr_engine()
    if not ocr:
        print("no OCR engine (swiftc/Vision or tesseract): check the claims by eye on frames from each clip")
        return

    bad, report = False, []
    with tempfile.TemporaryDirectory() as tmp:
        for text, clip, shown, t in claims:
            label = f'"{text}" {shown} @{t:g}'
            if not os.path.exists(clip):
                print(f"MISSING {label} — clip not found")
                report.append({"text": text, "clip": shown, "t": t, "verdict": "MISSING", "box": None, "screen": []})
                bad = True
                continue
            pages = ocr(frames(clip, t, tmp))
            lines = [text_ for page in pages for text_, _ in page]
            verdict, miss, near, frac = check(text, lines)
            # Box from the frame where the claim reads best, preferring the middle one (t itself).
            located = [locate(text, page) for page in pages]
            order = [1, 0, 2][:len(located)]
            box = max((located[i] for i in order), key=lambda r: r[1], default=(None, 0))[0]
            report.append({"text": text, "clip": shown, "t": t, "verdict": verdict, "box": box, "screen": near[:3]})
            bad |= verdict == "MISSING"
            if verdict == "OK":
                if not a.quiet:
                    print(f"OK      {label}")
                continue
            why = f"number {', '.join(miss)} not on screen" if miss else f"only {frac:.0%} of words found"
            print(f"{verdict:<7} {label} — {why}")
            shown_lines = near[:4] or [l.strip() for l in lines if l.strip()][:4]
            print("        screen has: " + " | ".join(f'"{l}"' for l in shown_lines))
    if a.json:
        with open(a.json, "w") as f:
            json.dump(report, f, indent=1, ensure_ascii=False)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
