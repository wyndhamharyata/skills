#!/usr/bin/env python3
"""Measure where the time and turns went in a test run of the product-demo-video skill, and list rule breaks.

  python3 tools/audit_run.py ses_xxx [--since "2026-10-14 00:48"]   # OpenCode session (reads its SQLite DB)
  python3 tools/audit_run.py path/to/transcript.jsonl              # Claude Code transcript (approximate)

Each model turn costs 15-30 s of thinking before anything happens, so turn count is the main cost; the
budget is 16 turns. --since (local time) skips an earlier run in the same session. Claude Code numbers are
approximate: thinking and tool time come from gaps between transcript timestamps, and there is no cost.
Standard library only.
"""
import argparse, datetime, json, os, re, sqlite3, statistics, sys

DB = os.path.expanduser("~/.local/share/opencode/opencode.db")
BUDGET, AWAY, LINES = 16, 600.0, 45
IMAGE_RE = re.compile(r"\.(jpe?g|png|webp)$", re.I)
DEMO_STEPS = ["new", "plan", "cut", "build", "check", "finish", "next"]
DEMO_RE = re.compile(r"demo\.py\s+(%s)\b" % "|".join(DEMO_STEPS))
RUN_RE = re.compile(r"\b(python3?|node|bash)\s+\S")
PHASES = [  # fallback for runs without demo.py; the last match in a command wins
    ("prepare", re.compile(r"find_windows|activity\.py|contact_sheet")),
    ("cut", re.compile(r"suggest_cuts|cut_clips|cursor_track")),
    ("build", re.compile(r"make_config|auto-?cams|lint|check_claims|--style\s+all")),
    ("stills", re.compile(r"stills\s+auto")),
    ("finish", re.compile(r"--out\s+\S+\.mp4|add_music|music_beds")),
]
SKILL_SRC = re.compile(r"product-demo-video/(scripts|references|assets)")
SKILL_REL = re.compile(r"(^|[\s/])(scripts|references|assets)/|\$\{?\w+\}?/\w+\.(py|mjs|sh|md)\b")  # after cd into the skill
READERS = re.compile(r"(^|[\s;&|(])(cat|sed|head|tail|grep|rg|less|awk|bat)\s")
HELP_RE = re.compile(r"\S+\.(py|sh|mjs)\b[^;&|]*\s(--help|-h)(\s|$)")
FRAME_RE = re.compile(r"ffmpeg.*(-frames:v\s+1\b|-vframes\s+1\b)")
CONFIG_SHELL = re.compile(r"(sed\s+-i|perl\s+-\w*i)\b[^;&|]*?demo\.config\.js|>\s*\S*demo\.config\.js")
CONFIG_PY = re.compile(r"['\"][^'\"\s]*demo\.config\.js['\"][\s\S]*(write_text|\.write\()")
MULTI_CHAPTER = re.compile(r"chapters\s*\d|\bch(apter)?s?\s*\d+\s*[-–,&+]\s*\d|\w\s*\+\s*\w", re.I)
BLOCKED = ("demo.py prints", "Not on this step's list", "Don't grab single frames", "is generated. Edit work/chapters")
CC_TOOLS = {"Bash": "shell", "Read": "read", "Write": "write", "Edit": "edit", "MultiEdit": "edit", "Grep": "grep",
            "Glob": "glob", "AskUserQuestion": "question", "Task": "subagent", "Agent": "subagent", "Skill": "skill"}


def clock(ms):
    return datetime.datetime.fromtimestamp(ms / 1000).strftime("%H:%M")


def tool(name, inp, status="completed", err="", out=""):
    inp = inp if isinstance(inp, dict) else {}
    return {"name": name, "input": inp, "status": status, "err": err, "out": out,
            "cmd": inp.get("command", "") if name == "shell" else "",
            "path": inp.get("path") or inp.get("file_path") or ""}


def turn(t0, ts, tc, finish, tools, text, cost=0.0, ctx=0, out=0, model=""):
    return {"kind": "turn", "t0": t0, "ts": ts, "tc": tc, "finish": finish, "tools": tools, "text": text,
            "cost": cost or 0.0, "ctx": ctx, "out": out, "model": model}


# --- loading ---------------------------------------------------------------------------------------------

def oc_session(db, sid, since):
    """Events of one OpenCode session after `since` (ms): turns, plus user/helper/other messages."""
    events = []
    for kind, created, data in db.execute(
            "select type, time_created, data from session_message where session_id=? and time_created>=? order by seq",
            (sid, since)):
        d = json.loads(data)
        if kind != "assistant":
            src = (d.get("metadata") or {}).get("source", "")
            events.append({"kind": kind if kind == "user" else ("helper" if src == "subagent" else "other"),
                           "t0": created, "text": d.get("text", "")})
            continue
        tm, tok, tools, text = d.get("time", {}), d.get("tokens") or {}, [], False
        for c in d.get("content", []):
            if c.get("type") == "text" and c.get("text", "").strip():
                text = True
            elif c.get("type") == "tool":
                st = c.get("state") or {}
                body = st.get("content") or st.get("output") or ""
                tools.append(tool(c.get("name", ""), st.get("input"), st.get("status", ""),
                                  json.dumps(st.get("error")) if st.get("error") else "", json.dumps(body)))
        cache = tok.get("cache") or {}
        m = d.get("model") or {}
        events.append(turn(tm.get("created", created), tm.get("streamed"), tm.get("completed"), d.get("finish"),
                           tools, text, d.get("cost"),
                           (tok.get("input") or 0) + (cache.get("read") or 0) + (cache.get("write") or 0),
                           tok.get("output") or 0, " ".join(x for x in (m.get("id"), m.get("variant")) if x)))
    return events


def load_opencode(sid, since_text):
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    since = 0
    if since_text:
        since = int(datetime.datetime.strptime(since_text, "%Y-%m-%d %H:%M").timestamp() * 1000)
    row = db.execute("select title, model from session_v2 where id=?", (sid,)).fetchone()
    if not row:
        sys.exit(f"no session {sid} in {DB}")
    helpers = []
    for hid, title, created in db.execute(
            "select id, title, time_created from session_v2 where parent_id=? order by time_created", (sid,)):
        events = oc_session(db, hid, since)
        if any(e["kind"] == "turn" for e in events):
            helpers.append({"title": title or hid, "events": events})
    return oc_session(db, sid, since), helpers


def load_claude(path):
    """Claude Code transcript: one turn per assistant message id; times come from neighbouring entries."""
    entries = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("type") in ("user", "assistant") and e.get("timestamp") and not e.get("isSidechain"):
                ts = datetime.datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00")).timestamp() * 1000
                entries.append((ts, e))
    events, turns, results, prev = [], {}, {}, None
    for ts, e in entries:
        msg = e.get("message") or {}
        content = msg.get("content")
        if e["type"] == "user":
            parts = content if isinstance(content, list) else [{"type": "text", "text": content or ""}]
            for p in parts:
                if p.get("type") == "tool_result":
                    results[p.get("tool_use_id")] = (ts, p)
            if any(p.get("type") == "text" for p in parts) and not e.get("isMeta"):
                events.append({"kind": "user", "t0": ts, "text": " ".join(p.get("text", "") for p in parts)})
            prev = ts
            continue
        mid = msg.get("id") or e.get("uuid")
        t = turns.get(mid)
        if t is None:
            u = msg.get("usage") or {}
            t = turns[mid] = turn(prev or ts, ts, ts, "tool-calls", [], False, 0.0,
                                  sum(u.get(k) or 0 for k in ("input_tokens", "cache_read_input_tokens",
                                                              "cache_creation_input_tokens")),
                                  u.get("output_tokens") or 0, msg.get("model", ""))
            t["ids"] = []
            events.append(t)
        for p in content if isinstance(content, list) else []:
            if p.get("type") == "text" and p.get("text", "").strip():
                t["text"] = True
            elif p.get("type") == "tool_use":
                t["tools"].append(tool(CC_TOOLS.get(p.get("name"), p.get("name", "").lower()), p.get("input")))
                t["ids"].append(p.get("id"))
        if msg.get("stop_reason") and msg["stop_reason"] != "tool_use":
            t["finish"] = "stop"
        prev = ts
    for t in turns.values():
        for tl, tid in zip(t["tools"], t["ids"]):
            if tid in results:
                rts, r = results[tid]
                t["tc"] = max(t["tc"], rts)
                body = json.dumps(r.get("content"))
                if r.get("is_error"):
                    tl["status"], tl["err"] = "error", body
                tl["out"] = body
    events.sort(key=lambda e: e["t0"])
    return events, []


# --- analysis --------------------------------------------------------------------------------------------

def is_image_read(t):
    return t["name"] == "read" and IMAGE_RE.search(t["path"] or "")


def analyse(events):
    turns = [e for e in events if e["kind"] == "turn"]
    for t in turns:
        t["failed"] = t["finish"] not in ("tool-calls", "stop") or not t["ts"] or not t["tc"]
        t["think"] = (t["ts"] - t["t0"]) / 1000 if t["ts"] else 0.0
        t["run"] = (t["tc"] - t["ts"]) / 1000 if t["ts"] and t["tc"] else 0.0
        names = {x["name"] for x in t["tools"]}
        t["wait"] = "user" if "question" in names else "helpers" if "subagent" in names else "tools"
    split = {k: 0.0 for k in ("thinking", "tools", "helpers", "user", "between", "away", "failed")}
    away, end, after = [], None, set()
    for e in events:
        if e["kind"] != "turn":
            after.add(e["kind"])
            continue
        if end is not None:
            gap = (e["t0"] - end) / 1000
            if gap > AWAY:
                split["away"] += gap
                away.append((end, e["t0"]))
            else:
                split["user" if "user" in after else "helpers" if "helper" in after else "between"] += max(gap, 0)
        if e["failed"]:
            split["failed"] += ((e["tc"] or e["ts"] or e["t0"]) - e["t0"]) / 1000
        else:
            split["thinking"] += e["think"]
            split[e["wait"]] += e["run"]
        end, after = e["tc"] or e["ts"] or e["t0"], set()
    good = [t for t in turns if not t["failed"]]
    med_think = statistics.median(t["think"] for t in good) if good else 0
    med_out = statistics.median(t["out"] for t in good) if good else 0
    # A turn that fails while a question is open was interrupted by the user, not the network.
    network = [t for t in turns if t["wait"] != "user" and (
        t["finish"] == "error" or (t["think"] > 3 * med_think and t["out"] < med_out))]
    return turns, split, away, network, med_think


def segments(cmd):
    return re.split(r"&&|\|\||[;|\n]", cmd)


def runs(cmd):
    """The parts of a shell command that run a script (not --help, not text that only mentions one)."""
    return " ; ".join(s for s in segments(cmd) if RUN_RE.search(s) and not re.search(r"\s(--help|-h)\b", s))


def steps(turns):
    """Turns per step: the most recent demo.py command, else the fallback phase from script names."""
    use_demo = any(DEMO_RE.search(runs(x["cmd"])) for t in turns for x in t["tools"])
    first = "before demo.py" if use_demo else "before scripts"
    order = [first] + (DEMO_STEPS if use_demo else [p for p, _ in PHASES])
    label, seen_cut, counts = first, False, {}
    for t in turns:
        for x in t["tools"]:
            cmd = runs(x["cmd"])
            if use_demo:
                m = list(DEMO_RE.finditer(cmd))
                if m:
                    label = m[-1].group(1)
                continue
            hits = [(m.start(), name) for name, rx in PHASES for m in rx.finditer(cmd)]
            hits = [h for h in hits if h[1] != "prepare" or not seen_cut]
            if hits:
                label = max(hits)[1]
                seen_cut = seen_cut or label != "prepare"
        counts[label] = counts.get(label, 0) + 1
    return {k: counts[k] for k in order if k in counts}, use_demo


def rule_breaks(events):
    turns = [e for e in events if e["kind"] == "turn"]
    found = {k: [] for k in ("--help on skill scripts", "reading skill source", "single-frame ffmpeg grabs",
                             "image opens", "hand edits of demo.config.js", "status-only turns",
                             "one image per turn", "blocked calls")}
    last, prev_kind = turns[-1] if turns else None, None
    for e in events:
        if e["kind"] != "turn":
            prev_kind = e["kind"]
            continue
        hit = lambda k: found[k].append(e["t0"])
        for x in e["tools"]:
            cmd, path = x["cmd"], x["path"] or ""
            in_skill = "product-demo-video" in cmd
            parts = segments(cmd)
            if any(HELP_RE.search(s) for s in parts):
                hit("--help on skill scripts")
            if (x["name"] in ("read", "grep") and SKILL_SRC.search(path)) or \
                    any(READERS.search(s) and (SKILL_SRC.search(s) or in_skill and SKILL_REL.search(s)) for s in parts):
                hit("reading skill source")
            if FRAME_RE.search(cmd):
                hit("single-frame ffmpeg grabs")
            if is_image_read(x):
                hit("image opens")
            if (x["name"] in ("write", "edit") and path.endswith("page/demo.config.js")) or \
                    CONFIG_SHELL.search(cmd) or CONFIG_PY.search(cmd):
                hit("hand edits of demo.config.js")
            if x["status"] == "error" and any(b in x["err"] + x["out"] for b in BLOCKED):
                hit("blocked calls")
        if e["text"] and not e["tools"] and e is not last and prev_kind != "user":
            hit("status-only turns")
        if len(e["tools"]) == 1 and is_image_read(e["tools"][0]):
            hit("one image per turn")
        prev_kind = "turn"
    return found


def helper_line(h):
    events = [e for e in h["events"]]
    turns, split, _, _, _ = analyse(events)
    active = sum(v for k, v in split.items() if k not in ("away", "failed"))
    images = sum(1 for t in turns for x in t["tools"] if is_image_read(x))
    return turns, active, split["thinking"], images


# --- report ----------------------------------------------------------------------------------------------

def report(events, helpers):
    turns, split, away, network, med = analyse(events)
    if not turns:
        sys.exit("no assistant turns in range")
    out = []
    models = sorted({t["model"] for t in turns if t["model"]})
    active = sum(v for k, v in split.items() if k not in ("away", "failed"))
    images = sum(1 for t in turns for x in t["tools"] if is_image_read(x))
    cost = sum(t["cost"] for t in turns)
    hcost = sum(t["cost"] for h in helpers for t in h["events"] if t["kind"] == "turn")
    out.append(f"Run {clock(turns[0]['t0'])}–{clock(turns[-1]['tc'] or turns[-1]['t0'])}  model: {', '.join(models) or '?'}")
    money = f"cost ${cost:.2f} (+ helpers ${hcost:.2f})" if cost else "cost n/a"
    out.append(f"turns {len(turns)} | active {active / 60:.1f} min | {money} | "
               f"peak context {max(t['ctx'] for t in turns) / 1000:.0f}K | images opened {images}")
    out.append("")
    out.append("Time split (min)")
    out.append(f"  thinking {split['thinking'] / 60:.1f} (median {med:.0f} s/turn) | scripts/tools {split['tools'] / 60:.1f}"
               f" | waiting on helpers {split['helpers'] / 60:.1f} | waiting on user {split['user'] / 60:.1f}"
               f" | between turns {split['between'] / 60:.1f}")
    failed = [t for t in turns if t["failed"]]
    out.append(f"  excluded: away {split['away'] / 60:.1f} ("
               + (", ".join(f"{clock(a)}–{clock(b)}" for a, b in away) or "none")
               + f"), failed turns {split['failed'] / 60:.1f} ({len(failed)} turns)")
    if network:
        out.append("  possibly network: " + ", ".join(
            f"{clock(t['t0'])} {'error' if t['finish'] == 'error' else 'slow %.0fs' % t['think']}" for t in network[:8])
            + (f" (+{len(network) - 8})" if len(network) > 8 else ""))
    out.append("")
    counts, use_demo = steps(turns)
    out.append("Turns per step" + ("" if use_demo else " (no demo.py; phases from script names)"))
    out.append("  " + " | ".join(f"{k} {v}" for k, v in counts.items()))
    over = len(turns) - BUDGET
    out.append(f"Budget: {len(turns)} turns vs {BUDGET}: " + (f"OVER by {over}" if over > 0 else "PASS"))
    out.append("")
    out.append("Rule breaks")
    for k, times in rule_breaks(events).items():
        first = ", ".join(clock(t) for t in times[:4]) + (" …" if len(times) > 4 else "")
        out.append(f"  {k}: {len(times)}" + (f" ({first})" if times else ""))
    calls = [x for t in turns for x in t["tools"] if x["name"] == "subagent"]
    resumed = sum(1 for x in calls if x["input"].get("sessionID") or x["input"].get("resume"))
    multi = [x["input"].get("description", "") for x in calls if MULTI_CHAPTER.search(x["input"].get("description", ""))]
    out.append(f"  helpers: {len(calls) - resumed} started, {resumed} resumed; briefs covering several chapters: "
               + (", ".join(f'"{d}"' for d in multi) if multi else "none"))
    out.append("")
    out.append("Helpers (title | minutes | turns | thinking min | images)")
    room = LINES - len(out) - 1
    rows = [(h["title"],) + helper_line(h) for h in helpers]
    for title, ht, active_h, think, img in rows[:room if len(rows) > room else len(rows)]:
        out.append(f"  {title[:40]:40} {active_h / 60:5.1f} {len(ht):4} {think / 60:5.1f} {img:3}")
    if len(rows) > room:
        rest = rows[room:]
        out.append(f"  +{len(rest)} more: {sum(len(r[1]) for r in rest)} turns, {sum(r[4] for r in rest)} images")
    if not rows:
        out.append("  none")
    return "\n".join(out[:LINES])


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("run", help="OpenCode session id (ses_...) or a Claude Code transcript .jsonl")
    ap.add_argument("--since", help='local time "YYYY-MM-DD HH:MM"; ignore earlier messages (OpenCode)')
    a = ap.parse_args()
    if a.run.endswith(".jsonl"):
        events, helpers = load_claude(a.run)
    else:
        events, helpers = load_opencode(a.run, a.since)
    print(report(events, helpers))


if __name__ == "__main__":
    main()
