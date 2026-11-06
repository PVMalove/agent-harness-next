# Setup Labels — Label setup

## 1. Name and localization

- **English name:** `setup-labels`
- **Russian translation:**

```text
Настройка меток
```

## 2. Full translation of the skill text

<div class="ah-skill-text" markdown="1">

```yaml
name: setup-labels
description: Create or update this repository's GitHub or GitLab labels (status::*, hitl/afk, task-report::required, resolution::wontfix, wayfinder:*), so that they match docs/agents/triage-labels.md. Run it once for each repository before the first use of triage, to-spec, to-tickets, implement, to-guide, or wayfinder.
disable-model-invocation: true
```

### Setup Labels

`gh issue edit --add-label`/`gh issue create --label` fail on a label that does not exist yet: `gh` never creates it automatically. GitLab does the opposite: a `--label` with a missing label silently creates it with GitLab's default color, so a label applied to a ticket before this skill runs stays wrongly colored. This skill creates every label that the triage taxonomy of this repository needs, with its canonical color, so run it before the first `/to-spec` or `/to-tickets`.

#### Process

1. **Read the tables.** Pull every `Label` / `Color` row from `docs/agents/triage-labels.md` — the taxonomy tables (category, execution mode, workflow state, context labels) and the Wayfinder addendum. Name and hex color only, skip the `Applied by` column; on GitHub skip `Meaning` too, and on GitLab keep its first sentence as the label description. If the file does not exist, ask the user to run `harness update` — it creates the file from the harness templates — and stop.
2. **Show the plan.** List every label that will be created or updated, together with its color. Confirm with the maintainer before changing the tracker: this changes the shared state of the repository and requires the same discipline as any step of this repository that mutates the tracker (see `docs/agents/issue-tracker.md`).
3. **Apply.**
   - **GitHub:** for each label, run `gh label create "<name>" --color "<hex>" --force`. `--force` makes the operation idempotent: it updates the color of an existing label instead of failing, and it touches nothing else (issues that already carry this label are unchanged).
   - **GitLab:** the CLI has no `--force` for label creation, so compare with the existing labels first. `<host>`, `<project-url>`, and `<project-id>` are defined in `docs/agents/issue-tracker.md` → GitLab → Conventions.
     - Read the existing labels once: `GITLAB_HOST=<host> glab api --paginate projects/<project-id>/labels` — through the paginated API, because the CLI's own label list returns a single page. Each entry contains `id`, `name`, and `color`.
     - Missing label: `glab label create -R <project-url> -n '<name>' -c '<hex>' -d '<description>'`. `<description>` is the first sentence of the `Meaning` column as plain text, without backticks and quotes: inside double quotes the shell would run a backticked word as a command, and a value in single quotes cannot contain a quote.
     - Existing label with a different color (the hex is compared case-insensitively): `glab label edit -R <project-url> --label-id <id> -c '<hex>'`, where `<id>` comes from the list. Only the color changes; issues that already carry the label are unchanged.
     - Existing label with the same color: no-op.
4. **Report.** One line per label: created, updated (color changed), or already correct (no-op). Do not reprint the full plan from step 2.

</div>

## 3. Contracts

- **Input (Input/Brief):** `docs/agents/triage-labels.md` and the explicit confirmation of the maintainer.
- **Output (Output/Report):** one result line for each label.

## Source

[SKILL.md](https://github.com/PVMalove/agent-harness-next/blob/master/skills/first-party/engineering/setup-labels/SKILL.md)
