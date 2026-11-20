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
- the fix goes on the ticket's issue branch, per the Issue First rule in `.harness/instructions/git-workflow.md`.

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

`mattpocock-suite` continues to ship the unchanged
[vendor snapshot](https://github.com/PVMalove/agent-harness-next/blob/master/skills/vendor/mattpocock/engineering/diagnosing-bugs/SKILL.md).
