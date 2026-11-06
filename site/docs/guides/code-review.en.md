# Code review

The review runs on two independent axes, and their reports are not merged. Code can satisfy one axis
and fail the other: it can be tidy in style but implement the wrong thing. Subagents check both axes
in parallel from a fixed point: a commit, branch, tag, or merge-base.

## Standards

This axis checks conformance to the repository's documented standards and to a baseline of twelve
Fowler code "smells", for example Mysterious Name, Duplicated Code, Primitive Obsession, and
Repeated Switches. A smell is a judgment, not a hard violation, so it does not count as a defect.
The axis does not repeat what a linter catches: the linter has already reported it. If they conflict,
the repository standard takes precedence over the baseline.

## Spec

This axis checks conformance to the originating ticket or specification: what is missing, what is
done in excess (scope creep), and what is implemented incorrectly. If the specification cannot be
found, the axis is skipped explicitly and does not invent requirements.

## How it works

The input is the diff from the fixed point and the task description. Two subagents receive independent
instructions, work in parallel, and return reports to the main session. The main session does not
silently fix another reviewer's findings; it decides on each one. The report language comes from the
`language` field of the project configuration, not from the language of code comments.

<figure class="ah-diagram">
  <div class="ah-diagram-bar">
    <figcaption>The diff and the ticket split into the Standards and Spec axes, and the reports stay separate.</figcaption>
    <button class="ah-diagram-expand" type="button" aria-haspopup="dialog">Expand</button>
    <a class="ah-diagram-open" href="../../assets/diagrams/review-axes.html" target="_blank" rel="noopener">Open separately ↗</a>
  </div>
  <iframe class="ah-diagram-frame" data-theme-sync src="../../assets/diagrams/review-axes.html" title="Code review: two independent axes" loading="lazy"></iframe>
</figure>

An example of a report fragment:

```text
Standards — Warning
- services/reports/csv.py: Primitive Obsession (judgment) — the delimiter is passed as a string in three places.
Spec — Clean
- All ticket items are covered; there is no extra behavior.
```

## What counts as a blocker

- An unmet acceptance criterion.
- A change outside the declared scope of the task.
- New behavior without a test.
- A weakened check: a disabled test, `except: pass` around the action under test, or a case narrowed
  to a trivial one.

A Standards finding is a matter of judgment: it can be accepted as debt if it does not affect
behavior. A Spec finding is not a matter of judgment: a divergence from the task is either fixed, or
the task is explicitly reworded.

## Next

- [QA gate and Release Gate](qa-gate.md)
- [Examples](examples.md)
