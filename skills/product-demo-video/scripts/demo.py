#!/usr/bin/env python3
"""The one entry point for a product demo. Each command runs every scripted step up to the next decision, then
prints exactly what to do next: images to look at, a question to ask, helpers to start, or the next command.

  demo.py new "<recording>" [--name reader-hero] [--dir <parent folder>]
  demo.py plan <project>                    # checks work/plan.json and prints the plan question
  demo.py cut <project>                     # cuts the clips and writes the helpers' briefs
  demo.py build <project> [--style pop --tempo fast --music auto|choose|none]
  demo.py check <project> <chapter>         # stills helpers: rebuild, check and re-render one chapter
  demo.py sheet <project> <clip> --times 1.2,1.6   # chapter helpers: one extra sheet of their clip
  demo.py still <project> <page time>       # stills helpers: one moment of the page at full size
  demo.py finish <project> [--bed <name>] [--note "worth checking: …"]
  demo.py next [<project>]                  # where a run stands, and the command to run

State lives in <project>/work/state.json; the guard hooks read its "look" list (the images allowed right now).
Needs everything doctor.sh checks.
"""
import argparse, fcntl, glob, hashlib, json, os, re, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
ME = os.path.join(HERE, "demo.py")
ACTIVE = os.path.expanduser("~/.cache/product-demo-video/active")
STYLES = {
    "midnight": "dark, text left, app right; most launch and feature videos",
    "paper": "warm off-white, serif; reading, writing and content apps",
    "aurora": "blurred brand-colour gradient, glass; consumer launches",
    "keynote": "black, minimal; one hero feature, phone apps",
    "swiss": "solid brand colour, strict grid; B2B tools, walkthroughs",
    "pop": "recording fills an outlined panel, tilted caption card; indie / Product Hunt launches",
    "terminal": "editor panes, monospace; developer tools",
}
TEMPOS = {"calm": "slow, ×1.5 holds", "steady": "as written", "brisk": "×0.7 holds, slides", "fast": "×0.5 holds, snappy"}


# ---- small helpers ---------------------------------------------------------------------------------------------
def die(msg):
    print(msg)
    sys.exit(1)


def run(cmd, cwd=None, ok=(0,), what=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode not in ok:
        tail = "\n".join((r.stdout + r.stderr).strip().splitlines()[-12:])
        die(f"FAILED: {what or os.path.basename(cmd[1] if cmd[0] in ('python3', 'node') else cmd[0])}\n{tail}")
    return r.stdout


def py(script, *args, cwd=None, ok=(0,)):
    return run(["python3", os.path.join(HERE, script), *map(str, args)], cwd=cwd, ok=ok, what=script)


def node(project, *args, ok=(0,)):
    return run(["node", os.path.join(HERE, "render.mjs"), os.path.join(project, "page", "index.html"), *map(str, args)],
               cwd=os.path.join(project, "render"), ok=ok, what="render.mjs " + " ".join(map(str, args[:2])))


def rjson(path, default=None):
    return json.load(open(path)) if os.path.exists(path) else default


def wjson(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.write("\n")


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def W(project, *p):
    return os.path.join(project, "work", *p)


def load(project):
    st = rjson(W(project, "state.json"))
    if not st:
        die(f"{project} is not a demo project (no work/state.json). Start with: python3 {ME} new \"<recording>\"")
    return st


def save(project, st, step=None, look=None):
    if step:
        st["step"] = step
    if look is not None:
        st["look"] = [os.path.abspath(p) for p in look]
    st["updated"] = time.time()
    wjson(W(project, "state.json"), st)
    os.makedirs(ACTIVE, exist_ok=True)
    mark = os.path.join(ACTIVE, hashlib.sha1(project.encode()).hexdigest()[:12] + ".json")
    if st["step"] == "done":
        if os.path.exists(mark):
            os.remove(mark)
    else:
        wjson(mark, {"project": project, "updated": time.time()})


def nxt(*lines):
    print("\nNEXT")
    for l in lines:
        print("  " + l)


def project_arg(p):
    if p:
        return os.path.abspath(os.path.expanduser(p))
    marks = sorted(glob.glob(os.path.join(ACTIVE, "*.json")), key=os.path.getmtime)
    if not marks:
        die(f"no active demo project; start with: python3 {ME} new \"<recording>\"")
    return rjson(marks[-1])["project"]


def probe(path):
    out = json.loads(run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,r_frame_rate:format=duration", "-of", "json", path]))
    s = out["streams"][0]
    n, d = s["r_frame_rate"].split("/")
    return {"w": s["width"], "h": s["height"], "dur": round(float(out["format"]["duration"]), 2), "fps": round(int(n) / int(d))}


def crop_tuple(c):
    w, h, x, y = (int(v) for v in c.split(":"))
    return w, h, x, y


def spans_text(spans):
    return ", ".join(f"{a:.1f}–{b:.1f}" for a, b in spans) or "none"


# ---- step 1: windows and activity ------------------------------------------------------------------------------
def find_windows(rec):
    out = py("find_windows.py", rec)
    wins, cur = [], None
    for line in out.splitlines():
        m = re.match(r"window (\d+): x (\d+)\D+(\d+), y (\d+)\D+(\d+) \((\d+)\D(\d+)\)", line)
        if m:
            n, x0, x1, y0, y1, w, h = map(int, m.groups())
            cur = {"n": n, "whole": f"{w}:{h}:{x0}:{y0}", "content": f"{w}:{h}:{x0}:{y0}", "edges": "clean"}
            wins.append(cur)
        elif cur and "content crops:" in line:
            sug = re.search(r"(\d+:\d+:\d+:\d+) \([^)]*suggested", line)
            if sug:
                cur["content"] = sug[1]
        elif cur and "edges:" in line:
            cur["edges"] = line.split("edges:", 1)[1].strip()
            inset = re.search(r"use (\d+:\d+:\d+:\d+)", line)
            if inset:
                cur["content"] = inset[1]
    return wins


def activity(rec, info, regions, fps=10):
    """One decode pass: per region, the change per sample and the box around what changed; plus whole-screen jumps."""
    from PIL import Image, ImageChops, ImageStat
    sw = 480
    sh = int(round(info["h"] * sw / info["w"] / 2)) * 2
    k = sw / info["w"]
    boxes = {}
    for name, c in regions.items():
        w, h, x, y = crop_tuple(c)
        boxes[name] = (int(x * k), int(y * k), max(int(x * k) + 2, int((x + w) * k)), max(int(y * k) + 2, int((y + h) * k)))
    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-i", rec, "-vf", f"fps={fps},scale={sw}:{sh},format=gray",
                             "-f", "rawvideo", "-"], stdout=subprocess.PIPE)
    size, prev, i = sw * sh, None, 0
    series = {n: [] for n in regions}
    whole = []
    while True:
        buf = proc.stdout.read(size)
        if len(buf) < size:
            break
        frame = Image.frombytes("L", (sw, sh), buf)
        t = i / fps
        if prev is not None:
            diff = ImageChops.difference(frame, prev)
            whole.append((t, ImageStat.Stat(diff).mean[0]))
            for n, b in boxes.items():
                d = diff.crop(b)
                bb = d.point(lambda v: 255 if v > 24 else 0).getbbox()
                if bb:
                    bb = [int((b[0] + bb[0]) / k), int((b[1] + bb[1]) / k), int((b[0] + bb[2]) / k), int((b[1] + bb[3]) / k)]
                series[n].append((t, ImageStat.Stat(d).mean[0], bb))
        prev, i = frame, i + 1
    proc.wait()
    return series, whole


def merge(times, gap, step=.1):
    spans = []
    for t in times:
        if spans and t - spans[-1][1] <= gap:
            spans[-1][1] = t
        else:
            spans.append([t - step, t])
    return [(round(max(0, a), 2), round(b, 2)) for a, b in spans]


def cmd_new(a):
    rec = os.path.abspath(os.path.expanduser(a.recording))
    if not os.path.exists(rec):
        die(f"no such recording: {rec}")
    r = subprocess.run(["bash", os.path.join(HERE, "doctor.sh")], capture_output=True, text=True)
    if r.returncode:
        die("Missing tools; install them first:\n" + r.stdout.strip())
    info = probe(rec)
    name = slug(a.name) if a.name else "demo"
    project = os.path.abspath(os.path.expanduser(a.dir or os.path.join(os.path.dirname(rec), f"{name}-demo-{time.strftime('%Y-%m-%d')}")))
    if " " in os.path.basename(project):
        project = os.path.join(os.path.dirname(project), os.path.basename(project).replace(" ", "-"))
    for d in ("page", "output", "render", "work/sheets", "work/chapters", "work/briefs"):
        os.makedirs(os.path.join(project, d), exist_ok=True)

    wins = find_windows(rec)
    if not wins:
        wins = [{"n": 1, "whole": f"{info['w']}:{info['h']}:0:0", "content": f"{info['w']}:{info['h'] - int(info['h'] * .03)}:0:{int(info['h'] * .03)}", "edges": "clean"}]
    regions = {f"w{w['n']}": w["content"] for w in wins}
    series, whole = activity(rec, info, regions)
    # The whole screen jumping at once is a desktop flash or a space switch: drop it, and ignore it per window.
    # A jump is every window changing a lot at the same moment (with one window, nothing counts as one).
    per_t = {}
    for n, ser in series.items():
        for t, m, _ in ser:
            per_t.setdefault(t, []).append(m)
    jumps = merge([t for t, ms in sorted(per_t.items()) if len(series) > 1 and len(ms) == len(series) and min(ms) > 3], .5)
    in_jump = lambda t: any(a - .2 <= t <= b + .2 for a, b in jumps)
    total = {n: sum(m for t, m, _ in s if not in_jump(t)) for n, s in series.items()}
    app = max(wins, key=lambda w: total[f"w{w['n']}"])
    others = [w for w in wins if w is not app]
    act = {n: merge([t for t, m, _ in s if m > .5 and not in_jump(t)], .6) for n, s in series.items()}
    app_spans = act[f"w{app['n']}"]
    idle = []
    last = 0.0
    for s0, s1 in app_spans + [(info["dur"], info["dur"])]:
        if s0 - last >= 1.5:
            idle.append((round(last, 1), round(s0, 1)))
        last = max(last, s1)

    step = 2 if info["dur"] <= 150 else round(info["dur"] / 70, 1)
    sheets = W(project, "sheets")
    look = []
    py("contact_sheet.py", rec, "--step", step, "--width", 240, "--out", os.path.join(sheets, "overview.jpg"))
    look.append(os.path.join(sheets, "overview.jpg"))
    py("contact_sheet.py", rec, "--crop", app["content"], "--step", max(1, step / 2), "--width", 260, "--out", os.path.join(sheets, "app.jpg"))
    look.append(os.path.join(sheets, "app.jpg"))
    outside = []
    for w in others:
        for s0, s1 in act[f"w{w['n']}"]:
            if s1 - s0 < .3:
                continue
            bbs = [bb for t, m, bb in series[f"w{w['n']}"] if bb and s0 <= t <= s1]
            box = [min(b[0] for b in bbs), min(b[1] for b in bbs), max(b[2] for b in bbs), max(b[3] for b in bbs)] if bbs else None
            outside.append({"window": w["whole"], "at": [round(s0, 1), round(s1, 1)], "change_box": box})
    for o in sorted(outside, key=lambda o: o["at"][1] - o["at"][0], reverse=True)[:3]:
        s0, s1 = o["at"]
        n = min(12, max(4, int((s1 - s0 + .6) / .25)))
        times = ",".join(f"{max(0, s0 - .2 + i * (s1 - s0 + .6) / (n - 1)):.2f}" for i in range(n))
        f = os.path.join(sheets, f"outside-{s0:.1f}.jpg")
        py("contact_sheet.py", rec, "--crop", o["window"], "--times", times, "--width", 300, "--out", f)
        look.append(f)

    plan = {
        "_how": "Fill in every TODO. Times are source seconds. Keep the keys starting with _ as they are.",
        "product": a.name.replace("-", " ").title() if a.name else "TODO product name",
        "tagline": "TODO two to four words", "accent": "TODO #RRGGBB: the app's main UI colour",
        "app": app["content"],
        "_app": "The app's crop from find_windows.py; change it only if this is the wrong window.",
        "intro": {"title": "TODO Meet <product>", "sub": "TODO one line on what it does"},
        "outro": {"title": "TODO <product>", "sub": "TODO URL or call to action"},
        "chapters": [{"clip": "01-TODO", "label": "TODO", "range": [0, 0], "shows": "TODO what the viewer sees"}],
        "_chapters": "3-6 chapters in order, each one feature. clip: NN-word, label: one word, range: [start, end].",
        "outside": [{"at": o["at"], "window": o["window"], "change_box": o["change_box"], "what": "TODO what happens there",
                     "treat": "overlay", "chapter": "TODO clip it belongs to", "why": "TODO"} for o in outside],
        "_outside": "Every moment in another window, dialog or the desktop. treat: overlay (shown as an inset over its chapter;"
                    " the default when it starts or completes a feature), cut, or ignore (not part of the story).",
        "drop": [list(j) for j in jumps],
        "_drop": "Source ranges to cut everywhere: desktop flashes, popups, mistakes.",
        "facts": [],
        "_facts": "Things the user told you that captions may say (e.g. 'Reader Hero is the default PDF app').",
        "questions": [],
        "_questions": "Only facts you can't see and that change wording: [{\"q\": \"…\", \"options\": [\"…\", \"…\"]}].",
    }
    if not os.path.exists(W(project, "plan.json")):
        wjson(W(project, "plan.json"), plan)
    notes = os.path.join(project, "NOTES.md")
    if not os.path.exists(notes):
        with open(notes, "w") as f:
            f.write(f"# Demo notes\n- Recording: {rec}, {info['w']}×{info['h']}, {info['dur']} s, {info['fps']} fps\n"
                    f"- App crop: {app['content']} (edges: {app['edges']})\n"
                    + "".join(f"- Other window: {w['whole']}\n" for w in others)
                    + f"- App activity: {spans_text(app_spans)}\n- App idle: {spans_text(idle)}\n"
                    f"- Whole-screen jumps: {spans_text(jumps)}\n"
                    f"- Run state: work/state.json. Resume with: python3 {ME} next {project}\n")
    st = {"step": "new", "recording": rec, "project": project, "info": info, "app": app["content"],
          "windows": [w["whole"] for w in others], "rounds": {}, "started": time.time()}
    save(project, st, look=look)

    print(f"Project: {project}")
    print(f"Recording: {info['w']}×{info['h']}, {info['dur']} s, {info['fps']} fps")
    print(f"App: {app['content']} (the window with the most activity; edges: {app['edges']})")
    for w in others:
        print(f"Other window: {w['whole']} — activity at {spans_text(act['w%d' % w['n']])}")
    print(f"App activity: {spans_text(app_spans)}")
    print(f"App idle (dead air): {spans_text(idle)}")
    print(f"Whole screen jumps (already in plan.json drop): {spans_text(jumps)}")
    print(f"Outside-the-app moments found: {len(outside)} (pre-filled in plan.json; each needs what/treat/chapter)")
    nxt(f"1. LOOK at all of these in ONE turn: {' '.join(look)}",
        f"2. In ONE turn: fill in {W(project, 'plan.json')} (it explains each field), then run: python3 {ME} plan {project}",
        "Don't open other frames or read the skill's files: everything you need is above and in plan.json.")


# ---- step 2: the plan ------------------------------------------------------------------------------------------
def cmd_plan(a):
    project = project_arg(a.project)
    st = load(project)
    plan = rjson(W(project, "plan.json"))
    dur, problems = st["info"]["dur"], []
    text = json.dumps({k: v for k, v in plan.items() if not k.startswith("_")})
    if "TODO" in text:
        problems.append("plan.json still has TODO values: " + ", ".join(sorted(set(re.findall(r'"(\w+)": "TODO', text))))[:200])
    chs = plan.get("chapters", [])
    if not 1 <= len(chs) <= 8:
        problems.append(f"{len(chs)} chapters; use 3-6")
    clips = [c.get("clip", "") for c in chs]
    for c in chs:
        r = c.get("range", [0, 0])
        if not re.fullmatch(r"\d\d-[a-z0-9-]+", c.get("clip", "")):
            problems.append(f"clip name {c.get('clip')!r}: use NN-word, e.g. 01-open")
        if not (0 <= r[0] < r[1] <= dur + .05):
            problems.append(f"{c.get('clip')}: range {r} must be inside 0–{dur}")
    if len(set(clips)) != len(clips):
        problems.append("two chapters have the same clip name")
    if "outside" not in plan:
        problems.append('plan.json has no "outside" list; every moment in another window needs an entry')
    for o in plan.get("outside", []):
        if o.get("treat") not in ("overlay", "cut", "ignore"):
            problems.append(f"outside {o.get('at')}: treat must be overlay, cut or ignore")
        if o.get("treat") == "overlay" and o.get("chapter") not in clips:
            problems.append(f"outside {o.get('at')}: chapter {o.get('chapter')!r} is not one of {clips}")
    if problems:
        die("Fix work/plan.json, then run demo.py plan again:\n  - " + "\n  - ".join(problems))

    used = sum(c["range"][1] - c["range"][0] for c in chs)
    lines = [f"{i + 1}. {c['label']}: {c['shows']} (source {c['range'][0]}–{c['range'][1]} s)" for i, c in enumerate(chs)]
    out = [f"{o['at'][0]}–{o['at'][1]} s {o['what']}: {o['treat']}" + (f" (inset over {o['chapter']})" if o['treat'] == 'overlay' else "")
           + f" — {o.get('why', '')}" for o in plan.get("outside", [])] or ["none"]
    q = ("Here's the plan for the demo (about %d s of footage before trimming):\n" % used + "\n".join(lines)
         + "\n\nOutside the app:\n" + "\n".join(out) + (f"\nCut everywhere: {spans_text(plan.get('drop', []))}" if plan.get("drop") else ""))
    save(project, st, step="planned", look=[])
    print("Plan checked.")
    nxt("ASK with the question tool (OpenCode: question, Claude Code: AskUserQuestion), ONE call with these questions:",
        f'  header "Chapter plan", options ["Cut it as planned", "Change something"], question:\n' + "\n".join("      " + l for l in q.splitlines()),
        *[f'  header "Question", question {x["q"]!r}, options {x.get("options", [])}' for x in plan.get("questions", [])],
        f"Approved: put any answers into plan.json \"facts\", then run: python3 {ME} cut {project}",
        f"Changes: edit plan.json, run: python3 {ME} plan {project} (then ask again, once).")


# ---- step 3: cut -----------------------------------------------------------------------------------------------
def overlay_crop(o, info):
    ww, wh, wx, wy = crop_tuple(o["window"])
    b = o.get("change_box") or [wx, wy, wx + ww, wy + wh]
    w = max(b[2] - b[0] + 120, ww * .45)
    h = max(b[3] - b[1] + 120, wh * .3)
    w, h = max(w, h * 1.2), max(h, w / 2.0)
    w, h = min(w, ww), min(h, wh)
    cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    x = int(min(max(wx, cx - w / 2), wx + ww - w))
    y = int(min(max(wy, cy - h / 2), wy + wh - h))
    w, h = int(w) // 2 * 2, int(h) // 2 * 2
    return f"{w}:{h}:{x}:{y}", w / h


def clip_len(segs):
    return sum((b - a) / r for a, b, r in segs)


def cmd_cut(a):
    project = project_arg(a.project)
    st = load(project)
    if st["step"] not in ("planned", "cut"):
        die(f"The plan isn't confirmed yet (step: {st['step']}). Run: python3 {ME} next {project}")
    n = st["rounds"].get("cut", 0)
    if n >= 3:
        die("Cut three times already. Go on with these clips and mention anything off in the hand-over:\n"
            f"  python3 {ME} next {project}")
    plan, info, rec = rjson(W(project, "plan.json")), st["info"], st["recording"]
    cj_path = os.path.join(project, "clips.json")
    drops = [list(d) for d in plan.get("drop", [])] + [o["at"] for o in plan.get("outside", []) if o["treat"] == "cut"]
    cj = {"source": rec, "out": "page", "crop": plan["app"], "fps": min(60, info["fps"]), "clips": {}}
    wjson(cj_path, cj)
    overlays = {o["chapter"]: o for o in plan.get("outside", []) if o["treat"] == "overlay"}
    for c in plan["chapters"]:
        a0, a1 = c["range"]
        args = ["--crop", plan["app"], "--range", f"{a0}-{a1}"]
        for d in drops:
            if d[1] > a0 and d[0] < a1:
                args += ["--drop", f"{d[0]}-{d[1]}"]
        o = overlays.get(c["clip"])
        if o:   # the inset and its chapter share clip time, so keep the chapter whole and at 1x until the inset is gone
            args += ["--keep", f"{a0}-{min(a1, o['at'][1] + .4)}"]
        py("suggest_cuts.py", rec, *args, "--clips", cj_path, "--name", c["clip"])
    cj = rjson(cj_path)
    for clip, o in overlays.items():
        segs = cj["clips"][clip]["segments"]
        s0 = segs[0][0]
        crop, aspect = overlay_crop(o, info)
        cj["clips"][f"{clip}-inset"] = {"crop": crop, "segments": [[s0, round(o["at"][1] + .5, 2), 1]],
                                        "overlay": {"chapter": clip, "at": [.5, .45], "width": 820 if aspect >= 1.3 else round(640 * aspect),
                                                    "outAt": round(o["at"][1] - s0 + .2, 2)}}
    wjson(cj_path, cj)
    py("cut_clips.py", cj_path)
    chapters = [c["clip"] for c in plan["chapters"]]
    py("cursor_track.py", *[os.path.join(project, "page", c + ".mp4") for c in chapters], "--out", W(project, "cursor"))
    py("cut_clips.py", cj_path, "--preview", W(project, "sheets", "preview.jpg"))

    durs = {c: probe(os.path.join(project, "page", c + ".mp4"))["dur"] for c in chapters}
    sheets = []
    for c in chapters:
        d = durs[c]
        times = ",".join(f"{.15 + i * (d - .3) / 7:.2f}" for i in range(8))
        f = W(project, "sheets", f"{c}.jpg")
        py("contact_sheet.py", os.path.join(project, "page", c + ".mp4"), "--times", times, "--width", 420, "--out", f)
        sheets.append(f)

    page = rjson(W(project, "page.json"), {})
    page.update({"brand": {"name": plan["product"], "tag": plan["tagline"], "accent": plan["accent"]},
                 "frame": {"type": "mac", "title": plan["product"]}, "chapters": chapters,
                 "intro": {**page.get("intro", {}), **plan["intro"]}, "outro": plan["outro"]})
    page.setdefault("style", "midnight")
    page.setdefault("tempo", "steady")
    wjson(W(project, "page.json"), page)

    # Intro cut-outs: automatic when the app shows repeated items (covers, cards), else a background helper.
    times = ",".join(f"{c['range'][0] + .6:.1f}" for c in plan["chapters"][:3])
    auto = subprocess.run(["python3", os.path.join(HERE, "cutout.py"), rec, "--auto", "--crop", plan["app"], "--times", times,
                           "--count", "6", "--out-dir", W(project, "cutouts")], capture_output=True, text=True)
    cut_sheet = W(project, "cutouts", "cutouts-sheet.jpg")
    briefs = []
    for i, c in enumerate(plan["chapters"]):
        f = W(project, "briefs", f"chapter-{c['clip']}.md")
        with open(f, "w") as fh:
            fh.write(chapter_brief(project, plan, c, i + 1, durs[c["clip"]], sheets[i]))
        briefs.append(f)
    cut_brief = None
    if auto.returncode or not os.path.exists(W(project, "cutouts", "cutouts.json")):
        cut_brief = W(project, "briefs", "cutouts.md")
        with open(cut_brief, "w") as fh:
            fh.write(cutout_brief(project, plan, st))

    st["rounds"]["cut"] = n + 1
    st["durations"] = durs
    save(project, st, step="cut", look=[W(project, "sheets", "preview.jpg")] + sheets + ([cut_sheet] if os.path.exists(cut_sheet) else []))
    for c in chapters:
        segs = cj["clips"][c]["segments"]
        print(f"{c}: {durs[c]:.1f} s from source {segs[0][0]}–{segs[-1][1]} ({len(segs)} pieces)")
    for clip in overlays:
        print(f"{clip}-inset: {cj['clips'][clip + '-inset']['crop']}, over {clip} until clip {cj['clips'][clip + '-inset']['overlay']['outAt']} s")
    print("intro cut-outs: " + (f"automatic, {cut_sheet}" if not cut_brief else "need a helper (no repeated items found)"))
    prompts = [f'"Read {b} and do exactly what it says."' for b in briefs]
    nxt(f"1. LOOK at {W(project, 'sheets', 'preview.jpg')}: one row per clip (start, middle, end). Each row should be the app"
        " showing that chapter's action, with no popup or other window. To see one clip larger, run"
        f" python3 {ME} sheet {project} <clip> --times 1,3,5 (don't crop the preview).",
        "2a. If every row is right, in ONE turn start one helper per chapter, all at once, each with this one-line prompt:",
        *[f"     {p}" for p in prompts],
        *([f"     and one more in the background (don't wait for it): \"Read {cut_brief} and do exactly what it says.\""] if cut_brief else []),
        f"   When the chapter helpers are back, run: python3 {ME} build {project}",
        f"2b. If a row is wrong, change that chapter's range or add a drop in plan.json and run: python3 {ME} cut {project}"
        f" ({2 - n} re-cut{'s' if 2 - n != 1 else ''} left).")


SHARED = """You are a helper on a product demo video. Do only this task, then reply in a few lines.
- You can't ask the user anything; put questions in your reply.
- Don't open images other than the ones named here, don't grab frames with ffmpeg, and don't read the skill's
  scripts or references: everything you need is in this brief.
"""


def inset_note(plan, c):
    o = next((o for o in plan.get("outside", []) if o["treat"] == "overlay" and o["chapter"] == c["clip"]), None)
    return (f"An inset of another window plays over the start of this clip (it isn't in the clip itself): {o['what']}."
            " The copy may mention it; leave it out of the claims.\n") if o else ""


def chapter_brief(project, plan, c, n, d, sheet):
    facts = "".join(f"- {f}\n" for f in plan.get("facts", [])) or "- none\n"
    return f"""# Chapter {n}: {c['label']} ({c['clip']})
{SHARED}
Product: {plan['product']} ({plan['tagline']}). This chapter shows: {c['shows']}.
Facts the user confirmed:
{facts}
Clip: {project}/page/{c['clip']}.mp4, {d:.2f} s long. All times below are clip seconds (0 = start of this clip).
{inset_note(plan, c)}
1. Look at {sheet} (8 moments, each labelled with its clip time).
   If you need to see one more moment to settle a time, run once:
     python3 {ME} sheet {project} {c['clip']} --times 1.2,1.5,1.8
   and look at the sheet it prints. No other images.
2. Write {project}/work/chapters/{c['clip']}.json, exactly this shape:
   {{"label": "{c['label']}", "title": "…", "body": "…",
    "steps": [["hold", 0, 0.4], ["play", 0, 2.5], ["hold", 2.5, 1.0], ["play", 2.5, {d:.2f}]],
    "chips": [[2.5, 0, "Short chip text", 4.0]],
    "claims": [["356 pages", 2.5]]}}
   - title: 2–5 words. body: one sentence. Both say only what the clip shows (and the facts above).
   - steps cover the clip from 0 to {d:.2f} in order. ["hold", clipTime, seconds] freezes on a result so it can be
     read (0.4–1.4 s). ["play", from, to] plays; add a rate (1.5–2) only for scrolling or waiting.
   - chips: 1–3 of [clipTime, 0, "text", endClipTime], under 45 characters each, never two at the same time, each
     about something on screen at that moment.
   - claims: every number and on-screen label used in the title, body or chips, with a clip time where it is
     clearly on screen. Anything you couldn't read clearly stays out of the copy: never guess a number.
     A script reads the screen at each claim's time afterwards, so don't double-check them by eye.
   - No camera moves: a script sets them from the claims and the cursor.
3. Reply: "done {project}/work/chapters/{c['clip']}.json" and any question.
"""


def cutout_brief(project, plan, st):
    return f"""# Intro cut-outs
{SHARED}
Make 4–7 cut-outs for the intro of the {plan['product']} demo: recognisable pieces of its UI (covers, cards, a key
button, app icons), similar in shape (width ÷ height about 1.3–1.8, or all portrait).
Recording: {st['recording']}. App crop: {plan['app']} (W:H:X:Y in source pixels).
Stop after 8 tool calls or 5 minutes, with whatever you have; the demo works without them.
1. Look at {W(project, 'sheets', 'app.jpg')} to pick a moment and the pieces.
2. For each piece: python3 {HERE}/cutout.py "{st['recording']}" <source seconds> --box X,Y,W,H --trim --out {project}/work/cutouts/cut-NN.png
   (X,Y,W,H in source pixels: the app crop's X,Y plus the position inside the app).
3. Write {project}/work/cutouts/cutouts.json: {{"files": ["cut-01.png", …], "width": <px so the row spans about 65% of 1920>}}
4. Reply "done" and the number of cut-outs.
"""


def cmd_sheet(a):
    project = project_arg(a.project)
    st = load(project)
    clip = os.path.join(project, "page", a.clip + ".mp4")
    if not os.path.exists(clip):
        die(f"no clip {clip}")
    k = st["rounds"].get(f"sheet-{a.clip}", 0)
    if k >= 2:
        die("Two extra sheets already for this clip. Decide from what you've seen.")
    f = W(project, "sheets", f"{a.clip}-extra{k + 1}.jpg")
    py("contact_sheet.py", clip, "--times", a.times, "--width", 520, "--out", f)
    st = load(project)   # other helpers may have saved in between
    st["rounds"][f"sheet-{a.clip}"] = k + 1
    save(project, st, look=st.get("look", []) + [f])
    print(f"LOOK at {f}")


def cmd_still(a):
    project = project_arg(a.project)
    st = load(project)
    k = st["rounds"].get("still", 0)
    if k >= 12:
        die("Enough extra stills for this demo. Decide from what you've seen, or report it as uncertain.")
    out = node(project, "--stills", f"{float(a.time):.2f}", "--stills-dir", W(project, "stills", "extra"))
    f = W(project, "stills", "extra", f"t_{float(a.time):06.2f}.jpg")
    st = load(project)
    st["rounds"]["still"] = k + 1
    save(project, st, look=st.get("look", []) + [f])
    print(f"LOOK at {f}")


# ---- step 5: build ---------------------------------------------------------------------------------------------
def timeline(project):
    out = node(project, "--timeline")
    tl = {"chapters": []}
    for line in out.splitlines():
        m = re.match(r"(.+?)\s+([\d.]+) – ([\d.]+)$", line)
        if m:
            name, a0, a1 = m[1].strip(), float(m[2]), float(m[3])
            if name == "intro":
                tl["intro"] = a1
            elif name == "outro":
                tl["outro"] = a0
            else:
                tl["chapters"].append((name, a0, a1))
        m = re.match(r"duration\s+([\d.]+)", line)
        if m:
            tl["duration"] = float(m[1])
    return tl


def lint(project):
    r = subprocess.run(["node", os.path.join(HERE, "render.mjs"), os.path.join(project, "page", "index.html"), "--lint", "--json"],
                       cwd=os.path.join(project, "render"), capture_output=True, text=True)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        die("FAILED: render.mjs --lint\n" + "\n".join((r.stdout + r.stderr).strip().splitlines()[-12:]))


def claims_check(project):
    """OCR every claim in its clip; reuse the last result while the claims and clips are unchanged."""
    md = W(project, "claims.md")
    key = hashlib.sha1((open(md).read() + "".join(str(os.path.getmtime(p)) for p in sorted(glob.glob(os.path.join(project, "page", "*.mp4"))))).encode()).hexdigest()
    st = load(project)
    if st.get("claims_key") != key or not os.path.exists(W(project, "claims.json")):
        if open(md).read().strip():
            py("check_claims.py", md, "--json", W(project, "claims.json"), "--quiet", ok=(0, 1))
        else:
            wjson(W(project, "claims.json"), [])
        st = load(project)
        st["claims_key"] = key
        save(project, st)
    return rjson(W(project, "claims.json"), [])


def ensure_render(project):
    if not os.path.exists(os.path.join(project, "render", "node_modules", "playwright-core")):
        run(["npm", "init", "-y"], cwd=os.path.join(project, "render"))
        run(["npm", "i", "playwright-core"], cwd=os.path.join(project, "render"), what="npm i playwright-core")


def assemble(project, chapter_only=None):
    """config -> claims -> camera -> config -> lint (+ overlay fix). Returns (errors, warnings, missing claims)."""
    cfg = os.path.join(project, "page", "demo.config.js")
    if os.path.exists(cfg):
        first, _, rest = open(cfg).read().partition("\n")
        m = re.search(r"fingerprint (\w+)\)", first)
        if m and hashlib.sha1(rest.partition("\n")[2].encode()).hexdigest()[:12] != m[1]:
            die("page/demo.config.js was edited by hand, and building would lose that. Move the change into "
                "work/chapters/<clip>.json or work/page.json, then delete page/demo.config.js and run this again.")
    shutil.copy(os.path.join(SKILL, "assets", "demo-template.html"), os.path.join(project, "page", "index.html"))
    cut = rjson(W(project, "cutouts", "cutouts.json"))
    page = rjson(W(project, "page.json"))
    if cut and cut.get("files"):
        os.makedirs(os.path.join(project, "page", "cutouts"), exist_ok=True)
        for f in cut["files"]:
            shutil.copy(W(project, "cutouts", f), os.path.join(project, "page", "cutouts", f))
        page["intro"]["cutouts"] = ["cutouts/" + f for f in cut["files"]]
        page["intro"]["cutoutWidth"] = cut.get("width", 240)
        wjson(W(project, "page.json"), page)
    py("make_config.py", project)
    claims = claims_check(project)
    node(project, "--auto-cams", "--write")
    py("make_config.py", project)
    res = lint(project)
    if res.get("overlays"):
        cj = rjson(os.path.join(project, "clips.json"))
        for fix in res["overlays"]:
            name = re.sub(r"\.mp4$", "", fix["clip"])
            if name in cj["clips"] and "overlay" in cj["clips"][name]:
                cj["clips"][name]["overlay"]["at"] = fix["at"]
                print(f"moved the {name} inset to at {fix['at']} so the caption and chips don't cover it")
        wjson(os.path.join(project, "clips.json"), cj)
        py("make_config.py", project)
        res = lint(project)
    missing = [c for c in claims if c["verdict"] == "MISSING"]
    return res["errors"], res["warnings"], missing


def fix_lines(project, errors, missing, only_clip=None):
    lines = []
    for c in missing:
        clip = os.path.basename(c["clip"]).replace(".mp4", "")
        if only_clip and clip != only_clip:
            continue
        lines.append(f"{clip}: claim \"{c['text']}\" at clip {c['t']} s is not on screen; the screen has: "
                     + " | ".join(c.get("screen", [])[:3]) + f" -> correct the copy and the claim in work/chapters/{clip}.json")
    for e in errors:
        if only_clip and e.get("clip") and e["clip"] != only_clip:
            continue
        if e.get("kind") == "claim":
            lines.append(e["text"] + f" -> move the claim (and its chip) to a clip time where it shows, or set \"cams\" in work/chapters/{e['clip']}.json")
        else:
            lines.append(e["text"])
    return lines


def cmd_build(a):
    project = project_arg(a.project)
    st = load(project)
    if st["step"] not in ("cut", "built", "styled", "checked"):
        die(f"Not ready to build (step: {st['step']}). Run: python3 {ME} next {project}")
    page = rjson(W(project, "page.json"))
    missing = [c for c in page["chapters"] if not os.path.exists(W(project, "chapters", c + ".json"))]
    if missing:
        die("Waiting for the chapter helpers: no work/chapters/" + ".json, ".join(missing) + ".json yet. When they're back, run this again.")
    if a.style:
        if a.style not in STYLES or (a.tempo and a.tempo not in TEMPOS):
            die(f"style: {', '.join(STYLES)}; tempo: {', '.join(TEMPOS)}")
        page["style"], page["tempo"] = a.style, a.tempo or page.get("tempo", "steady")
        st["look_chosen"] = True
        st["music"] = a.music or st.get("music", "auto")
        wjson(W(project, "page.json"), page)
    # Fix rounds only count once the look is chosen; the first builds are setup.
    n = st["rounds"].get("build", 0) if st.get("look_chosen") and not a.style else 0
    st["rounds"]["build"] = n + 1
    save(project, st)
    ensure_render(project)
    errors, warnings, missing = assemble(project)
    fixes = fix_lines(project, errors, missing)
    tl = timeline(project)
    st = load(project)
    st["timeline"] = tl
    print(f"Page: {project}/page/index.html — {page['style']} / {page['tempo']}, {tl.get('duration')} s, chapter 1 at {tl.get('intro')} s")
    print(f"Checks: {len(fixes)} to fix, {len(warnings)} warnings" + ("" if fixes else " — layout, cursor and every claim pass"))
    for f in fixes:
        print("  FIX " + f)

    if not st.get("look_chosen"):
        chs = tl["chapters"]
        picks = [chs[min(1, len(chs) - 1)], chs[min(3, len(chs) - 1)]]
        times = ",".join(f"{(c[1] + c[2]) / 2:.2f}" for c in picks)
        looks = W(project, "looks")
        shutil.rmtree(looks, ignore_errors=True)
        node(project, "--stills", times, "--style", "all", "--stills-dir", looks)
        sheets = sorted(glob.glob(os.path.join(looks, "sheet_*.jpg")))
        save(project, st, step="built", look=sheets)
        nxt(*([f"0. First fix these in work/chapters/<clip>.json (copy follows the screen), in ONE turn:"] + [f"     {f}" for f in fixes] if fixes else []),
            f"1. LOOK at {' '.join(sheets)} (every style at two moments).",
            "2. ASK with the question tool, ONE call with three questions:",
            f'   header "Style", options {list(STYLES)} — describe each in a few words: ' + "; ".join(f"{k}: {v}" for k, v in STYLES.items()),
            f'   header "Tempo", options {list(TEMPOS)} (steady = about {tl.get("duration")} s; fast is about a third shorter)',
            '   header "Music", options ["Yes, pick one for me", "Yes, I\'ll choose by ear", "No music"]',
            "   Recommend one or two styles from the sheet and put them first.",
            f"3. Run: python3 {ME} build {project} --style <style> --tempo <tempo> --music auto|choose|none")
        return

    if fixes and n < 3:
        save(project, st, step="styled", look=[])
        nxt("Fix these in ONE turn, in work/chapters/<clip>.json (or work/page.json), then run the same build again:",
            *[f"  {f}" for f in fixes],
            f"  python3 {ME} build {project}   ({3 - n - 1} fix round{'s' if 3 - n - 1 != 1 else ''} left after this one)")
        return
    if st.get("music", "auto") != "none" and not st.get("music_started"):
        log = open(W(project, "music.log"), "w")
        proc = subprocess.Popen(["python3", os.path.join(HERE, "music_beds.py"), "--style", page["style"], "--tempo", page["tempo"],
                                 "--duration", str(tl["duration"]), "--intro-end", str(tl["intro"]), "--out", "music_choices",
                                 "--src", "music_src"], cwd=project, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        st["music_started"] = {"pid": proc.pid, "tempo": page["tempo"], "duration": tl["duration"]}
    # One stills round; after it, only chapters changed since their check get a helper again, once.
    rnd = st.get("stills_round", 0)
    todo = list(range(len(page["chapters"])))
    if rnd:
        todo = [i for i, c in enumerate(page["chapters"]) if chapter_hash(project, c) != st.get("stills_hash", {}).get(c)]
        if not todo or rnd >= 2:
            if fixes:
                st["open_issues"] = fixes
            save(project, st, step="styled", look=[])
            nxt("The stills check is done" + ("" if not todo else " (its rounds are used up)") + ". Run:",
                f"  python3 {ME} finish {project}" + ('  --note "…" for anything a helper reported as still wrong' if not fixes else ""))
            return
        for i in todo:
            st["rounds"].pop(f"check-{i + 1}", None)
    st["stills_round"] = rnd + 1
    st.setdefault("stills_hash", {}).update({c: chapter_hash(project, c) for c in page["chapters"]})
    stills = W(project, "stills")
    shutil.rmtree(stills, ignore_errors=True)
    node(project, "--stills", "auto", "--stills-dir", stills)
    sheets = sorted(glob.glob(os.path.join(stills, "sheet_*.jpg")))
    intro = [s for s in sheets if "00-intro-outro" in s]
    chapter_sheets = [s for s in sheets if s not in intro]
    briefs = []
    for i, s in enumerate(chapter_sheets):
        if i not in todo:
            continue
        clip = page["chapters"][i]
        f = W(project, "briefs", f"stills-{i + 1}.md")
        with open(f, "w") as fh:
            fh.write(stills_brief(project, page, i + 1, clip, s, rjson(W(project, "plan.json"))))
        briefs.append(f)
    save(project, st, step="styled", look=intro + [chapter_sheets[i] for i in todo if i < len(chapter_sheets)])
    if fixes:
        print("Fix rounds used up; these go into the hand-over as 'worth checking':")
        st["open_issues"] = fixes
        save(project, st)
    nxt("In ONE turn, all at once:",
        *[f'  - start a helper with: "Read {b} and do exactly what it says."' for b in briefs],
        f"  - LOOK yourself at {' '.join(intro)} (intro and outro). If the intro or outro text is wrong, change work/page.json.",
        f"When the helpers are back, run: python3 {ME} finish {project}  (add --note \"…\" for anything a helper reported as still wrong).")


def chapter_hash(project, clip):
    d = rjson(W(project, "chapters", clip + ".json"), {})
    d.pop("auto_cams", None)
    return hashlib.sha1(json.dumps(d, sort_keys=True).encode()).hexdigest()[:12]


def stills_brief(project, page, n, clip, sheet, plan):
    c = next(c for c in plan["chapters"] if c["clip"] == clip)
    return f"""# Stills check: chapter {n} ({clip}), {page['style']} / {page['tempo']}
{SHARED}
This chapter shows: {c['shows']}. {inset_note(plan, c)}
1. Look at {sheet}. Each tile is labelled with its page time and why it's there (start, zoom, hold, chip).
   Scripts have already checked overlaps, the cursor, and that every claim is readable on the page. Don't
   re-check those.
2. Only fix what a viewer would notice:
   - a chip, title or body that says something the screen doesn't show at that moment;
   - a hold that shows the wrong state (one frame early, a half-open panel);
   - the action, or the text the chapter is about, is out of view or has its line starts cut off.
   Not: other text cut at the edge of a zoom, small framing preferences, or a zoom you'd have set differently.
   The first moments of a chapter belong to the change from the previous one; judge from the second tile on.
3. To fix, edit only {project}/work/chapters/{clip}.json:
   - copy or chip time: change the text, or the chip's [clipTime, 0, "text", endClipTime]; update its claim too;
   - hold: move ["hold", clipTime, seconds];
   - camera: set "cams": [[clipTime, 0, scale, fx, fy, 0.6], …] (replaces the automatic ones for this chapter;
     clipTime must be a hold time or inside a play; scale 1–2.4; fx, fy = focus point as fractions of the clip;
     fx 0 keeps text lines' first words).
   Then run once: python3 {ME} check {project} {n}
   and look at the sheet it prints. You get one fix round: if something is still wrong after it, report it.
4. Reply in at most 5 lines: "OK", or "fixed: …", or "still wrong: page <t>: <problem>".

Limits: at most 8 tool calls in all. No image processing (cropping, zooming, sampling pixels): if the sheet
doesn't settle a question, run `python3 {ME} still {project} <page time>` (at most twice) and look at that
full-size still; if you still can't tell, report it as uncertain instead of investigating.
"""


# ---- step 6: one chapter, for the stills helpers ---------------------------------------------------------------
def cmd_check(a):
    project = project_arg(a.project)
    st = load(project)
    page = rjson(W(project, "page.json"))
    i = int(a.chapter)
    clip = page["chapters"][i - 1]
    k = st["rounds"].get(f"check-{i}", 0)
    if k >= 1:
        die("This chapter has had its fix round. Don't fix again: report what is still wrong in your reply.")
    with open(W(project, ".lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        errors, warnings, missing = assemble(project)
        stills = W(project, "stills")
        out = node(project, "--stills", "auto", "--chapter", i, "--stills-dir", stills)
    sheet = next((l.split()[0] for l in out.splitlines() if l.strip().endswith("moments)")), None)
    st = load(project)
    st["rounds"][f"check-{i}"] = k + 1
    st.setdefault("stills_hash", {})[clip] = chapter_hash(project, clip)
    save(project, st, look=st.get("look", []) + ([sheet] if sheet else []))
    tl = timeline(project)
    g = next(((c[1], c[2]) for j, c in enumerate(tl["chapters"]) if j == i - 1), (0, 1e9))
    mine = [e for e in errors if e.get("clip") == clip or (not e.get("clip") and any(g[0] <= float(x) <= g[1] for x in re.findall(r"page ([\d.]+)", e["text"])))]
    fixes = fix_lines(project, mine, missing, only_clip=clip)
    print("PASS: layout, cursor and claims" if not fixes else "Still failing (report these, don't fix again):\n  " + "\n  ".join(fixes))
    print(f"LOOK at {sheet}, then reply.")


# ---- step 7-8: render, music, hand-over -------------------------------------------------------------------------
def cut_summary(project, plan):
    cj = rjson(os.path.join(project, "clips.json"))
    lines = []
    for c in plan["chapters"]:
        segs = cj["clips"][c["clip"]]["segments"]
        gaps = [(segs[i][1], segs[i + 1][0]) for i in range(len(segs) - 1) if segs[i + 1][0] - segs[i][1] >= .4]
        fast = [(s[0], s[1], s[2]) for s in segs if s[2] > 1]
        bits = ([f"cut {spans_text(gaps)}"] if gaps else []) + [f"{a0:.1f}–{a1:.1f} at ×{r:g}" for a0, a1, r in fast]
        lines.append(f"- {c['label']}: source {c['range'][0]}–{c['range'][1]} s" + (f"; {', '.join(bits)}" if bits else ", as recorded"))
    return lines


def cmd_finish(a):
    project = project_arg(a.project)
    st = load(project)
    if st["step"] not in ("styled", "finished"):
        die(f"Not ready to finish (step: {st['step']}). Run: python3 {ME} next {project}")
    page, plan = rjson(W(project, "page.json")), rjson(W(project, "plan.json"))
    res = lint(project)
    if res["errors"] and not a.force:
        die("Lint still has errors; fix them in work/chapters/<clip>.json and run demo.py build, or add --force:\n  "
            + "\n  ".join(e["text"] for e in res["errors"]))
    tl = st.get("timeline") or timeline(project)
    music = st.get("music", "auto")
    beds = []
    if music != "none":
        pid = (st.get("music_started") or {}).get("pid")
        for _ in range(120):   # the beds were started in the background by build
            try:
                os.kill(pid, 0)
                time.sleep(2)
            except (OSError, TypeError):
                break
        beds = rjson(os.path.join(project, "music_choices", "beds.json"), [])
        if music == "choose" and not a.bed and beds:
            save(project, st, step="finished", look=[])
            nxt("ASK with the question tool which bed to use; options: " + ", ".join(f"{b['name']} ({b['bpm']} bpm, {b['source']})" for b in beds),
                f"   The beds are in {project}/music_choices/ for the user to play.",
                f"Then run: python3 {ME} finish {project} --bed <name>")
            return
    node(project, "--out", os.path.join(project, "output", "demo-silent.mp4"))
    final, bed = os.path.join(project, "output", "demo-silent.mp4"), None
    if beds:
        bed = next((b for b in beds if b["name"] == a.bed), beds[0])
        py("add_music.py", "--track", bed["track"], "--offset", bed["offset"], "--duration", tl["duration"],
           "--page-out", os.path.join(project, "page", "music.m4a"), "--video-in", final,
           "--video-out", os.path.join(project, "output", "demo.mp4"))
        page["music"] = {"src": "music.m4a", "volume": .35}
        wjson(W(project, "page.json"), page)
        py("make_config.py", project)
        final = os.path.join(project, "output", "demo.mp4")
    spot = W(project, "sheets", "final.jpg")
    py("contact_sheet.py", final, "--step", round(tl["duration"] / 12, 2), "--width", 360, "--out", spot)
    info = probe(final)
    size = run(["du", "-sh", project]).split()[0]
    frames = run(["du", "-sh", os.path.join(project, "page", "frames")]).split()[0] if os.path.exists(os.path.join(project, "page", "frames")) else "0"
    notes = list(a.note or []) + st.get("open_issues", [])
    credit = ""
    if bed and "incompetech" in bed["source"].lower():
        credit = f' Credit line (required): "{bed["name"].replace("-", " ").title()}" Kevin MacLeod (incompetech.com), licensed under Creative Commons: By Attribution 4.0.'
    out = [o for o in plan.get("outside", []) if o["treat"] != "ignore"]
    hand = [
        "The demo is ready.", "",
        "**Files**",
        *( [f"- Video with music: `{final}` ({info['w']}×{info['h']}, {info['fps']} fps, {info['dur']:.0f} s)"] if bed else []),
        f"- Video without music: `{os.path.join(project, 'output', 'demo-silent.mp4')}`",
        f"- Page to play while recording a Loom: `{os.path.join(project, 'page', 'index.html')}`", "",
        f"**Look:** {page['style']} style, {page['tempo']} tempo. Press S and T on the page to try others live.", "",
        "**To record:** open the page in Chrome, press F for full screen, C to show where your camera bubble goes, Space to"
        " play and M for music. Loom only records the music with computer audio on.", "",
        *( [f"**Music:** {bed['name']} ({bed['source'] or 'see music_choices'}).{credit} The other beds are in `{project}/music_choices/`;"
            " tell me which you prefer and I'll swap it in.", ""] if bed else []),
        "**What it shows:** " + " → ".join(f"{c['label']} ({c['shows']})" for c in plan["chapters"]), "",
        "**Cut or sped up:**", *cut_summary(project, plan),
        *( ["", "**Outside the app:**", *[f"- {o['at'][0]}–{o['at'][1]} s {o['what']}: {'shown as an inset' if o['treat'] == 'overlay' else 'cut'}" for o in out]] if out else []),
        *( ["", "**Worth checking:**", *[f"- {n_}" for n_ in notes]] if notes else []), "",
        "**To change something,** tell me what; I'll update the chapter and re-render.", "",
        f"**Folder:** `{project}` is {size}, of which {frames} is extracted frames (page/frames), rebuilt when needed."
        " Want me to delete page/frames, work/ and music_src/?",
    ]
    with open(W(project, "handover.md"), "w") as f:
        f.write("\n".join(hand) + "\n")
    save(project, st, step="done", look=[spot])
    print("\n".join(hand))
    nxt(f"1. LOOK at {spot} (12 frames of the final video). If it looks right:",
        "2. Send the hand-over above to the user as it is. Add nothing except anything wrong you saw in step 1.")


# ---- resume ----------------------------------------------------------------------------------------------------
def cmd_next(a):
    project = project_arg(a.project)
    st = load(project)
    step = st["step"]
    todo = {
        "new": f"fill in {W(project, 'plan.json')}, then: python3 {ME} plan {project}",
        "planned": f"ask the user to confirm the plan (run python3 {ME} plan {project} to print the question), then: python3 {ME} cut {project}",
        "cut": f"start the chapter helpers (briefs in {W(project, 'briefs')}), then: python3 {ME} build {project}",
        "built": f"ask style, tempo and music, then: python3 {ME} build {project} --style <s> --tempo <t> --music auto|choose|none",
        "styled": f"start the stills helpers (briefs in {W(project, 'briefs')}, stills-*.md), then: python3 {ME} finish {project}",
        "finished": f"python3 {ME} finish {project} --bed <name>",
        "done": f"the demo is done; the hand-over is in {W(project, 'handover.md')}",
    }[step]
    print(f"Project {project}: step {step}")
    nxt(todo)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("new"); p.add_argument("recording"); p.add_argument("--name"); p.add_argument("--dir")
    for name in ("plan", "cut", "next"):
        sub.add_parser(name).add_argument("project", nargs="?")
    p = sub.add_parser("build"); p.add_argument("project", nargs="?"); p.add_argument("--style"); p.add_argument("--tempo")
    p.add_argument("--music", choices=["auto", "choose", "none"])
    p = sub.add_parser("check"); p.add_argument("project"); p.add_argument("chapter")
    p = sub.add_parser("sheet"); p.add_argument("project"); p.add_argument("clip"); p.add_argument("--times", required=True)
    p = sub.add_parser("still"); p.add_argument("project"); p.add_argument("time")
    p = sub.add_parser("finish"); p.add_argument("project", nargs="?"); p.add_argument("--bed"); p.add_argument("--note", action="append")
    p.add_argument("--force", action="store_true")
    a = ap.parse_args()
    {"new": cmd_new, "plan": cmd_plan, "cut": cmd_cut, "build": cmd_build, "check": cmd_check, "sheet": cmd_sheet, "still": cmd_still,
     "finish": cmd_finish, "next": cmd_next}[a.cmd](a)


if __name__ == "__main__":
    main()
