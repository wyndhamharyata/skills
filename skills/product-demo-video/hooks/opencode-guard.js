// OpenCode plugin for the product-demo-video skill: before each tool call, while a demo project is active,
// asks scripts/guard.py whether the call breaks the skill's rules, and blocks it with guard.py's message.
// install.sh links it into ~/.config/opencode/plugins/ (or <project>/.opencode/plugins/ with --project).

import { spawnSync } from "node:child_process";
import { existsSync, readdirSync, realpathSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ACTIVE = join(homedir(), ".cache", "product-demo-video", "active");
const GUARD = join("skills", "product-demo-video", "scripts", "guard.py");

// Beside this file in the repo when linked; in the installed skill folders when copied.
const findGuard = () => {
  const here = dirname(realpathSync(fileURLToPath(import.meta.url)));
  return [
    join(here, "..", "scripts", "guard.py"),
    join(here, "..", "..", ".agents", GUARD),
    join(here, "..", "..", ".claude", GUARD),
    join(homedir(), ".agents", GUARD),
    join(homedir(), ".claude", GUARD),
  ].find((path) => existsSync(path));
};

const guard = (tool, args, cwd) => {
  let active = false;
  try {
    active = readdirSync(ACTIVE).some((name) => name.endsWith(".json"));
  } catch {}
  if (!active) return;
  const script = findGuard();
  if (!script) return;
  const result = spawnSync("python3", [script, "--opencode"], {
    input: JSON.stringify({ tool, args: args ?? {}, cwd: cwd ?? process.cwd() }),
    encoding: "utf8",
    timeout: 5000,
  });
  const message = result.status === 2 ? result.stdout?.trim() : "";
  if (message) throw new Error(message);
};

export default {
  id: "product-demo-video.guard",
  async setup(ctx) {
    await ctx.tool.hook("execute.before", (event) => guard(event.tool, event.input, ctx.location?.directory));
  },
  // OpenCode 1.x
  async server(input) {
    return {
      "tool.execute.before": async (event, output) => guard(event.tool, output.args, input?.directory),
    };
  },
};
