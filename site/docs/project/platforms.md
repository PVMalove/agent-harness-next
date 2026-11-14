# Платформы

CI проверяет Agent Harness Next 2.0 на платформах из таблицы ниже. Данные и имена заданий взяты из
файлов `.github/workflows/verify.yml` и `.github/workflows/podman-smoke.yml`.

## Поддерживаемые платформы

| Платформа | Что проверяет CI |
| --- | --- |
| Linux | Полный набор тестов harness и clean-room установка, `harness-runtime` (Rust-тесты, Unix domain socket, супервизор процессов), веб-консоль, сайт, матрица сбоев |
| Windows | Полный набор тестов harness и clean-room установка, `harness-runtime` через named pipe и супервизор на Job Object |
| Docker (rootful) | Сквозной smoke: dispatch worker и QA в контейнерах |
| Fedora, SELinux enforcing, rootless Podman | Сквозной smoke контейнерного исполнителя на self-hosted runner |

Ни одно задание CI не проверяет macOS, поэтому работа на ней не подтверждена. Rootless Docker тоже
не покрыт: `docker-smoke` проверяет только rootful Docker.

## Задания CI

### Linux (`ubuntu-latest`)

| Задание | Что проверяет |
| --- | --- |
| `lint` | ruff, mypy, `cargo fmt --check`, Clippy, публичные метаданные Git |
| `rust` | `cargo test` workspace `native/harness-runtime` и debug-сборка `harness-runtime` для остальных заданий |
| `docs` | Строгая сборка публичного сайта |
| `verify` | Полный `make verify`: тесты harness и clean-room установка |
| `console-spa` | Сборка веб-консоли, Vitest и Playwright в Chromium |
| `diff-coverage` | Покрытие изменённых строк pull request |
| `docker-smoke` | Coordinator, настоящий `harness-runtime`, worktree и store запускают dispatch worker и QA в контейнерах Docker |
| `fault-injection` | Матрица сбоев и границ безопасности: coordinator против debug-сборки `harness-runtime` |
| `parser-bundle`, `repo-map-bundle` | Офлайн-пакет парсеров tree-sitter и тесты Repo Map на нём |
| `verify-light` | Только для pull request в `integration/**`: `make lint`, `cargo fmt --check`, Clippy, тесты по diff pull request и публичные метаданные Git |
| `verify-linux-unit`, `verify-linux-integration` | Только для pull request: группы тестов unit и integration на Linux |
| `verify-test-groups` | Только для pull request: сводный узел, падает, если не прошла одна из четырёх групп Linux и Windows |
| `private-terms` | Только для pull request: коммиты, ветка, заголовок и тело против списка закрытых терминов |
| `dashboard` | Сводная страница прогона: какие задания и тесты упали и почему. Само задание ничего не проверяет |

### Windows (`windows-latest`)

| Задание | Что проверяет |
| --- | --- |
| `verify-windows (tests)` | Полный набор тестов harness |
| `verify-windows (clean-room)` | Clean-room установка |
| `verify-windows-unit`, `verify-windows-integration` | Только для pull request: группы тестов unit и integration на Windows |
| `runtime-ipc-windows` | Контрактные тесты IPC runtime через named pipe на Python и Rust и Rust-тесты Job Object супервизора |

### Fedora, SELinux, rootless Podman (self-hosted)

| Задание | Что проверяет |
| --- | --- |
| `podman-smoke` | Сквозной smoke контейнерного исполнителя на rootless Podman с SELinux в режиме enforcing |

## Когда задания запускаются

- **Pull request в `integration/**`** получает лёгкий путь: `verify-light`, `docs`, `console-spa`,
  `parser-bundle`, `private-terms`, четыре группы тестов Linux и Windows и `verify-test-groups`.
- **Pull request в другие ветки и push в `master`** получают полный путь: все задания Linux и
  Windows, кроме `verify-light`. `diff-coverage`, `private-terms`, группы тестов и
  `verify-test-groups` идут только на pull request.
- **`dashboard`** запускается после всех заданий на любом пути, каким бы ни был их результат.
- **`podman-smoke`** не запускается на pull request, потому что репозиторий публичный. Self-hosted
  runner запускает его только на push, который меняет контейнерный исполнитель или runtime, и вручную.
  Если runner выключен, проверки pull request и релиз его не ждут.
