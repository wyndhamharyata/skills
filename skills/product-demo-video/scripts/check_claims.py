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
Needs ffmpeg.
"""
import argparse, hashlib, os, re, shutil, subprocess, sys, tempfile
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
        if let top = obs.topCandidates(1).first { print(top.string) }
    }
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
    vision = build_vision()
    if vision:
        return lambda pngs: subprocess.run(vision + pngs, capture_output=True, text=True).stdout.splitlines()
    if shutil.which("tesseract"):
        def tess(pngs):
            out = []
            for p in pngs:
                out += subprocess.run(["tesseract", p, "-", "--psm", "11"], capture_output=True, text=True).stdout.splitlines()
            return out
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
    words = {w.lower().removesuffix("s") for w in WORD.findall(text)}
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

    bad = False
    with tempfile.TemporaryDirectory() as tmp:
        for text, clip, shown, t in claims:
            label = f'"{text}" {shown} @{t:g}'
            if not os.path.exists(clip):
                print(f"MISSING {label} — clip not found")
                bad = True
                continue
            lines = ocr(frames(clip, t, tmp))
            verdict, miss, near, frac = check(text, lines)
            bad |= verdict == "MISSING"
            if verdict == "OK":
                print(f"OK      {label}")
                continue
            why = f"number {', '.join(miss)} not on screen" if miss else f"only {frac:.0%} of words found"
            print(f"{verdict:<7} {label} — {why}")
            shown_lines = near[:4] or [l.strip() for l in lines if l.strip()][:4]
            print("        screen has: " + " | ".join(f'"{l}"' for l in shown_lines))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
