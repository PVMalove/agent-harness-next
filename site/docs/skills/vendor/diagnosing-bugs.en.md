# diagnosing-bugs — Diagnosing errors

## 1. Name and localization

- **English name:** `diagnosing-bugs`
- **Translation:** Diagnosing errors.
- **Source skill:** [`SKILL.md`](https://github.com/PVMalove/agent-harness-next/blob/master/skills/vendor/mattpocock/engineering/diagnosing-bugs/SKILL.md)

## 2. Russian description

Leads a step-by-step diagnosis of a hard failure or a performance regression: reproduction, hypotheses, observations, and verification of the cause.

## 3. Application

The source `SKILL.md` defines the exact order of steps, the entry conditions, and the limits. This page is a Russian pointer to the pinned upstream version.

In `engineering-suite`, a [first-party override](../diagnosing-bugs.md) is used. With project memory enabled, it searches
for past fixes through `harness memory search`. The vendor snapshot stays unchanged.
