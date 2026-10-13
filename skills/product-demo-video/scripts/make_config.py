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
                           {"label": …, "title": …, "body": …, "steps": […], "cams": […], "chips": […],
                            "claims": [["356 pages · 847 KB", 4.0], …]}
Missing steps default to: hold 0.4 s, play the whole clip, hold 0.8 s. Every chapter gets a cams entry, even an
empty one, so render.mjs --auto-cams --write can fill it in. The old config is kept as demo.config.js.bak.
Also writes work/claims.md (one line per claim, the format check_claims.py reads).
"""
import json, os, shutil, sys


def js(value):
    return json.dumps(value, ensure_ascii=False, separators=(", ", ": "))


def clip_seconds(clip):
    return round(sum((b - a) / r for a, b, r in clip["segments"]), 3)


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
        dur = clip_seconds(clip)
        steps = ch.get("steps") or [["hold", 0, .4], ["play", 0, dur], ["hold", dur, .8]]
        fields = [f"label: {js(ch.get('label', name))}", f"title: {js(ch.get('title', 'TODO title'))}", f"clip: {js(name + '.mp4')}",
                  f"body: {js(ch.get('body', 'TODO body'))}", f"steps: {js(steps)}", f"cams: {js(ch.get('cams', []))}",
                  f"chips: {js(ch.get('chips', []))}"]
        chapters.append("    {" + ",\n      ".join(fields) + "},")
        for text, t in ch.get("claims", []):
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
    lines = ["// demo.config.js, written by make_config.py from clips.json and work/. Edit those and re-run, or edit here.",
             "window.DEMO = {",
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
    with open(target, "w") as f:
        f.write("\n".join(lines))
    os.makedirs(os.path.join(root, "work"), exist_ok=True)
    with open(os.path.join(root, "work", "claims.md"), "w") as f:
        f.write("\n".join(claims) + "\n")
    print(f"{target}: {len(chapters)} chapters, {len(overlays)} overlays, {len(claims)} claims -> work/claims.md")
    for p in problems:
        print("  check:", p)


if __name__ == "__main__":
    main()
