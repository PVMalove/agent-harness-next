# diagnosing-bugs — Diagnosing errors

Source: [`SKILL.md`](https://github.com/PVMalove/agent-harness-next/blob/master/skills/first-party/engineering/diagnosing-bugs/SKILL.md).
In `engineering-suite`, this first-party override keeps the upstream diagnosis loop. It differs from
upstream in these edits:

- it adds the project memory search step;
- it drops the call "Be aggressive. Be creative. Refuse to give up." from the feedback-loop phase;
- its description names the boundary with `/tdd`: diagnosis finds the cause through a red feedback
  loop, and `/tdd` takes over once the cause is known;
- `SKILL.md` keeps the first way to build the loop, a failing test. The other ways in order and the
  branches for a flaky bug and a performance regression moved to
  [`references/feedback-loops.md`](https://github.com/PVMalove/agent-harness-next/blob/master/skills/first-party/engineering/diagnosing-bugs/references/feedback-loops.md),
  which the agent reads when a failing test gives no red loop;
- the fix goes on the ticket's issue branch, per the Issue First rule in `.claude/rules/git-delivery.md`;
- it adds the [RCA phase](#rca) on an error stop.

After the symptom is pinned, before the hypotheses are ranked, an interactive session with memory
enabled runs `harness memory search . "<symptom, error, and module>"` once to search for past
fixes. Without an external CLI, it uses the installed entry point from the shared contract.
The pointers help propose a hypothesis; reproduction still proves the cause.
Disabled or unavailable memory leaves the ordinary diagnosis process.

The shared contract [`project-memory.md`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/instructions/project-memory.md) distinguishes the search status
and the source status: `ok`/`stale_sources` allow the returned pointers to be considered;
`historical`, `unknown`, and unconfirmed sources require verification, and superseded sources are excluded.
A source is opened only when necessary, its hash is checked, and it is treated as untrusted
evidence. There is no automatic rebuild. In a dispatch, orchestration roles use the Context Package
and escalate a lack of evidence to the coordinator, without calling the search.

## RCA phase — on an error stop { #rca }

The RCA phase finds the root cause of an [error stop](../concepts/error-stops.md), a call to a human
caused by an error, and writes it to a draft; it does not fix the error. When
the error carries a `FMEA: <guid> (<title>)` line, the agent first applies the recovery of that
[FMEA catalog](../concepts/fmea.md) entry within the attempt budget and enters the phase only if the
failure remains.

The phase is a separate entry, not a step after Phases 1–6: it fixes nothing. The fix comes later,
through a bug ticket and `/tdd`. The phase follows
[`references/rca.md`](https://github.com/PVMalove/agent-harness-next/blob/master/skills/first-party/engineering/diagnosing-bugs/references/rca.md),
and secrets are redacted in every evidence line and in the draft itself.

1. **Why-chain.** The agent asks "why" up to five times, starting from the exact symptom. A step
   counts only with evidence: a command with its output, a log line, or a code line as `path:line`.
   The chain stops at the first cause that harness code, a harness contract or a harness process
   controls. A remedy or hint that misled or did not help is itself a harness defect. If five steps
   find no such cause, the agent records the last cause found as
   `Root cause: unresolved after 5 whys`, which is a valid outcome.
2. **Root-cause class.** `harness` is code, a contract, a process, or a misleading remedy;
   `environment-or-misuse` is the environment (network, credentials, an external service, a machine
   state) or a use of the harness outside its contract. The class decides the draft: `harness` gets
   a bug-ticket draft, `environment-or-misuse` only the proposed FMEA entry.
3. **RCA draft.** The agent writes `docs/tasks/rca-<symptom-slug>/rca-<symptom-slug>.md`.
   `docs/tasks/` is gitignored, so the draft is never committed. It holds the stopped ticket, the
   symptom, the why-chain, the root cause and its class, the evidence, and a proposed FMEA entry
   with six keys and no GUID: only `python scripts/fmea_catalog.py new <title>` in the harness
   repository generates the GUID. `recovery` is written as an action and a retry ("do X and
   retry"). For the `harness` class, the draft also holds a bug-ticket draft labelled `type::bug`
   and `rca::done` and a decision section the developer fills in: the target tracker and whether the
   bug blocks the stopped ticket.
4. **Duplicate search.** Before the bug-ticket draft, the agent searches open `type::bug` tickets
   for the same root cause or the same FMEA `title`, never the symptom alone. On a match, it drafts
   a comment to the existing ticket instead of a new one. When the search cannot run, the draft
   names the reason: the search is never skipped silently.
5. **Publication only after "yes".** The phase does not wait for an answer: it writes the draft and
   returns control. The tracker is written only after the developer's explicit "yes" for a specific
   draft: a new ticket labelled `type::bug` and `rca::done`, or a comment to the duplicate. When the
   bug blocks the stopped ticket, that ticket gets `status::blocked` and a `Blocked by #<bug>` line,
   plus the native dependency link on GitHub. The labels `type::bug` and `rca::done` must already
   exist in the tracker, otherwise `/setup-labels` runs first. When the root cause is in the harness
   but the stopped work ran in a target project, the developer picks the harness tracker. An
   `environment-or-misuse` draft has nothing to publish: its outcome is the FMEA entry.

The phase ends with the line `RCA draft: <path>. Continue with the next free ticket.` and never
selects the next ticket itself: the calling skill (`/implement`, `/fast-implement`) does. When a
human invoked `diagnosing-bugs` directly, the agent reports the draft path and stops.

`mattpocock-suite` continues to ship the unchanged
[vendor snapshot](https://github.com/PVMalove/agent-harness-next/blob/master/skills/vendor/mattpocock/engineering/diagnosing-bugs/SKILL.md).
