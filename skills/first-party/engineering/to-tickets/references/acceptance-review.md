# Acceptance review

## Compare acceptance criteria

For each epic criterion, compare its conditions, actions, and observable results with the mapped
`Action -> Verify` lines. Check that the actions exercise the required conditions and the checks
would fail if any promised result or constraint were violated. For a criterion split across tickets,
check their combined coverage and identify the ticket that verifies any result that depends on the
pieces working together.

For example, if `R3` requires a repeated import to produce no duplicates, rerun the same import
and assert the absence of duplicates in the stored records. A successful response alone leaves
that obligation uncovered.

For the plan, repair missing or weakened checks in the cards and update the traceability matrix
before requesting approval. Surface any unresolved requirement meaning to the user and return to
`/to-spec` when the specification needs clarification.

## Review published tickets

Use the current tracker as the source. Read the published epic and use the approved specification
in its body as the baseline. If it is missing or unapproved, ask for the approved specification
before making a coverage claim. If the specification leaves the acceptance outcome undefined,
report the gap in the specification itself.

Read the current bodies of all linked child tickets, open and closed. The placeholders follow the
conventions in `docs/agents/issue-tracker.md`.

- GitHub: list the children with
  `gh api repos/<owner>/<repo>/issues/<epic>/sub_issues --paginate --jq '.[] | [.number, .state, .title] | @tsv'`,
  then read each one with `gh issue view <n> --json title,state,body`.
- GitLab: list the links with `GITLAB_HOST=<host> glab api --paginate projects/<project-id>/issues/<epic>/links`
  and keep the linked issues of this project whose description carries `## Parent: #<epic>`. Read
  each one with `glab issue view <n> -R <project-url> -F json`.
- Local tracker: read `.scratch/<feature-slug>/spec.md` and the ticket files under its `issues/`
  directory.

Compare the published lines using the checks above. For older tickets without IDs, map criteria
by their text where the obligation is clear and flag ambiguous mappings. Report each gap or
weakened check with the epic criterion, ticket link or path when available, and proposed correction.
If a ticket or the full child list cannot be read, report incomplete coverage. Return the findings
in chat. This route is read-only.
