#!/usr/bin/env python3
"""Block the tool calls that derail a demo run, and say what to do instead.

Runs before every tool call, as a Claude Code PreToolUse hook or from the OpenCode plugin in hooks/:

  python3 guard.py --claude     # stdin: {"tool_name", "tool_input", "cwd"}; blocks with exit 2 + stderr
  python3 guard.py --opencode   # stdin: {"tool", "args", "cwd"}; blocks with exit 2 + stdout

It only acts while demo.py has an active project (~/.cache/product-demo-video/active/*.json, updated in the
last 8 hours, whose work/state.json step isn't "done"); otherwise it exits 0 at once.
Set PRODUCT_DEMO_VIDEO_GUARD=0 in the agent's environment to switch it off.
Standard library only.
"""
import os, sys

ACTIVE = os.path.join(os.path.expanduser("~"), ".cache", "product-demo-video", "active")
MAX_AGE = 8 * 3600


def main():
    if os.environ.get("PRODUCT_DEMO_VIDEO_GUARD") == "0":
        return 0
    try:
        entries = [e.path for e in os.scandir(ACTIVE) if e.name.endswith(".json")]
    except OSError:
        return 0
    if not entries:
        return 0
    projects = active_projects(entries)
    if not projects:
        return 0

    import json
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    claude = "--claude" in sys.argv[1:]
    if claude:
        tool, args = data.get("tool_name", ""), data.get("tool_input") or {}
    else:
        tool, args = data.get("tool", ""), data.get("args") or {}
    cwd = data.get("cwd") or os.getcwd()

    message = check(str(tool).lower(), args if isinstance(args, dict) else {}, cwd, projects)
    if not message:
        return 0
    print(message, file=sys.stderr if claude else sys.stdout)
    return 2


def active_projects(entries):
    """[(project dir, updated, state)] for live projects, most recently updated first."""
    import json, time
    now, found = time.time(), []
    for path in entries:
        try:
            with open(path, encoding="utf-8") as f:
                entry = json.load(f)
            project, updated = entry["project"], float(entry.get("updated") or os.path.getmtime(path))
            if now - updated > MAX_AGE:
                continue
            with open(os.path.join(project, "work", "state.json"), encoding="utf-8") as f:
                state = json.load(f)
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if isinstance(state, dict) and state.get("step") != "done":
            found.append((project, updated, state))
    return sorted(found, key=lambda p: -p[1])


SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_REAL = os.path.realpath(SKILL)
SKILL_DIRS = ("scripts", "references", "assets")
IMAGES = (".jpg", ".jpeg", ".png", ".webp", ".gif")
READERS = {"cat", "sed", "head", "tail", "less", "more", "grep", "rg", "awk", "gawk", "bat", "nl", "egrep", "fgrep"}
WRAPPERS = {"sudo", "env", "command", "exec", "time", "nohup", "nice", "xargs", "then", "do", "else", "{", "(", "!"}
SEPARATORS = {";", "|", "||", "&&", "&", "|&", "(", ")"}
REDIRECTS = {">", ">>", ">|", "&>", "&>>"}
INTERPRETERS = ("python", "python3", "node", "bun", "deno", "ruby", "perl")

SHELL = {"bash", "shell"}
READ = {"read"}
WRITE = {"write", "edit", "multiedit", "patch", "apply_patch"}

ASK_DEMO = "Not needed: demo.py prints the exact command for this step. Run: python3 {skill}/scripts/demo.py next {project}"
NO_FRAMES = ("Don't grab single frames: demo.py made the sheets for this step (see `look` in work/state.json); "
             "a script check covers the rest.")
NOT_LISTED = "Not on this step's list. Already checked by a script; trust its verdict. Images for this step: {images}"
GENERATED = ("{name} is generated. Edit work/chapters/<clip>.json (caption, chips, steps, cams) or work/page.json "
             "(brand, style, tempo, intro, outro), then run: python3 {skill}/scripts/demo.py build {project}")


def check(tool, args, cwd, projects):
    if tool in SHELL:
        command = args.get("command") or ""
        workdir = args.get("workdir") or args.get("cwd") or cwd
        return check_shell(command if isinstance(command, str) else "", resolve(workdir, cwd), projects)
    paths = [resolve(p, cwd) for p in arg_paths(args) if isinstance(p, str) and p]
    if tool in READ:
        for path in paths:
            if skill_file(path):
                return ASK_DEMO.format(skill=SKILL, project=pick(projects, path)[0])
            for project, _, state in projects:
                if inside(path, project) and path.lower().endswith(IMAGES) and not listed(path, state):
                    look = [str(p) for p in state.get("look") or []]
                    return NOT_LISTED.format(images=", ".join(look) or "none")
    if tool in WRITE:
        for path in paths:
            for project, _, _ in projects:
                if is_generated(path, project):
                    return GENERATED.format(name=os.path.basename(path), skill=SKILL, project=project)
    return None


def arg_paths(args):
    for key in ("file_path", "filePath", "path"):
        if key in args:
            yield args[key]
    for key in ("patchText", "patch", "input"):
        text = args.get(key)
        if isinstance(text, str):
            yield from patch_paths(text)


def patch_paths(text):
    import re
    for m in re.finditer(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$|^\*\*\* Move to: (.+)$|^\+\+\+ (?:b/)?(.+)$", text, re.M):
        yield (m.group(1) or m.group(2) or m.group(3)).strip()


def resolve(path, cwd):
    return os.path.normpath(os.path.join(cwd, os.path.expanduser(str(path))))


def real(path):
    return os.path.realpath(path)


def inside(path, folder):
    path, folder = real(path), real(folder)
    return path == folder or path.startswith(folder.rstrip("/") + "/")


def pick(projects, *paths):
    """The project the call is about: the one containing a path, else the most recently updated."""
    for project in projects:
        if any(p and inside(p, project[0]) for p in paths):
            return project
    return projects[0]


def skill_file(path):
    """A file in this skill's scripts/, references/ or assets/ (any installed copy). SKILL.md is fine."""
    path = path.replace("\\", "/")
    for d in SKILL_DIRS:
        if f"product-demo-video/{d}/" in path or inside(path, os.path.join(SKILL_REAL, d)):
            return True
    return False


def listed(path, state):
    target = real(path)
    return any(isinstance(p, str) and real(p) == target for p in state.get("look") or [])


def is_generated(path, project):
    page = os.path.join(real(project), "page")
    return real(path) in (os.path.join(page, "demo.config.js"), os.path.join(page, "index.html"))


def tokenize(command):
    """Shell words with ; | && > etc. as their own tokens. Newlines count as ;."""
    import shlex
    text = command.replace("\n", " ; ")
    try:
        lex = shlex.shlex(text, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        return list(lex)
    except ValueError:
        return text.split()


def segments(tokens):
    seg = []
    for t in tokens:
        if t in SEPARATORS:
            if seg:
                yield seg
            seg = []
        else:
            seg.append(t)
    if seg:
        yield seg


def program(seg):
    """(name, index) of the program a simple command runs, skipping VAR=x, sudo, env, xargs and their flags."""
    for i, t in enumerate(seg):
        if "=" in t.split("/")[0] and not t.startswith("-"):
            continue
        name = os.path.basename(t)
        if name in WRAPPERS or (i and t.startswith("-") and os.path.basename(seg[i - 1]) in WRAPPERS):
            continue
        return name, i
    return "", len(seg)


def skill_script(token):
    """The script name if token names a script in this skill, else None."""
    t = token.replace("\\", "/")
    name = os.path.basename(t)
    if "product-demo-video/scripts/" in t or (name and os.path.isfile(os.path.join(SKILL_REAL, "scripts", name))
                                              and name.endswith((".py", ".sh", ".mjs", ".js"))):
        return name
    return None


def names_skill_file(token, cwd):
    t = token.replace("\\", "/")
    if t.startswith("-"):
        return False
    if t.startswith("$") and any(f"/{d}/" in t or t.endswith(f"/{d}") for d in SKILL_DIRS):
        return True
    return skill_file(resolve(t, cwd)) or ("product-demo-video/" in t and t.rstrip("/").split("/")[-1] in SKILL_DIRS)


def names_skill_root(token, cwd):
    t = token.rstrip("/")
    return t.endswith("product-demo-video") or real(resolve(t, cwd)) == SKILL_REAL


def check_shell(command, cwd, projects):
    import re
    if not command.strip():
        return None
    tokens = tokenize(command)
    segs = list(segments(tokens))
    project = pick(projects, cwd, *[resolve(t, cwd) for t in tokens if "/" in t])
    ask = ASK_DEMO.format(skill=SKILL, project=project[0])

    # 5: hand-writing the generated page files
    def generated(token):
        if os.path.basename(token) == "demo.config.js":
            return True
        path = resolve(token, cwd)
        return any(is_generated(path, p) for p, _, _ in projects)

    for seg in segs:
        name, i = program(seg)
        hits = [t for t in seg if generated(t)]
        if not hits:
            continue
        runs_script = any(skill_script(t) for t in seg[i:i + 2])
        redirected = [seg[k + 1] for k in range(len(seg) - 1) if seg[k] in REDIRECTS and generated(seg[k + 1])]
        args = seg[i + 1:]
        writes = (
            (redirected and not runs_script)
            or (name == "tee" and hits)
            or (name in ("sed", "gsed") and any(re.match(r"^-[a-zA-Z]*i|^--in-place", a) for a in args))
            or (name == "perl" and any(re.match(r"^-[a-zA-Z]*i", a) for a in args))
            or (name in ("cp", "mv", "install", "ln", "rsync") and args and generated(args[-1]))
        )
        if writes:
            return GENERATED.format(name=os.path.basename(hits[0]), skill=SKILL, project=project[0])
    named = re.search(r"demo\.config\.js|page/index\.html", command)
    if (named and re.search(r"\b(" + "|".join(INTERPRETERS) + r")\d*(\.\d+)?\b", command)
            and re.search(r"writeFileSync|writeFile\(|\.write\(|write_text|open\([^)]*,\s*['\"][wa]", command)):
        return GENERATED.format(name=os.path.basename(named.group(0)), skill=SKILL, project=project[0])

    for seg in segs:
        name, i = program(seg)
        args = seg[i + 1:]
        # 3: single-frame grabs
        if name == "ffmpeg":
            frames = [args[k + 1] for k in range(len(args) - 1) if args[k] in ("-frames:v", "-vframes", "-frames", "-frames:0")]
            single_image = args and args[-1].lower().endswith(IMAGES) and "%" not in args[-1]
            if "1" in frames or (frames and any("select=" in a for a in args)) or single_image:
                return NO_FRAMES
        # 1: --help on a skill script, or reading the skill's files
        scripts = [skill_script(t) for t in seg[i:]]
        if any(s and s != "demo.py" for s in scripts) and any(a in ("--help", "-h") for a in seg):
            return ask
        if name in READERS and any(names_skill_file(a, cwd) for a in args):
            return ask
        if name in ("grep", "rg", "egrep", "fgrep"):
            searched = [a for a in args if not a.startswith("-")][1:]
            if any(names_skill_root(a, cwd) for a in searched):
                return ask
    return None


if __name__ == "__main__":
    sys.exit(main())
