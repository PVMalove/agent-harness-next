# Integrations

`.harness/integrations.json` is the inventory of project MCP, plugin, hook, and other integration
configs. It associates a file with a runtime, its SHA-256, and a verification action. The connection
itself stays in the runtime's native config; an inventory entry does not enable it.

## Who updates the file

The installer records hook configs during `harness init`, `adopt`, and `update`. Registering an
integration again replaces its entry and preserves the other entries. The project records its own
integrations itself. The installer refuses an unreadable existing inventory rather than
replacing it with an empty one; repair its format first.

Hook updates merge managed entries with user settings instead of replacing the entire native
config. `managed_entries` holds fingerprints of previously written handlers, helping distinguish
outdated harness entries from user edits. See [hook installation and update](../../hooks/install-and-update.md).

## Structure and constraints

The top level is an object with `schema: 1` and an `integrations` array. Each entry is an object:

| Field | Validation rule |
| --- | --- |
| `id` | A non-empty string, unique within the inventory. |
| `kind` | One of `mcp`, `plugin`, `hook`, `runtime-setting`, `other`. |
| `runtimes` | A non-empty array of runtime name strings. The validator does not define a closed list of names. |
| `config` | A non-empty relative path inside the project, without `..` segments. The file must exist. |
| `sha256` | 64 lowercase hexadecimal characters; the hash must match the bytes of the `config` file. |
| `secret_refs` | An array of variable names matching `[A-Z][A-Z0-9_]*`. May be omitted, defaulting to an empty list. Secret values are not allowed here. |
| `verify` | A string that is non-empty after trimming whitespace: an action to verify the integration. |
| `managed_entries` | An optional array of unique SHA-256 fingerprints, each with 64 lowercase hexadecimal characters. The installer writes it for hooks. |

`files.integrations` validates the shape of `verify` but does not execute its action. Likewise,
`secret_refs` validates names, not variable availability or access to an external service.

## Native configs to record

The validator looks for these files relative to the project root. Each existing file needs an
entry with its path in `config`:

- `.mcp.json`
- `.claude/settings.json`
- `.claude/settings.local.json`
- `.codex/hooks.json`
- `.kimi/mcp.json`
- `opencode.json`
- `opencode.jsonc`

If none of these files exist, a missing inventory is not itself an error for this check. Other
paths can also be recorded through `config`.

## Example entry

This example records `.claude/settings.json` containing exactly `{}` followed by an LF newline.
It is an inventory example, not an instruction to replace an existing config with an empty object.

```json {.ah-code-wrap}
{
  "schema": 1,
  "integrations": [
    {
      "id": "claude-settings",
      "kind": "runtime-setting",
      "runtimes": ["claude"],
      "config": ".claude/settings.json",
      "sha256": "ca3d163bab055381827226140568f3bef7eaac187cebd76878e0b63e9e442356",
      "secret_refs": [],
      "verify": "Review the project settings in Claude Code"
    }
  ]
}
```

For your own file, compute the hash of its current bytes:

```bash {.ah-code-wrap}
python3 -c 'import hashlib, pathlib; print(hashlib.sha256(pathlib.Path(".claude/settings.json").read_bytes()).hexdigest())'
```

## Check and troubleshoot

With the CLI installed, run this from the project directory:

```bash {.ah-code-wrap}
harness health .
```

From the harness source checkout, the equivalent is `python3 harness/bin/harness.py health <repo>`.
Look for `files.integrations` in the report; without the project lock file, it is `skipped`.

| Diagnostic | What to check |
| --- | --- |
| `project integrations are not inventoried` | Add an entry for every listed native config. |
| `file is missing` | Check the `config` path and whether the file exists. |
| `hash mismatch` | Review the native config diff, then update `sha256` after confirming the change. Use `harness update` for managed hooks. |
| An entry field error | Compare the entry with the constraints table above. |

Then perform the integration's own `verify` action. A successful health check does not prove an
external service is available.

## Configure with an agent {#agent-setup}

??? quote ah-skill-text "Agent prompt: record project integrations"

    ```text
    Help me configure the project integration inventory.

    Follow repository instructions. Keep questions, choices and user-facing summaries in Russian.
    Read .harness/integrations.json if present, the installed integrations validator,
    hook installation/update guide and runtime discovery documentation. Inspect native config
    file names and existing inventory metadata without printing authentication values.
    Never read auth files or request, print, copy or store token/key values.
    Ask only for unresolved facts, one question at a time. Offer 2-4 concrete choices
    plus «Другое», with one consequence each. Put an evidence-based recommendation
    first and mark it «Рекомендуется»; otherwise ask for the missing fact.

    Ask which existing MCP/plugin/hook/runtime-setting should be recorded, for which runtimes
    and what exact verification action confirms it. Inventory registration does not activate
    an integration or perform login. Use only actual repository-relative config paths.
    Explain schema: 1, unique IDs, allowed kinds and SHA-256 of current config bytes.
    Ask for variable NAMES only in secret_refs; this neither exports variables nor verifies auth.
    Treat managed_entries as installer-owned fingerprints; do not fabricate them or reset hashes
    merely to silence health. For managed hooks, propose the supported update procedure separately.
    Preserve existing native config and unrelated inventory entries. If an existing inventory
    is malformed, report it and propose a repair rather than replacing it with an empty list.
    Show the exact proposed diff and why each entry is needed. Include hashes, never config
    contents that could contain secrets. Wait for approval, then apply only that inventory diff
    with Edit/Write. Run harness health and inspect files.integrations. A skipped check is not
    a pass; explain missing prerequisites. Ask separately before executing verify actions,
    connecting services or changing native settings. Report checks and unresolved activation.
    Do not install plugins, enable MCP servers, change credentials or permissions, run updates,
    change Git, commit or open a PR as part of inventory registration.
    ```

## Related settings

- [Secrets and tokens](secrets.md) — storing values and passing them to a container.
- [Container](container.md) — configure variable passing and network access separately.
- [Dependencies and environment](environment.md) — host tools and the worker image.
- [Runtime discovery](../../runtime-discovery.md) — native roots and skill routes.
