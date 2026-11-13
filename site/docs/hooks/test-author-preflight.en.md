# test-author-preflight.sh — activation check of test-author

## 1. Name and localization

- **Source script:** [`harness/project/hooks/test-author-preflight.sh`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/test-author-preflight.sh)
- **Translation:** a check that the test author can be enabled without losing protection.

## 2. Full description

`test-author-preflight.sh` is not an event hook: the installation copies it to
`.claude/hooks/test-author-preflight.sh` but does not connect it in `settings.local.json`. The developer
runs it before a call of the test-author subagent. The script prints exactly one line of JSON and always
exits with code 0: `{"status":"ok"}` or `{"status":"disabled","reason":"<reason>"}`. A refusal creates no
orchestration state, and the developer continues the usual route.

**The `--worktree <path>` argument.** The script checks only the checkout where it lives, that is, the
checkout it is started from. The developer calls `test-author-preflight.sh --worktree <worktree
from the brief>` from the worktree it works in; an in-process developer does so through the
`.harness/health/test_author.py run` launcher of its worktree. The answer `{"status":"ok"}`
is possible only if the canonical path (after `cd` and `pwd -P`) matches the checkout of the script;
otherwise the script answers `checkout_mismatch`. A missing, empty, or unresolvable path, as well as
any other arguments (an unknown flag, extra arguments, `--worktree` without a value) give the same
`checkout_mismatch`. The check runs right after the determination of the script root and before the others, and the path
from the argument does not appear in the answer. A call without arguments works as before.

The script checks the conditions and, on the first violation, answers with a fixed reason (the table of conditions and
reasons is in the [guide](../agents/test-author.md), section 3). Supported reasons:
`checkout_mismatch`, `runner_unavailable`, `project_untrusted`, `project_dir_mismatch`,
`claude_code_unsupported`, `agent_missing`,
`scoped_hook_unsupported`, `test_paths_missing`, `test_runner_missing`, `config_invalid`,
`write_zone_rejected`, `guard_hook_unavailable`, `isolation_unavailable`. The answers of the guard and the runner
pass through the list of allowed reasons: any other value is replaced with
`guard_hook_unavailable` or `isolation_unavailable`, so no paths and no text of foreign errors get into the answer.

**Project root.** The script takes the root from `git rev-parse --show-toplevel` of its checkout:
it must match the script's checkout, otherwise the answer is `project_untrusted`. This works the
same in the main checkout, any worktree, Claude Code and Codex. `CLAUDE_PROJECT_DIR` is optional:
Claude Code does not always pass it to Bash. When the variable is set, its canonical path is
compared with the Git root, and a mismatch gives `project_dir_mismatch`: the scoped guard of the
native subagent takes the project from this variable.

**Project trust.** The native mode `claude --print` shows no trust dialog, so the script
reads the decision itself: in `~/.claude.json` (or `$CLAUDE_CONFIG_DIR/.claude.json`),
`hasTrustDialogAccepted: true` must be set for the exact checkout path or for the repository's
main checkout when the checkout is its linked worktree. The main checkout is the parent of
`git rev-parse --git-common-dir`; it must list the checkout in `git worktree list`. A missing
file, broken JSON, foreign projects, trust given only to a parent directory, an unregistered
directory, and any value except the boolean `true` give `project_untrusted`. This is the safe
direction of the error (ADR 0033).

**Claude Code modes.** The variables `CLAUDE_CODE_SIMPLE` and `CLAUDE_CODE_SAFE_MODE` turn off
hooks; with the value `1` the script answers `claude_code_unsupported`. Both variables are present in the
Claude Code 2.1.300 binary; repeat this check when the version changes.

**Static nature.** The script does not start Claude Code. The checks of the agent, the frontmatter, and the guard
are static, so `guard_hook_unavailable` means a broken or non-executable guard, not
proof that the hook fires in a live session.

## 3. Checking with real Claude Code in clean-room

The firing of the scoped hook is confirmed not by preflight but by the scenario
[`scripts/clean_room/isolated_test_runner.py`](https://github.com/PVMalove/agent-harness-next/blob/master/scripts/clean_room/isolated_test_runner.py) with
the module [`claude_probe.py`](https://github.com/PVMalove/agent-harness-next/blob/master/scripts/clean_room/claude_probe.py). It is controlled by environment
variables:

| Variable | Effect |
| --- | --- |
| not set | the probe is not requested; the log has the line `confirmation not requested` |
| `HARNESS_VERIFY_CLAUDE_TEST_AUTHOR=1` | the probe is requested; without `claude` in `PATH` it is skipped with a message, and any other failure fails the scenario |
| `HARNESS_REQUIRE_CLAUDE_TEST_AUTHOR=1` | the probe is mandatory; the absence of `claude` is also a failure |

`make verify` and CI do not set these variables: CI has no Claude Code credentials, and the probe spends
quota, so it is run by hand before a PR:

```bash
make test-author-probe
```

The target sets `HARNESS_REQUIRE_TEST_SANDBOX=1`, `HARNESS_VERIFY_CLAUDE_TEST_AUTHOR=1`, and
`HARNESS_REQUIRE_CLAUDE_TEST_AUTHOR=1` and runs the whole clean-room (`scripts/test_clean_room.py`).
It needs Linux with bubblewrap, `claude` in `PATH`, and a completed login; the result of the probe is reported in the body of the PR.

The probe runs `claude --agent test-author` in a trusted clean-room project twice. The first run
asks for three calls: a write of `src/canary.txt`, the command `touch bash-probe.txt`, and a write of
`tests/allowed-probe.txt`. The hook must refuse the first two with the reasons
`write_outside_test_paths` and `runner_only` (they exist only in the guard, so they serve as a sign that it
fired) and pass the third. The second run gives the subagent a requirement and a scenario: it
writes one test itself and runs it through the runner. The result is accepted only if the runner reported
`failed`, the run log contains `AssertionError` without `TypeError`, `ImportError`, and `SyntaxError`, and the
production code did not change. An isolated `HOME` with the trust decision lies next to the project, and
a link to the user's credentials is created only for the duration of the probe and deleted after it.

Besides the probe, the scenario checks without Claude Code that preflight activates in a trusted project and
stays `project_untrusted` under three trust states: the decision is not accepted, the record is only for
another project, and `.claude.json` is missing.

## Source

[test-author-preflight.sh](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/test-author-preflight.sh),
[test_preflight.py](https://github.com/PVMalove/agent-harness-next/blob/master/tests/test_author/test_preflight.py),
[claude_probe.py](https://github.com/PVMalove/agent-harness-next/blob/master/scripts/clean_room/claude_probe.py),
[docs/agents/test-author.md](../agents/test-author.md),
ADR 0035, ADR 0033
