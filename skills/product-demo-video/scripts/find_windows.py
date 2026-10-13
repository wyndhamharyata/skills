#!/usr/bin/env python3
"""Find the app windows in a macOS screen recording and print ready-to-use crops.

  find_windows.py rec.mov                       # 8 frames spread over the recording
  find_windows.py rec.mov --times 2,30,60       # only these timestamps
  find_windows.py rec.mov --min-area 0.1        # ignore windows under 10% of the screen

Crops use ffmpeg order W:H:X:Y in source pixels, ready for activity.py / contact_sheet.py --crop.
For each window it lists the whole window and the content area below the title bar / toolbar
(inside any frame or sidebar strip), says in how many sampled frames the window was in the same
place, and warns when something (Dock, another window, a popup) covers one of its edges.
Needs ffmpeg and Pillow.
"""
import argparse, statistics, subprocess
from PIL import Image, ImageChops, ImageFilter

SMALL = 1200  # detection width


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height:format=duration", "-of", "default=nw=1", path],
                         capture_output=True, text=True, check=True).stdout
    kv = dict(l.split("=", 1) for l in out.split() if "=" in l)
    return int(kv["width"]), int(kv["height"]), float(kv["duration"])


def grab(path, t, W, H):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", path, "-frames:v", "1",
                          "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout
    return Image.frombytes("L", (W, H), raw[:W * H]) if len(raw) >= W * H else None


def grad(im, vertical_lines, t):
    """Binary map of strong steps between neighbouring pixels (columns for vertical lines)."""
    d = ImageChops.difference(im, ImageChops.offset(im, 1, 0) if vertical_lines else ImageChops.offset(im, 0, 1))
    return d.point(lambda v: 255 if v >= t else 0)


def profile(im, along_x):
    """Mean of each column (along_x) or row, 0-255."""
    w, h = im.size
    return list(im.resize((w, 1) if along_x else (1, h), Image.BOX).tobytes())


def lines(edge, vertical, minlen):
    """Long straight edge runs: (pos, start, end) in small-image pixels."""
    w, h = edge.size
    n, length = (w, h) if vertical else (h, w)
    counts = profile(edge, vertical)
    data = edge.filter(ImageFilter.MaxFilter(3)).tobytes()
    out = []
    for p in range(1, n):
        c = counts[p]
        if c * length / 255 < minlen or c < max(counts[max(1, p - 1):p + 2]):
            continue
        run0, gap, last = None, 0, None
        for q in range(length + 3):
            on = q < length and data[q * w + p if vertical else p * w + q]
            if on:
                run0 = q if run0 is None else run0
                last, gap = q, 0
            elif run0 is not None:
                gap += 1
                if gap > 2:
                    if last - run0 >= minlen:
                        out.append((p, run0, last))
                    run0, gap = None, 0
    return out


def rects_in(full, small, min_area):
    w, h = small.size
    size = 2 * int(full.size[0] / w / 2) + 1  # max-pool full-res edges so 1 px borders survive
    ex, ey = [grad(full, v, 12).filter(ImageFilter.MaxFilter(size)).resize((w, h), Image.NEAREST) for v in (True, False)]
    V = lines(ex, True, int(.25 * h))
    Hl = [l for l in lines(ey, False, int(.2 * w)) if not (l[0] < .035 * h and l[1] < .01 * w and l[2] > .99 * w)]  # menu bar
    dx, dy = ex.filter(ImageFilter.MaxFilter(3)).tobytes(), ey.filter(ImageFilter.MaxFilter(3)).tobytes()
    sums = {}

    def cover(vertical, pos, a, b):  # fraction of edge pixels along a line, via cached prefix sums
        if (vertical, pos) not in sums:
            acc, s = [0], 0
            for q in range(h if vertical else w):
                s += (dx[q * w + pos] if vertical else dy[pos * w + q]) > 0
                acc.append(s)
            sums[vertical, pos] = acc
        acc = sums[vertical, pos]
        a, b = max(0, a), min(len(acc) - 1, b)
        return (acc[b] - acc[a]) / (b - a) if b > a else 0

    found = []
    for i, l in enumerate(V):
        for r in V[i + 1:]:
            if r[0] - l[0] < .1 * w:
                continue
            hs = [t for t in Hl if t[1] <= l[0] + 3 and t[2] >= r[0] - 3 or cover(False, t[0], l[0], r[0]) >= .8]
            for j, t in enumerate(hs):
                for b in hs[j + 1:]:
                    top, bot = min(t[0], b[0]), max(t[0], b[0])
                    if (r[0] - l[0]) * (bot - top) < min_area * w * h:
                        continue
                    if min(cover(True, l[0], top, bot), cover(True, r[0], top, bot),
                           cover(False, top, l[0], r[0]), cover(False, bot, l[0], r[0])) >= .8:
                        found.append((l[0], top, r[0], bot))
    found = sorted(set(found), key=lambda r: -(r[2] - r[0]) * (r[3] - r[1]))
    inside = lambda a, b: a[0] >= b[0] - 2 and a[1] >= b[1] - 2 and a[2] <= b[2] + 2 and a[3] <= b[3] + 2
    area = lambda r: (r[2] - r[0]) * (r[3] - r[1])

    def composite(R):  # two windows side by side (or stacked) with wallpaper between them
        kids = [k for k in found if k != R and inside(k, R) and sum(abs(p - q) <= 3 for p, q in zip(k, R)) == 3]
        for i, a in enumerate(kids):
            for b in kids[i + 1:]:
                if area(a) + area(b) < .8 * area(R):
                    continue
                for lo, hi, vert in ((a, b, True), (b, a, True), (a, b, False), (b, a, False)):
                    g0, g1 = (lo[2], hi[0]) if vert else (lo[3], hi[1])
                    if g1 - g0 >= 2:
                        if vert:
                            br = min(cover(False, R[1], g0 + 1, g1), cover(False, R[3], g0 + 1, g1))
                        else:
                            br = min(cover(True, R[0], g0 + 1, g1), cover(True, R[2], g0 + 1, g1))
                        if br < .5:
                            return True
        return False

    px = small.load()
    score = {}

    def odd_side(R):  # how much the strip just inside one side differs from the other sides (wallpaper gap?)
        if R not in score:
            x0, y0, x1, y1 = R
            ys, xs = range(y0 + (y1 - y0) // 10, y1 - (y1 - y0) // 10), range(x0 + (x1 - x0) // 10, x1 - (x1 - x0) // 10)
            means = [sum(px[x, y] for x in (x0 + 1, x0 + 2) for y in ys) / 2 / len(ys),
                     sum(px[x, y] for x in (x1 - 2, x1 - 3) for y in ys) / 2 / len(ys),
                     sum(px[x, y] for y in (y0 + 1, y0 + 2) for x in xs) / 2 / len(xs),
                     sum(px[x, y] for y in (y1 - 2, y1 - 3) for x in xs) / 2 / len(xs)]
            mid = statistics.median(means)
            score[R] = max(abs(m - mid) for m in means)
        return score[R]

    keep, groups, done = [], [], set()
    for R in found:
        if R in done or any(inside(R, k) for k in keep) or composite(R):
            continue
        # of near-identical rects keep the one whose four sides look alike inside, then the larger one
        group = [k for k in found if max(abs(p - q) for p, q in zip(k, R)) <= 6]
        done.update(group)
        best = min(group, key=lambda k: (round(odd_side(k) / 10), -area(k)))
        if not any(inside(best, k) for k in keep):
            keep.append(best)
            groups.append(group)

    def sliver(a, b):  # overlap of two rects that only touch along an edge (two windows side by side)
        ox, oy = min(a[2], b[2]) - max(a[0], b[0]) + 1, min(a[3], b[3]) - max(a[1], b[1]) + 1
        return min(ox, oy) if ox > 0 and oy > 0 and min(ox, oy) <= 6 else 0

    for i in range(len(keep)):
        for j in range(len(keep)):
            if i != j and sliver(keep[i], keep[j]):
                keep[i] = min(groups[i], key=lambda k: (sliver(k, keep[j]), round(odd_side(k) / 10), -area(k)))
    return keep


def refine(full, r, k):
    """Move each edge of a small-image rect to the exact first/last window pixel in source pixels."""
    W, H = full.size
    x0, y0, x1, y1 = [round(v * k) for v in r]
    rad = int(k) + 4
    ya, yb = y0 + (y1 - y0) // 10, y1 - (y1 - y0) // 10
    xa, xb = x0 + (x1 - x0) // 10, x1 - (x1 - x0) // 10

    def best(at, inward, vertical):
        """Strong step nearest to `at`; returns the first pixel inside the window."""
        lo, hi = max(1, at - rad), min((W if vertical else H) - 1, at + rad)
        p = line_profile([full], (lo - 1, ya, hi + 1, yb) if vertical else (xa, lo - 1, xb, hi + 1), vertical, 12)[1:]
        peaks = [lo + i for i in range(len(p)) if p[i] >= .5 and p[i] == max(p[max(0, i - 2):i + 3])]
        s = min(peaks, key=lambda s: (abs(s - at), -p[s - lo])) if peaks else at
        return s if inward > 0 else s - 1

    return best(x0, 1, True), best(y0, 1, False), best(x1, -1, True), best(y1, -1, False)


def line_profile(frames, box, vertical, t=4):
    """Median (over frames) fraction of rows/columns in box with a step at each position."""
    profs = []
    for f in frames:
        s = f.crop(box)
        e = ImageChops.difference(s, ImageChops.offset(s, 1, 0) if vertical else ImageChops.offset(s, 0, 1))
        p = profile(e.point(lambda v: 255 if v >= t else 0), vertical)
        p[0] = 0
        profs.append(p)
    return [statistics.median(v) / 255 for v in zip(*profs)]


def content(frames, win):
    """Candidate content tops and the suggested inner content rect for one window."""
    x0, y0, x1, y1 = win
    w, h = x1 - x0 + 1, y1 - y0 + 1
    m = max(4, w // 30)
    rows = line_profile(frames, (x0 + m, y0, x1 - m, y0 + int(.15 * h)), False)
    tops = []
    for i, f in enumerate(rows):
        if f >= .85 and i > 2:
            if tops and i - tops[-1] <= 3:
                tops[-1] = i
            else:
                tops.append(i)
    tops = [y0 + i for i in tops]
    sug = max([t for t in tops if t - y0 <= .08 * h], default=y0)
    ya, yb = sug + int(.05 * h), y1 - int(.05 * h)
    zx = max(3, int(.03 * w))
    cols = line_profile(frames, (x0, ya, x1 + 1, yb), True)
    L = max([x0 + i for i in range(3, zx) if cols[i] >= .97], default=x0)
    R = min([x0 + i - 1 for i in range(w - zx, w - 2) if cols[i] >= .97], default=x1)
    zy = max(3, int(.015 * h))
    rows = line_profile(frames, (L + m, y1 - zy, R - m, y1 + 1), False)
    B = min([y1 - zy + i - 1 for i in range(1, zy - 2) if rows[i] >= .9], default=y1)
    return tops, (L, sug, R, B)


def still_there(frame, win):
    """True if most of the window's outline is still in place (window partly covered, not gone)."""
    x0, y0, x1, y1 = win
    ya, yb, xa, xb = y0 + (y1 - y0) // 10, y1 - (y1 - y0) // 10, x0 + (x1 - x0) // 10, x1 - (x1 - x0) // 10
    sides = [max(line_profile([frame], box, v, 12)[1:]) for box, v in
             (((x0 - 3, ya, x0 + 3, yb), True), ((x1 - 2, ya, x1 + 4, yb), True),
              ((xa, y0 - 3, xb, y0 + 3), False), ((xa, y1 - 2, xb, y1 + 4), False))]
    return sum(f >= .8 for f in sides) >= 3 and min(sides) >= .3


def mode(vals):
    """Most common value, counting neighbours within 2 px."""
    return max(sorted(vals, key=lambda v: abs(v - statistics.median(vals))),
               key=lambda v: sum(abs(v - u) <= 2 for u in vals))


def crop_str(r):
    return f"{r[2] - r[0] + 1}:{r[3] - r[1] + 1}:{r[0]}:{r[1]}"


def changed(frames, box):
    """Frames where some 1/16 of a thin strip differs a lot from the per-pixel median over all frames."""
    strips = [f.crop(box) for f in frames]
    ref = Image.frombytes("L", strips[0].size, bytes(sorted(v)[len(v) // 2] for v in zip(*(s.tobytes() for s in strips))))
    w, h = ref.size
    diffs = [max(ImageChops.difference(s, ref).resize((1, 16) if h > w else (16, 1), Image.BOX).tobytes())
             for s in strips]
    base = statistics.median(diffs)
    return [d > max(30, 3 * base + 8) for d in diffs]


def edge_check(frames, times, r, win, strip=12):
    """Edges covered at some frames by something that also covers the outside (Dock, popup, other window)."""
    x0, y0, x1, y1 = r
    W, H = frames[0].size
    wx0, wy0, wx1, wy1 = win
    inner = {"left": (x0, y0, x0 + strip, y1 + 1), "right": (x1 + 1 - strip, y0, x1 + 1, y1 + 1),
             "top": (x0, y0, x1 + 1, y0 + strip), "bottom": (x0, y1 + 1 - strip, x1 + 1, y1 + 1)}
    outer = {"left": (max(0, wx0 - strip), y0, wx0, y1 + 1), "right": (wx1 + 1, y0, min(W, wx1 + 1 + strip), y1 + 1),
             "top": (x0, max(0, wy0 - strip), x1 + 1, wy0), "bottom": (x0, wy1 + 1, x1 + 1, min(H, wy1 + 1 + strip))}
    notes, inset = [], list(r)
    for side in inner:
        bad_in = changed(frames, inner[side])
        ob = outer[side]
        bad_out = changed(frames, ob) if ob[2] - ob[0] >= 4 and ob[3] - ob[1] >= 4 else bad_in
        bad = [i for i in range(len(frames)) if bad_in[i] and bad_out[i]]
        if not bad:
            continue
        notes.append(f"{side} edge covered at {', '.join(f'{times[i]:.1f}' for i in bad)} s")
        # how far the change reaches into the window, measured on the first covered frame
        i = bad[0]
        vertical = side in ("left", "right")
        span = (x1 - x0) // 6 if vertical else (y1 - y0) // 6
        if side == "left":
            box2 = (x0, y0, x0 + span, y1 + 1)
        elif side == "right":
            box2 = (x1 + 1 - span, y0, x1 + 1, y1 + 1)
        elif side == "top":
            box2 = (x0, y0, x1 + 1, y0 + span)
        else:
            box2 = (x0, y1 + 1 - span, x1 + 1, y1 + 1)
        others = [f.crop(box2) for j, f in enumerate(frames) if j not in bad]
        if not others:
            continue
        d = profile(ImageChops.difference(frames[i].crop(box2), others[len(others) // 2]), vertical)
        order = range(len(d)) if side in ("left", "top") else range(len(d) - 1, -1, -1)
        reach, quiet = 0, 0
        for n, j in enumerate(order):
            if d[j] > 6:
                reach, quiet = n + 1, 0
            elif (quiet := quiet + 1) > 8:
                break
        reach += 8
        if side == "left":
            inset[0] = max(inset[0], x0 + reach)
        elif side == "right":
            inset[2] = min(inset[2], x1 - reach)
        elif side == "top":
            inset[1] = max(inset[1], y0 + reach)
        else:
            inset[3] = min(inset[3], y1 - reach)
    return notes, inset


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--frames", type=int, default=8)
    ap.add_argument("--times", help="comma-separated timestamps instead of --frames")
    ap.add_argument("--min-area", type=float, default=.05, help="smallest window, as a fraction of the screen")
    a = ap.parse_args()

    W, H, dur = probe(a.video)
    if a.times:
        times = [float(x) for x in a.times.split(",")]
    else:
        n = max(1, a.frames)
        times = [round(.5 + (dur - 1) * i / max(1, n - 1), 1) for i in range(n)]
    k = W / SMALL
    frames, per = [], []
    for t in times:
        f = grab(a.video, t, W, H)
        if f is None:
            continue
        small = f.resize((SMALL, round(H / k)), Image.BOX)
        frames.append((t, f))
        per.append([refine(f, r, k) for r in rects_in(f, small, a.min_area)])

    clusters = []  # [rect, {frame index}]
    for i, rs in enumerate(per):
        for r in rs:
            c = next((c for c in clusters if max(abs(p - q) for p, q in zip(c[0], r)) <= 10), None)
            if c:
                c[1][i] = r
            else:
                clusters.append([r, {i: r}])
    need = max(2, (len(frames) + 1) // 2) if len(frames) > 1 else 1
    wins = []
    for c in clusters:
        if len(c[1]) >= need:
            rect = tuple(mode([r[j] for r in c[1].values()]) for j in range(4))
            wins.append((rect, sorted(c[1])))
    wins = [(rect, sorted(set(idx) | {i for i, (t, f) in enumerate(frames) if i not in idx and still_there(f, rect)}))
            for rect, idx in wins]
    wins.sort(key=lambda w: -(w[0][2] - w[0][0]) * (w[0][3] - w[0][1]))
    if not wins:
        print(f"no stable windows found in {len(frames)} frames (try --min-area lower or --times)")
        return

    missing = {}
    for n, (win, idx) in enumerate(wins, 1):
        x0, y0, x1, y1 = win
        fr = [frames[i][1] for i in idx]
        ts = [frames[i][0] for i in idx]
        tops, inner = content(fr, win)
        print(f"window {n}: x {x0}–{x1}, y {y0}–{y1} ({x1 - x0 + 1}×{y1 - y0 + 1}), "
              f"stable in {len(idx)}/{len(frames)} frames")
        opts = [crop_str(inner) + " (below the title bar, suggested)"]
        opts += [crop_str((inner[0], t, inner[2], inner[3])) + f" (below line at y {t})"
                 for t in tops if t != inner[1]][:1]
        if inner != win:
            opts.append(crop_str(win) + " (whole window)")
        print("  content crops: " + " | ".join(opts))
        notes, inset = edge_check(fr, ts, inner, win)
        if notes:
            print(f"  edges: {'; '.join(notes)} (Dock / popup / other window?) -> use {crop_str(inset)}")
        else:
            print("  edges: clean")
        for i in range(len(frames)):
            if i not in idx:
                missing.setdefault(frames[i][0], []).append(n)
    if missing:
        print("missing windows: " + ", ".join(
            f"{t:.1f} s ({'all' if len(v) == len(wins) else 'window ' + ','.join(map(str, v))})"
            for t, v in sorted(missing.items())))


if __name__ == "__main__":
    main()
