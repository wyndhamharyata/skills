#!/usr/bin/env python3
"""Cut a UI element out of a recording frame as a PNG with its background removed.

  cutout.py rec.mov 2.0 --box 35,375,318,482 --radius 22 --out page/covers/a.png
  cutout.py rec.mov 2.0 --box 20,360,360,520 --trim --radius 22 --out page/covers/a.png

--box is X,Y,W,H in source pixels. The result keeps only the box, with rounded transparent
corners (--radius 0 for square). --trim first shrinks the box to its content by removing the
surrounding flat background colour (sampled at the box corner), which is handy when you only
know roughly where the element is. Check the result on a dark background; light pages often
leave a 1–2 px halo, which --inset removes.
Needs ffmpeg and ImageMagick (magick).
"""
import argparse, os, subprocess, tempfile


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("time", type=float)
    ap.add_argument("--box", required=True)
    ap.add_argument("--radius", type=int, default=20)
    ap.add_argument("--trim", action="store_true")
    ap.add_argument("--fuzz", default="6%")
    ap.add_argument("--inset", type=int, default=2)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    x, y, w, h = (int(v) for v in a.box.split(","))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        frame = os.path.join(tmp, "f.png")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(a.time), "-i", a.video, "-frames:v", "1", frame], check=True)
        if a.trim:
            geo = subprocess.run(["magick", frame, "-crop", f"{w}x{h}+{x}+{y}", "+repage", "-fuzz", a.fuzz,
                                  "-format", "%@", "info:"], capture_output=True, text=True, check=True).stdout.strip()
            size, ox, oy = geo.replace("+", " ").split()
            w, h = (int(v) for v in size.split("x"))
            x, y = x + int(ox), y + int(oy)
        x, y, w, h = x + a.inset, y + a.inset, w - 2 * a.inset, h - 2 * a.inset
        subprocess.run(["magick", frame, "-crop", f"{w}x{h}+{x}+{y}", "+repage",
                        "(", "-size", f"{w}x{h}", "xc:none", "-fill", "white",
                        "-draw", f"roundrectangle 0,0,{w - 1},{h - 1},{a.radius},{a.radius}", ")",
                        "-alpha", "set", "-compose", "CopyOpacity", "-composite", a.out], check=True)
    print(f"{a.out}  box {x},{y},{w},{h}")


if __name__ == "__main__":
    main()
