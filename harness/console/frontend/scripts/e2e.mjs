// `npm run test:e2e`: builds the SPA, installs Chromium where it can be written, runs Playwright.
// Every run builds dist first, so a spec never runs against a build older than the sources (#1188).
// Arguments after `--` go to `playwright test`.
import { spawnSync } from "node:child_process";
import { accessSync, constants, existsSync, mkdirSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const FRONTEND = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const CONFIG = resolve(FRONTEND, "../../../tests/web/playwright.config.ts");

/** The checkout that owns the git metadata: the main checkout also for an issue worktree. */
function mainCheckout() {
  const result = spawnSync(
    "git",
    ["rev-parse", "--path-format=absolute", "--git-common-dir"],
    { cwd: FRONTEND, encoding: "utf-8" },
  );
  return result.status === 0 ? dirname(result.stdout.trim()) : resolve(FRONTEND, "../../..");
}

function writable(directory) {
  try {
    mkdirSync(directory, { recursive: true });
    accessSync(directory, constants.W_OK);
    return true;
  } catch {
    return false;
  }
}

/** Playwright's own default cache, or the main checkout's sandbox cache when that is read-only. */
export function browsersPath(env = process.env) {
  if (env.PLAYWRIGHT_BROWSERS_PATH) return env.PLAYWRIGHT_BROWSERS_PATH;
  const cache =
    process.platform === "win32"
      ? join(env.LOCALAPPDATA ?? join(homedir(), "AppData", "Local"), "ms-playwright")
      : process.platform === "darwin"
        ? join(homedir(), "Library", "Caches", "ms-playwright")
        : join(env.XDG_CACHE_HOME ?? join(homedir(), ".cache"), "ms-playwright");
  return writable(cache)
    ? cache
    : join(mainCheckout(), ".harness", ".sandboxes", "cache", "ms-playwright");
}

function run(command, args, env) {
  const result = spawnSync(command, args, {
    cwd: FRONTEND,
    env,
    stdio: "inherit",
    shell: process.platform === "win32",
  });
  if (result.status !== 0) process.exit(result.status ?? 1);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const env = { ...process.env, PLAYWRIGHT_BROWSERS_PATH: browsersPath() };
  console.log(`e2e: Playwright browsers in ${env.PLAYWRIGHT_BROWSERS_PATH}`);
  if (!existsSync(env.PLAYWRIGHT_BROWSERS_PATH)) mkdirSync(env.PLAYWRIGHT_BROWSERS_PATH, { recursive: true });
  run("npm", ["run", "build"], env);
  run("npx", ["playwright", "install", "chromium"], env);
  run("npx", ["playwright", "test", "-c", CONFIG, ...process.argv.slice(2)], env);
}
