#!/usr/bin/env python3
"""Suggest the segments of a clip from a rough source range: keep clicks, cut dead air, speed up long changes.

  suggest_cuts.py rec.mov --crop 1784:2182:1804:144 --range 23.0-38.8
  suggest_cuts.py rec.mov --crop … --range 23.0-38.8 --keep 25.0-25.6 --drop 28.6-29.9
  suggest_cuts.py rec.mov --crop … --range 23.0-38.8 --clips clips.json --name 03-summaries   # also write it

Measures the change inside the crop (20 samples/s) and sorts the time into idle (no visible change),
bursts (clicks, panels opening, results appearing) and continuous change (--steady seconds or more of
change: scrolling, streaming text, slider drags). Bursts stay at 1x with 0.3 s before and 0.5 s after;
idle longer than --max-idle is cut down to those margins; continuous change is sped up (--speed) except
its first and last 0.5 s. --keep forces 1x, --drop forces a cut (popups, desktop flashes).
Prints the segments, the clip length and a JSON line for clips.json ([sourceStart, sourceEnd, speed]).
Needs ffmpeg only.
"""
import argparse, json, os, subprocess

FPS, STEP, BEFORE, AFTER, RAMP, GAP, MIN_SEG = 20, 0.05, 0.3, 0.5, 0.5, 0.3, 0.25


def span(s):
    a, b = s.split("-")
    return float(a), float(b)


def changes(video, crop, start, end, W=96, H=64):
    t0 = max(0, start - 1 / FPS)
    vf = (f"crop={crop}," if crop else "") + f"fps={FPS},scale={W}:{H},format=gray"
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t0), "-t", str(end - t0), "-i", video,
                          "-vf", vf, "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    n = W * H
    frames = [raw[i:i + n] for i in range(0, len(raw) - n + 1, n)]
    return [(t0 + i / FPS, sum(abs(x - y) for x, y in zip(frames[i], frames[i - 1])) / n) for i in range(1, len(frames))]


def runs_of(samples, threshold, dropped):
    """Change runs as (start, end) in seconds; dips up to GAP seconds inside a run are bridged."""
    runs = []
    for t, d in samples:
        if d <= threshold or dropped(t):
            continue
        if runs and t - runs[-1][1] <= GAP + 1e-6:
            runs[-1][1] = t
        else:
            runs.append([t - 1 / FPS, t])
    return runs


def plan(samples, rng, a):
    lo, hi = round(rng[0] / STEP), round(rng[1] / STEP)
    slots = {k: (0, "idle") for k in range(lo, hi)}          # slot k covers [k*STEP, (k+1)*STEP)

    def put(s, e, speed, kind, force=False):
        for k in range(max(lo, round(s / STEP)), min(hi, round(e / STEP))):
            if force or speed == 1 or slots[k][0] == 0:
                slots[k] = (speed, kind)

    dropped = lambda t: any(s <= t - 1 / FPS and t <= e for s, e in a.drop)
    runs = runs_of(samples, a.threshold, dropped)
    edges = [rng[0]] + [x for r in runs for x in r] + [rng[1]]
    for i in range(0, len(edges), 2):                       # idle stretches between runs
        s, e = edges[i], edges[i + 1]
        if e - s <= a.max_idle:
            put(s, e, 1, "idle")
    for s, e in runs:
        if e - s >= a.steady:
            put(s + RAMP, e - RAMP, a.speed, "continuous")
            put(s - BEFORE, s + RAMP, 1, "continuous")
            put(e - RAMP, e + AFTER, 1, "continuous")
        else:
            put(s - BEFORE, e + AFTER, 1, "burst")
    for s, e in a.keep:
        put(s, e, 1, "keep", force=True)
    for s, e in a.drop:
        put(s, e, 0, "drop", force=True)

    out = []                                                # [start, end, speed, kinds]
    for k in range(lo, hi):
        speed, kind = slots[k]
        if out and out[-1][2] == speed and out[-1][1] == k:
            out[-1][1] = k + 1
            out[-1][3].append(kind)
        else:
            out.append([k, k + 1, speed, [kind]])
    for seg in out:
        if seg[2] and (seg[1] - seg[0]) * STEP < MIN_SEG - 1e-6:
            seg[2], seg[3] = 0, ["short"]
    merged = []
    for seg in out:
        if merged and merged[-1][2] == seg[2] == 0:
            merged[-1][1] = seg[1]
            merged[-1][3] += seg[3]
        else:
            merged.append(seg)
    return [(round(s * STEP, 2), round(e * STEP, 2), sp, kinds) for s, e, sp, kinds in merged]


def label(kinds, kept=True):
    names = list(dict.fromkeys(kinds))
    if kept and len(names) > 1 and "idle" in names:
        names.remove("idle")
    return "+".join(names)


def write_clip(path, name, video, crop, segs):
    if os.path.exists(path):
        with open(path) as f:
            cfg = json.load(f)
    else:
        cfg = {"source": os.path.abspath(video), "out": "page", "crop": crop, "fps": 60, "clips": {}}
    clips = cfg.setdefault("clips", {})
    created = name not in clips
    clip = clips.setdefault(name, {})
    if created and crop and crop != cfg.get("crop"):
        clip["crop"] = crop
    clip["segments"] = segs
    lines = [f"  {json.dumps(k)}: {json.dumps(v)}," for k, v in cfg.items() if k != "clips"]
    rows = [f"    {json.dumps(k)}: {json.dumps(v)}" for k, v in clips.items()]
    with open(path, "w") as f:
        f.write("{\n" + "\n".join(lines) + '\n  "clips": {\n' + ",\n".join(rows) + "\n  }\n}\n")
    return created


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--crop", help="W:H:X:Y in source pixels")
    ap.add_argument("--range", type=span, action="append", required=True, help="source seconds, e.g. 23.4-38.6")
    ap.add_argument("--keep", type=span, action="append", default=[], help="force 1x")
    ap.add_argument("--drop", type=span, action="append", default=[], help="force a cut")
    ap.add_argument("--speed", type=float, default=1.6, help="speed for continuous change")
    ap.add_argument("--max-idle", type=float, default=1.0, help="cut still stretches longer than this")
    ap.add_argument("--steady", type=float, default=2.5, help="change this long counts as continuous")
    ap.add_argument("--threshold", type=float, default=0.5, help="mean abs diff (0–255) treated as no change")
    ap.add_argument("--clips", help="clips.json to write the segments into")
    ap.add_argument("--name", help="clip name in --clips")
    a = ap.parse_args()
    if bool(a.clips) != bool(a.name):
        ap.error("--clips and --name go together")

    segs = []
    for rng in a.range:
        for s, e, speed, kinds in plan(changes(a.video, a.crop, *rng), rng, a):
            if speed:
                print(f"{s:6.2f}–{e:6.2f} ×{speed:g}  {label(kinds)}")
                segs.append([s, e, int(speed) if speed == int(speed) else speed])
            else:
                print(f"cut {s:.2f}–{e:.2f}  {label(kinds, kept=False)}")
    kept = sum(e - s for s, e, _ in segs)
    print(f"\nkept {kept:.2f}s of source, clip {sum((e - s) / r for s, e, r in segs):.2f}s")
    print(json.dumps(segs))
    if a.clips:
        created = write_clip(a.clips, a.name, a.video, a.crop, segs)
        print(f"{'added' if created else 'updated'} {a.name} in {a.clips}")


if __name__ == "__main__":
    main()
