# FMEA catalog

The FMEA catalog holds the analysed failure modes of the harness: how a failure arises, how to
detect it, and what brings the work back. An error that points to a catalog entry gives the agent a
verified recovery scenario, so the agent retries the step itself instead of calling a human. The
decision is recorded in ADR 0041.

## Why a catalog

Every harness error has a `remedy`, but before the catalog no remedy was verified. The catalog adds
a rule: an error gets a remedy step only for an **analysed failure mode**, that is, a catalog entry
together with an automated recovery test. An error without an entry still prints its remedy, but it
is only a hint (legacy). When the hint does not help, an [error stop](error-stops.md) follows, and
its RCA phase proposes a new catalog entry. The same failure then no longer stops the agent.

## Entry format

The catalog is the file `harness/fmea/catalog.toml` in the harness package. Each failure mode is a
`[[failure_mode]]` table with exactly seven string keys; no other keys are allowed in the table or
at the top level of the file.

| Key | Content |
| --- | --- |
| `id` | the entry GUID, a lower-case uuid4; unique and never changes |
| `title` | a unique slug such as `git-timeout`; it may be renamed |
| `mode` | what fails and how it shows up |
| `detection` | how the harness detects the failure |
| `recovery` | what to do and retry: the error prints this text as its remedy |
| `test` | the node id of the automated recovery test |
| `residual_risk` | what stays unmitigated |

The first catalog entry, shortened:

```toml
[[failure_mode]]
id = "869778d3-80c0-4702-97eb-88068b2baab1"
title = "git-timeout"
mode = "Git plumbing read (`git diff`, `git show`) … hangs longer than `GIT_TIMEOUT_SECONDS` …"
detection = "… `_run_git` raises `ContextPackageError` with `fmea=FmeaId.GIT_TIMEOUT`."
recovery = "check the repository for a held Git lock or an overloaded disk, then retry"
test = "tests/fmea/test_git_timeout_recovery.py::test_git_timeout_recovers_after_the_lock_is_released"
residual_risk = "…"
```

The values are shortened. `harness fmea show git-timeout` prints the full entry, and the source is
`harness/fmea/catalog.toml`.

## GUID and `title`

An `id` is never typed by hand. Only this command adds a new entry:

```bash
python scripts/fmea_catalog.py new <title>
```

It generates a uuid4, appends an entry skeleton with empty fields and regenerates `FmeaId`. The
command has no option to pass an `id`. A `title` must match `^[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*$`
and be unique. Renaming a `title` is allowed: code refers to an entry by its GUID, not its name.

## The `FmeaId` generator

The module `harness/fmea/ids.py` with the `FmeaId(StrEnum)` enumeration is generated from the
catalog and never edited by hand:

```bash
python scripts/fmea_catalog.py generate          # rewrite ids.py
python scripts/fmea_catalog.py generate --check  # compare only, exit 1 on drift
```

The member name is the `title` upper-cased with `-` replaced by `_` (`git-timeout` → `GIT_TIMEOUT`);
the value is the GUID. Member names must be unique, so `git-timeout` and `git_timeout` cannot
coexist. `scripts/verify.py` runs `generate --check` and fails when the module drifts from the
catalog.

## An error that points to the catalog

`HarnessError` takes exactly one of two parameters: `remedy` (text) or `fmea` (an `FmeaId` member).
With `fmea`, the remedy text comes from the entry's `recovery` field, and the `except` block keeps
its structure and passes `fmea=FmeaId.X` instead of a copied string. An unknown id or an entry
without `recovery` fails when the exception is created. The CLI prints this line under the remedy:

```text
FMEA: 869778d3-80c0-4702-97eb-88068b2baab1 (git-timeout)
```

By this line, `/implement` and `/fast-implement` tell a verified scenario from a hint: they apply
the `recovery` and repeat the step at most three times (ADR 0012).

## Automated recovery test

A failure mode counts as analysed only when its entry has an automated recovery test. The test
triggers the failure, applies the scenario, repeats the step and asserts that the failure is gone.
It carries the pytest marker `fmea`, and the entry's `test` field holds its node id. The example is
`tests/fmea/test_git_timeout_recovery.py`: the test simulates a hanging `git`, checks that the error
carries `FmeaId.GIT_TIMEOUT` and the catalog remedy, then "releases the lock" and gets a successful
call. Separate tests check that every `FmeaId` reference in code is in the catalog and that the test
named by each entry's `test` field exists.

## `harness fmea show`

For queries, the catalog is built into the SQLite file `.harness/fmea.db`. The file is read-only,
never committed, and takes no part in error handling.

```bash
python scripts/fmea_catalog.py db       # build .harness/fmea.db from the catalog
harness fmea show git-timeout           # or the entry GUID
```

`harness fmea show` prints the `FMEA: <guid> (<title>)` line and the fields `mode`, `detection`,
`recovery`, `test` and `residual_risk`. When the file is not built, the command refuses and names
the build command.

## Limits

- Existing remedies stay hints until their areas move into the catalog through separate tickets:
  hooks, Python outside `orchestration`, the rest of `orchestration`. The `fmea` field in the hooks'
  JSON answer arrives with the hooks migration.
- The remedy of an internal invariant violation (`INTERNAL_INVARIANT_REMEDY`) leads to the
  [RCA phase](../skills/diagnosing-bugs.md#rca), not to the catalog: such a failure has no analysed
  scenario by definition.
- The Rust runtime does not pass an FMEA entry id yet: the `ErrorBody` change is a separate epic.

## Next

- [Error stops and RCA](error-stops.md)
- [CLI: `harness fmea show`](../reference/cli.md)
- [diagnosing-bugs: RCA phase](../skills/diagnosing-bugs.md#rca)
