# Context for roles

A Context Package pins sources, tests and decisions for a role. The coordinator checks its size and freshness before dispatch. It guides reading but does not replace result verification.

[Orchestration overview](../../backend-orchestration.md)

## Discovery Context and Context Package {#discovery-context-and-context-package}

The Discovery Pipeline carries verified context from design to dispatch. `/grilling` maintains a
`Live Artifact` with candidate paths, but adds a path only after the user explicitly agrees.
`/to-spec` saves the approved list in the epic under `## Relevant Files (Discovery Context)`.
`/to-tickets` assigns each path to a suitable tracer-bullet ticket and builds the Path inventory. A single
cheap advisory call may add only exact dependencies from this Path inventory. Its output is
neither evidence nor authority.

Before the first dispatch, the coordinator may register a deterministic Context Package in the
ledger:

```bash
python .harness/orchestration/coordinator.py --repo . context-package register \
  --batch <batch-id> --candidate-commit <candidate-sha> \
  --symbol-graph-depth 1 --min-starting-files 5 --max-starting-files 10 \
  --max-package-tokens 60000
```

`context_builder.py` does not call an LLM and works from pinned base/candidate commits. The package contains
the exact diff, 5–10 starting files with reasons, a bounded symbol/dependency graph, related tests,
short ADR/precedent cards, the SHA-256 of each included file, the byte size, and a conservative token
estimate. Byte-for-byte identical files (for example, the mirror `docs/agents/*` ↔
`harness/project/instructions/*`) stay starting files, but the estimate counts their content once;
the reason for the second copy names the original and requires keeping the copies identical. A Markdown file
enters the package as a table of contents if its estimate is not less than
`context_package_policy.section_index_min_tokens` (20000 by default). `sections` lists the
headings of levels 1–3 (outside fenced code) with `start_line`/`end_line`; the estimate counts only this
table of contents, and the role reads only the line ranges it needs. A file without headings is counted whole.

A Python file enters as a symbol index at the same threshold. It consists of top-level functions,
classes, and class methods; anything nested inside functions and methods is not listed. The rest of the file's code
is covered by the pointers `module header` (before the first definition) and `module code` (between definitions,
after the last one, and blocks such as `if TYPE_CHECKING:`), so the index hides nothing. Symbols hidden by
`repo_map_policy.redact_symbols` stay in the headings as the marker `[REDACTED-SYMBOL]`. The index
applies only if it is cheaper than the file. A file without definitions, with a syntax error, or of another
format is counted whole. If the package does not fit the limit, the heaviest starting files for
which an index can be built are replaced by the index one at a time until the package fits the limit.
An added file cannot be shortened this way: its text already lies in the diff, and the related tests and ADRs stay in the
package whole.

Dependency cards use Repo Map signatures for direct local dependencies. If signatures are absent, the fallback is the first 30 lines of the file. This one-level dependency context is separate from the bounded symbol graph: `symbol_graph_depth` controls graph expansion. If the package does not fit
the token limit even after replacing files with indexes, the build ends with an error and does not silently truncate the package. You may set the legacy `--max-package-size-bytes` as an additional diagnostic,
but it does not replace the token limit.

The package record is immutable, versioned, and hash-verifiable. It is shared within the batch. The same
base/candidate reuses one package ID across the architect, developer, and continuation sessions.
A new package is created only after a new candidate. The coordinator does not reuse a package if
its frozen source from `memory.pointers` changed after registration, became unavailable, or was revoked.
Then the next dispatch registers a new package with current pointers. The old package
stays unchanged for the briefs already issued. The coordinator checks freshness before handoff and does not create a
brief with a stale package. If the new package is not fresh by memory either, the error names the path and the expected and
actual `source_hash`. The remedy suggests `harness memory rebuild .` from the main checkout or
`--no-memory`. The brief passes a compact summary (starting files, related tests, precedents, and pinned
commits). The full diff stays in the package once. The package does not replace the immutable brief and does not
cancel the mandatory self-report, heartbeat, review, or QA.
