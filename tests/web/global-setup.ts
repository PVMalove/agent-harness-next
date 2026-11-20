/* Starts tests/web/serve_console.py once for all specs and exports its address and token. */
import { spawn } from "node:child_process";
import { resolve } from "node:path";
import { createInterface } from "node:readline";

const REPO = resolve(__dirname, "../..");

export default async function globalSetup(): Promise<() => Promise<void>> {
  const python = process.env.HARNESS_PYTHON ?? resolve(REPO, ".harness/.venv/bin/python");
  const env = { ...process.env };
  delete env.HARNESS_CONSOLE_LANG;
  const server = spawn(python, ["-m", "tests.web.serve_console"], {
    cwd: REPO,
    env,
    stdio: ["pipe", "pipe", "inherit"],
  });
  const line = await new Promise<string>((done, fail) => {
    const lines = createInterface({ input: server.stdout! });
    lines.once("line", done);
    server.once("exit", (code) => fail(new Error(`serve_console exited with ${code}`)));
    server.once("error", fail);
  });
  const { port, token } = JSON.parse(line) as { port: number; token: string };
  process.env.CONSOLE_BASE_URL = `http://127.0.0.1:${port}`;
  process.env.CONSOLE_TOKEN = token;
  return async () => {
    const exited = new Promise((done) => server.once("exit", done));
    server.stdin!.end();
    server.kill("SIGTERM");
    await exited;
  };
}
