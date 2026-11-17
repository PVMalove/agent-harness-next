# Platforms

This page lists the platforms of Agent Harness Next 2.0 and the CI jobs that check them. The source is `.github/workflows/verify.yml` and `.github/workflows/podman-smoke.yml`. Job
names match the names in GitHub Actions.

## Supported platforms

| Platform | What CI checks |
| --- | --- |
| Linux | Full harness test suite and clean-room install, `harness-runtime` (Rust tests, Unix domain socket, process supervisor), web console, site, fault matrix |
| Windows | Full harness test suite and clean-room install, `harness-runtime` over the named pipe and the Job Object supervisor |
| Docker (rootful) | End-to-end smoke: a worker dispatch and QA in containers |
| Fedora, SELinux enforcing, rootless Podman | End-to-end smoke of the container executor on a self-hosted runner |

No CI job checks macOS, so running on it is not confirmed. Rootless Docker is not covered:
`docker-smoke` checks rootful Docker only.

## CI jobs

### Linux (`ubuntu-latest`)

| Job | What it checks |
| --- | --- |
| `lint` | ruff, mypy, `cargo fmt --check`, Clippy, public Git metadata |
| `rust` | `cargo test` of the `native/harness-runtime` workspace and the debug build of `harness-runtime` for the other jobs |
| `docs` | Strict build of the public site |
| `verify` | Full `make verify`: harness tests and the clean-room install |
| `console-spa` | Web console build, Vitest, and Playwright in Chromium |
| `diff-coverage` | Coverage of the lines a pull request changes |
| `docker-smoke` | The coordinator, the real `harness-runtime`, worktrees, and the store run a worker dispatch and QA in Docker containers |
| `fault-injection` | Fault and security boundary matrix: the coordinator against a debug build of `harness-runtime` |
| `parser-bundle`, `repo-map-bundle` | Offline tree-sitter parser bundle and the Repo Map tests on it |
| `verify-light` | Pull requests into `integration/**` only: `make lint`, `cargo fmt --check`, Clippy, tests selected by the pull request diff, and public Git metadata |
| `verify-linux-unit`, `verify-linux-integration` | Pull requests only: the unit and integration test groups on Linux |
| `verify-test-groups` | Pull requests only: a roll-up node that fails if one of the four Linux and Windows groups did not pass |
| `private-terms` | Pull requests only: commits, branch, title, and body against the private term list |
| `dashboard` | Summary page of the run: which jobs and tests failed and why. It checks nothing itself |

### Windows (`windows-latest`)

| Job | What it checks |
| --- | --- |
| `verify-windows (tests)` | Full harness test suite |
| `verify-windows (clean-room)` | Clean-room install |
| `verify-windows-unit`, `verify-windows-integration` | Pull requests only: the unit and integration test groups on Windows |
| `runtime-ipc-windows` | Runtime IPC contract tests over the named pipe in Python and Rust, and Rust tests of the Job Object supervisor |

### Fedora, SELinux, rootless Podman (self-hosted)

| Job | What it checks |
| --- | --- |
| `podman-smoke` | End-to-end smoke of the container executor on rootless Podman with SELinux in enforcing mode |

## When jobs run

- **A pull request into `integration/**`** gets the light path: `verify-light`, `docs`,
  `console-spa`, `parser-bundle`, `private-terms`, the four Linux and Windows test groups, and
  `verify-test-groups`.
- **A pull request into other branches and a push to `master`** get the full path: every Linux and
  Windows job except `verify-light`. `diff-coverage`, `private-terms`, the test groups, and
  `verify-test-groups` run on pull requests only.
- **`dashboard`** runs after all jobs on any path, whatever their result.
- **`podman-smoke`** never runs on a pull request: the repository is public, and the self-hosted
  runner accepts only a push that changes the container executor or the runtime, and a manual
  run. An offline runner does not hold pull request checks or a release.
