# run-test.sh — an isolated run of one test

## 1. Name and localization

- **Source script:** [`harness/project/hooks/run-test.sh`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/run-test.sh),
  the core — [`harness/health/isolated_runner.py`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/health/isolated_runner.py)
- **Translation:** an isolated runner of one selected test.

## 2. Full description

`run-test.sh` is not an event hook: the `engineering-suite` installation copies it to
`.claude/hooks/run-test.sh` but does not wire it into `settings.local.json`. The script runs one test,
selected by identifier, inside bubblewrap, so the test and all of its child processes cannot
change the production code, `.git`, and the runner configuration. The script itself does nothing but
find Python and the repository root (two levels above `.claude/hooks/`) and load the core from
`.harness/health/` through `python3 -I -B`: the `PYTHON*` variables, the user site, the current
directory, and bytecode writing are disabled, and it imports and executes nothing from the write zones
of the runner. There is no run mode without isolation: any failure before the test starts gives a
refusal.

**Settings.** The runner reads only the `.harness/project.json` of the checkout and accepts from the
CLI only the test identifier, so the caller cannot widen the write zone or substitute the command.
Both fields are optional and are checked by the same functions as in `harness health`
(`test_paths_problems`, `test_runner_problems` in `harness/health/project_files.py`):

- `test_paths` — a non-empty list of unique relative globs without `..` segments, the test paths and
  the only write zone of the test author;
- `test_runner` — the object `{"command": [...]}`: an argv without a shell, made of non-empty strings,
  in which exactly one element equals `{test_id}`, and this element is not the first.

```json
"test_paths": ["tests/**"],
"test_runner": {"command": ["python3", "-m", "unittest", "{test_id}"]}
```

A new project gets these fields through `harness init` flags; the `project.json.tmpl` template writes
them only on flags, and `init` rejects an invalid value before writing the files:

```bash
harness init . --capability engineering-suite \
  --test-path 'tests/**' \
  --test-runner-command 'python3 -m unittest {test_id}'
```

Without the flags the fields are absent, and the runner refuses with `test_paths_missing` or
`test_runner_missing`. There is no default value: it would enable the test author in every new project
and would assume the layout and the stack of the project. The enabling of the subagent and the project
opt-in are moved to a separate task.

**Write zones.** The schema accepts any relative glob, but the runner mounts for writing only entries
of the form `<directory>/**` and refuses with `write_zone_rejected` for the rest. Each entry must pass
all checks:

- the other segments are literal: without `*?[]{}` and `\`, non-empty, not `.` and not `..`;
- the first segment is not `.git`, `.harness`, `.claude`, `.agents`, or `.codex` (case-insensitive), and
  the zone does not coincide with the root;
- the directory exists, no path component from the checkout root is a symlink, and `realpath`
  matches the path itself;
- the zones are not nested in each other: otherwise a test of one run could replace the directory of
  an inner zone with a symlink to production before the mount in a parallel run;
- the zone has no regular file with several hard links: a hardlink to a production file created in
  advance would give alternative access to it.

A symlink inside a zone is safe: a write through it lands in the read-only mount and gets `EROFS`.
Outside the zones the test writes to `/tmp` and to the `cache/` and `reports/` directories, fresh for
each run. Like the hermetic `/tmp` in Bazel, `/tmp` is not the host directory but its own empty
directory `<run>/tmp-*` for each bwrap run (probe, build, test); after the run it is deleted. Inside,
the path stays short, `/tmp`, so database sockets fit into the AF_UNIX limit of 107 bytes. There is no
shared cache between runs: through it a test would slip the `.pyc` of a production module to the next
run.

**Sandbox.** The flag set from ADR 0014 is not weakened:

```text
bwrap --ro-bind / / --dev /dev --proc /proc --bind <run>/tmp-* /tmp --tmpfs /run
      --bind <зона> <зона> ... --bind <run>/cache <run>/cache --bind <run>/reports <run>/reports
      --chdir <repo> --unshare-all --die-with-parent --new-session --cap-drop ALL
      --json-status-fd <fd> -- <test_runner.command с id вместо {test_id}>
```

The identifier is substituted as one argv element, and no shell is used. `bwrap` is looked up in
`PATH`; the isolation working is proven by the probe, not by the presence of the binary. The test gets
only `PATH`, `LANG`, `LC_ALL`, `LC_CTYPE`, and `TZ` from the environment of the caller, plus
`HOME=/tmp`, `TMPDIR=/tmp`, `XDG_CACHE_HOME`, `PYTHONPYCACHEPREFIX`, `HARNESS_TEST_CACHE_DIR` (the
`cache/` directory), and `HARNESS_TEST_REPORT_DIR` (the `reports/` directory). The test does not see
the other variables, including tokens. The test timeout is 300 seconds; when it expires, the runner
terminates the process group, and `--die-with-parent` terminates the whole tree inside the sandbox.

**Host sockets.** A read-only mount does not forbid `connect()` to a Unix socket. `/run` (which
`/var/run` references) holds the sockets of host services: the system and session D-Bus, the systemd
user manager in `/run/user/<uid>`, container engines. Through such a socket a test would start a
process outside the sandbox with full write rights, so an empty tmpfs is mounted over `/run`, as over
`/tmp`. Abstract sockets are unavailable to the test: `--unshare-all` separates the network namespace.

**Order of checks.** The runner checks the identifier, then the settings and the zones, then the host:
Linux, `bwrap` in `PATH`, a checkout and a run directory outside `/tmp`, `/run`, `/dev`, and `/proc`,
which the sandbox replaces with its own. Then it creates the run directory and performs the probe with
the same set of mounts: creating a file in the checkout root must get exactly `EROFS`, `/run` and
`/var/run` must be empty or absent, a write to `cache/` must succeed, and both artifacts are deleted.
Only after that the test starts. If bwrap did not report `child-pid`, the sandbox did not come up, and
the result is the refusal `sandbox_failed`, not a test failure. A diff check of the files does not
serve as protection, and the runner does not perform it.

**Local artifacts.** The directory `.harness/.sandboxes/runs/isolated-test-<run_id>/` contains
`log.txt` (stdout and stderr of the probe and the test, a ceiling of 4 MiB with a truncation marker;
the runner writes it outside the sandbox), `cache/`, and `reports/`. Only `cache/` and `reports/` are
mounted into the sandbox. `harness cleanup` deletes old runs by age.

**Support boundary.** Linux and bubblewrap 0.9.0+ with unprivileged user namespaces are supported. On
Windows and macOS the runner answers `isolation_unavailable` with `platform`. A checkout inside `/tmp`
or `/run` is not supported: the test would not see it, and the runner refuses with
`checkout_masked`. If `/var/run` is a separate non-empty directory rather than a link to `/run`, the
runner refuses with `probe_failed`. The runner hides only the sockets in `/run` and `/tmp`: a service
that listens on a socket at another path visible to the test (for example, in the home directory) must
not start processes or write files on a request through that socket.
Only zones of the form `<directory>/**` are supported: a project with tests next to the sources (for
example, `**/*_test.go`) gets `write_zone_rejected`.

**Boundary with other tasks.** The runner protects the checkout from the test process and its
descendants, but not from the calling agent outside the sandbox. The test-author subagent, its scoped
guard, the preflight with a canary check of the guard, and the project opt-in are moved to a separate
task; `--probe` gives the preflight only the isolation status. The section below describes the
preparation of build artifacts and the separate test database.

## 3. Contracts

- **Input:** `run-test.sh <test-id>` or `run-test.sh --probe`; any other arguments give the refusal
  `test_id_invalid`. The identifier matches `^[A-Za-z0-9_][A-Za-z0-9_.:/\[\]-]{0,199}$`
  (a pytest node id, a unittest dotted id): a leading `-`, a space, `;`, `$`, a backtick, and a newline
  are rejected. The settings are `test_paths` and `test_runner` from `.harness/project.json`.
- **Output:** one JSON line no longer than 512 bytes with fixed keys:
  - `test_id` — the identifier, or `null` for an invalid one;
  - `result` — `passed`, `failed`, `timeout`, or `refused`;
  - `reason` — `test_passed`, `test_failed`, `timeout`, or the refusal reason;
  - `detail` — only for `isolation_unavailable`, otherwise `null`;
  - `exit_code` — the test code, or `null`;
  - `run_id` — the hex identifier of the run directory, or `null`.

  The test output, absolute paths, and environment variables do not get into the line, and stderr is
  empty.
- **Refusal reasons (a closed set):**
  - `runner_unavailable` — there is no Python, `.harness/health` does not load, or the runner crashed;
  - `test_id_invalid` — an invalid identifier or extra arguments;
  - `config_invalid` — `project.json` is unreadable or the fields do not pass the check;
  - `test_paths_missing`, `test_runner_missing` — the field is not set;
  - `write_zone_rejected` — the write zone did not pass the checks;
  - `build_failed`, `build_timeout` — the protected preparation ended with an error or a timeout;
  - `database_unavailable` — the selected test could not get a separate database prepared;
  - `isolation_unavailable` with `detail`: `platform`, `bwrap_missing`, `checkout_masked`,
    `sandbox_failed`, or `probe_failed`.
- **Exit codes:** `0` — the test passed; `1` — the test failed or exceeded the timeout; `3` — a refusal,
  the test did not run.
- **`--probe`:** validates the existing `project.json` and the mount plans of both phases without
  performing the build, the server, or the test. Without `project.json` only the host check remains.
  Prints `{"status":"ok"}` with code `0`, or `status: unavailable` with code `3` and a fixed
  configuration/zone reason, `isolation_unavailable` with `detail`, or `runner_unavailable`.
  The probe run directory is deleted.

## Source

[run-test.sh](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/run-test.sh),
[isolated_runner.py](https://github.com/PVMalove/agent-harness-next/blob/master/harness/health/isolated_runner.py),
[project_files.py](https://github.com/PVMalove/agent-harness-next/blob/master/harness/health/project_files.py),
ADR 0014

### Build and test database

The optional `test_runner.build` contains exactly `command` (a non-empty argv without `{test_id}`)
and `artifact_paths` (unique `<directory>/**`). The directories exist in advance and are empty. The
runner mounts fresh run directories on these paths: for writing during the build, and read-only during
the test. The sources and `test_paths` are read-only during the build; the command runs without a
shell inside the verified sandbox. The runner rejects non-empty directories and does not clear them.

The optional `test_runner.database` contains exactly `engine`, `test_ids`, `command`, and
`ready_command`. `engine` names the production engine; `test_ids` are unique `fnmatchcase` selectors.
Only matching tests get a fresh database instance inside the sandbox, without TCP and without access
to host services. `command` starts the server in the foreground, and `ready_command` checks readiness;
both commands are a non-empty argv without `{test_id}`. They get `HARNESS_TEST_DATABASE_DIR` and
`HARNESS_TEST_DATABASE_SOCKET_DIR` in a private `/tmp`. The project wrapper reads these variables
directly; no shell substitution is performed in the argv. SQL, transactions, and constraints are
checked on the production engine; pure domain logic does not need a database.

The CLI adds these groups only on complete sets of `--test-build-command`, `--test-artifact-path`
and `--test-database-engine`, `--test-database-test-id`, `--test-database-command`,
`--test-database-ready-command`, together with `--test-runner-command`. The absence of the groups keeps
the previous behavior. `test_paths` remains the only `Write`/`Edit` zone of the test author.

A preparation with a non-zero code gives the refusal `build_failed`, and its timeout gives
`build_timeout`. A failed server start or a missing readiness within 15 seconds gives
`database_unavailable`; the selected test does not start in this case. The server, the readiness
check, and the test work in one isolated environment. The server and its descendants terminate after
the test or an error; the external runner timeout limits the whole database session together with the
test to 300 seconds. The output of all commands goes to a bounded local log. The private result channel
of the helper is unavailable to child commands, so the test output and its code 3 cannot fake a
database refusal.

The clean-room scenario `scripts/clean_room/isolated_test_runner_build_db.py` is called by the existing
runner scenario and separately through `python -m scripts.clean_room.isolated_test_runner_build_db`.
It checks a real C compiler and PostgreSQL (`postgres`, `initdb`, `psql`, `pg_isready` in
`PATH`): two fresh clusters, server identity, SQL, rollback, CHECK/PK, and the absence of TCP.
Missing binaries are explicitly marked as missing proof.
`HARNESS_REQUIRE_TEST_DATABASE=1` turns the absence of a real database into an error;
`HARNESS_REQUIRE_TEST_SANDBOX=1` requires the sandbox and the compiler. Stand-in processes in unit tests
check only the lifecycle and do not replace this proof.

The scenario `scripts/clean_room/fast_implement_route.py` runs the short route `/fast-implement`
through the same installed runner with a scripted model stand-in: the cycle with the author at an agreed
seam, the fallback to the regular `/tdd` when a hook fails, when the isolation is unavailable, or when
the project has no `test_paths`, and also the refusals `build_failed` and `database_unavailable`, which
do not count as Red. It does not replace a check on a real Claude Code (`make test-author-probe`) and does not
measure the quality of the tests the model writes.
