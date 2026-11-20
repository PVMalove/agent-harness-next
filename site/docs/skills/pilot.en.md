# Pilot — Pilot baseline

Source: [`harness/orchestration/pilot.md`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/pilot.md).

## 1. Name and localization

- **English name:** `Pilot`
- **Russian translation:**

```text
Пилотная базовая линия
```

## 2. Full translation of the source document

<div class="ah-skill-text" markdown="1">

### Backend orchestration pilot baseline

This guide records the first observable baseline for the optional `backend-orchestration` capability. It is an observation protocol for the coordinator, not a dispatch mechanism or a performance policy.

#### Purpose

Collect comparable evidence from batches that actually completed, before deciding whether future targets or process changes are needed. Use the same worksheet and the same counting rules for the whole observation period.

#### Before the first run

1. Choose the observation period and record its start and end timestamps.
2. Decide where the evidence comes from: batch records, completion reports, quality gate logs, and the issue tracker. Record the unavailable sources before the period starts.
3. Record the batch ID, ticket ID, issue branch, role sequence, and completion state for every batch in the observation scope.
4. Declare the post-integration observation window and the project's defect severity rule.
5. Prepare one worksheet row per batch and one summary row per closed ticket. Do not fill missing measurements with estimates.

#### Observation period

For every closed ticket in the period, apply the same rules:

- count every role start as a start, and count a retry as the start of a new dispatch;
- attribute the observed provider or runtime input and output tokens to the dispatch that produced them; a role's self-report is not token telemetry, and mark unavailable data as missing;
- record the elapsed quality gate run time separately from queue or wait time;
- link every post-integration defect to its batch, and apply the declared observation window and severity rule consistently;
- keep with the worksheet the measurement period, the batch/ticket IDs, the source, the notes on missing data, and the single set of counting rules.

#### Recording each batch

Record the following before closing the batch record:

- the batch and ticket IDs, the roles that ran, the dispatch IDs, and whether a repeat dispatch happened;
- the token count of each dispatch only when provider or runtime telemetry exists, with its source and a note on missing data;
- the start and result timestamps of the quality gate, and the queue time when it is available;
- the integration timestamp and all linked defect IDs observed in the declared window.

#### Measuring the quality gate

Use the timestamps issued by the serialized quality gate lane. Calculate wall time from the gate start to its result, and keep queue time as a separate observation. If any timestamp is unavailable, record the gap instead of reconstructing it from unrelated events.

#### Recording post-integration defects

During the declared observation window, record every defect that can be linked to a batch. Include the batch ID, defect ID, detection timestamp, severity under the project rule, and the source of evidence. Do not count an unrelated defect, or a defect outside the window, without documenting the reason for including it.

#### Baseline worksheet

| Measurement | Required observation | Source / note on missing data |
| --- | --- | --- |
| Agent starts per closed ticket | Starts and retries for each closed ticket | Batch records and dispatch IDs |
| Tokens per batch | Observed provider or runtime input and output tokens for each dispatch | Telemetry or execution records; otherwise a note on missing data |
| Quality gate wall time | From the gate start to the result, with the queue separate | Quality gate timestamps |
| Post-integration defects | Linked defects in the declared window under the severity rule | Issue tracker and defect records |

The resulting baseline is evidence for future decisions. This guide prescribes no named provider, model, runtime, or platform, and no hard numeric target.

</div>

## 3. Contracts

- **Input (Input/Brief):** the observation period, the closed batches/tickets, the completion reports, the quality gate logs, the tracker, and the defect severity rule.
- **Process (Process):** the coordinator collects the same observations without estimates for missing data, and separate queue time from execution time.
- **Output (Output/Report):** a baseline worksheet with four measurements and the data gaps marked.

## Source

[pilot.md](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/pilot.md)
