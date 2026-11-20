# TDD

The test is written before the code. The cycle is short: a failing test, a minimal implementation, a
refactor. Every step ends with a green run, so a breakage always has one author.

## The cycle

1. **Red.** New behavior is described by a test at the agreed seam. The test must fail, and it must
   fail for the reason it was written for, not because of a typo in an import.
2. **Green.** Write exactly the implementation needed for the green test. Extra generality only gets
   in the way at this step.
3. **Refactor.** Behavior does not change, and the tests stay green. Refactoring lives here, not
   inside the red → green transition.

<figure class="ah-diagram">
  <div class="ah-diagram-bar">
    <figcaption>Red, Green, Refactor, and the return to a red test when it failed for the wrong reason.</figcaption>
    <button class="ah-diagram-expand" type="button" aria-haspopup="dialog">Expand</button>
    <a class="ah-diagram-open" href="../../assets/diagrams/tdd-cycle.html" target="_blank" rel="noopener">Open separately ↗</a>
  </div>
  <iframe class="ah-diagram-frame" data-theme-sync src="../../assets/diagrams/tdd-cycle.html" title="The TDD cycle" loading="lazy"></iframe>
</figure>

## Test rules

- **One behavior per test.** The test name names the behavior, not the method.
- **An agreed seam.** The test is written at a level the parties agreed on in advance: the service,
  not a private method; the public contract, not the internal structure.
- **An independent expectation.** The expected value comes from an external source (a specification,
  an example from the task, a manual calculation), not from the current implementation.
- **Deterministic clocks and RNG.** Time and randomness are injected, not read from the environment.
- **The same DBMS.** SQL and transactions are checked on the same DBMS as in production: the locking
  and data-type behavior of another DBMS proves nothing.
- **The test does not duplicate the design.** If a test breaks on any refactoring, it checks the
  implementation, not the behavior.

## The test-author role

In some projects a separate agent writes the test, with a protected test zone and an isolated runner:
it prepares one behavioral red test and runs it, but it does not change the implementation and does
not extend the test zone. This role is enabled separately. It is useful where it matters that the
author of the code does not fit the expectation to their own implementation.

The role does not replace `/tdd`: it removes from the implementing role the choice of the expected
behavior, and the red → green → refactor cycle stays the same.

## Next

- [Code review](code-review.md)
- [QA gate and Release Gate](qa-gate.md)
