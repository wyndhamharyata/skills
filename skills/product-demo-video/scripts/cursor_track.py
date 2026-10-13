#!/usr/bin/env python3
"""Rough cursor trace of cut clips, so camera moves can be checked against where the action is.

  cursor_track.py page/01-open.mp4 page/02-reader.mp4 --out work/cursor
  node render.mjs page/index.html --check-cams work/cursor      # times the cursor leaves the camera view

Compares each sample with the one before it. A small changed area is taken as the cursor; a large one is a UI
change and is skipped. When nothing moves, the last position is held for up to 2 s. Writes
<out>/<clip name>.json with samples [clipTime, fx, fy, "seen" | "held"] (fx, fy are 0-1 inside the clip, or
null when unknown) and changes [clipTime, x0, y0, x1, y1] (the box around everything that changed since the
previous sample), and prints a one-line summary per clip. render.mjs --auto-cams reads both. It's a check, not a tracker: a spinner or a
playing video next to the cursor can fool it, so read flagged times on a still before trusting them.
Needs ffmpeg and Pillow.
"""
import argparse, json, os, subprocess
from PIL import Image, ImageChops

WIDTH = 640
CHANGED = [0] * 26 + [255] * 230          # grey levels that count as a change
SMALL = .15                               # a cursor change spans under 15% of the frame each way
HOLD = 2.0


def size(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                          "-of", "csv=p=0", path], capture_output=True, text=True, check=True).stdout
    w, h = (int(x) for x in out.strip().split(",")[:2])
    return WIDTH, round(h * WIDTH / w / 2) * 2


def trace(path, fps):
    w, h = size(path)
    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-i", path, "-vf", f"fps={fps},scale={w}:{h},format=gray",
                             "-f", "rawvideo", "-"], stdout=subprocess.PIPE)
    samples, changes, prev, last, last_t, i = [], [], None, None, None, 0
    while True:
        raw = proc.stdout.read(w * h)
        if len(raw) < w * h:
            break
        frame, t = Image.frombytes("L", (w, h), raw), round(i / fps, 3)
        i += 1
        if prev is not None:
            box = ImageChops.difference(frame, prev).point(CHANGED).getbbox()
            if box:
                changes.append([t, round(box[0] / w, 3), round(box[1] / h, 3), round(box[2] / w, 3), round(box[3] / h, 3)])
            if box and box[2] - box[0] < w * SMALL and box[3] - box[1] < h * SMALL:
                last, last_t = ((box[0] + box[2]) / 2 / w, (box[1] + box[3]) / 2 / h), t
                samples.append([t, round(last[0], 3), round(last[1], 3), "seen"])
            elif last and t - last_t <= HOLD:
                samples.append([t, round(last[0], 3), round(last[1], 3), "held"])
            else:
                samples.append([t, None, None, "unknown"])
        prev = frame
    proc.wait()
    return samples, changes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clips", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=float, default=10)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    for clip in a.clips:
        name = os.path.splitext(os.path.basename(clip))[0]
        samples, changes = trace(clip, a.fps)
        with open(os.path.join(a.out, name + ".json"), "w") as f:
            json.dump({"clip": os.path.basename(clip), "fps": a.fps, "samples": samples, "changes": changes}, f)
        seen = sum(s[3] == "seen" for s in samples)
        print(f"{name}: {len(samples)} samples, cursor seen in {seen}, held in {sum(s[3] == 'held' for s in samples)}")


if __name__ == "__main__":
    main()
