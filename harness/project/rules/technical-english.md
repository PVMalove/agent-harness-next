# Technical English for agent coordination

This rule governs English agent-to-agent text.

## Scope, language, and authority

The rule covers briefs, handoff notes, checkpoints, state evidence, dependency explanations,
messages to the next worker, and the free coordination fields that the protocol requires in English.
Coordinators and workers follow it from their first English handoff.

Text a human reads — chat replies, user-facing summaries, and completion reports — follows the
project's language policy; Russian text follows [Technical Russian](technical-russian.md).
Exact tokens and source quotations keep their original language.

## Clear instructions without changing meaning

Use short sentences as guidance, not a word-count limit.
Put one instruction in each sentence.
Use active voice.
Name the actor in every instruction; omit the actor only when the source makes it unambiguous.
Put necessary conditions before the action they control.
Use one established project term for each concept.
Keep facts, assumptions, and requested actions distinguishable in ordinary prose.
Label an assumption when the reader could mistake it for a verified fact.

Meaning takes priority over brevity.
Preserve every material condition, negation, prohibition, and limit on scope.
Preserve modality: `must` is an obligation, `must not` is a prohibition, and `may` is permission
or possibility as used in the source.
Keep uncertainty and unknown results explicit.
Keep an ambiguous requirement ambiguous in the handoff; resolve it by asking, never by paraphrase.

## Exact tokens and source fidelity

Preserve JSON field names, enums, commands, paths, SHA, test names, code, and quotations of
source evidence verbatim.
Explain a token in surrounding prose when needed; keep the token itself unchanged.
A paraphrase must preserve the source's conditions, uncertainty, and limits.
Do not strengthen a claim, omit a limit, or present a paraphrase as an exact quotation.

Before sending English coordination text, silently check:

- Is the recipient clear, and is the requested action clear?
- Are the necessary conditions and prohibitions preserved?
- Are scope, modality, and uncertainty unchanged?
- Are exact tokens, quoted evidence, and paraphrased conditions faithful to the source?

Revise the text until these checks pass.

## Examples and counterexamples

| Source meaning | Clear English | Counterexample and lost meaning |
| --- | --- | --- |
| QA evidence must cover the candidate SHA, and opening a PR needs explicit human approval. | If accepted QA evidence covers candidate SHA `0123456789abcdef0123456789abcdef01234567`, and the developer explicitly approves opening the PR, the coordinator may start the separate PR step for that candidate. | "QA passed. Open the PR." drops the candidate binding and human approval, and turns permission into an order. |
| Workers are prohibited from editing the immutable brief. | Workers must not edit the immutable brief. If scope must change, workers must escalate to the coordinator. | "Workers should avoid editing the brief." weakens a prohibition into advice. |
| A runtime may provide telemetry; the result is unknown for this dispatch. | The runtime may provide token telemetry. Its availability is unknown for this dispatch. | "The runtime will provide telemetry." turns an uncertain possibility into a promise. |
| The requested command is `make lint`; the completion field is `"report_language": "ru"`. | Run `make lint`. Keep `"report_language": "ru"` in the completion report. | "Run the lint command and set the language to Russian." loses the exact command, field name, and enum value. |

Apply the same checks when reviewing another agent's English text: a shorter message passes only
when it preserves that meaning and those tokens.
