# Access and container

`access_policy` in `.harness/orchestration.json` describes execution mode and access to the
network, files, images and environment. `extensions` selects implementations that verify and
apply the plan. This is separate from [assignments and tool_policy](roles.md): a tool list
does not prove process permissions, and `transport: external` alone does not mean a container.

## When the policy is absent

The managed `.harness/orchestration.example.json` has no `access_policy`, and all six extensions
are `none`. The example does not choose images, networking or host paths for the project.
Without an authored policy, the brief preserves historical `inherit` behavior; this is not
proof of sandbox isolation.

Adding **any** `access_policy`, even `{}` or `mode: inherit`, makes `dispatch send` require a
selected `extensions.runtime_access` implementation. `none` proves no access, so sending is
blocked before handoff; there is no silent fallback to legacy `inherit`. Valid JSON and a
successful health check do not prove native-executor readiness.

## Defaults: access components {#defaults}

`access_policy.defaults` provides shared `mode`, `container`, `environment`, `network` and
`filesystem` components. All components are optional, but authored objects must satisfy the
table below. Network/environment values describe the selected plan; without a policy, legacy
`inherit` does not become a network ban or an environment reset.

| Field | Contract |
| --- | --- |
| `access_policy.defaults.mode` | `inherit`, `sandbox`, `unsandboxed`. If omitted, the resolver selects `inherit`. The built-in container executor refuses `unsandboxed`; schema validity does not prove environment support. |
| `access_policy.defaults.container.engine` | `docker` or `podman`; the default inside an authored `container` is `docker`. The container component itself is not added automatically. |
| `access_policy.defaults.container.worker_image` | Required within `container`: an image-reference string, such as `harness-worker:local`. 1–255 characters, starting with a letter/digit, with no spaces or leading `-`. |
| `access_policy.defaults.container.proxy_image` | Optional image reference in the same format. The executor requires it for non-empty `network.hosts`; when named, the image must exist locally. |
| `access_policy.defaults.environment` | Array of unique names matching `[A-Za-z_][A-Za-z0-9_]*`, never values. `[]` clears the list; an unauthored component is not added to the plan. |
| `access_policy.defaults.network.hosts` | Array of explicit DNS names, without URL, port or wildcard; up to 253 characters, with labels up to 63. Required inside an authored `network`. Without a network component, the resolver uses `[]`. |
| `access_policy.defaults.filesystem[].resource` | Required in each entry: `checkout`, `git_common`, `shared_storage`, `cache`. The `filesystem` array is optional; the selected plan defaults to `[]`. |
| `access_policy.defaults.filesystem[].path` | Non-empty string without NUL. Required only for `cache` and forbidden for other resources. Relative paths resolve against the worktree; the resolver expands `~`. |
| `access_policy.defaults.filesystem[].variable` | Environment variable name for a `cache` path; forbidden for other resources. The name must be unique in the component and cannot override runtime environment variables. |
| `access_policy.defaults.filesystem[].access` | Required in each entry: `read` or `write`. Actual environment permissions are checked separately, not inferred from configuration text. |

`checkout`, `git_common` and `shared_storage` roots are resolved from the worktree and project
storage; they cannot take an arbitrary `path`. A read-only role cannot request `write` for
these roots. A separate `cache` may have its own access. The resolver adds mandatory roots and
operational scratch separately: `filesystem: []` does not remove execution/report requirements.

## Role overrides {#role-overrides}

`access_policy.roles.<ключ>` accepts manifest names: `architect`, `developer`, `code-review`,
`qa`, `verification`, `conflict-resolver`, `database-migrations`, `messaging-integration`.
Each override replaces the **entire named component**; other components come from defaults.
The field formats and restrictions are the same as above:

- `access_policy.roles.<ключ>.mode`.
- `access_policy.roles.<ключ>.container.engine`, `access_policy.roles.<ключ>.container.worker_image`, `access_policy.roles.<ключ>.container.proxy_image`.
- `access_policy.roles.<ключ>.environment`.
- `access_policy.roles.<ключ>.network.hosts`.
- `access_policy.roles.<ключ>.filesystem[].resource`, `access_policy.roles.<ключ>.filesystem[].path`, `access_policy.roles.<ключ>.filesystem[].variable`, `access_policy.roles.<ключ>.filesystem[].access`.

For example, a `filesystem` with just `checkout: read` replaces the defaults array instead of
extending it. `container` is not deep-merged either: repeating only `worker_image` drops the
inherited `proxy_image`, and an omitted `engine` defaults to `docker` again. Repeat all needed
component fields explicitly, including `podman` when that is the intended engine.

## Coordinator-operation overrides {#operation-overrides}

`access_policy.operations.<ключ>` accepts only `qa`, `git`, `publish`. The coordinator executes
the operation, so the resolver uses defaults plus its operation override, **without the role
override**. Its own entries have the same format:

- `access_policy.operations.<ключ>.mode`.
- `access_policy.operations.<ключ>.container.engine`, `access_policy.operations.<ключ>.container.worker_image`, `access_policy.operations.<ключ>.container.proxy_image`.
- `access_policy.operations.<ключ>.environment`.
- `access_policy.operations.<ключ>.network.hosts`.
- `access_policy.operations.<ключ>.filesystem[].resource`, `access_policy.operations.<ключ>.filesystem[].path`, `access_policy.operations.<ключ>.filesystem[].variable`, `access_policy.operations.<ключ>.filesystem[].access`.

A read-only QA role does not mean the coordinator operation cannot write its clean-room
checkout, Git metadata or shared storage. Operational requirements are checked separately.
`qa run` and publish use a pinned plan; integration local-QA/refresh/resolve commands read the
operation plan from current configuration. See the [backend guide](../../../backend-orchestration.md).

## Implementations: extensions {#extensions}

`extensions` is an optional dictionary of strings. Exactly six keys are allowed:

| Extension key | Purpose |
| --- | --- |
| `transport_health` | Transport-health observations. |
| `verification_environment_health` | Verification-environment observations. |
| `retry_reason_classifier` | Retry-reason classification; the coordinator retains decision authority. |
| `context_telemetry_provider` | Observed context telemetry. |
| `human_notifier` | Human notifications. |
| `runtime_access` | Native verification, plan application and worker handoff. The built-in name `docker` selects the Docker/Podman container executor. |

Each key defaults to `none`. Other forms are an implementation name registered by the host
process, or `module:factory`: a no-argument factory in an importable project module. An unknown
or unsuitable implementation is refused. A name alone does not install a package or create an
implementation. Extensions add no model tools and do not change system prompts.

The distribution provides the built-in `docker` name for `runtime_access`; it supports both
engines. Selecting it makes the schema and validator require
`access_policy.defaults.container` with `worker_image`. Any other provider must be implemented
and verified by the project.

## Container plan {#container}

The built-in executor requires Linux, the runtime store and an available local engine. Roles
sent through it need `transport: external`. The harness does not build or pull images: the
user prepares them separately, `dispatch propose` pins their digests, and changing an image
after approval requires a new approved plan.

- Non-empty `network.hosts` needs a local `proxy_image`. Egress uses a separate proxy and only
  HTTP(S), ports 80/443, to exact allowed hosts. Subdomains, wildcards, IP literals and SSH are
  not authorized by this list. With `[]`, the container uses `--network none`.
- `environment` contains names only. Values come from the environment of `harness-runtime serve`;
  restart the runtime after changing them. Names enter the digest; values do not enter config,
  briefs, argv, evidence or logs. Agent auth files are not mounted. A missing runtime variable
  is a blocker, not a reason to request its value in chat.
- The executor reserves `HOME`, `GIT_CONFIG_COUNT`, `GIT_CONFIG_KEY_0`, `GIT_CONFIG_VALUE_0`,
  `HARNESS_EXECUTOR`; with networking it also reserves `HTTP_PROXY`, `HTTPS_PROXY`, `http_proxy`,
  `https_proxy`, `NO_PROXY`, `no_proxy`. Do not list these for forwarding.
- Container QA requires an explicit `access_policy.operations.qa.container`.
  `defaults.container` alone is insufficient: without the override, QA commands stay on the host.

The JSON below is a fragment to merge into current configuration, not a ready installation.
Image tags, the API host and variable name are examples; replace them with confirmed project
values. Provider profiles and external transport are not configured here.

```json
{
  "access_policy": {
    "defaults": {
      "mode": "sandbox",
      "container": {
        "engine": "docker",
        "worker_image": "harness-worker:local",
        "proxy_image": "harness-proxy:local"
      },
      "environment": [
        "LLM_API_KEY"
      ],
      "network": {
        "hosts": [
          "llm-api.example.com"
        ]
      },
      "filesystem": [
        {
          "resource": "checkout",
          "access": "write"
        },
        {
          "resource": "git_common",
          "access": "write"
        },
        {
          "resource": "shared_storage",
          "access": "write"
        },
        {
          "resource": "cache",
          "path": "~/.cache/uv",
          "access": "write"
        }
      ]
    },
    "roles": {
      "code-review": {
        "filesystem": [
          {
            "resource": "checkout",
            "access": "read"
          }
        ]
      }
    },
    "operations": {
      "qa": {
        "container": {
          "worker_image": "harness-worker:local"
        },
        "environment": [],
        "network": {
          "hosts": []
        }
      }
    }
  },
  "extensions": {
    "runtime_access": "docker"
  }
}
```

Here `code-review` replaces only filesystem and inherits other components. QA replaces
container, environment and network: its container uses `docker`, receives no `LLM_API_KEY`,
does not inherit the proxy and has no network. This does not configure git/publish access.

For image/environment/network preparation and blockers, see [Container](../container.md) and
the installed `.harness/docs/container-executor.md`. Names and secret values are covered in
[Secrets and tokens](../secrets.md).

## Configure with an agent {#agent-access-setup}

Agree the shared access first, then container components if needed. The agent must ask only
for missing decisions and show the complete resulting plan before writing configuration.

??? quote ah-skill-text "Agent prompt: access and implementations"

    ```text
    Help me configure access_policy and extensions for this repository.

    Follow repository instructions. Keep questions, choices and user-facing summaries in Russian.
    Read .harness/project.json, .harness/orchestration.json, the installed schema,
    managed example and role manifests. Read .harness/docs/container-executor.md
    when container execution is involved. Run available read-only health/config checks.
    Ask only for unresolved facts, one question at a time. Offer 2-4 concrete choices
    plus «Другое», with one consequence each. Put an evidence-based recommendation
    first and mark it «Рекомендуется»; otherwise ask for the missing fact.
    Never read authentication files or request, print or store token/key values.

    First distinguish keeping unauthored legacy inherit from declaring an access policy.
    Explain that even an authored inherit policy blocks dispatch send until a working
    runtime_access provider verifies it; none is not an access proof.
    Ask which executor is intended: the built-in docker provider, an existing trusted
    project provider, or keeping the current unauthored behavior. Do not choose
    unsandboxed as a workaround for blockers. Do not invent a module:factory provider.
    Ask for the minimal network hosts, named filesystem resources/cache paths and access
    levels. Then ask which role and qa/git/publish operation overrides are needed.
    Explain whole-component replacement: container/network/filesystem/environment
    entries do not deep-merge. Operations use defaults plus their own override, never
    a role override. Keep read-only roles read-only and retain operational requirements.
    For docker, verify defaults.container.worker_image is present. Explain that
    container QA requires an explicit operations.qa.container; defaults alone do not
    containerize QA. Do not enable other extensions just because fields are available.

    Use only supported fields and repository evidence or my answers; do not guess
    paths, image tags, module names or hosts. Preserve unrelated configuration.
    Show the exact proposed diff and a concise summary of inherited/replaced components.
    Wait for my approval, then apply only the approved diff with Edit/Write.
    Run installed config validate --canonical --json and harness health again.
    For an existing dispatch I identify, inspect installed dispatch preflight --help
    and run the read-only preflight with the required arguments. Without a suitable
    dispatch, report native verification as not performed; do not create one to test.
    Report checks and remaining blockers. Do not send workers, create batches, install
    extensions, build/pull images, migrate state, change Git, commit or open a PR.
    ```

??? quote ah-skill-text "Agent prompt: container, network and environment"

    ```text
    Help me configure the container access components of this repository.

    Follow repository instructions. Keep questions, choices and user-facing summaries in Russian.
    Read .harness/project.json, .harness/orchestration.json, the installed schema,
    managed example and role manifests. Read .harness/docs/container-executor.md
    when container execution is involved. Run available read-only health/config checks.
    Ask only for unresolved facts, one question at a time. Offer 2-4 concrete choices
    plus «Другое», with one consequence each. Put an evidence-based recommendation
    first and mark it «Рекомендуется»; otherwise ask for the missing fact.
    Never read authentication files or request, print or store token/key values.

    Check the documented Linux/runtime-store prerequisites and existing role transport.
    Ask which local engine (docker/podman) and existing worker/proxy image references
    should be used. Explain that roles sent through the container executor need external
    transport. If assignment transport must change, show that as a separate explicit
    change; do not silently switch roles while configuring resource access.
    Ask for the complete required HTTP(S) host allowlist, including the model API host.
    No URL, port, wildcard or IP literal; do not infer that subdomains or SSH are allowed.
    A non-empty host list needs a proxy image. Show the full allowlist for review.
    Ask only for environment variable NAMES and explain which list replaces defaults.
    Validate names and reject executor-reserved names. Do not read their values.
    Ask which interactive shell I use. For Bash and a user-approved name, offer
    a manual silent command such as
    read -rs -p 'LLM_API_KEY: ' LLM_API_KEY; export LLM_API_KEY
    using the validated chosen name. The user enters the value privately; never run
    this command yourself or request the resulting value. Explain that the user must
    restart harness-runtime serve to supply changed values; do not restart it yourself.
    Check whether QA should have its own container, hosts and environment list.
    Do not copy an image tag or API hostname from an example without confirmation.

    Use only supported fields and repository evidence or my answers; do not guess
    paths, image tags, module names or hosts. Preserve unrelated configuration.
    Show the exact proposed diff and a concise summary of inherited/replaced components.
    Wait for my approval, then apply only the approved diff with Edit/Write.
    Run installed config validate --canonical --json and harness health again.
    For an existing dispatch I identify, inspect installed dispatch preflight --help
    and run the read-only preflight with the required arguments. Without a suitable
    dispatch, report native verification as not performed; do not create one to test.
    Report checks and remaining blockers. Do not send workers, create batches, install
    extensions, build/pull images, migrate state, change Git, commit or open a PR.
    ```

## Validation and next steps

Start with [configuration validation](index.md#config-validation). `dispatch preflight` then
checks a specific execution environment without creating a container. Use arguments from the
installed coordinator's help, not an invented dispatch ID. Engine/image availability, variable
names and access evidence are checked separately from JSON. Resolve refusals before send;
do not remove restrictions to bypass a blocker. QA commands are in [verification](verification.md).
