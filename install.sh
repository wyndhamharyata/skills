#!/usr/bin/env bash
# Install the skills in this repo for Claude Code, Codex, OpenCode, pi, or any agent that reads a skills folder.
# Symlinks by default, so `git pull` updates every agent at once.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$REPO/skills"
MARK=".installed-from"

usage() {
  cat <<'EOF'
Usage: ./install.sh [options] [skill ...]

Installs every skill in skills/ (or only the ones named) into each agent's skills folder.

  Agent      Folder                    Also read by
  claude     ~/.claude/skills          OpenCode
  codex      ~/.agents/skills          OpenCode, pi
  opencode   ~/.agents/skills
  pi         ~/.agents/skills

Options:
  --agent LIST    claude, codex, opencode, pi or all (default: all). Comma-separated or repeated.
  --dir PATH      also install into PATH, for any other agent that reads <PATH>/<skill>/SKILL.md
  --project DIR   install into DIR/.claude/skills and DIR/.agents/skills instead of your home folder
  --copy          copy the files instead of symlinking (use when this clone won't stay put)
  --force         replace an existing skill of the same name (the old one is kept as <name>.bak-<time>)
  --uninstall     remove the links and copies this script made
  --no-check      skip each skill's dependency check
  --dry-run       print what would happen
  --list          list the skills in this repo
  -h, --help      show this help
EOF
}

agents="" dirs=() base="$HOME" mode=link force=0 uninstall=0 check=1 dry=0 picked=()
while [ $# -gt 0 ]; do
  case "$1" in
    --agent) agents="$agents,${2:?--agent needs a value}"; shift 2 ;;
    --agent=*) agents="$agents,${1#*=}"; shift ;;
    --dir) dirs+=("${2:?--dir needs a path}"); shift 2 ;;
    --project) base="$(cd "${2:?--project needs a folder}" && pwd)"; shift 2 ;;
    --copy) mode=copy; shift ;;
    --force) force=1; shift ;;
    --uninstall) uninstall=1; shift ;;
    --no-check) check=0; shift ;;
    --dry-run) dry=1; shift ;;
    --list) for d in "$SRC"/*/; do [ -f "$d/SKILL.md" ] && basename "$d"; done; exit 0 ;;
    -h|--help) usage; exit 0 ;;
    -*) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    *) picked+=("$1"); shift ;;
  esac
done

targets=()
add_target() { local t; for t in ${targets[@]+"${targets[@]}"}; do [ "$t" = "$1" ] && return; done; targets+=("$1"); }
[ -z "$agents" ] && [ ${#dirs[@]} -eq 0 ] && agents=all
IFS=',' read -r -a agent_list <<< "${agents#,}"
for a in ${agent_list[@]+"${agent_list[@]}"}; do
  case "$a" in
    "") ;;
    all) add_target "$base/.claude/skills"; add_target "$base/.agents/skills" ;;
    claude) add_target "$base/.claude/skills" ;;
    codex|opencode|pi) add_target "$base/.agents/skills" ;;
    *) echo "Unknown agent: $a (use claude, codex, opencode, pi or all; --dir for anything else)" >&2; exit 2 ;;
  esac
done
for d in ${dirs[@]+"${dirs[@]}"}; do add_target "$d"; done

skills=()
if [ ${#picked[@]} -gt 0 ]; then
  for s in "${picked[@]}"; do
    [ -f "$SRC/$s/SKILL.md" ] || { echo "No skill named '$s' in $SRC (try --list)" >&2; exit 2; }
    skills+=("$s")
  done
else
  for d in "$SRC"/*/; do [ -f "$d/SKILL.md" ] && skills+=("$(basename "$d")"); done
fi

run() { if [ $dry -eq 1 ]; then echo "  would: $*"; else "$@"; fi; }

# True when $1 was put there by this script (a link into this repo, or a copy carrying our marker).
ours() {
  if [ -L "$1" ]; then
    case "$(readlink "$1")" in "$SRC"/*) return 0 ;; esac
    return 1
  fi
  [ -f "$1/$MARK" ] && [ "$(cat "$1/$MARK")" = "$SRC" ]
}

for target in "${targets[@]}"; do
  echo "$target"
  for s in "${skills[@]}"; do
    dest="$target/$s"
    if [ $uninstall -eq 1 ]; then
      if [ -e "$dest" ] || [ -L "$dest" ]; then
        if ours "$dest"; then run rm -rf "$dest"; [ $dry -eq 1 ] || echo "  removed $s"; else echo "  kept $s (not installed by this script)"; fi
      fi
      continue
    fi
    if [ -e "$dest" ] || [ -L "$dest" ]; then
      if ours "$dest"; then
        run rm -rf "$dest"
      elif [ $force -eq 1 ]; then
        run mv "$dest" "$dest.bak-$(date +%Y%m%d%H%M%S)"
      else
        echo "  skipped $s: $dest already exists and isn't from this repo (use --force to replace it)"
        continue
      fi
    fi
    run mkdir -p "$target"
    if [ $mode = link ]; then
      run ln -s "$SRC/$s" "$dest"
    else
      run cp -R "$SRC/$s" "$dest"
      if [ $dry -eq 0 ]; then printf '%s' "$SRC" > "$dest/$MARK"; fi
    fi
    verb="$([ $mode = link ] && echo linked || echo copied)"
    if [ $dry -eq 1 ]; then echo "  would have ${verb} $s"; else echo "  $verb $s"; fi
  done
done

if [ $uninstall -eq 0 ] && [ $check -eq 1 ] && [ $dry -eq 0 ]; then
  for s in "${skills[@]}"; do
    doctor="$SRC/$s/scripts/doctor.sh"
    if [ -x "$doctor" ]; then
      echo
      echo "Checking what $s needs:"
      "$doctor" || echo "  ($s is installed; install the missing tools above before using it)"
    fi
  done
fi

if [ $uninstall -eq 0 ] && [ $dry -eq 0 ]; then
  echo
  echo "Done. Start a new session (or run /reload in pi) for the agents to pick up new skills."
fi
