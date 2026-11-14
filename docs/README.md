# Документация Agent Harness Next

Публичная документация — [pvmalove.github.io/agent-harness-next](https://pvmalove.github.io/agent-harness-next/).
Её исходники лежат в `site/`, локальный просмотр — `make docs-serve`, строгая сборка — `make docs-build`.

Корневой `docs/` — внутренняя документация для разработчика исходного репозитория. Она не
устанавливается в целевые проекты. Агентам доставляются только их собственные контракты:
проектные руководства из `harness/project/instructions/`, `harness/project/instructions/project-memory.md`,
`harness/project/instructions/technical-english.md`, роли и playbook оркестрации, скиллы и hooks.

## Публичные страницы

| Страница | Содержимое |
| --- | --- |
| [Быстрый старт](../site/docs/getting-started/index.md) | Требования, установка, подключение к проекту и verification. |
| [Архитектура](../site/docs/architecture/index.md) | Слои, Rust runtime, store и безопасность. |
| [Справочник](../site/docs/reference/index.md) | CLI, конфигурация, hooks и агенты. |
| [Демо](../site/docs/demo/index.md) | Веб-консоль на демонстрационных данных. |

## Внутренние разделы

| Раздел | Содержимое |
| --- | --- |
| [ADR](./adr/) | Действующие архитектурные контракты по доменам. |
| [Руководства для агентов](./agents/) | Git, тикеты, артефакты, worktrees, блоки промпта агента доски задач (английские источники). Описания агентов — на [сайте](../site/docs/agents/index.md). |
| [Skills](../site/docs/skills/index.md) | Русские описания first-party, global, role и vendor skills (на сайте). |
| [Hooks](../site/docs/hooks/index.md) | Описания проектных hooks и вспомогательных скриптов (на сайте). |
| [Backend-оркестрация](../site/docs/backend-orchestration.md) | Конфиг, coordinator, роли и lifecycle batch. |
| [Конфигурация консоли](../site/docs/console-configuration.md) | Целевой проект, мастер JSON, версии и откат. |
| [Technical English](../harness/project/instructions/technical-english.md) | Контракт английской координации агентов. |
| [Technical Russian](./technical-russian.md) | Правила технического русского языка и Keep a Changelog. |
| [Runtime discovery](../site/docs/runtime-discovery.md) | Обнаружение skills в Claude Code и Codex. |
| [Восстановление и runtime store](./adr/0030-runtime-store-ledger-reconciliation.md) | ADR 0030: записи восстановления в runtime store, сверка с authority lifecycle и граница гарантии. |

Порядок выпуска описан в [releases.md](../site/docs/agents/releases.md), рабочий процесс — в
[git-workflow.md](./agents/git-workflow.md). Дизайн публичного сайта и макеты — в
[design/](./design/) и [rfc/docs-site.md](./rfc/docs-site.md).
