# Skills

My agent skills. Each one is a folder with a `SKILL.md` that follows the open
[Agent Skills spec](https://agentskills.io/specification), so the same files work in Claude Code, Codex,
OpenCode, pi and any other agent that reads skills.

<!-- skills:start -->
| Skill | What it does |
| --- | --- |
| [`product-demo-video`](skills/product-demo-video/SKILL.md) | Turn a screen recording into an auto-playing product demo page (7 styles, 4 tempos) to narrate in Loom, plus an MP4 with music. |
<!-- skills:end -->

## Install

### Every agent at once (recommended)

```sh
gh repo clone wyndhamharyata/skills ~/side_project/skills   # or git clone
~/side_project/skills/install.sh
```

This links each skill into the folders the agents read, then checks each skill's tools (ffmpeg and so on).
The links point back at this clone, so `git pull` updates every agent.

| Agent | Folder the script uses | Notes |
| --- | --- | --- |
| Claude Code | `~/.claude/skills` | Run as `/product-demo-video`, or let Claude pick it |
| Codex | `~/.agents/skills` | Run as `$product-demo-video`, or let Codex pick it |
| OpenCode | `~/.agents/skills` | Also reads `~/.claude/skills`; mention as `@product-demo-video` |
| pi | `~/.agents/skills` | Run as `/skill:product-demo-video`; `/reload` in a running session |

Useful options (`./install.sh --help` lists them all):

```sh
./install.sh --agent claude,pi              # only some agents
./install.sh product-demo-video             # only some skills
./install.sh --project ~/work/my-app        # into <project>/.claude/skills and <project>/.agents/skills
./install.sh --dir ~/.some-agent/skills     # any other agent that reads <dir>/<skill>/SKILL.md
./install.sh --copy                         # copy instead of link
./install.sh --uninstall                    # remove what the script installed
```

The script never overwrites a skill it didn't install. Use `--force` to replace one (the old copy is kept as a backup).

### Agent-native installs

Use these instead of the script if you prefer each agent's own package manager. Don't use both for the same
agent, or it will load each skill twice.

**Claude Code** (plugin marketplace; each skill is its own plugin):

```sh
claude plugin marketplace add wyndhamharyata/skills
claude plugin install product-demo-video@wyndham-skills
```

Plugin skills are namespaced, so it runs as `/product-demo-video:product-demo-video`. Update with
`claude plugin marketplace update wyndham-skills`.

**pi** (package):

```sh
pi install git:github.com/wyndhamharyata/skills
```

**OpenCode** (config, no links): add the folder to `skills` in `~/.config/opencode/opencode.json`:

```jsonc
{ "skills": ["~/side_project/skills/skills"] }
```

**Codex** reads `~/.agents/skills`, so use the script (`--agent codex`) or link a skill there yourself.

## Add a skill

1. Create `skills/<name>/SKILL.md`. The folder name must match the frontmatter `name` and be lowercase-kebab-case.
   Put helper scripts in `scripts/`, docs in `references/` and templates in `assets/`.
2. Optional: add an executable `scripts/doctor.sh` that checks the tools the skill needs. `install.sh` runs it.
3. Run `python3 tools/catalog.py`. It validates every skill and regenerates the table above and
   `.claude-plugin/marketplace.json`. CI runs it with `--check`.
4. Commit, push, then `./install.sh <name>` (existing links pick up edits on their own).

## Layout

```
skills/<name>/SKILL.md          the skill (plus scripts/, references/, assets/)
install.sh                      link or copy skills into agent folders
tools/catalog.py                validate skills, regenerate the marketplace and the table above
.claude-plugin/marketplace.json Claude Code marketplace (generated)
package.json                    pi package manifest
```
