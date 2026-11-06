# Ask Matt — Ask Matt

## 1. Name and localization

- **English name:** `ask-matt`
- **Russian translation:**

```text
Спроси Мэтта
```

## 2. Full translation of the skill text

<div class="ah-skill-text" markdown="1">

```yaml
name: ask-matt
description: Ask which skill or flow fits your situation. A router over the skills in this repository.
disable-model-invocation: true
```

### Ask Matt

You don't remember every skill, so ask.

A **flow** is a path through the skills. Most paths run along one **main flow**, and two **on-ramps** merge onto it. Everything else is standalone, or a vocabulary layer that runs underneath.

#### The main flow: idea → ship

The route that most work travels. You have an idea and want it built.

1. **`/grill-with-docs`** — sharpen the idea by interview. Start here whenever you are **working in a working directory**: the skill is stateful and keeps what it learns in `CONTEXT.md` and ADRs. (No working directory? Use `/grill-me` — see "Standalone". Both run the same `/grilling` primitive. `grill-with-docs` leaves a paper trail, so it is the better choice wherever a repository exists to hold that trail.)
2. **Branch — can you settle every question in conversation?** If a question needs a runnable answer (state, business logic, a UI you have to see), take a detour through a prototype, bridged by **`/handoff`** in both directions (a prototype lives in its own directory, which is exactly what `/handoff` is for — see "Phase boundaries"):
   - run **`/handoff`** outward, then open a new session on that file;
   - run **`/prototype`** to answer the question with throwaway code;
   - run **`/handoff`** back with what you learned, and reference it from the original idea thread.
3. **Branch — is this a multi-session build?**
   - **Yes** → **`/to-spec`** (turn the conversation thread into a spec), then **`/to-tickets`** to split it into tracer-bullet tickets, each declaring its **blocking edges**. On a local tracker this is one file per ticket under `.scratch/<feature>/issues/`, worked by hand, blockers first. On a real tracker the edges become native blocking links, so you can take any ticket whose blockers are done. Run **`/implement`** (`pipeline::full`) or **`/fast-implement`** (`pipeline::fast`) for each ticket, **clearing the context with `/clear` between tickets**. Each ticket is self-contained, so the context of the last one is disposable.
   - **No** → open one `pipeline::fast` ticket for it (the Issue First rule from the git workflow) and run **`/fast-implement`** on it right here, in the same context window.

   **`/fast-implement`** builds the ticket by driving **`/tdd`** — one red-green slice at a time. It then asks the developer whether to run **`/code-review`**, a two-axis review (Standards + Spec) of the diff, and asks for approval to commit and push the current issue branch. **`/implement`** instead coordinates gated architect → developer → code-review → QA → publish dispatches and never writes code in its own session. Both then offer a manual **`/to-pull-requests`**. Use **`/tdd`** on its own when you only want to build a concrete behavior test-first without a full spec. Use **`/code-review`** on its own whenever you want to review a branch or PR against a fixed point.

##### Context hygiene

Keep steps 1–3 in **one unbroken context window** — do not compact or clear it before `/to-tickets` — so that the grilling, the spec, and the tickets all build on the same thinking. Each `/implement` then starts fresh and works from the ticket.

The limit is the **[smart zone](https://www.aihero.dev/ai-coding-dictionary/smart-zone)**: the part of the context window, well short of its full size, within which the model still reasons sharply. If a session approaches it before `/to-tickets`, do not push on in a degraded state — run `/compact` at the nearest phase boundary and carry on (see "Phase boundaries").

#### On-ramps

A starting situation that generates work and then merges onto the main flow.

- **Bugs and requests are piling up** → **`/triage`**. It moves issues through the triage roles and produces agent-ready issues, which **`/implement`** picks up later.

  Triage is only for issues **you did not create**: bug reports, incoming feature requests, anything that arrives raw. Tickets that `/to-tickets` produced are already agent-ready, so **do not triage them**.

- **Something is broken** → **`/diagnosing-bugs`**. It is for the hard cases: a bug that resists a first look, an intermittent flaky test, a regression that crept in between two known-good states. It refuses to theorize until it has a **tight feedback loop** — one command that already goes red on exactly this bug — and then fixes the bug with a regression test. Its post-mortem hands off to **`/improve-codebase-architecture`** when the real finding is that there is no good seam to lock the bug down.

- **A huge, foggy effort — a greenfield project or a very large feature, too big for one session** → **`/wayfinder`**, the most cognitively demanding flow here. When the way from here to the destination is not visible yet, it charts a **shared map** of **decision tickets** in the issue tracker and resolves them one at a time — producing **decisions, not deliverables** — until the fog lifts and the way is clear. **`/grill-with-docs`** sharpens an idea that you can hold in one session. Wayfinder is for the idea that you cannot. It is slower and denser, so keep it for exactly that case, not for a well-scoped feature.

  When the map clears, **it hands off, it does not build**: merge onto the main flow at **`/to-spec`**, which collapses the linked decisions of the map into a buildable plan, then continue with `/to-tickets` and `/implement` as usual. Looping the map straight into `/implement` skips this collapse and throws away the linked detail. Go straight to `/implement` only if the effort turned out to be genuinely small.

#### Codebase health

Not feature work — upkeep.

- **`/improve-codebase-architecture`** — run it whenever you have a spare moment, to keep the codebase easy for agents to work in. It surfaces **deepening opportunities**. Picking one _generates an idea_ that you can take into the main flow through `/grill-with-docs`. It is the survey that finds candidates. **`/codebase-design`** (below) is the bench on which you design the chosen candidate.

#### Vocabulary underneath

Two model-invoked references that run *beneath* the other skills. Each is the single source of truth for its vocabulary. Use them directly when the **words**, not the process, are the problem, or let the skills above pull them in.

- **`/domain-modeling`** — sharpen the *domain* language of the project: challenge a fuzzy term, resolve an overloaded word ("account" doing three jobs), record a hard-to-reverse decision as an ADR. This is the active discipline that `/grill-with-docs` applies to keep `CONTEXT.md` a clean glossary.
- **`/codebase-design`** — the deep-module vocabulary (module, interface, depth, seam, adapter, leverage, locality) for designing the *shape* of a module: a lot of behavior behind a small interface at a clean seam. Both `/tdd` and `/improve-codebase-architecture` speak it.

#### Phase boundaries

A **phase** is a chunk of work inside a session: grilling, implementation, QA. At the **boundary** between two phases you have five options, and choosing between them is the fuzziest decision in this whole map:

- **Continue** — stay put. It costs nothing and loses nothing.
- **`/clear`** — empty the window, when nothing here matters for the next step.
- **`/handoff`** — write a portable Markdown file. It is narrow: use it only for a **new harness**, a **new directory**, a **colleague**, or for forking a side task **mid-phase**. What it buys is portability.
- **Subagent** — send a tightly scoped task to its own window and get a report back.
- **`/compact`** — compress this context and seed a new session with it. It is the **default** at the bottom of the tree, not the first thing to reach for.

Read [PHASE-BOUNDARIES.md](https://github.com/PVMalove/agent-harness-next/blob/master/skills/first-party/engineering/ask-matt/PHASE-BOUNDARIES.md) for the ordered tree: the five questions, the reasoning behind each branch, and why the cost of the primary source makes **Continue** the first option to rule out. Make the decision **at** a boundary. In mid-phase, continue or split the rest into subagents.

#### Standalone

Off the main flow entirely.

- **`/grill-me`** — the same relentless interview as `/grill-with-docs`, but **stateless**: it saves nothing locally and builds no `CONTEXT.md`. Use it when you are **not working in a working directory**: sharpening a plan, a design, a piece of writing — anything with no repository under it. If you are in a working directory, use `/grill-with-docs` instead. It runs the same interview and leaves a paper trail, so it is strictly better.
- **`/grilling`** — the interview primitive itself: rounds, the frontier, facts are the agent's job and decisions are yours. `/grill-me` and `/grill-with-docs` are the two named ways in. `/triage`, `/wayfinder`, and `/improve-codebase-architecture` also run it internally. Use it directly only when you want the interview with no wrapper around it.
- **`/resolving-merge-conflicts`** — work an in-progress merge or rebase conflict hunk by hunk. It resolves by **intent**, traced to the primary source of each side, not by picking lines, and then finishes the operation. It never runs `--abort`. It is standalone and off every flow: use it when you are already in the middle of a conflict.
- **`/prototype`** — a small, throwaway program that answers one design question: does this state model feel right, or what should this UI look like. Throwaway is a constraint on how the code is written, not a promise to destroy it. The answer is folded into the real code, and the prototype itself is kept as a **primary source** on a `prototype/<name>` branch outside main, referenced from the implementation issue. It is the detour in step 2 of the main flow, but use it any time a design question is hard to settle on paper.
- **`/research`** — delegate reading and searching to a **background agent**. It investigates a question against **primary sources** and then leaves a Markdown file with citations in the repository. Keep working while it reads. The file it produces is material to bring *into* the main flow through `/grill-with-docs`: research feeds the thinking, but does not replace it.
- **`/to-questionnaire`** — use it when the blocker is not in your head or in the codebase, but in **someone else's head**. The skill writes a questionnaire for that person. It is the inverse of `/grill-me`: instead of interviewing you about the subject, it interviews you about the **send** — who it is for, what you need back — and aims the questions at the gap. What comes back is material for `/grill-with-docs` or `/to-spec`.
- **`/wizard`** — for steps that only a **human** can take: provisioning infrastructure, setting up credentials or CI secrets, clicking through an unfamiliar third-party dashboard, running a one-off migration or cutover. It generates an interactive bash script that opens each URL, captures each value, and writes it into `.env` and GitHub secrets. The procedure then stops being something you re-explain to an agent every time. It is model-invoked, so the agent uses it the moment it hits a wall that only you can pass. If the agent can do the step itself, it must do it; the skill is for cases where a human genuinely stays in the loop.
- **`/wait-what`** — the corrective for a message that did not land. Use it mid-conversation, inside any other skill, and the agent restates what it just said, with the context you were missing, in plain English, using the `CONTEXT.md` vocabulary. It works after the fact. `/grill-with-docs` is the upfront prevention, because a shared language agreed early stops jargon from appearing at all.
- **`/teach`** — learn a concept over multiple sessions, using the current directory as a stateful workspace.
- **`/writing-for-agents`** — a reference for writing documents that agents consume: skills, AGENTS.md, and targeted documents.

#### Precondition

**`/setup-matt-pocock-skills`** — run it before your first engineering flow, to configure the issue tracker, the triage label vocabulary, and the documentation layout that the other skills assume. Custom issue trackers also work.

</div>

## 3. Contracts

- **Input (Input/Brief):** a description of the current situation, problem, or next development step.
- **Output (Output/Report):** a recommendation of a specific skill or flow, and an explanation of why it fits.

## Source

[SKILL.md](https://github.com/PVMalove/agent-harness-next/blob/master/skills/first-party/engineering/ask-matt/SKILL.md)
