# <Feature or change>

**Status** — <`Approved` or `Draft — has open blockers`>

## Goal & Scope

<Describe the user-visible outcome, the problem it solves, and the scope. Give each functional
requirement an ID such as `R1` so it can be traced to a check.>

## Non-Goals & Rejected Alternatives

<List the explicit exclusions. For each rejected alternative, record the decision ID, option
number when available, approach, and reason it was rejected. Describe a rejected approach without
citing unapproved paths.>

## Architecture & Selected Approach

<Record each accepted decision with its original ID, selected option number and profile when
available, mechanism, rationale, and trade-off. Use confirmed domain terms and cite applicable ADRs
from approved paths or identify them by title or ID from the handoff. Describe the flow and
invariants needed to implement the design. If the handoff provides an existing, agreed integration
branch, record its exact name as `- Branch: ...` under a separate `## Integration Branch` heading
before the Discovery Context section.>

## Surgical File & Contract Changes

| Approved path | Required change | Contract or invariant |
| --- | --- | --- |
| `<repo-relative path>` | <Smallest change that satisfies the requirement> | <Model, signature, API, event, or invariant affected> |

<Use one row per file to change. Distinguish additions from edits. Use only approved paths.>

## Edge Cases & Failure Modes

<For each relevant invalid input, error, timeout, or boundary state, describe the trigger, observable
behavior, and recovery where applicable. Cover realistic failures at the affected boundary.>

## Acceptance & Verification Criteria

| Requirement | Observable result | Test to add or update and its seam | Verification command or steps |
| --- | --- | --- | --- |
| `R1` | <Specific condition that proves success> | <Behavior and approved test path if named> | <Project command or reproducible manual check> |

<Cover every functional requirement. Prefer existing public seams. Include regression checks for
the relevant failure modes. Mark checks that depend on an unresolved choice as blocked.>

## Open Questions & Risks

<List risks and residual questions. For a Draft, list each blocker, the work it blocks, and the
explicit decision or evidence needed before implementation.>

## Relevant Files (Discovery Context)

<Copy the approved artifact entries in order, retaining their notes. Include any additional paths
explicitly approved in chat. Use one repo-relative path per bullet. When none are approved, state
that the spec cites no repository files.>
