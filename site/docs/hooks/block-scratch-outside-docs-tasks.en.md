# block-scratch-outside-docs-tasks

## 1. Name and localization
- **English name:** Block Scratch Outside Docs Tasks
- **Translation / Essence:**

```text
Blocking of saving drafts outside the tasks directory
```
## 2. Full description
The script is a pre-hook (called before the file write or edit tools run). Its main goal is to enforce the artifact storage standards (according to `docs/agents/artifacts.md` and `docs/agents/git-workflow.md`).

Internal logic:
1. Reads JSON from STDIN and extracts `tool_input.file_path` with a JSON parser, normalizing
   Windows separators before the check. A path outside the project (`CLAUDE_PROJECT_DIR`) is blocked with
   a message that names the exit from the project. The exception is the Claude Code memory directory
   `<CLAUDE_CONFIG_DIR or ~/.claude>/projects/<slug>/memory/`: writing there is allowed.
2. If the file path indicates that the file is a PR body or a comment (by the presence of `pr-body`, `pr-comment`, `issue-comment` in the path):
   - The script allows writing only to the publication file directory `.harness/.sandboxes/pr_body/` (for example, `.harness/.sandboxes/pr_body/pr-body-<issue>-<slug>.md`) and blocks any other path, including `docs/tasks/`. After a successful submission through `gh`/`glab`, the file is deleted; on an error, it stays for a retry.
3. For all other files (working files, drafts, specifications):
   - The exception is the bound session scratchpad: `.harness/.sandboxes/scratch/sessions/<session_id>/scratchpad/`. Writing there is allowed only if `<session_id>` in the path equals `session_id` from the input JSON and matches `[A-Za-z0-9][A-Za-z0-9_-]{0,127}`. A path of another session is blocked. The runtime system scratchpad directory outside the project is still blocked as a path outside the project.
   - If someone tries to save a file to temporary system directories (for example, `AppData\Local\Temp`, `AppData\Roaming\Temp`, `/tmp/`, or `/scratchpad/`), the script blocks the operation and reminds that task specifications and drafts must be stored in `docs/tasks/`.
4. The script passes the `apply_patch` payload of the second runtime (`tool_name: "apply_patch"`, the patch in `tool_input.command`) to the adapter `apply_patch_payload.py fanout`: the adapter parses the patch the same way the runtime does, and for each path from the headers `*** Add File:`, `*** Update File:`, `*** Delete File:`, `*** Move to:` (made absolute from the payload `cwd`) it runs this script again with the payload `Write{file_path}`. The first refusal is returned as is, so a patch for several files is blocked if even one path is blocked. A patch that cannot be parsed (the runtime itself would reject it), a `tool_input.command` that is not a string, and a missing adapter give a block with the prefix `[apply-patch-unparseable]` and a remedy: which patch format to send. The second runtime does not set `CLAUDE_PROJECT_DIR`: the adapter passes the root of the checkout that the hook command from the template changes into. The shell call `apply_patch <<'EOF'` in Bash is not checked by this hook: in the first runtime it is not attached to Bash either.
5. If none of the blocking conditions fired, the script exits successfully (allows the operation).
## 3. Contracts
- **Input (Input/Brief):** JSON through STDIN that contains information about the tool call, including the argument `file_path` and `session_id`.
- **Output (Output/Report):** Return code `0` (allow the tool to run), or `2` (block) with an error message in STDERR that names the violated rule from the documentation. In the `hook_response.py` envelope, a block gets the `reason_code` `scratch-location`, and an unparseable `apply_patch` gets `apply-patch-unparseable`.
## Source

[block-scratch-outside-docs-tasks.sh](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/block-scratch-outside-docs-tasks.sh), [apply_patch_payload.py](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/apply_patch_payload.py)
