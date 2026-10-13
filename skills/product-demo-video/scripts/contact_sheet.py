#!/usr/bin/env python3
"""Time-labelled contact sheet of a video, for planning cuts and camera focus points.

  contact_sheet.py rec.mov --step 1 --out sheet.jpg                       # whole recording, 1 frame/s
  contact_sheet.py rec.mov --start 8 --end 23 --step .5 --crop 1782:2180:1806:144 --out s.jpg
  contact_sheet.py rec.mov --times 2,5,10.5 --crop ... --grid --width 450 --out grid.jpg

--crop uses ffmpeg order W:H:X:Y. --grid draws 0.1 gridlines labelled 1–9 so you can read
normalised focus points (fx, fy) for the page camera straight off the image.
Needs ffmpeg and Pillow.
"""
import argparse, glob, os, subprocess, tempfile
from PIL import Image, ImageDraw, ImageFont


def font(size):
    for p in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/System/Library/Fonts/Helvetica.ttc",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--start", type=float, default=0)
    ap.add_argument("--end", type=float)
    ap.add_argument("--step", type=float, default=1)
    ap.add_argument("--times", help="comma-separated timestamps instead of start/end/step")
    ap.add_argument("--crop", help="W:H:X:Y in source pixels")
    ap.add_argument("--width", type=int, default=300, help="tile width")
    ap.add_argument("--cols", type=int, default=0, help="columns (default: about square)")
    ap.add_argument("--grid", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    if a.times:
        times = [float(x) for x in a.times.split(",")]
    else:
        end = a.end if a.end is not None else duration(a.video) - .05
        n = int((end - a.start) / a.step + 1e-6) + 1
        times = [round(a.start + i * a.step, 3) for i in range(n)]

    vf = (f"crop={a.crop}," if a.crop else "") + f"scale={a.width}:-2"
    tiles = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, t in enumerate(times):
            p = os.path.join(tmp, f"{i:04d}.png")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", a.video, "-frames:v", "1", "-vf", vf, p], check=True)
            if os.path.exists(p):
                tiles.append((t, Image.open(p).convert("RGB")))
        w, h = tiles[0][1].size
        cols = a.cols or max(1, round(len(tiles) ** .5 * 1.3))
        rows = (len(tiles) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * (w + 3), rows * (h + 3)), "white")
        big, small = font(max(14, w // 12)), font(max(10, w // 36))
        for i, (t, im) in enumerate(tiles):
            d = ImageDraw.Draw(im)
            if a.grid:
                for k in range(1, 10):
                    d.line([(w * k / 10, 0), (w * k / 10, h)], fill=(255, 0, 0))
                    d.line([(0, h * k / 10), (w, h * k / 10)], fill=(255, 0, 0))
                    d.text((w * k / 10 + 2, 2), str(k), fill=(255, 0, 0), font=small)
                    d.text((2, h * k / 10 + 1), str(k), fill=(255, 0, 0), font=small)
            d.text((6, 4) if not a.grid else (w - w // 4, h - w // 9), f"{t:g}", fill=(230, 0, 0) if not a.grid else (0, 0, 255), font=big)
            sheet.paste(im, ((i % cols) * (w + 3), (i // cols) * (h + 3)))
        sheet.save(a.out, quality=85)
    print(f"{a.out}: {len(tiles)} frames, {cols}x{rows}, tile {w}x{h}")


if __name__ == "__main__":
    main()
