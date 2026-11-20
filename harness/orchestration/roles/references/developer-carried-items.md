# Developer: carried items

Read this when a developer-retry brief's `carried_items` is not empty.

A developer-retry brief whose `carried_items` is not empty hands on the closed list of items its
retry decision recorded as `retry_item_ids`, keyed by source: each `coordinator-finding` is a defect
the coordinator found when it accepted a developer report, each `review-finding` is a Standards or
Spec finding of the retried code-review, and each `incomplete-item` is an item a read-only report
handed to the developer; a retried developer brief hands on its own items again. Every item has an
`item_id`, `summary`, `files` and `expected_evidence`. Close every carried item in this retry with
new commits: its files belong to the working set, and its fix goes into the commit of the plan entry
whose scope it belongs to. The completion report maps every item once in `carried_item_closure`,
which replaces naming the items in `output`: `{"item_id": <id>, "commits": [<sha>, ...]}` with the
commits that close it, as its `expected_evidence` asks, or
`{"item_id": <id>, "not_closed": "<reason>"}`. The commits are this dispatch's own, or, for an item
an earlier attempt that handed you the same list already closed (a retried developer report or a
tooling-retry), that attempt's commit; after a `rebase-fix-forward` attempt of the chain, its
rebased copy, never the pre-rebase original. A completed report without the field, or with an item
left out, repeated or unknown, an empty reason or a commit neither this dispatch nor such an earlier
attempt created, is refused.
An item that cannot be closed inside the allowed paths and the prohibited changes is `not_closed` with its
reason, never a silent omission: the report is then not clean, a plain accept is refused, and the
next code-review carries every open coordinator finding again and accounts for it.
