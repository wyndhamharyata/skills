#!/usr/bin/env python3
"""Build page/demo.config.js from the project's files, so nobody writes the config by hand.

  make_config.py demo/

Reads, inside the project folder:
  clips.json               crops and segments (cut_clips.py). A clip used as an overlay has an "overlay" key:
                           {"chapter": "01-open", "at": [.44, .47], "width": 900, "outAt": 2.75, "origin": "0 71%", "push": [.2, 1.9, .1]}
                           (chapter, at and width are needed; the rest are optional; its aspect comes from its crop).
  work/page.json           written by the main agent:
                           {"brand": {"name": …, "tag": …, "accent": "#22A863"}, "style": "paper", "tempo": "steady",
                            "frame": {"type": "mac", "title": …}, "intro": {"title": …, "sub": …, "cutouts": [], "cutoutWidth": 240},
                            "outro": {"title": …, "sub": …}, "chapters": ["01-open", "02-read", …], "music": {…}, "stage": {…}}
  work/chapters/<clip>.json   one per chapter, from the chapter brief:
                           {"label": …, "title": …, "body": …, "steps": […], "chips": […],
                            "claims": [["356 pages · 847 KB", 4.0], …]}
                           "auto_cams" is written by render.mjs --auto-cams --write; a "cams" set by hand wins.
Missing steps default to: hold 0.4 s, play the whole clip, hold 0.8 s. Every chapter gets a cams entry, even an
empty one, so render.mjs --auto-cams --write can fill it in. The old config is kept as demo.config.js.bak.
Also writes work/claims.md (one line per claim, the format check_claims.py reads).
"""
import hashlib, json, os, re, shutil, sys


def js(value):
    return json.dumps(value, ensure_ascii=False, separators=(", ", ": "))


def fingerprint(body):
    return hashlib.sha1(body.encode()).hexdigest()[:12]


def hand_edited(path):
    # True when demo.config.js no longer matches the fingerprint make_config.py wrote into it.
    text = open(path).read()
    m = re.search(r"fingerprint (\w+)\)", text.split("\n", 1)[0])
    return bool(m) and fingerprint(text.split("\n", 2)[2]) != m[1]


def normalise(name, ch, dur):
    """Make the chapter's timeline valid: steps in order and joined end to end inside the clip, and every chip,
    claim and cam time on it. Helpers' small slips (a chip before the first play, a hold 0.003 s past the end)
    used to stop the page from loading."""
    notes, end = [], round(dur - .02, 2)
    steps, pos = [], None
    for st in ch.get("steps") or [["hold", 0, .4], ["play", 0, end], ["hold", end, .8]]:
        if st[0] == "hold":
            c = round(min(max(st[1], 0), end), 2)
            if pos is not None and c > pos + .01:
                steps.append(["play", pos, c])
                notes.append(f"{name}: added play {pos}-{c} to reach the hold at {c}")
            elif pos is not None and abs(c - pos) > .01:
                notes.append(f"{name}: hold at {st[1]} moved to {pos} (the clip had already passed it)")
                c = pos
            steps.append(["hold", c, st[2]])
            pos = c
        else:
            a, b, rate = max(st[1], 0), min(st[2], end), (st[3] if len(st) > 3 else 1)
            if pos is not None and abs(a - pos) > .01:
                notes.append(f"{name}: play {st[1]}-{st[2]} now starts at {pos}, where the previous step ended")
                a = pos
            if b - a < .05:
                continue
            steps.append(["play", round(a, 2), round(b, 2)] + ([rate] if rate != 1 else []))
            pos = round(b, 2)
    start = steps[0][1]
    plays = any(st[0] == "play" for st in steps)
    holds = [st[1] for st in steps if st[0] == "hold"]

    def fix(t, what):
        v = min(max(t, start), pos - .01) if plays else min(holds, key=lambda h: abs(h - t))
        v = round(v, 2)
        if abs(v - t) > .005:
            notes.append(f"{name}: {what} at {t} moved to {v} (outside the timeline {start}-{pos})")
        return v
    chips = [[fix(k[0], f'chip "{k[2]}"'), *k[1:3]] + ([min(k[3], pos)] if len(k) > 3 else []) for k in ch.get("chips", [])]
    claims = [[text, fix(t, f'claim "{text}"')] for text, t in ch.get("claims", [])]
    cams = [[fix(k[0], "cam"), *k[1:]] for k in (ch.get("cams") or ch.get("auto_cams") or [])]
    return steps, chips, claims, cams, notes


def clip_seconds(clip):
    return round(sum((b - a) / r for a, b, r in clip["segments"]), 3)


def probe_seconds(path):
    import subprocess
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                                capture_output=True, text=True).stdout.strip() or 0)


def aspect(cfg, clip):
    w, h = (int(x) for x in clip.get("crop", cfg.get("crop")).split(":")[:2])
    return f"{w} / {h}"


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    root = os.path.abspath(sys.argv[1])
    cfg = json.load(open(os.path.join(root, "clips.json")))
    page = json.load(open(os.path.join(root, "work", "page.json")))
    out_dir = os.path.join(root, cfg.get("out", "page"))
    rel = os.path.relpath(out_dir, root)
    clips, problems, claims, chapters = cfg["clips"], [], [], []

    for i, name in enumerate(page["chapters"]):
        clip = clips.get(name)
        if not clip:
            problems.append(f"{name}: not in clips.json")
            continue
        path = os.path.join(root, "work", "chapters", name + ".json")
        ch = json.load(open(path)) if os.path.exists(path) else {}
        if not ch:
            problems.append(f"{name}: no work/chapters/{name}.json, so its caption is a placeholder")
        mp4 = os.path.join(out_dir, name + ".mp4")
        dur = probe_seconds(mp4) if os.path.exists(mp4) else clip_seconds(clip)
        steps, chips, claims_, cams, fixed = normalise(name, ch, dur)
        problems += fixed
        fields = [f"label: {js(ch.get('label', name))}", f"title: {js(ch.get('title', 'TODO title'))}", f"clip: {js(name + '.mp4')}",
                  f"body: {js(ch.get('body', 'TODO body'))}", f"steps: {js(steps)}",
                  f"cams: {js(cams)}",
                  f"chips: {js(chips)}"]
        chapters.append("    {" + ",\n      ".join(fields) + "},")
        for text, t in claims_:
            claims.append(f'- "{text}" -> {rel}/{name}.mp4 at {t}')

    overlays = []
    for name, clip in clips.items():
        o = clip.get("overlay")
        if not o:
            continue
        if o["chapter"] not in page["chapters"]:
            problems.append(f"{name}: overlay chapter {o['chapter']} is not a chapter")
            continue
        main_clip = clips[o["chapter"]]
        if abs(main_clip["segments"][0][0] - clip["segments"][0][0]) > .05:
            problems.append(f"{name}: starts at source {clip['segments'][0][0]} s, its chapter at {main_clip['segments'][0][0]} s; they must match")
        entry = {"clip": name + ".mp4", "chapter": page["chapters"].index(o["chapter"]), "at": o["at"], "width": o["width"]}
        entry.update({k: o[k] for k in ("origin", "push", "outAt", "radius") if k in o})
        overlays.append("    " + js(entry)[:-1] + f", aspect: {aspect(cfg, clip)}}},")

    first = clips[page["chapters"][0]]
    frame = {"type": "mac", **page.get("frame", {})}
    lines = ["window.DEMO = {",
             f"  brand: {js(page['brand'])},",
             f"  style: {js(page.get('style', 'midnight'))},",
             f"  tempo: {js(page.get('tempo', 'steady'))},",
             f"  stage: {js(page.get('stage', {'w': 1920, 'h': 1248}))},",
             f"  frame: {{type: {js(frame['type'])}, aspect: {aspect(cfg, first)}" + (f", title: {js(frame['title'])}" if frame.get("title") else "") + "},",
             f"  intro: {js(page['intro'])},",
             "  chapters: [", *chapters, "  ],",
             "  overlays: [", *overlays, "  ],",
             f"  outro: {js(page['outro'])},"]
    for key in ("music", "stamp", "duration"):
        if key in page:
            lines.append(f"  {key}: {js(page[key])},")
    lines.append("};\n")

    target = os.path.join(out_dir, "demo.config.js")
    if os.path.exists(target):
        shutil.copy(target, target + ".bak")
    body = "\n".join(lines)
    with open(target, "w") as f:
        f.write(f"// Generated by make_config.py from clips.json and work/ (fingerprint {fingerprint(body)}). Don't edit it:\n"
                f"// change work/chapters/<clip>.json or work/page.json and run demo.py build.\n" + body)
    os.makedirs(os.path.join(root, "work"), exist_ok=True)
    with open(os.path.join(root, "work", "claims.md"), "w") as f:
        f.write("\n".join(claims) + "\n")
    print(f"{target}: {len(chapters)} chapters, {len(overlays)} overlays, {len(claims)} claims -> work/claims.md")
    for p in problems:
        print("  check:", p)


if __name__ == "__main__":
    main()
