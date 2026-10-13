# Working in this repo

This repo is a collection of agent skills that has to work unchanged in Claude Code, Codex, OpenCode and pi.

- Each skill lives in `skills/<name>/` with a `SKILL.md`. Its frontmatter `name` equals the folder name
  (lowercase-kebab-case, 64 characters or fewer) and `description` (1024 characters or fewer) says what it
  does and when to use it.
- Keep skills agent-neutral. Don't name one agent's tools (for example "the question tool"), and don't
  hard-code paths from this machine. Refer to bundled files by paths relative to the skill folder.
- Optional `metadata.short-description` gives the one-line summary used in the README and the marketplace.
- Optional `compatibility` frontmatter states what the skill needs to run. An executable
  `scripts/doctor.sh` checks for it, and `install.sh` runs that check.
- After adding, renaming or changing a skill's description, run `python3 tools/catalog.py`. It regenerates
  `.claude-plugin/marketplace.json` and the README table; never edit those by hand.
- Before committing: `python3 tools/catalog.py --check` and `bash -n install.sh`.
