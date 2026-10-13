#!/usr/bin/env python3
"""Find dead air and sudden pop-ups (Dock, notifications) in a screen recording.

  activity.py rec.mov                                   # whole frame, 10 samples/s
  activity.py rec.mov --crop 1782:2180:1806:144         # only the app window
  activity.py rec.mov --crop 900:120:1806:2200 --start 27 --end 32 --fps 20 --ref   # Dock check on a strip

Prints the per-sample change and lists idle spans (no visible change for --idle seconds or more).
--ref compares each sample with the first one instead of the previous one, which shows exactly
when something appears on top and when it is gone again.
Needs ffmpeg only.
"""
import argparse, subprocess


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--crop", help="W:H:X:Y in source pixels")
    ap.add_argument("--start", type=float, default=0)
    ap.add_argument("--end", type=float)
    ap.add_argument("--fps", type=float, default=10)
    ap.add_argument("--idle", type=float, default=1.5, help="report still spans at least this long")
    ap.add_argument("--threshold", type=float, default=0.4, help="mean abs diff (0–255) treated as no change")
    ap.add_argument("--ref", action="store_true")
    ap.add_argument("--quiet", action="store_true", help="only print idle spans")
    a = ap.parse_args()

    W, H = 96, 64
    vf = (f"crop={a.crop}," if a.crop else "") + f"fps={a.fps},scale={W}:{H},format=gray"
    cmd = ["ffmpeg", "-v", "error", "-ss", str(a.start)]
    if a.end is not None:
        cmd += ["-t", str(a.end - a.start)]
    cmd += ["-i", a.video, "-vf", vf, "-f", "rawvideo", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    n = W * H
    frames = [raw[i:i + n] for i in range(0, len(raw) - n + 1, n)]
    diffs = []
    for i, f in enumerate(frames):
        base = frames[0] if a.ref else frames[max(0, i - 1)]
        diffs.append(sum(abs(x - y) for x, y in zip(f, base)) / n)

    if not a.quiet:
        print(" | ".join(f"{a.start + i / a.fps:.2f} {d:.1f}" for i, d in enumerate(diffs)))
    if a.ref:
        return
    spans, s0 = [], None
    for i, d in enumerate(diffs + [99]):
        t = a.start + i / a.fps
        if d <= a.threshold and i:
            s0 = s0 if s0 is not None else t - 1 / a.fps
        elif s0 is not None:
            if t - s0 >= a.idle:
                spans.append((s0, t))
            s0 = None
    print("\nidle spans (candidates to cut or speed up):")
    for s, e in spans:
        print(f"  {s:.2f} – {e:.2f}  ({e - s:.1f}s)")
    if not spans:
        print("  none")


if __name__ == "__main__":
    main()
