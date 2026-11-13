# Skill discovery in Claude Code and Codex

This page describes skill discovery in Claude Code and Codex. The installed set is physically
stored in `.harness/skills/`; the links in the project point to the same files. The paths
and hook wiring for these two runtimes are described below.

| Runtime | Project path | Global `start-project` and `integrate-project` |
| --- | --- | --- |
| Claude Code | `.claude/skills` → `.harness/skills` | `~/.claude/skills/start-project`, `~/.claude/skills/integrate-project` |
| Codex | `.agents/skills` → `.harness/skills` | `~/.agents/skills/start-project`, `~/.agents/skills/integrate-project` |

`harness init`, `adopt`, and `update` create or check the project links and write
`.harness/skills/REGISTRY.md` with the names, paths, and descriptions of the installed set.
`harness health` checks the integrity of the files and links. `bin/install-global.py` creates
the global profile and the links to `global-skills/start-project` and `global-skills/integrate-project`
for the selected runtime.

Skill discovery does not load the full body of a skill in every session: the runtime uses
the metadata to choose, and then reads the matching `SKILL.md`. The pinned
upstream files are preserved byte for byte; their frontmatter and invocation settings remain part of
the original skill. Project-owned integrations are described in `.harness/integrations.json` with
the path, SHA-256, runtime target, and activation check; secret values are not stored there.

Project hooks connect to the same two runtimes, but not through links to `.harness/skills/`:
`harness init`, `adopt`, and `update` merge the managed entries into `.claude/settings.local.json` for
Claude Code and into `.codex/hooks.json` for Codex, and they do not touch user entries. For Codex,
the critical guards and `require-bounded-check` are connected on `PreToolUse` for `Bash`, and the advisory
`targeted-check-reminder` is connected on `Stop` and `SubagentStop`. Codex sends file edits as `apply_patch`:
the critical guards `protect-hook-policy` and `block-scratch-outside-docs-tasks` are connected by the group
`apply_patch|Write|Edit` and check the patch paths through the `apply_patch_payload.py` adapter. The `Write`
and `Edit` rows of the ChangeImpact hooks are not connected to `apply_patch`, and the project hooks
work after the user trusts the `.codex/` layer and each hook by hash. The `hooks.policy` check
in `harness health` shows the connected and missing hooks of each runtime;
for details, see [install-and-update](hooks/install-and-update.md).

The CLI and the sources may contain routes for other runtimes. They are not part of the declared
compatibility described on this page, because their operation was not verified in this project.
