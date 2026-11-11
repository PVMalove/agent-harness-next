# diagnosing-bugs — Diagnosing errors

Source: [`SKILL.md`](https://github.com/PVMalove/agent-harness-next/blob/master/skills/first-party/engineering/diagnosing-bugs/SKILL.md).
In `engineering-suite`, this first-party override keeps the upstream diagnosis loop.

After the symptom is pinned, before the hypotheses are ranked, an interactive session with memory
enabled runs `harness memory search . "<symptom, error, and module>"` to search for past
fixes. Without an external CLI, it uses the installed entry point from the shared contract.
The pointers help propose a hypothesis; reproduction still proves the cause.
Disabled or unavailable memory leaves the ordinary diagnosis process.

The shared contract [`project-memory.md`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/docs/project-memory.md) distinguishes the search status
and the source status: `ok`/`stale_sources` allow the returned pointers to be considered;
historical, unknown, and unconfirmed sources require verification, and superseded sources are excluded.
A source is opened only when necessary, its hash is checked, and it is treated as untrusted
evidence. There is no automatic rebuild. In a dispatch, orchestration roles use the Context Package
and escalate a lack of evidence to the coordinator, without calling the search.

`mattpocock-suite` continues to ship the unchanged
[vendor snapshot](https://github.com/PVMalove/agent-harness-next/blob/master/skills/vendor/mattpocock/engineering/diagnosing-bugs/SKILL.md).
