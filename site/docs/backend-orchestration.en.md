# Backend orchestration {#backend-orchestration-guide}

Use `backend-orchestration` for tasks that need independent roles or separate verification. It extends `engineering-suite`. A coordinator session plans the work and advances it under the configured approval policy. Roles do not choose their own model or merge PRs.

## Choose a task

- <span id="1-enabling"></span><span id="2-configuring-harnessorchestrationjson"></span><span id="configuration-normalization-and-validation"></span><span id="context-budget-and-preflight"></span><span id="tool-policy-and-context-budget-in-the-brief"></span><span id="operating-loop-policy-attention-approval-ttl-and-extensions"></span>[Enable and configure](guides/orchestration/setup.md).
- <span id="role-access-access_policy-and-runtime_access"></span><span id="built-in-docker-container-executor"></span><span id="container-worker-status-and-cleanup"></span><span id="qa-git-and-publish-access"></span>[Prepare access and containers](guides/orchestration/access.md).
- <span id="discovery-context-and-context-package"></span>[Prepare role context](guides/orchestration/context.md).
- <span id="observing-a-launch-and-a-ready-unsubmitted-report"></span><span id="3-choosing-roles-and-planning-a-batch"></span><span id="4-coordinator-cli-and-lifecycle"></span><span id="5-optional-external-adapter"></span><span id="6-first-pilot-and-the-source-of-rules"></span>[Run a batch and accept a report](guides/orchestration/run.md).
- <span id="retry-routing-and-the-abandon-decision"></span><span id="automatic-path-approval_policy-auto"></span><span id="approval-bound-to-the-transition-digest"></span><span id="idempotency-of-a-read-only-retry"></span><span id="context-pressure"></span><span id="attention-state"></span>[Choose a decision or retry](guides/orchestration/decisions.md).
- <span id="compatibility-and-migration"></span><span id="inventory-and-closing-a-dead-end-batch"></span><span id="model-self-report-and-dispatch-watchdog"></span><span id="busy-ledger-report-complete-and-ledger-release-lock"></span><span id="lifecycle-writes-in-the-runtime-store-epoch"></span><span id="reporting-and-token-monitoring-dispatch-telemetry"></span><span id="checkpoint-and-a-new-worker-session"></span>[Inspect state and diagnostics](guides/orchestration/operations.md).
- <span id="clean-room-qa-lane"></span>[Run clean-room QA](guides/orchestration/qa.md).
- <span id="integration-accounting-after-publish"></span><span id="advisory-tool-call"></span>[Publish the candidate and prepare a PR](guides/orchestration/publish.md).
- <span id="manual-recovery-and-stage-repeat"></span><span id="batch-hold-and-the-recovery-commands"></span>[Recover stopped work](guides/orchestration/recovery.md).

## Who owns the rules {#rule-ownership}

The coordinator applies rules from the installed `.harness/orchestration/playbook.md`.
Manifests in `roles/` define role boundaries. The project's `orchestration.json` chooses assignments,
checks and policies within those boundaries. A runtime adapter delivers approved work.

`/implement` follows `architect → developer → code-review → qa → publish`.
`approval_policy` determines report acceptance. Opening a PR requires separate confirmation;
a person performs the merge.

## What gets installed {#what-gets-installed}

- `.harness/orchestration/roles/`: role manifests and the shared contract.
- `.harness/orchestration/playbook.md`: workflow and handoff rules.
- `.harness/orchestration/pilot.md`: observation of early batches.
- `.harness/orchestration/coordinator.py`: CLI for batches, dispatch, approval and reports.
- `.harness/orchestration.json`: project settings.

After migration, Rust owns operational records in `.harness/orchestration/state/runtime.db`.
Python reads and changes them through the runtime protocol. Paths such as `reports/<id>.json`
identify logical records, not JSON files to edit manually. Use the CLI for reads and changes.
Local state stays out of Git; cleanup requires a separate coordinator decision.

## Language and evidence

Read [Technical English](https://github.com/PVMalove/agent-harness-next/blob/master/harness/docs/technical-english.md) before the first English handoff.
Role handoffs, checkpoints and state evidence use English; completion reports to the coordinator
use Russian with `"report_language": "ru"`. Commands, paths and SHA values are not translated.

Token accounting uses only observed provider or runtime telemetry with its source stated.
A role's estimate cannot replace missing telemetry. Secret values do not belong in configuration,
briefs or reports.

## Start here

For a first run, open [enable and configure](guides/orchestration/setup.md).
To choose settings with an agent, use the [initial setup prompt](getting-started/settings/orchestration/index.md#agent-setup).
