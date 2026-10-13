#!/usr/bin/env python3
"""Validate every skill and regenerate the files that list them.

  python3 tools/catalog.py          # validate, then rewrite .claude-plugin/marketplace.json and the README table
  python3 tools/catalog.py --check  # validate and fail if either file is out of date (CI)

A skill is skills/<name>/SKILL.md with `name` and `description` frontmatter, following the Agent Skills
spec (https://agentskills.io/specification), which Claude Code, Codex, OpenCode and pi all read.
Standard library only.
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(ROOT, "skills")
MARKETPLACE = os.path.join(ROOT, ".claude-plugin", "marketplace.json")
README = os.path.join(ROOT, "README.md")
TABLE_START, TABLE_END = "<!-- skills:start -->", "<!-- skills:end -->"

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MARKET = {
    "name": "wyndham-skills",
    "description": "Wyndham's agent skills",
    "owner": {"name": "Wyndham Haryata", "url": "https://github.com/wyndhamharyata"},
}


def frontmatter(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None
    # Enough YAML for skill frontmatter: scalars, folded/literal blocks, and one level of maps (metadata).
    fields, key = {}, None
    for line in m.group(1).splitlines():
        top = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if top:
            key, value = top.group(1), top.group(2).strip()
            fields[key] = value.strip("\"'") if value not in ("", ">", "|", ">-", "|-") else ({} if value == "" else "")
        elif key and line.startswith((" ", "\t")) and line.strip():
            if isinstance(fields[key], dict):
                sub = re.match(r"^\s+([^:]+):\s*(.*)$", line)
                if sub:
                    fields[key][sub.group(1).strip()] = sub.group(2).strip().strip("\"'")
            else:
                fields[key] = (fields[key] + " " + line.strip()).strip()
    return fields


def summary(skill):
    """One line for listings: metadata.short-description, else the description's first sentence."""
    if skill["short"]:
        return skill["short"]
    first = re.split(r"(?<=\.)\s", skill["description"], maxsplit=1)[0]
    return first if len(first) <= 160 else first[:157].rsplit(" ", 1)[0] + "..."


def load():
    skills, errors = [], []
    for name in sorted(os.listdir(SKILLS)):
        d = os.path.join(SKILLS, name)
        if not os.path.isdir(d) or name.startswith("."):
            continue
        md = os.path.join(d, "SKILL.md")
        if not os.path.exists(md):
            errors.append(f"skills/{name}: missing SKILL.md")
            continue
        fm = frontmatter(md)
        if fm is None:
            errors.append(f"skills/{name}/SKILL.md: missing --- frontmatter ---")
            continue
        n, desc = fm.get("name", ""), fm.get("description", "")
        if n != name:
            errors.append(f"skills/{name}: frontmatter name '{n}' must equal the folder name")
        if not NAME_RE.match(name) or len(name) > 64:
            errors.append(f"skills/{name}: folder name must be lowercase-kebab-case, 64 characters or fewer")
        if not desc:
            errors.append(f"skills/{name}: description is required (agents use it to decide when to load the skill)")
        elif len(desc) > 1024:
            errors.append(f"skills/{name}: description is {len(desc)} characters; the spec allows 1024")
        meta = fm.get("metadata") if isinstance(fm.get("metadata"), dict) else {}
        skills.append({"name": name, "description": desc, "short": meta.get("short-description", "")})
    return skills, errors


def marketplace(skills):
    plugins = [{"name": s["name"], "description": summary(s), "source": "./", "strict": False,
                "skills": [f"./skills/{s['name']}"]} for s in skills]
    # A skill's hooks/hooks.json becomes its plugin's hooks (paths in it are relative to the repo root).
    for p in plugins:
        if os.path.exists(os.path.join(SKILLS, p["name"], "hooks", "hooks.json")):
            p["hooks"] = f"./skills/{p['name']}/hooks/hooks.json"
    return json.dumps({**MARKET, "plugins": plugins}, indent=2, ensure_ascii=False) + "\n"


def readme(skills, current):
    rows = ["| Skill | What it does |", "| --- | --- |"]
    rows += [f"| [`{s['name']}`](skills/{s['name']}/SKILL.md) | {summary(s).replace('|', '/')} |" for s in skills]
    block = f"{TABLE_START}\n" + "\n".join(rows) + f"\n{TABLE_END}"
    return re.sub(re.escape(TABLE_START) + ".*?" + re.escape(TABLE_END), lambda _: block, current, flags=re.S)


def main():
    check = "--check" in sys.argv[1:]
    skills, errors = load()
    for e in errors:
        print("error:", e)
    if errors:
        sys.exit(1)

    with open(README, encoding="utf-8") as f:
        old_readme = f.read()
    old_market = open(MARKETPLACE, encoding="utf-8").read() if os.path.exists(MARKETPLACE) else ""
    new_market, new_readme = marketplace(skills), readme(skills, old_readme)

    stale = [p for p, old, new in ((MARKETPLACE, old_market, new_market), (README, old_readme, new_readme)) if old != new]
    if check:
        for p in stale:
            print(f"out of date: {os.path.relpath(p, ROOT)} (run python3 tools/catalog.py)")
        sys.exit(1 if stale else 0)
    os.makedirs(os.path.dirname(MARKETPLACE), exist_ok=True)
    for p, content in ((MARKETPLACE, new_market), (README, new_readme)):
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
    print(f"{len(skills)} skill(s) valid; updated " + (", ".join(os.path.relpath(p, ROOT) for p in stale) or "nothing"))


if __name__ == "__main__":
    main()
