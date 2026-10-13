#!/usr/bin/env python3
"""Cut a UI element out of a recording frame as a PNG with its background removed.

  cutout.py rec.mov 2.0 --box 35,375,318,482 --radius 22 --out page/covers/a.png
  cutout.py rec.mov 2.0 --box 20,360,360,520 --trim --radius 22 --out page/covers/a.png
  cutout.py rec.mov --auto --crop 1784:2182:1804:144 --times 1,2.5 --count 6 --out-dir work/cutouts

--box is X,Y,W,H in source pixels. The result keeps only the box, with rounded transparent
corners (--radius 0 for square). --trim first shrinks the box to its content by removing the
surrounding flat background colour (sampled at the box corner), which is handy when you only
know roughly where the element is. Check the result on a dark background; light pages often
leave a 1–2 px halo, which --inset removes.

--auto finds repeated items itself (book covers, cards, thumbnails: things of the same size laid
out in a row or grid, on a flat background) inside the --crop area (W:H:X:Y, ffmpeg order) at each
of --times, picks --count distinct-looking, fully visible ones and writes cut-01.png … plus
cutouts.json (files, suggested intro.cutoutWidth, source time and box) and cutouts-sheet.jpg (all
cut-outs on dark grey) to --out-dir. If an item's own corners are rounder than --radius, its
radius is used. Exits 1 if it finds nothing suitable.
Needs ffmpeg, ImageMagick (magick) and, for --auto, Pillow.
"""
import argparse, json, os, re, subprocess, sys, tempfile


def grab(video, t, frame):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", video, "-frames:v", "1", frame], check=True)


def cut(frame, x, y, w, h, radius, out):
    subprocess.run(["magick", frame, "-crop", f"{w}x{h}+{x}+{y}", "+repage",
                    "(", "-size", f"{w}x{h}", "xc:none", "-fill", "white",
                    "-draw", f"roundrectangle 0,0,{w - 1},{h - 1},{radius},{radius}", ")",
                    "-alpha", "set", "-compose", "CopyOpacity", "-composite", out], check=True)


def backgrounds(img, share):
    """Flat colours that cover at least `share` of the image, most common first."""
    small = img.resize((max(1, img.width // 4), max(1, img.height // 4)))
    q = small.point(lambda v: v // 16 * 16 + 8)
    cols = sorted(q.getcolors(1 << 16) or [], reverse=True)
    n = small.width * small.height
    return [c for k, c in cols if k >= share * n][:4]


def components(img, bgs, tmp):
    """Bounding boxes (x, y, w, h) of connected regions that are not any of the bgs colours.
    Smooth pixels (shadows, gradients, flat fills) also count as background, so an item's outline
    and texture hold it together while a window shadow next to it does not join it to the edge."""
    from PIL import Image, ImageChops
    chmax = lambda im: (lambda c: ImageChops.lighter(ImageChops.lighter(c[0], c[1]), c[2]))(im.split())
    mask = None
    for c in bgs:
        d = chmax(ImageChops.difference(img, Image.new("RGB", img.size, c)))
        mask = d if mask is None else ImageChops.darker(mask, d)
    steps = None
    for dx, dy in ((2, 0), (-2, 0), (0, 2), (0, -2)):
        d = chmax(ImageChops.difference(img, ImageChops.offset(img, dx, dy)))
        steps = d if steps is None else ImageChops.lighter(steps, d)
    fg = ImageChops.multiply(mask.point(lambda v: 255 if v > 14 else 0), steps.point(lambda v: 255 if v > 4 else 0))
    # label at half size (much faster), then fit each box to the full-size mask
    path = os.path.join(tmp, "mask.png")
    fg.resize((max(1, img.width // 2), max(1, img.height // 2)), Image.BOX).point(lambda v: 255 if v else 0).save(path)
    out = subprocess.run(["magick", path, "-define", "connected-components:verbose=true",
                          "-define", f"connected-components:area-threshold={img.width * img.height // 4000}",
                          "-connected-components", "8", "null:"], capture_output=True, text=True, check=True).stdout
    boxes = []
    for m in re.finditer(r"^\s*\d+: (\d+)x(\d+)\+(\d+)\+(\d+) \S+ \S+ (\S+)", out, re.M):
        if m.group(5) in ("gray(255)", "white", "srgb(255,255,255)"):
            w, h, x, y = (2 * int(v) for v in m.groups()[:4])
            x0, y0 = max(0, x - 2), max(0, y - 2)
            bb = fg.crop((x0, y0, min(img.width, x + w + 2), min(img.height, y + h + 2))).getbbox()
            if bb:
                boxes.append((x0 + bb[0], y0 + bb[1], bb[2] - bb[0], bb[3] - bb[1]))
    return boxes


def stats(img, box):
    """(grey stddev, 6×6 RGB thumbnail bytes) of a box."""
    from PIL import ImageStat
    x, y, w, h = box
    part = img.crop((x, y, x + w, y + h))
    return ImageStat.Stat(part.convert("L")).stddev[0], part.resize((6, 6)).tobytes()


def tighten(img, box, most=8):
    """Shrink each side while its edge line still looks like what lies just outside the box."""
    x0, y0, w, h = box
    x1, y1 = x0 + w - 1, y0 + h - 1
    px = img.load()
    W, H = img.size
    same = lambda p, q: max(abs(a - b) for a, b in zip(p, q)) <= 14
    for _ in range(most):
        moved = False
        if x0 > 3 and sum(same(px[x0, y], px[x0 - 3, y]) for y in range(y0, y1 + 1)) > .6 * (y1 - y0 + 1):
            x0, moved = x0 + 1, True
        if x1 < W - 4 and sum(same(px[x1, y], px[x1 + 3, y]) for y in range(y0, y1 + 1)) > .6 * (y1 - y0 + 1):
            x1, moved = x1 - 1, True
        if y0 > 3 and sum(same(px[x, y0], px[x, y0 - 3]) for x in range(x0, x1 + 1)) > .6 * (x1 - x0 + 1):
            y0, moved = y0 + 1, True
        if y1 < H - 4 and sum(same(px[x, y1], px[x, y1 + 3]) for x in range(x0, x1 + 1)) > .6 * (x1 - x0 + 1):
            y1, moved = y1 - 1, True
        if not moved:
            break
    return x0, y0, x1 - x0 + 1, y1 - y0 + 1


def corner_radius(img, box):
    """Rough corner radius of an item: run of outside colour along the corner diagonals."""
    x, y, w, h = box
    px = img.load()
    runs = []
    for cx, cy, sx, sy in ((x, y, 1, 1), (x + w - 1, y, -1, 1), (x, y + h - 1, 1, -1), (x + w - 1, y + h - 1, -1, -1)):
        bg = px[min(img.width - 1, max(0, cx - 2 * sx)), min(img.height - 1, max(0, cy - 2 * sy))]
        k = 0
        while k < min(w, h) // 4 and max(abs(a - b) for a, b in zip(px[cx + sx * k, cy + sy * k], bg)) <= 14:
            k += 1
        runs.append(k)
    return round(sorted(runs)[1] / .293)


def regions(img, tmp, depth=2):
    """Candidate boxes; panels bigger than an item that are mostly one other flat colour are
    searched again against that colour (a highlighted group, a card list on a sidebar)."""
    W, H = img.size
    bgs = backgrounds(img, .06 if depth > 1 else .12)
    subsets = [bgs] + [[c] for c in bgs] if depth > 1 and len(bgs) > 1 else [bgs] if bgs else []
    boxes, seen = [], set()
    for subset in subsets:
        for b in components(img, subset, tmp):
            boxes.append(b)
            x, y, w, h = b
            if depth > 1 and b not in seen and .02 * W * H < w * h < .9 * W * H and min(w, h) > 40:
                seen.add(b)
                sub = regions(img.crop((x, y, x + w, y + h)), tmp, depth - 1)
                boxes += [(sx + x, sy + y, sw, sh) for sx, sy, sw, sh in sub if sw < w - 4 or sh < h - 4]
    return boxes


def find_items(img, tmp):
    """Largest group of same-size, aligned, fully visible items: [(box, stddev, thumb)]."""
    W, H = img.size
    boxes = regions(img, tmp)
    cands = []
    for b in boxes:
        x, y, w, h = b
        if not h or not (.5 <= w / h <= 2 and .004 <= w * h / (W * H) <= .08):
            continue
        if x <= 2 or y <= 2 or x + w >= W - 2 or y + h >= H - 2:
            continue
        if not any(max(abs(p - q) for p, q in zip(b, c)) <= 3 for c in cands):
            cands.append(b)
    best, key, st = [], None, {c: stats(img, c) for c in cands}
    for seed in cands:
        group = [c for c in cands if abs(c[2] - seed[2]) <= .08 * seed[2] and abs(c[3] - seed[3]) <= .08 * seed[3]]
        tol = .04 * seed[3]
        group = [c for c in group if any(d != c and (abs(d[1] - c[1]) <= tol or abs(d[0] - c[0]) <= tol) for d in group)]
        kept = []  # of overlapping variants (same item found twice) keep the one closest to the seed size
        for c in sorted(group, key=lambda c: abs(c[2] - seed[2]) + abs(c[3] - seed[3])):
            if not any(d[0] < c[0] + c[2] and c[0] < d[0] + d[2] and d[1] < c[1] + c[3] and c[1] < d[1] + d[3] for d in kept):
                kept.append(c)
        group = kept
        if len(group) < 3:
            continue
        info = [(c,) + st[c] for c in group]
        full = [i for i in info if i[1] >= 18]
        k = (len(full), sum(i[1] for i in info) / len(info))
        if key is None or k > key:
            best, key = info, k
    return best


def pick(items, count):
    """Greedy farthest-first on thumbnails, starting from the busiest item; skips near-duplicates."""
    dist = lambda a, b: sum(abs(p - q) for p, q in zip(a, b)) / len(a)
    rest = sorted(items, key=lambda i: -i["sd"])
    chosen = [rest.pop(0)]
    while rest and len(chosen) < count:
        far = max(rest, key=lambda i: min(dist(i["thumb"], c["thumb"]) for c in chosen))
        rest.remove(far)
        if min(dist(far["thumb"], c["thumb"]) for c in chosen) >= 6:
            chosen.append(far)
    return sorted(chosen, key=lambda i: (i["t"], i["box"][1] // max(1, i["box"][3] // 2), i["box"][0]))


def sheet(paths, out):
    from PIL import Image, ImageDraw, ImageFont
    th, pad, lab = 360, 30, 40
    ims = [Image.open(p).convert("RGBA") for p in paths]
    ims = [im.resize((max(1, round(im.width * th / im.height)), th), Image.LANCZOS) for im in ims]
    canvas = Image.new("RGB", (pad + sum(im.width + pad for im in ims), pad + th + lab + pad), "#222222")
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.load_default(size=26)
    except TypeError:
        font = ImageFont.load_default()
    x = pad
    for p, im in zip(paths, ims):
        canvas.paste(im, (x, pad), im)
        draw.text((x, pad + th + 8), os.path.basename(p), fill="#dddddd", font=font)
        x += im.width + pad
    canvas.save(out, quality=90)


def auto(a):
    from PIL import Image
    if not a.times:
        sys.exit("--auto needs --times")
    times = [float(v) for v in a.times.split(",")]
    cw = ch = cx = cy = None
    if a.crop:
        cw, ch, cx, cy = (int(v) for v in a.crop.split(":"))
    os.makedirs(a.out_dir, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        found, frames, lines = [], {}, []
        for t in times:
            frame = os.path.join(tmp, f"f{len(frames)}.ppm")
            grab(a.video, t, frame)
            img = Image.open(frame).convert("RGB")
            ox, oy = 0, 0
            if a.crop:
                img, ox, oy = img.crop((cx, cy, cx + cw, cy + ch)), cx, cy
            items = find_items(img, tmp)
            frames[t] = frame
            boxes = [tighten(img, i[0]) for i in items]
            if items:
                w, h = sorted(b[2] for b in boxes)[len(boxes) // 2], sorted(b[3] for b in boxes)[len(boxes) // 2]
                lines.append(f"t={t:g}: {len(items)} items ~{w}x{h}")
            else:
                lines.append(f"t={t:g}: none")
            for box, (_, sd, thumb) in zip(boxes, items):
                found.append({"t": t, "box": box, "off": (ox, oy), "sd": sd, "thumb": thumb,
                              "radius": corner_radius(img, box)})
        if not found:
            print("; ".join(lines))
            print("no repeated items found; pass --box for each cut-out instead")
            sys.exit(1)
        # keep the size of the biggest group, so the row is uniform
        ref = max(found, key=lambda i: sum(j["t"] == i["t"] for j in found))["box"]
        found = [i for i in found if abs(i["box"][2] - ref[2]) <= .08 * ref[2] and abs(i["box"][3] - ref[3]) <= .08 * ref[3]]
        picks = pick(found, a.count)
        files, source = [], []
        for n, i in enumerate(picks, 1):
            x, y, w, h = i["box"]
            x, y = x + i["off"][0] + a.inset, y + i["off"][1] + a.inset
            w, h = w - 2 * a.inset, h - 2 * a.inset
            r = max(a.radius, i["radius"] - a.inset) if a.radius else 0
            name = f"cut-{n:02d}.png"
            cut(frames[i["t"]], x, y, w, h, r, os.path.join(a.out_dir, name))
            files.append(name)
            source.append({"t": i["t"], "box": [x, y, w, h]})
    width = round(1920 * .65 / len(files) / .88)
    with open(os.path.join(a.out_dir, "cutouts.json"), "w") as f:
        json.dump({"files": files, "width": width, "source": source}, f, indent=2)
    sheet_path = os.path.join(a.out_dir, "cutouts-sheet.jpg")
    sheet([os.path.join(a.out_dir, n) for n in files], sheet_path)
    print("; ".join(lines))
    print("picked: " + ", ".join(f"t={s['t']:g} {','.join(map(str, s['box']))}" for s in source))
    print(f"wrote {len(files)} cut-outs + cutouts.json (width {width}) to {a.out_dir}")
    print(f"check: {sheet_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("time", type=float, nargs="?")
    ap.add_argument("--box")
    ap.add_argument("--radius", type=int, default=20)
    ap.add_argument("--trim", action="store_true")
    ap.add_argument("--fuzz", default="6%")
    ap.add_argument("--inset", type=int, default=2)
    ap.add_argument("--out")
    ap.add_argument("--auto", action="store_true", help="find repeated items (covers, cards) by themselves")
    ap.add_argument("--crop", help="--auto: app area W:H:X:Y (ffmpeg order)")
    ap.add_argument("--times", help="--auto: comma-separated source seconds")
    ap.add_argument("--count", type=int, default=6)
    ap.add_argument("--out-dir", default="cutouts")
    a = ap.parse_args()
    if a.auto:
        if a.times is None and a.time is not None:
            a.times = str(a.time)
        return auto(a)
    if a.time is None or not a.box or not a.out:
        ap.error("time, --box and --out are required (or use --auto)")

    x, y, w, h = (int(v) for v in a.box.split(","))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        frame = os.path.join(tmp, "f.png")
        grab(a.video, a.time, frame)
        if a.trim:
            geo = subprocess.run(["magick", frame, "-crop", f"{w}x{h}+{x}+{y}", "+repage", "-fuzz", a.fuzz,
                                  "-format", "%@", "info:"], capture_output=True, text=True, check=True).stdout.strip()
            size, ox, oy = geo.replace("+", " ").split()
            w, h = (int(v) for v in size.split("x"))
            x, y = x + int(ox), y + int(oy)
        x, y, w, h = x + a.inset, y + a.inset, w - 2 * a.inset, h - 2 * a.inset
        cut(frame, x, y, w, h, a.radius, a.out)
    print(f"{a.out}  box {x},{y},{w},{h}")


if __name__ == "__main__":
    main()
