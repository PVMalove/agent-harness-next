# Code Review — Code review

## 1. Name and localization

- **English name:** `code-review`
- **Russian translation:**

```text
Ревью кода
```

## 2. Full translation of the skill text

<div class="ah-skill-text" markdown="1">

```yaml
name: code-review
description: Review the changes since a fixed point (commit, branch, tag, or merge-base) along two axes — Standards (does the code follow the documented coding standards of this repository?) and Spec (does the code match what the originating issue/spec asked for?). Runs both reviews in parallel subagents and reports them side by side. Use when the user wants to review a branch, a PR, or work-in-progress changes, or asks to "review since X".
```

Two-axis review of the diff between `HEAD` and a fixed point that the user supplies:

- **Standards** — does the code follow the documented coding standards of this repository?
- **Spec** — does the code implement the originating issue / spec faithfully?

Both axes run as **parallel subagents**, so they do not pollute each other's context. This skill then aggregates their findings.

##### Runtime boundary

This workflow does not depend on the runtime. The output language is set by `language` from `.harness/project.json`; use the review mechanism that is already configured by hand. The workflow must not launch a runtime-specific adapter, choose a provider or a model, or change the reviewed branch.

The issue tracker must be provided. If `docs/agents/issue-tracker.md` is missing, tell the user to run `harness update`, which creates the file from the harness templates. On GitLab, every `glab` command takes `-R <project-url>`; `<project-url>` and the other GitLab placeholders (`<host>`, `<project-id>`) are defined in `docs/agents/issue-tracker.md` → GitLab → Conventions.

#### Process

##### 1. Pin the fixed point

Whatever the user named is the fixed point: a commit SHA, a branch name, a tag, `main`, `HEAD~5`, and so on. If the user did not specify one, ask.

If the user named a PR or MR, its target branch is the fixed point. Read the target and source branches — GitHub: `gh pr view <n> --json baseRefName,headRefName`; GitLab: `glab mr view <iid> -R <project-url> -F json` (`target_branch`, `source_branch`). Then run `git fetch origin <target>` and use `origin/<target>` as the fixed point. The current checkout must be the source branch. If it is not, tell the user instead of switching the branch (see _Runtime boundary_).

Capture the diff command once: `git diff <fixed-point>...HEAD` (three dots, so the comparison is against the merge-base). Also capture the list of commits with `git log <fixed-point>..HEAD --oneline`.

Before you continue, confirm that the fixed point resolves (`git rev-parse <fixed-point>`) and that the diff is not empty. An invalid ref or an empty diff must end the process here, not inside the two parallel subagents.

In the coordinator pipeline, the review receives the candidate SHA and the Context Package as evidence. Before the review and before publish, the coordinator checks again that `base_commit` matches the current `origin/<integration_ref>`. If they drift apart, a new developer/rebase dispatch and a new risk assessment are required.
There are two kinds of delta-review. A test-only delta-review is allowed after a Warning for a new candidate whose diff touches only test files and does not match the risk triggers. It runs as a new independent dispatch, rechecks only the Warning axis, and inherits Standards=Clean.
The coordinator itself assigns the delta-review after a fix-forward. That delta-review checks both axes on the fix diff only, and relies on the earlier review report for the rest of the candidate. A full review is assigned instead of a delta-review in five cases: the candidate or the new commits match a risk trigger that the earlier review did not see; the new commits change a file outside the carried items; the `git patch-id` of a carried copy does not match; the candidate lost a commit of the earlier candidate; there are no new commits.

##### 2. Find the spec source

Look for the originating spec in this order:

1. Issue references in the commit messages or in the named PR/MR (`#123`, `Closes #45`, `Related to #45`, and so on). Fetch them with the workflow in `docs/agents/issue-tracker.md`: GitHub `gh issue view <n> --comments`; GitLab `glab issue view <n> -R <project-url> --comments`. A GitLab `!67` is a merge request, not an issue: read it with `glab mr view 67 -R <project-url> --comments` (GitHub PR: `gh pr view <n> --comments`) and take the ticket from the footer `Closes #<ID>`/`Related to #<ID>`.
2. A path that the user passed as an argument.
3. A spec file under `docs/`, `specs/`, or `.scratch/` that matches the branch name or the feature.
4. If nothing is found, ask the user where the spec is. If the user says there is none, the **Spec** subagent skips the check and reports "spec unavailable".

##### 3. Find the standards sources

Anything in the repository that documents the rules for writing code, for example `CODING_STANDARDS.md` or `CONTRIBUTING.md`.

On top of what the repository documents, the Standards axis always contains the **smell baseline** described below. It is a fixed set of Fowler code smells (_Refactoring_, ch. 3) that applies even when the repository documents nothing. Two rules bind it:

- **The repository overrides.** A documented repository standard always wins. If it approves something that the baseline would flag, do not report the smell.
- **Always a judgment call.** Each smell is a labeled heuristic ("possible Feature Envy"), not a hard violation. As with any standard here, skip everything that tooling already enforces.

Each smell reads _what it is_ → _how to fix it_. Match it against the diff:

- **Mysterious Name** — the name of a function, variable, or type does not reveal what it does or holds. → rename it; if no honest name can be found, the design is murky.
- **Duplicated Code** — the same shape of logic occurs in more than one hunk or file of the change. → extract the shared shape and call it from both places.
- **Feature Envy** — a method reaches into the data of another object more than into its own. → move the method onto the data it envies.
- **Data Clumps** — the same few fields or parameters constantly travel together (a type that wants to be born). → bundle them into one type and pass that type.
- **Primitive Obsession** — a primitive or a string stands in for a domain concept that deserves its own type. → give the concept its own small type.
- **Repeated Switches** — the same `switch`/`if` cascade on the same type recurs in the change. → replace it with polymorphism or with one map that both places share.
- **Shotgun Surgery** — one logical change forces scattered edits across many files of the diff. → gather what changes together into one module.
- **Divergent Change** — one file or module is edited for several unrelated reasons. → split it so that each module changes for one reason.
- **Speculative Generality** — an abstraction, parameters, or hooks are added for needs that are not in the spec. → delete them; fold them back until a real need appears.
- **Message Chains** — a long `a.b().c().d()` navigation that the caller should not depend on. → hide the walk behind one method of the first object.
- **Middle Man** — a class or function that mostly only delegates onward. → remove the middleman and call the real target directly.
- **Refused Bequest** — a subclass or implementer ignores or overrides most of what it inherits. → drop the inheritance and use composition.

##### 4. Review both axes

Launch the `code-review-standards` and `code-review-spec` subagents, defined in `.claude/agents/`, through the manually configured mechanism of the coding application. Wait for both reports, then return them to this primary session for aggregation. Do not replace either axis with an inline review.

The **prompt for `code-review-standards`** must include:

- the full diff command and the list of commits;
- the list of standards source files found in step 3, **plus the smell baseline from step 3**, pasted in full: the subagent has no other access to it.

The **prompt for `code-review-spec`** must include:

- the diff command and the list of commits;
- the path to the spec or its fetched content.

If the spec is missing, skip the `code-review-spec` subagent and note this in the final report.

##### 5. Aggregate

Present the two reports under the headings `## Standards` and `## Spec`, verbatim or lightly cleaned. Do **not** merge the findings or change their ranking: the two axes are deliberately separate (see _Why two axes_).

End with one line: the total number of findings per axis and the worst issue _within each axis_ (if any). Do not pick a single winner between the axes: this is exactly the reranking that the separation prevents.

#### Why two axes

A change can pass one axis and fail the other:

- Code that follows every standard but implements the wrong thing → **Standards pass, Spec fail.**
- Code that does exactly what the issue asked for but breaks the conventions of the project → **Spec pass, Standards fail.**

A separate report stops one axis from hiding the other.

##### Output language

Read `language` from `.harness/project.json` (the default is `ru` if the file or the field is missing). If it is `ru`, write the whole report — both subagent briefs and the aggregated output — in Russian, regardless of the language of the prompt. If it is `en`, write in English.

</div>

## 3. Contracts

- **Input (Input/Brief):** the fixed point, the diff, the project standards, and the originating spec.
- **Output (Output/Report):** independent `Standards` and `Spec` reports, then a short two-axis summary.

## Source

[SKILL.md](https://github.com/PVMalove/agent-harness-next/blob/master/skills/first-party/engineering/code-review/SKILL.md)
