# Dependencies and environment

The environment consists of host tools, the `harness-runtime serve` process, and, for container
execution, the worker image. A command being available in your terminal does not mean the runtime
service or container can see it.

## Check the environment with an agent {#agent-setup}

??? quote ah-skill-text "Agent prompt: host tools"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Read installed host requirements and inspect executable paths/versions without dumping env.
    Check Python/Git/uv and the tracker-specific glab minimum only when GitLab applies.
    Ask which OS/shell/user owns the process; propose missing-tool installation for review instead
    of executing it automatically. Project toolchain dependencies are separate from harness tools.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

??? quote ah-skill-text "Agent prompt: runtime environment"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Locate the actual harness-runtime binary and process user/PATH/IPC directory. Rust is required
    to build from source, not to use a prebuilt executable. Ask about service versus interactive
    launch. Migration needs its own human approval; restart only after user authorization and do
    not create a second runtime. Keep authentication values out of diagnostics.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

??? quote ah-skill-text "Agent prompt: container and worker image"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Ask whether containers are required at all. Read supported engine modes and check runtime-user
    access to a local engine. Distinguish distrobox/agent tools from host runtime/engine visibility.
    Verify worker /bin/sh, adapter interpreter, CLI and project tools from image/build metadata;
    image builds and live containers require separate approval. Do not mount the engine socket to workers.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

??? quote ah-skill-text "Agent prompt: console environment"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Ask whether the console is needed and inspect its documented uv launch path. Explain first-run
    network downloads and the bootstrap URL's credential status. Propose launch/environment changes
    for review; never print the token-bearing URL in reports or start a server without consent.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

??? quote ah-skill-text "Agent prompt: project dependencies and QA"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Derive project install/QA commands from manifests and CI; do not assume harness installs them.
    .harness/.venv is the development environment of this toolkit, not every target application's env.
    Agree on separate host, worker-image and clean-room QA dependencies/preparation. Ask before
    running installation, network probes or full QA; report commands not actually exercised.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

## Host tools

| Component | Requirement and check |
| --- | --- |
| Python | 3.12 or newer; run harness with a suitable interpreter. `environment.python`: `fail` below the minimum version. |
| `uv` | Available on `PATH` and executable; required for the console environment and local harness checks. `environment.uv`: `fail` if unavailable. |
| Git | Installed; the project is a Git repository. Configure a name and email for commits. Checks: `environment.git`, `environment.git_identity`. |
| Agent CLI | The runtime selected in the role profile is installed and authenticated. General health does not replace checking authentication in the selected CLI. |
| `glab` | 1.117.0 or newer for a GitLab tracker. `environment.glab`: `warn` if missing or outdated, `skipped` for other trackers. The check is local, with no GitLab request. |

With the CLI installed, run the check from the project directory:

```bash {.ah-code-wrap}
harness health .
```

From the harness source checkout, use `python3 harness/bin/harness.py health <repo>`.
Health checks individual environment properties; a green report does not mean all project QA
commands have already run.

## Rust runtime and the service environment

Backend orchestration requires the `harness-runtime` executable. Building from source requires
Rust 1.89 or newer, the runtime workspace's `rust-version`. The compiler is needed for building;
using a prebuilt binary does not make it a separate execution dependency.

When moving the ledger to the runtime store, perform the one-time migration described in the
[backend orchestration guide](../../backend-orchestration.md). Keep `serve` running while working:

```bash {.ah-code-wrap}
harness-runtime serve --repo .
```

The runtime and clients must agree on the repository, user, and runtime directory. On Unix, an
absolute `XDG_RUNTIME_DIR` selects `$XDG_RUNTIME_DIR/harness`; otherwise, `/tmp/harness-<uid>` is
used. Windows uses `XDG_RUNTIME_DIR` or `%LOCALAPPDATA%\harness`. For a service, check its own
`PATH` and environment variables, not just the interactive shell settings. See
[Secrets and tokens](secrets.md) for IPC paths and tokens.

## Container execution

Docker or Podman is required only when selecting the container executor. It needs a Linux host
with a local engine, the `docker` or `podman` CLI on the `PATH` of `harness-runtime serve`, and
permission for that user to access the engine.

Images must already exist in the local engine under the tags named by the policy: the runtime
starts containers with `--pull never`. The worker image is always required; the proxy image is
required with non-empty `network.hosts`. The project builds and prepares these images.

| In the worker image | Purpose |
| --- | --- |
| `/bin/sh` | QA commands run through `/bin/sh -c`. |
| Interpreter named in the adapter's shebang | Runs the project-owned agent adapter. |
| Agent CLI, Git, and project tools | Executes the role and its commands inside the container. |
| Support for an arbitrary uid | A rootful engine runs the container with the host user's uid:gid. |

The image must not contain secrets, depend on its own home directory, or declare `VOLUME`. The
runtime sets the entrypoint, user, and working directory; `HOME` is a tmpfs. See the
[backend orchestration guide](../../backend-orchestration.md) for the full image contract and policy fields.

## Console

The launcher uses `uv` to run the console with pinned Python dependencies. They are downloaded on
first launch, so network access is required. The availability of `uv` is checked separately from
package registry access. See the [quick start](../index.md) for launch commands.

## Project dependencies and QA preparation

Installing harness does not install the project's own libraries and tools. Prepare them following
the project's instructions; QA commands must work in the checkout and environment where they run.

For orchestration, `qa_preparation` can prepare dependencies before `verification_commands`.
Optional `qa_environment_probes` and `qa_project_file_checks` run only after failed preparation to
collect independent diagnostics. See the [backend orchestration guide](../../backend-orchestration.md)
for the exact sequence.

The `.harness/.venv` directory created by `make bootstrap` in **this repository's source checkout**
contains harness development dependencies. It does not replace the target project's environment.
A separate test-author also needs a working runner and isolation; see the
[test-author guide](../../agents/test-author.md).

## If a tool is missing

1. Check the version and `PATH` in the process performing the action: the shell, runtime service,
   or worker container.
2. Install the missing dependency there; changing the host does not add it to an existing image.
3. After changing the service environment, restart the runtime, then repeat health and the
   relevant preflight. Do not print secret values in diagnostics.

Migration requires human approval: [command and arguments](container.md#host).
