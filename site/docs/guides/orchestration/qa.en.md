# Clean-room QA

QA checks the pinned candidate in a clean environment. Distinguish preparation failure from a project defect before choosing a rerun or developer retry.

[Orchestration overview](../../backend-orchestration.md)

## Clean-room QA lane {#clean-room-qa-lane}

The coordinator itself runs the approved `qa` dispatch in a separate temporary Git worktree,
detached exactly at `candidate_commit`. The commands come verbatim from `verification_commands` of the
immutable brief, and a HEAD mismatch or a dirty worktree stops the check. The run is not
passed to a runtime adapter:

```bash
python .harness/orchestration/coordinator.py --repo . qa run \
  --dispatch <qa-dispatch-id> --lease-seconds 1800
```

The repository has one FIFO lane for heavy checks. If the lane is busy, the command saves
the request and returns `state: queued` with a position. A repeated call for the same dispatch runs it
only when it becomes first in the queue. The state and the current owner are visible without running the gate:

```bash
python .harness/orchestration/coordinator.py --repo . qa status
```

In the runtime-store epoch, a lease records the owner's process identity, fencing token and
heartbeat time. After expiry, the next `qa run` can reap the lease only when the runtime proves
the owner is dead (`owner-dead`). A live or unverifiable owner is not treated as finished.
In the file-ledger epoch, an expired lease requires an explicit decision.

For manual recovery, inspect the owner with `qa status`, then use `qa clear-stale-lease`
with the expected host/PID/expiry, approval and reason:

```bash
python .harness/orchestration/coordinator.py --repo . qa clear-stale-lease \
  --expected-host <host> --expected-pid <pid> --expected-expiry <ISO-8601> \
  --approved-by 'имя coordinator-а' --approved-at <approval-time-utc> \
  --reason 'проверено, что владелец больше не выполняется'
```

If the lease belongs to a dispatch that stayed `working` with no recorded report, the command
returns that dispatch to `approved`. The `restored_dispatch_state` field in the response and in the recovery record
is `approved` or `null`.

### Environment preparation and failure categories

The optional `qa_preparation` in `.harness/orchestration.json` sets the environment preparation commands
(for example, `uv sync --locked`). The optional `qa_environment_probes` (for example, a check that
the package registry is reachable) and `qa_project_file_checks` (for example, `uv lock --check`) set
independent facts. Their commands run in the same checkout only after a failed preparation.
`qa run` runs them and then `verification_commands` in one clean checkout of the exact
`candidate_commit`. It stops at the first failed command. Without `qa_preparation`
(configurations with only `verification_commands`), the behavior and the report shape do not change.

A report and an artifact with preparation carry `qa_stages`. For each executed command, it holds the stage
(`preparation`, `environment-probe`, `project-file-check`, or `gate`), the exact command, the result,
the exit code, and a sanitized diagnostic of the failed command. They also carry `failed_stage` and
`code_checks_started` (`started`, `not_started`, or `unknown`). The records are checked against the immutable
artifact: the commands and exit codes must match its blocks. If preparation failed, the gate commands
in `checks_run` are recorded as `not_run`. This is not an invented failed code check.

Independent facts confirm the cause of a preparation failure: neither an exit code nor a keyword in the log
decides alone, and the preparation stage itself does not prove an infrastructure cause. Log signatures
only support the diagnosis, and without configured probes and project file checks an infrastructure
cause is not confirmed. The failure then requires triage:

| Diagnosis | Confirmation | Report | Route of `batch decide --decision retry` |
| --- | --- | --- | --- |
| `infrastructure` | an environment probe failed, and all project file checks passed (and at least one is configured); the output has no project-defect signature; the code was not checked | `blocked`, "code not checked" | `same-candidate-rerun` without `--reason-category`: a new qa dispatch on the same SHA, the developer retry budget is not spent |
| `project-defect` | a project file check failed (and no probe failed), or a defect signature (for example, an incompatible lock file) that matches a tracked manifest or lock file named in the output; the project file checks do not refute it | `failed` | `developer-retry`, reason `code` |
| `unknown` | no probes and checks are configured, they do not confirm a cause, or they contradict each other (for example, both a probe and a check failed) | `blocked`, triage needed | `retry` without `--reason-category` is rejected; the coordinator names the reason or blocks the batch |

A failure of the gate itself remains an ordinary code-check failure and follows the existing
`developer-retry` route.

**Recovery on the same SHA.** After the environment is confirmed ready, the coordinator runs
`batch decide --decision retry`. Then it creates a new qa dispatch for the same `candidate_commit` with
the same commands and limits. The earlier brief, report, artifact, and approval stay as audit
evidence. A failure of preparation or of the report write leaves no lease, queue entry, or `working`
state: the same approved dispatch can be run again without editing the ledger and without a new batch.
The exception is a ledger held by another operation for more than 30 seconds (see ["Busy ledger"](operations.md#busy-ledger-report-complete-and-ledger-release-lock)).

### Bounded infrastructure retries

A project can separately allow a policy retry of a confirmed infrastructure failure:

```json
{
  "infrastructure_retry_policy": {"enabled": true},
  "attention_policy": {"max_infrastructure_retries": 2}
}
```

Without opt-in, the manual gates apply. The policy does not grant platform permissions, does not replace native
approval, and does not accept a failed QA. The budget uses the existing
`attention_policy.max_infrastructure_retries`: the default is 2, and `0` forbids retries.
The developer retry budget is not spent. The opt-in, the budget, and the preparation/probe/project-file-check commands
are saved in `orchestration_policy.infrastructure_retry` and are bound to the approval digest.
Historical briefs without this section stay in manual mode. Editing the live config does not enable
a retry for an old approval and does not change the commands of a new, already approved brief.

After a QA preparation failure, the policy continues only the `same-candidate-rerun` route with a
confirmed `infrastructure` diagnosis, `code_checks_started: not_started`, and an unchanged SHA. Before the
decision, the coordinator checks access and reruns the pinned independent environment probes and
project file checks in a clean checkout; if the environment is not ready yet, there is no new dispatch. After
the cause is removed, within the same limits, run:

```bash
python .harness/orchestration/coordinator.py --repo . report complete --dispatch <qa-dispatch-id>
```

Each retry that takes place gets a new immutable dispatch and the decision source
`policy:infrastructure-retry`, and the earlier brief/report/artifact are kept. A repeated `report complete`
returns the dispatch that was already created, and an interruption after the decision completes the missing step. The command
does not start a worker and does not open a PR.

An access denial before the QA or publish run does not create a report about a code check. For an opt-in dispatch,
the coordinator saves a structured access attempt and a checksum. When the same resource becomes available,
request the check and a new policy-approved assignment:

```bash
python .harness/orchestration/coordinator.py --repo . dispatch retry-infrastructure --dispatch <dispatch-id>
```

This path is allowed only for a denial confirmed by a probe (`denied`), with a fresh confirmation of
readiness. The old unsent brief is cancelled with an audit of the reason, and the new one keeps the stage, SHA, commands,
runtime/model/effort, scope, and access; a repeated command returns the earlier result. The publish remote
must also stay the same. Then run `qa run` or `dispatch publish` with the new ID.
An unconfirmed network denial (`unverified`), an unsupported mode (`unsupported`), a denial by the plan itself,
and an arbitrary Git error require manual analysis. Git operations without an approved dispatch
keep the manual route: the opt-in does not allow an arbitrary Git command.

A change of candidate, commands, or access, an unknown cause, and an exhausted budget stop the
policy and raise `needs_attention`. A human clears the attention. This does not raise the budget
and does not allow a changed contract. New requirements go through the ordinary proposal and approval.
Do not edit the ledger and do not rewrite the candidate for the sake of infrastructure recovery.

**Native smoke.** The support check requires a real coding environment. Create a separate smoke project,
a local bare remote, and a new empty cache inside the allowed shared storage. Record the full
harness and candidate SHA, the checkout cleanliness, and the exact preparation/gate commands. Through the public CLI,
go through batch/dispatch approval, the native role handoff, preparation/clean-room QA, and publish of the
accepted SHA. Then confirm the access denial, the absence of a retry before readiness, the bounded
retry, and the preservation of evidence. Take dynamic IDs and the digest from the command JSON. Native approval accepts the
coding runtime according to the user's current policy, and the orchestration policy does not replace it.
Do not change machine/global profiles, do not clear the user's cache, do not create a PR, and do not
run a merge. An external push requires permission for the specific smoke remote, and a push to a local
bare remote checks Git/publish but not external Git access.

First steps from a source checkout (the paths and the actual model are set by a human):

```bash
python harness/bin/harness.py init "$SMOKE_REPO" --capability backend-orchestration \
  --base-branch integration/smoke --language ru --tracker-type local \
  --qa-gate-command "$SMOKE_GATE"
python "$SMOKE_REPO/.harness/orchestration/coordinator.py" --repo "$SMOKE_REPO" batch create \
  --ticket local:619 --branch feature/issue-619-native-smoke --worktree "$SMOKE_REPO" \
  --integration-ref integration/smoke --allowed-path smoke.py --expected-file smoke.py \
  --expected-service smoke --expected-changed-lines 2 \
  --goal 'Change answer to 42 and verify the native smoke' \
  --definition-of-done 'answer returns 42; exact candidate passes QA and local publish' \
  --prohibited-change 'global config, other projects, secrets, PR, merge'
```

Before this, the local `origin` must contain `integration/smoke`, and the checkout must be a clean issue branch.
Create a tracked `smoke.py`, a manifest/lock, and real project-owned commands for preparation, an independent
network/cache probe, and offline file checks. Configure the opt-in before the proposal, create a separate cache, and
record that it is empty. For QA, use, for example,
`UV_CACHE_DIR=<new-cache> UV_PROJECT_ENVIRONMENT=.harness/.venv uv sync --locked`, and the developer
uses a different cache. The runner selects Python from `.harness/.venv` of the current clean-room checkout.
The gate command must check the actual change in `smoke.py`, and also the location of `sys.prefix`
and of the imported package in this checkout. Save the actual `executed_command` from the stage evidence.

Choose the transport before creating the batch. For a separate native CLI session, set
`assignment_plans.<role>.transport: "external"` and the real `runtimes`, `provider_profiles`, and check
commands. The authored assignment plan requires architect, developer, code-review, and qa, and health
checks this set. Prepare a project-owned adapter that receives `dispatch --repo --brief` and
actually starts the coding CLI in the approved worktree with the model and effort from the brief; it
returns after the worker starts and does not manage the ledger. For `in-process`, the role runs as a
subagent of the current coordinator session, and a separate CLI session must not be treated as such a subagent.

Take `batch_id` from the `batch create` JSON, after which a human, or a coordinator the human explicitly designates,
runs `batch approve` with `--approved-by` and the actual `--approved-at`. In the same smoke checkout:

```bash
python .harness/orchestration/coordinator.py --repo . dispatch propose \
  --batch "$BATCH" --role architect --runtime "$RUNTIME" --model "$MODEL" --effort "$EFFORT"
python .harness/orchestration/coordinator.py --repo . dispatch create \
  --batch "$BATCH" --role architect --runtime "$RUNTIME" --model "$MODEL" --effort "$EFFORT" \
  --transition-digest "$DIGEST" --approved-by "$APPROVER" --approved-at "$APPROVED_AT"
python .harness/orchestration/coordinator.py --repo . dispatch send --dispatch "$DISPATCH"
```

For the chosen `external`, the last command contains the real adapter:

```bash
python .harness/orchestration/coordinator.py --repo . dispatch send \
  --dispatch "$DISPATCH" --adapter "$SMOKE_REPO/scripts/native_codex_adapter.py"
```

`DIGEST` comes from the reviewed proposal, and `DISPATCH` comes from create. The handoff prints the brief path, the
report staging path, and the expected model. With `external`, the adapter starts the role; with `in-process`, the
coordinator starts it in its own coding session. The role runs
`dispatch self-report --dispatch "$DISPATCH" --model "$ACTUAL_MODEL" --worktree "$SMOKE_REPO"`,
then `dispatch heartbeat --dispatch "$DISPATCH"` and a real `report submit --file <report>`.
The architect does not change code and does not run the full gate. After checking the report, the coordinator saves
its plan as `{"commit_plan": [...]}` in `$COMMIT_PLAN` and runs
`batch decide --batch "$BATCH" --decision accept --commit-plan-file "$COMMIT_PLAN" --approved-by "$APPROVER" --approved-at "$APPROVED_AT"`.
Repeat proposal/create/send for the developer: its commit/report set the full candidate SHA.
`risk assess --batch "$BATCH" --candidate-commit "$SHA" --changed-file smoke.py` determines
whether a review is needed, and a required review cannot be skipped; its send uses a checkout of the exact SHA.

For a new qa proposal/create, add `--candidate-commit "$SHA"` and use `qa run`,
not `dispatch send`. Arrange a write denial only in the created cache (in a POSIX fixture,
`chmod u-w "$SMOKE_CACHE"`). Save `qa_stages` and the `report complete` denial before readiness.
Restore with `chmod u+w "$SMOKE_CACHE"`. `report complete` must return a new ID for the same SHA,
and a replay must return the same ID. Run `qa run` for the new ID and manually accept only a successful report.
The publish proposal/create sets `--role developer --purpose publish --candidate-commit "$SHA"`.
For a POSIX metadata fixture, restrict writes only in the smoke `.git`. Save the denial of
`dispatch publish --dispatch "$PUBLISH" --remote origin` and the denial of `dispatch retry-infrastructure`
before recovery. After recovery, get a new ID and repeat the publish to the same `origin`.
`git ls-remote --heads origin refs/heads/feature/issue-619-native-smoke` must return exactly `$SHA`.
If interrupted, restore the write bit of your own fixture only. An incomplete or different diagnosis is a blocker,
not permission to continue the scenario. An authorized inherit of coordinator operations does not prove
that the authored worker permissions are applied. Run only a mode confirmed by the current extension.

In the evidence, save the runtime, version, transport and mode, full SHAs, native parameters and proof
of actual access, commands with exit codes, readiness, dispatch IDs and checksums, after
removing secrets. The health config and the checkout attestation do not prove network permissions.

The checks of this implementation cover real Git/ledger, preparation/gate, same-SHA retry,
budget, attention, metadata refusal, and local publish. These are controlled checks: they do not
prove the native handoff and the whole runtime matrix. A native handoff with an authored access plan needs an
implementation of `extensions.runtime_access` that observes and applies the actual worker access;
`none` gives no such proof, and an explicitly chosen unverified mode is blocked. `legacy-inherit`
keeps the earlier assignment handoff but does not confirm worker permissions.

The native smoke verified on 2026-10-08 was installed from harness
`cca45e172c7b3685c012e7e6c077356d6cbd6722`: Linux, Codex CLI 0.160.1, a real project adapter, and
two separate roles `architect`/`developer`. The candidate `1dba1785bc809971981129c747e85bffd9b29c51`
passed preparation and the gate in a new clean-room checkout with an empty QA cache, a fresh `.harness/.venv`, and
downloaded dependencies, and was then published to a local bare remote. A cache denial and a `.git` write
denial stopped the continuation before readiness. Recovery spent the two shared infrastructure
retries, the replay kept the successor IDs, and the earlier records kept their checksums. The batch finished through
the public CLI. This confirms only the following limits:

The following table records historical smoke evidence for the named versions. It is not a compatibility guarantee for the CLI installed now.

| Runtime / transport / mode | Native smoke result | Evidence boundary |
| --- | --- | --- |
| Codex CLI 0.160.1 / `external` / worker `legacy-inherit` | PASS: real roles, self-report, heartbeat, commit, and report | The native CLI ran with `workspace-write`; the authored worker access plan is not verified |
| Coordinator / `inherit` / QA and publish | PASS: fresh dependencies, exact-SHA gate, cache/Git denial, readiness, budget, and replay | Actual operations in one allowed coordinator environment; publish only to a local bare remote |
| Worker with authored `inherit`, `sandbox`, or `unsandboxed` / `runtime_access: none` | Blocker | A current extension with proof of observing and applying the plan is needed; an attestation does not replace it |
| `in-process`, Claude and other runtimes, external Git push | Not verified | Each combination needs its own actual run |

CLI flags, the coordinator host execution, and the POSIX `chmod` fixture do not prove the whole permission matrix.
Another runtime, transport, or authored mode needs its own native evidence for support.

After the run, an immutable completion report is created with the commands, exit codes, and short
sanitized evidence. The full sanitized stdout/stderr is stored outside Git in
`.harness/orchestration/state/qa-artifacts/<sha256>.log`. The report refers to this path and checksum.
A gate failure remains a QA finding and requires a new approved developer dispatch. The runner does not edit
code and does not rerun the check on its own.

After accepted QA evidence, the coordinator creates, but does not start, a publish dispatch for the same
candidate SHA. Only the developer publish pushes this SHA, and neither QA, nor review, nor the adapter
creates or merges a PR. After publish, a human manually runs `/to-pull-requests <ticket>`: it
checks the accepted QA evidence of the current SHA and follows the ordinary manual PR workflow without a repeated
heavy gate. The `require-qa-gate.sh` hook accepts the same evidence itself, so a repeated gate and a
marker are not needed for a clean checkout whose `HEAD` equals the accepted `candidate_commit` and with `pass` for
each command of `qa_gate_commands`. Otherwise the earlier path with a marker remains.

The ordinary entry point is `/implement <ticket>`. This session becomes the coordinator itself and runs
the described cycle. It stops at five approval gates (architect, developer, code-review, qa,
publish) and watches the heartbeat of each dispatch. One ticket is brought to a terminal batch state
before the next one starts. A manual run following this guide stays fully valid. For
it, a ready request to the controlling session can be worded like this:

```text
Выступи coordinator-ом backend batch для issue #123. Прочитай .harness/orchestration/roles/
и .harness/orchestration/playbook.md. Не запускай роль до моего явного approval. Предложи
explicit allowed paths, последовательность ролей, immutable brief и требуемые risk gates;
не меняй protected или integration branch.
```
