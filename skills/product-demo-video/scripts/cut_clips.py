#!/usr/bin/env python3
"""Cut a screen recording into cropped clips with dead air removed and slow parts sped up.

  cut_clips.py clips.json                 # cut every clip
  cut_clips.py clips.json 03-summaries    # re-cut one clip
  cut_clips.py clips.json --map 03-summaries 32.5   # source second -> clip second (for page timings)
  cut_clips.py clips.json --list          # every clip's segments with their clip-time ranges

clips.json:
{
  "source": "/path/Screen Recording.mov",
  "out": "page",                                   # relative to clips.json
  "crop": "1782:2180:1806:144",                    # default crop, ffmpeg W:H:X:Y
  "fps": 60,
  "clips": {
    "00-finder":    {"crop": "1784:1176:10:88", "segments": [[0.5, 4.5, 1]]},
    "01-open":      {"segments": [[0.5, 8.3, 1]]},
    "03-summaries": {"segments": [[22.7, 28.6, 1], [29.95, 32.0, 2], [32.0, 33.2, 1]]}
  }
}
Each segment is [sourceStart, sourceEnd, speed]. Leaving a gap between segments cuts it out.
Needs ffmpeg.
"""
import json, os, subprocess, sys


def load(path):
    with open(path) as f:
        cfg = json.load(f)
    cfg["_dir"] = os.path.dirname(os.path.abspath(path))
    return cfg


def clip_time(segs, src_t):
    t = 0.0
    for a, b, r in segs:
        if a <= src_t <= b:
            return round(t + (src_t - a) / r, 3)
        t += (b - a) / r
    raise SystemExit(f"{src_t} is not inside any kept segment")


def cut(cfg, name):
    clip = cfg["clips"][name]
    crop = clip.get("crop", cfg.get("crop"))
    fps = clip.get("fps", cfg.get("fps", 60))
    segs = clip["segments"]
    parts, labels = [], []
    for i, (a, b, r) in enumerate(segs):
        chain = f"[0:v]trim={a}:{b},setpts=(PTS-STARTPTS)/{r}" + (f",crop={crop}" if crop else "") + f",fps={fps}[p{i}]"
        parts.append(chain)
        labels.append(f"[p{i}]")
    fc = ";".join(parts) + f";{''.join(labels)}concat=n={len(segs)}:v=1:a=0,format=yuv420p[v]"
    out_dir = os.path.join(cfg["_dir"], cfg.get("out", "page"))
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, name + ".mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", cfg["source"], "-filter_complex", fc, "-map", "[v]",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-g", "30",
                    "-movflags", "+faststart", "-an", out], check=True)
    print(f"{name}.mp4  {sum((b - a) / r for a, b, r in segs):.3f}s")


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    cfg = load(sys.argv[1])
    args = sys.argv[2:]
    if args[:1] == ["--map"]:
        print(clip_time(cfg["clips"][args[1]]["segments"], float(args[2])))
        return
    if args[:1] == ["--list"]:
        for name, clip in cfg["clips"].items():
            t, rows = 0.0, []
            for a, b, r in clip["segments"]:
                d = (b - a) / r
                rows.append(f"src {a}-{b} x{r} -> clip {t:.3f}-{t + d:.3f}")
                t += d
            print(f"{name} ({t:.3f}s)\n  " + "\n  ".join(rows))
        return
    for name in cfg["clips"]:
        if not args or name in args:
            cut(cfg, name)


if __name__ == "__main__":
    main()
