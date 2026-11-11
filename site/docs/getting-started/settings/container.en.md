# Container

The built-in `docker` executor starts an approved external worker in a separate Docker or Podman
container. Container QA is enabled separately: each gate command gets its own container.
This page walks through setup; the complete field reference is in
[Access and container](orchestration/access.md).

## When to use it and what changes {#when-to-use}

Use the executor to limit worker access to project resources and provide a consistent set of
tools in an image. It supports only `transport: external`; `in-process` is a blocker.
Dispatch approval and the agent's native approval remain in place. The container does not
approve actions for a human, enable auto-approve or widen the pinned plan.

The harness does not build, pull or publish images. Prepare them first; `dispatch propose` pins
local image IDs, and execution uses those IDs. Configuration changes or image rebuilds need a
new propose and approval to apply to a dispatch.

## Host requirements {#host}

You need Linux, a local engine, the runtime store and a running `harness-runtime serve`.
The `docker`/`podman` CLI must be on the **runtime process's PATH**, and its user must have engine
access. The repository and all plan resources must be available at the same absolute paths.

| Environment | What the repository verifies |
| --- | --- |
| Rootful Docker on Linux | Live CI smoke covering worker + QA. |
| Rootless Podman, Fedora, SELinux enforcing, cgroup v2 | Live smoke on a self-hosted runner; cpu, memory and pids are delegated to the user. |
| Rootful Podman; rootless Docker; Docker with SELinux enforcing | Only the argv matrix and a scripted engine. No confirmed live smoke for these combinations. |
| Remote Podman; Docker `userns-remap`; CLI shim with a mismatched `info` response | Unsupported: preflight blocks execution. |
| Non-Linux host or file ledger | The container executor is blocked. |

When moving from the file ledger, stop its active work first and obtain human approval for
migration. The current Rust CLI requires `--approved-by`, `--approved-at` and `--reason`;
`migrate --repo .` alone is insufficient. In Bash at the target project root:

```bash {.ah-code-wrap}
read -r -p 'Approved by (human): ' MIGRATION_APPROVER
read -r -p 'Approval time (RFC 3339): ' MIGRATION_APPROVED_AT
read -r -p 'Approved migration reason: ' MIGRATION_REASON
harness-runtime migrate --repo . \
  --approved-by "$MIGRATION_APPROVER" \
  --approved-at "$MIGRATION_APPROVED_AT" --reason "$MIGRATION_REASON"
```

Record the actual approval: the time must not be in the future, and the approver cannot be
`policy:`. Do not migrate while ledger owners are active; follow its remedy. If the runtime
store is already in use, container setup does not require another migration.

```bash {.ah-code-wrap}
harness-runtime serve --repo .
```

Keep `serve` running. It and the coordinator must use the same user, repository and IPC directory:
on Unix, an absolute `XDG_RUNTIME_DIR` selects `$XDG_RUNTIME_DIR/harness`; otherwise it uses
`/tmp/harness-<uid>`. A service has its own PATH and environment; changing another terminal's
variables does not update them. Do not start a second runtime for the same repository.

## Build images {#images}

The following commands build images with your selected engine. A target project with
`backend-orchestration` installed has the sources in `.harness/container/`. In the harness
repository itself, they are in `harness/container/`: replace both path occurrences in each command.

### Base and proxy

Choose **one** engine. Docker and Podman use separate image stores.

```bash {.ah-code-wrap}
docker build -f .harness/container/Dockerfile.sandbox \
  -t harness-sandbox:local .harness/container
docker build -f .harness/container/Dockerfile.proxy \
  -t harness-proxy:local .harness/container
```

```bash {.ah-code-wrap}
podman build -f .harness/container/Dockerfile.sandbox \
  -t harness-sandbox:local .harness/container
podman build -f .harness/container/Dockerfile.proxy \
  -t harness-proxy:local .harness/container
```

The base contains `git`, `curl`, `jq`, CA certificates, Python with `uv`, Node.js and npm.
The current Dockerfile pins Debian `trixie-20261020-slim` and `uv:0.12.21`.
It does not install Rust, gcc or an agent CLI.

### Project Dockerfile.worker

This template adds Rust from a chosen official Rust image, gcc/libc6-dev and Claude Code.
`jq` and `uv` come from the base. Save it as `Dockerfile.worker` in your project.
All versions are explicit choices: a Rust image tag/digest, compatible Debian package versions
and a CLI version. Building this repository's runtime needs Rust ≥ 1.89; other projects set
their own requirements.

```dockerfile {.ah-code-wrap}
ARG RUST_IMAGE
FROM ${RUST_IMAGE} AS rust_toolchain

FROM harness-sandbox:local
ARG GCC_PACKAGE_VERSION
ARG LIBC6_DEV_PACKAGE_VERSION
ARG CLAUDE_CODE_VERSION
RUN test -n "$GCC_PACKAGE_VERSION" \
    && test -n "$LIBC6_DEV_PACKAGE_VERSION" \
    && test -n "$CLAUDE_CODE_VERSION" \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
       "gcc=$GCC_PACKAGE_VERSION" "libc6-dev=$LIBC6_DEV_PACKAGE_VERSION" \
    && rm -rf /var/lib/apt/lists/* \
    && npm install --global "@anthropic-ai/claude-code@$CLAUDE_CODE_VERSION"
COPY --from=rust_toolchain /usr/local/cargo /usr/local/cargo
COPY --from=rust_toolchain /usr/local/rustup /usr/local/rustup
ENV PATH="/usr/local/cargo/bin:${PATH}" \
    RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/harness-home/.cargo
```

The Rust image must use the official layout (`/usr/local/cargo`, `/usr/local/rustup`) and a
Linux/ABI compatible with the base. `CARGO_HOME` points into the worker's temporary HOME while
the installed toolchain stays outside it. Check the image under the host UID: this template
needs a build and live verification in your environment; it is not a ready-made shipped image.

```bash {.ah-code-wrap}
read -r -p 'Official Rust image, pinned tag/digest: ' WORKER_RUST_IMAGE
read -r -p 'Debian gcc package version: ' WORKER_GCC_VERSION
read -r -p 'Debian libc6-dev package version: ' WORKER_LIBC_VERSION
read -r -p 'Claude Code version: ' WORKER_CLAUDE_VERSION
docker build -f Dockerfile.worker -t harness-worker:local \
  --build-arg RUST_IMAGE="$WORKER_RUST_IMAGE" \
  --build-arg GCC_PACKAGE_VERSION="$WORKER_GCC_VERSION" \
  --build-arg LIBC6_DEV_PACKAGE_VERSION="$WORKER_LIBC_VERSION" \
  --build-arg CLAUDE_CODE_VERSION="$WORKER_CLAUDE_VERSION" .
```

For Podman, replace `docker build` with `podman build`, retaining the arguments and using that
engine's base image. Never pass tokens as build arguments. Chosen versions must exist in their
registries; this page deliberately does not select them for your project.

### Worker image contract

- Include `/bin/sh`, the adapter's shebang interpreter and all agent/QA tools. QA executes
  as `/bin/sh -c '<command>'`.
- Support an arbitrary UID: rootful uses the host uid:gid, which may have no `/etc/passwd` entry.
  The runtime selects user behavior according to the engine.
- `HOME` is a tmpfs at `/harness-home`; the worker cannot see auth files or tools in the image's
  previous HOME. Install tools outside the home directory.
- The runtime sets entrypoint, user and working directory. Do not depend on your own
  `ENTRYPOINT`, `CMD` or `USER`; do not declare `VOLUME`: anonymous volumes survive removal.
- Images must contain no secrets. The runtime uses `--pull never`, `--cap-drop ALL` and
  `no-new-privileges`; the engine socket is not mounted.

## Configuration fields {#configuration}

This `.harness/orchestration.json` fragment comes from the executor guide. Adjust the engine,
required hosts and your cache path. QA here gets Python registry access and no model key.
Model settings and provider profiles stay in the existing assignments.

```json {.ah-code-wrap}
{
  "extensions": {
    "runtime_access": "docker"
  },
  "access_policy": {
    "defaults": {
      "mode": "sandbox",
      "container": {
        "engine": "docker",
        "worker_image": "harness-worker:local",
        "proxy_image": "harness-proxy:local"
      },
      "environment": [
        "ANTHROPIC_API_KEY"
      ],
      "network": {
        "hosts": [
          "api.anthropic.com",
          "github.com"
        ]
      }
    },
    "roles": {
      "code-review": {
        "network": {
          "hosts": [
            "api.anthropic.com"
          ]
        }
      }
    },
    "operations": {
      "qa": {
        "container": {
          "engine": "docker",
          "worker_image": "harness-worker:local",
          "proxy_image": "harness-proxy:local"
        },
        "environment": [],
        "network": {
          "hosts": [
            "pypi.org",
            "files.pythonhosted.org"
          ]
        },
        "filesystem": [
          {
            "resource": "cache",
            "path": "~/.cache/uv",
            "access": "write"
          }
        ]
      }
    }
  },
  "execution_policy": {
    "worker_execution_timeout_seconds": 14400,
    "qa_command_timeout_seconds": 3600,
    "stop_grace_seconds": 30
  }
}
```

| Field | What to configure |
| --- | --- |
| `extensions.runtime_access` | `docker` for either engine. Selecting it requires `access_policy.defaults.container`. |
| `access_policy.defaults.container.engine` | `docker` (default) or `podman`; the extension name remains `docker`. |
| `access_policy.defaults.container.worker_image` | Required reference to an existing local worker image. |
| `access_policy.defaults.container.proxy_image` | The executor needs a proxy image for non-empty hosts; if configured, it must exist locally. |
| `access_policy.defaults.mode` | This executor accepts `sandbox` or `inherit`; it refuses the schema-valid `unsandboxed`. |
| `access_policy.defaults.environment` | Unique variable names, never values. The runtime must have them in its own environment. |
| `access_policy.defaults.network.hosts` | Exact DNS names without a URL scheme, port or wildcard; `[]` disables networking. |
| `access_policy.defaults.filesystem` | Resources `checkout`, `git_common`, `shared_storage`, `cache`, with `read`/`write`. Item fields: `resource`, `access`, `path`; `path` is required only for `cache` and forbidden for other resources. |
| `access_policy.operations.qa.container` | Explicitly enable container QA. `defaults.container` alone is insufficient: without the override, QA remains on the host. |
| `execution_policy.worker_execution_timeout_seconds` | Integer ≥ 1, default `14400`: worker deadline. |
| `execution_policy.qa_command_timeout_seconds` | Integer ≥ 1, default `3600`: deadline for one container QA command. |
| `execution_policy.stop_grace_seconds` | Integer ≥ 1, default `30`: grace period before forced termination. |
| `assignment_plans.<ключ>.transport` | `external` for every dispatched role; the schema default is `in-process`, which is blocked here. Change transport inside the existing role plan, retaining its runtimes/model. |

A role/operation override replaces the **entire named component**, such as `container`,
`environment` or `network`. QA uses defaults plus its own operation override, not QA-role settings.
When switching from Docker to Podman, change the engine in defaults and all explicit container
overrides. Keep read-only roles read-only; the full reference is [here](orchestration/access.md).

Caches persist only as plan `cache` resources mounted at the same absolute path. Relative paths
resolve from the dispatch worktree, and `~` expands on the host. Point tools at that path through
their configuration/a named variable. A container's HOME does not persist between runs.
Host `~/.gitconfig` is not mounted; configure Git identity in the repository or through allowed
variable names. A worker gets writable artifacts and read-only shared storage, without the
runtime socket.

### Project-owned agent adapter

The harness does not ship a ready-made adapter for a particular agent. Below is the full shell
example from the guide for **Claude Code**, rather than a universal adapter for any runtime.
Check that the role assignment, model and brief tools match this CLI. Save it, for example, as
`scripts/container-agent.sh`, make it executable and keep it inside a plan root at the same path
the container sees. A `.py` adapter does not work here: the coordinator passes the host Python path.

```sh {.ah-code-wrap}
#!/bin/sh
# Project-owned runtime adapter (example). The harness does not ship this file.
set -eu
[ "${1:-}" = dispatch ] || { echo "usage: $0 dispatch --repo <repo> --brief <brief>" >&2; exit 2; }
shift
brief=""
while [ $# -gt 0 ]; do
    case "$1" in
        --repo) shift 2 ;;
        --brief) brief=$2; shift 2 ;;
        *) echo "unsupported argument: $1" >&2; exit 2 ;;
    esac
done
if [ "${HARNESS_EXECUTOR:-}" != docker ]; then
    echo "this adapter runs only under the container executor" >&2
    exit 2
fi
# The container's working directory is the dispatch checkout; HOME is a tmpfs.
tools=$(jq -r '.allowed_tools | join(",")' "$brief")
model=$(jq -r '.resolved_model' "$brief")
staging=$(jq -r '.report_staging_path' "$brief")
exec claude --print --model "$model" --allowedTools "$tools" \
    "Work on the brief $brief. You cannot run coordinator commands in this container. \
Write the completion report JSON to $staging and stop."
```

The script keeps native approval and passes the brief's allowlist. In non-interactive mode,
an action outside that allowlist cannot obtain human approval. The completion JSON report goes
to `report_staging_path` inside `.harness/.sandboxes/scratch`; the coordinator/a human registers
it on the host. The worker does not run `dispatch self-report`, `dispatch heartbeat` or `report submit`.

Use `--adapter` when sending an **already approved** dispatch:

```bash {.ah-code-wrap}
chmod +x scripts/container-agent.sh
python .harness/orchestration/coordinator.py --repo . dispatch send \
  --dispatch '<approved-dispatch-id>' --adapter scripts/container-agent.sh
```

This command starts a worker; use preflight below to check configuration instead of send.

## Network {#network}

With `network.hosts: []`, the worker gets `--network none`. Otherwise the runtime creates an
internal network and proxy sidecar; the proxy is the only egress route. The executor sets
`HTTP_PROXY`/`HTTPS_PROXY` and their lowercase variants; `NO_PROXY` contains localhost, 127.0.0.1 and ::1.

- HTTP and CONNECT on ports 80/443 are allowed. SSH remotes and other protocols cannot use the proxy.
- Hosts must match exactly: case and a trailing dot are normalized, with no wildcards or
  automatic subdomain access. IP literals are refused even when allowlisted.
- DNS answers are checked: loopback, link-local, unspecified and multicast addresses are refused.
  That is the current filter's exact set; it does not blanket-block all private/RFC1918 addresses.
- A tool that ignores proxy variables has no direct egress.

For workers, list the chosen model's API and git hosting only when the task needs them.
Build a separate QA list from the project's registries: Python often needs `pypi.org` and
`files.pythonhosted.org`; Rust needs hosts for its crates.io/mirror registry and crate downloads.
Derive the exact list from manifests/registry configuration and tool failures; the two example
hosts do not promise access to every dependency.

| Symptom | Check and action |
| --- | --- |
| `--network none` | Check the effective role/operation host list; an approved plan change needs a new propose. |
| Proxy returns `403` | Check exact hostname, port and DNS addresses; do not add wildcards or the whole internet to bypass it. |
| Host is allowed but connection fails | Check the tool's own proxy configuration and DNS/host availability. Test inside the selected image and plan. |

## Token {#token}

For Claude Code, use `ANTHROPIC_API_KEY` or a subscription token generated with `claude setup-token`
and passed as `CLAUDE_CODE_OAUTH_TOKEN`. These are different
[Claude Code authentication options](https://code.claude.com/docs/en/authentication#generate-a-long-lived-token):
choose one appropriate to your account and CLI version. Run `setup-token` yourself in a private
terminal: it prints the value. Configuration retains only the chosen variable's name.

API-key example in **Bash**, without putting the value in command history:

```bash {.ah-code-wrap}
read -rs -p 'ANTHROPIC_API_KEY: ' ANTHROPIC_API_KEY
printf '\n'
export ANTHROPIC_API_KEY
harness-runtime serve --repo .
```

For OAuth, use `CLAUDE_CODE_OAUTH_TOKEN` instead of `ANTHROPIC_API_KEY` in both manual entry and
`environment`. Do not pass both blindly. If the runtime is running, stop it normally and restart
with the new environment; for a service, change the service's environment. The engine takes
values from the runtime, rather than a coordinator started later.

Never list reserved `HOME`, `GIT_CONFIG_COUNT`, `GIT_CONFIG_KEY_0`, `GIT_CONFIG_VALUE_0`,
`HARNESS_EXECUTOR` or, with networking, proxy variables in `environment`. Do not mount agent auth
files. If a value reaches a log/report/Git, revoke and replace it, then remove accessible copies;
removing a line from the current file does not clean history. See [Secrets and tokens](secrets.md).

## Checks and common errors {#checks}

Run [canonical validation and health](orchestration/index.md#config-validation) first.
For an existing batch, check access without starting containers; supply its actual ID:

```bash {.ah-code-wrap}
python .harness/orchestration/coordinator.py --repo . dispatch preflight \
  --batch '<batch-id>' --role developer
```

Preflight lists blockers with remedies and reads engine info/image IDs. For a separate checkout
or when not at the root, check `--worktree` and `--candidate-commit` in `--help`.
A passing preflight neither replaces a live smoke nor sends a worker.

| Error or blocker | Cause → action |
| --- | --- |
| `runtime_unavailable` | Runtime does not respond → check running serve, repository, user and IPC directory. Do not blindly start a second process. |
| `lease_held` | An owner still holds the QA-lane/ledger → inspect `ledger lock-status` and the owner; wait for release. Do not force-clear a live lease just for setup. |
| Missing variable | Its name is in the plan but the runtime lacks the value → set it privately and restart the runtime. Do not print the value to check it. |
| `approval_mismatch` | A pinned image/approval changed → restore the image ID or cancel the dispatch and propose again with new approval. |
| Image/engine unavailable | Check the real CLI, its PATH/permissions and local images under the runtime user. |
| No `external`, `unsandboxed`, or non-empty hosts without a proxy | Correct the selected plan according to its remedy; successful JSON validation does not prove executor readiness. |
| A root exposes a socket/runtime directory or overlaps `/harness-home` | Select a separate allowed resource; workers do not receive the engine socket or runtime directories. |

`dispatch status`/`dispatch wait` show runtime observations. After worker exit, the runtime saves
streams and exit code and removes the worker, proxy and network; reconcile retries incomplete
cleanup. Preview remaining objects and the cleanup plan:

```bash {.ah-code-wrap}
harness cleanup .
```

Apply `harness cleanup . --apply` only after reviewing removals. Cleanup skips live executions,
does not stop a running worker and does not remove volumes. Explicitly stop a particular worker
with `docker stop harness-<dispatch_id>` or its Podman equivalent.

Live smokes **in the harness repository**, not arbitrary target projects, are
`tests/orchestration/test_docker_smoke.py` and `test_podman_smoke.py`. CI builds the runtime and
smoke images, then runs the chosen marker with `HARNESS_REQUIRE_RUNTIME=1` and the corresponding
`HARNESS_REQUIRE_DOCKER_SMOKE=1`/`HARNESS_REQUIRE_PODMAN_SMOKE=1` so skips cannot count as success.
They start real containers and use networking; ordinary `make verify` excludes them.
Repeat the CI procedure only on a prepared host, rather than as a hidden setup action.

After `make bootstrap`, building the runtime and **smoke images** tagged `harness-worker:smoke`
and `harness-proxy:smoke` from [Docker CI](https://github.com/PVMalove/agent-harness-next/blob/master/.github/workflows/verify.yml)
or [Podman CI](https://github.com/PVMalove/agent-harness-next/blob/master/.github/workflows/podman-smoke.yml),
choose the matching run from the harness source root. The project's `:local` setup images
do not automatically replace the `:smoke` tags.

```bash {.ah-code-wrap}
HARNESS_RUNTIME_BIN="$PWD/native/harness-runtime/target/debug/harness-runtime" \
HARNESS_REQUIRE_RUNTIME=1 HARNESS_REQUIRE_DOCKER_SMOKE=1 \
  .harness/.venv/bin/python -m pytest -m docker_smoke -v \
  tests/orchestration/test_docker_smoke.py
```

```bash {.ah-code-wrap}
HARNESS_RUNTIME_BIN="$PWD/native/harness-runtime/target/debug/harness-runtime" \
HARNESS_REQUIRE_RUNTIME=1 HARNESS_REQUIRE_PODMAN_SMOKE=1 \
  .harness/.venv/bin/python -m pytest -m podman_smoke -v \
  tests/orchestration/test_podman_smoke.py
```

## Environment boundaries {#host-boundaries}

If the agent runs in distrobox/devcontainer while the engine is on the host, first establish
where the **runtime** runs. It invokes the engine CLI, reads named variables and passes absolute
mount paths. A `docker` executable inside the agent environment does not prove runtime engine access.

Check the runtime user/PATH, IPC directory, local engine access, matching worktree/cache paths
and their visibility to the engine. Do not expose the engine socket to workers to fix path
issues. If the mapping is unverified, stop at the blocker; a readable preflight JSON response
does not turn this combination into one of the verified environments in the table.

## Configure with an agent {#agent-setup}

??? quote ah-skill-text "Agent prompt: host, images and adapter"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Read the container guide. Establish Linux, local engine, runtime store, exact host paths and
    runtime user/PATH. Explain verified/unverified engine combinations. Ask which roles use external
    transport and whether QA needs its explicit container override. Inspect an existing adapter;
    choose image tools and pinned versions from evidence, never invented versions. Show Dockerfile,
    config and build commands for review; do not build/pull images or migrate state automatically.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

??? quote ah-skill-text "Agent prompt: container networking"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Read effective access_policy defaults/role/operation components. Ask which model API, git and
    registry hosts are actually needed. Build and show the complete exact-host list with the user;
    no wildcard, IP literals or SSH. Explain HTTP(S) 80/443, proxy-only egress, empty-host network none
    and whole-component overrides. Do not broaden an approved plan; changes need new propose/approval.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

??? quote ah-skill-text "Agent prompt: container token"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Ask only the credential variable NAME needed by the chosen adapter and which shell the user uses.
    Explain environment names versus values held by harness-runtime serve and reserved names.
    For Bash give private manual read -rs entry instructions with export; never execute the entry
    or collect its output. Ask the user to restart the existing runtime/service with that environment,
    not start a duplicate. Inspect preflight without reading or echoing credential values.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

??? quote ah-skill-text "Agent prompt: container preflight and failures"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Ask for an existing suitable batch/worktree; inspect dispatch preflight --help before using it.
    Read-only preflight can inspect engine/image readiness without starting containers. Without a
    suitable batch report it unperformed. Explain runtime_unavailable, lease_held, missing variables
    and approval_mismatch with remedies. Never force-clear a live lease or reuse approval for new
    image IDs. Preview cleanup; deletion/live smokes/worker send require separate authorization.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```
