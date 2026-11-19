# Developer: rerunning only the failed tests

Use this only when the project has `scripts/verify.py` with `--worktree-cache`. Otherwise rerun a
failed test by its node id through the bounded wrapper, as the core of the role says.

After a failure, rerun what failed, with your own worktree cache, instead of the whole suite. Run it from the checkout you work in, through the bounded wrapper:

- `scripts/verify.py --worktree-cache --only tests` keeps the mypy and pytest caches and the previous
  JUnit report in `.harness/.sandboxes/cache/<worktree-id>/<environment_fingerprint>/`. The cache of
  another worktree or of another `environment_fingerprint` is never read, and the clean-room QA run
  starts cold: only a clean-room run sets `HARNESS_VERIFY_COLD`, which refuses `--worktree-cache`; the
  bounded wrapper runs locally, is not cold and accepts the flag.
- `scripts/verify.py --worktree-cache --failed-only` reruns the pytest stage alone, with the exact
  failed nodeids of that previous JUnit report. A renamed or vanished nodeid switches the run to
  `focused`: the surviving test files of the failed tests run whole. An empty selection (no previous
  report, no failed test or no surviving file) and a pytest run that collects nothing are `not_run`
  with exit code 5, never a pass. `--failed-first` only reorders a full run: it is never failed-only
  and is recorded as the `full` selection.
- `--evidence-dir <dir>` writes `stage-evidence.v1` for the mypy, pytest and clean-room stages:
  separate stdout and stderr files with their sha256, exit code, duration, failed nodeids and
  `not_run` for every stage the run did not reach.

A failed-only, focused or cached result is a diagnostic of your session. It proves only the selected
tests, never replaces the brief's `verification_commands` in `checks_run`, which you run verbatim
before reporting, and never authorizes a publish: only the full clean-room QA run on the final SHA
does.
