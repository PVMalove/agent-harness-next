# Secrets and tokens

There are several kinds of credentials: agent CLI authentication, integration secrets, the runtime
IPC token, and the web console token. They belong to different processes and are not interchangeable.

## Configure secrets without sharing values with an agent {#agent-setup}

??? quote ah-skill-text "Agent prompt: CLI model authentication"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Ask which agent CLI/account type and shell are used. Read supported authentication instructions,
    never auth stores. Give the user private login/entry steps; do not accept credentials or perform
    login for them. Harness configuration must contain supported variable names, not secret values.
    Do not claim successful authentication without a separately authorized sanitized check.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

??? quote ah-skill-text "Agent prompt: container secrets"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Ask only required variable names, runtime process location and shell. Explain access_policy
    environment versus service environment, reserved names, proxy hosts and new approval for plan
    changes. For Bash provide manual read -rs and export instructions for the user to execute privately.
    The user restarts the existing runtime with updated environment; do not create a duplicate process.
    Use preflight metadata without printing values; see the container guide for the complete procedure.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

??? quote ah-skill-text "Agent prompt: integration secret_refs"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Read inventory metadata only; ask which variable names an existing integration needs.
    secret_refs documents names and neither exports them nor verifies auth. Do not read secret-bearing
    native config or fabricate managed_entries. Preserve native settings; actual credentials are
    entered by the user in the runtime's supported mechanism, separately from inventory editing.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

??? quote ah-skill-text "Agent prompt: runtime and console tokens"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    First distinguish IPC and console tokens. Check repository/user/IPC-directory metadata and
    service ownership without reading token files or requesting bootstrap URLs/cookies.
    IPC clients read their token themselves; the console exchanges its startup URL for a cookie.
    Explain rotation through the owning server's restart, performed by the user. If exposure is
    suspected, do not copy the value or purge history/logs automatically; agree on recovery actions.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

## Where credentials live

| Credentials | Where the value lives |
| --- | --- |
| Agent access to a model | The CLI's authentication mechanism or its environment. |
| Integration secret | The environment or native config, according to the runtime's rules; the inventory holds names only. |
| Runtime IPC token | A separate `<repo-id>.token` file created by `harness-runtime serve`. |
| Web console token | The server; after opening the launch URL, also an HttpOnly cookie in the browser. |

Do not copy CLI authentication files into `.harness/project.json`, `.harness/orchestration.json`,
a brief, or a prompt. Authenticate the CLI using its own mechanism; the integrations inventory does
not sign in to a service.

## Passing secrets to a container

The `environment` component in `access_policy.defaults` or a role override contains names, never
values:

```json {.ah-code-wrap}
{
  "environment": ["ANTHROPIC_API_KEY"]
}
```

This is a policy fragment, not a complete `orchestration.json`. Use the name your agent adapter
expects. The engine receives `--env NAME` and reads the value from the environment of
`harness-runtime serve`, not from the terminal that later invokes the coordinator.

In Bash, you can enter a value without displaying it or writing the value itself to command history:

```bash {.ah-code-wrap}
read -rs -p 'ANTHROPIC_API_KEY: ' ANTHROPIC_API_KEY
printf '\n'
export ANTHROPIC_API_KEY
harness-runtime serve --repo .
```

If the runtime is already running, stop it normally and restart it with the updated environment.
For a service, set the variable in that service's environment. Do not start a second runtime for
the same repository.

- A missing name blocks `dispatch preflight` and sending.
- Names are pinned in the plan digest: a variable added after `dispatch propose` will not reach
  an already proposed dispatch.
- Do not list names set by the executor: `HOME`, `GIT_CONFIG_COUNT`, `GIT_CONFIG_KEY_0`,
  `GIT_CONFIG_VALUE_0`, `HARNESS_EXECUTOR`.
- With non-empty `network.hosts`, these are also reserved: `HTTP_PROXY`, `HTTPS_PROXY`, `http_proxy`,
  `https_proxy`, `NO_PROXY`, `no_proxy`.

API access also depends on the network allowlist. See the
[backend orchestration guide](../../backend-orchestration.md) for policy fields and checks.

## Integration secrets

`secret_refs` accepts only names matching `[A-Z][A-Z0-9_]*`, for example:

```json {.ah-code-wrap}
{
  "secret_refs": ["ANTHROPIC_API_KEY"]
}
```

This list documents an integration's dependency. It does not export variables, pass them to a
container, or check authentication. A container needs `environment` separately. See
[Integrations](integrations.md) for the full contract.

## Runtime IPC token {#ipc-runtime}

On Unix, `harness-runtime serve` creates `$XDG_RUNTIME_DIR/harness/<repo-id>.token` when
`XDG_RUNTIME_DIR` is an absolute path. Otherwise, it uses `/tmp/harness-<uid>/<repo-id>.token`.
The runtime directory has mode `0700`; the token file and socket have mode `0600`. Windows uses
`XDG_RUNTIME_DIR` or `%LOCALAPPDATA%\harness` and platform access checks.

The client reads the token automatically; do not copy it into a project config or command.
When running as a service, the runtime and its clients must use the same runtime directory.
Restarting the server creates a new token. See [Rust runtime](../../architecture/runtime.md).

## Web console token {#web-console}

The server generates a token on startup, and the launcher prints a URL containing it. Opening the
correct URL redirects to a clean URL and sets a cookie with `HttpOnly` and `SameSite=Strict`.
The token is not written to project contracts.

Treat the original URL as a credential: do not paste it into an issue, report, screenshot, or
prompt. A new server process receives a new token; reopening an already running console does not
rotate it. See the [quick start](../index.md) for launch instructions.

## If a value is exposed

1. For a model or integration key, revoke it with the provider and issue a replacement; update
   the CLI authentication or the relevant process environment.
2. For an IPC token, restart the runtime. For a console token, stop the console server itself and
   start a new process. Closing a tab or TUI does not mean the web server has stopped.
3. Remove the value from accessible logs, reports, and publications. If it entered Git, revoke
   it first: deleting it from the current file does not remove history.
4. Check access without printing the value. An agent prompt should request checks of names,
   availability, and authentication results, not read authentication files or reveal a secret.

## Related settings

- [Dependencies and environment](environment.md) — host, service, and image environments.
- [Hook installation and update](../../hooks/install-and-update.md) — managed native config entries.

- [Container](container.md) — complete executor setup.
