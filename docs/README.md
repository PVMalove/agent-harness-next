# Документация Agent Harness Next

Публичная документация — [pvmalove.github.io/claude-agent-harness](https://pvmalove.github.io/claude-agent-harness/).
Её исходники лежат в `site/`, локальный просмотр — `make docs-serve`, строгая сборка — `make docs-build`.

Корневой `docs/` — внутренняя документация для разработчика исходного репозитория. Она не
устанавливается в целевые проекты. Агентам доставляются только их собственные контракты:
проектные руководства из `harness/project/docs-agents/`, `harness/docs/project-memory.md`,
`harness/docs/technical-english.md`, роли и playbook оркестрации, скиллы и hooks.

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
| [Руководства и агенты](./agents/README.md) | Git, тикеты, артефакты, worktrees и описания агентов. |
| [Skills](./skills/README.md) | Русские описания first-party, global, role и vendor skills. |
| [Hooks](./hooks/) | Описания проектных hooks и вспомогательных скриптов. |
| [Диаграммы](./diagrams/README.md) | Archify JSON, интерактивные HTML и PNG. |
| [Backend-оркестрация](./backend-orchestration.md) | Конфиг, coordinator, роли и lifecycle batch. |
| [Конфигурация консоли](./console-configuration.md) | Целевой проект, мастер JSON, версии и откат. |
| [Technical English](../harness/docs/technical-english.md) | Контракт английской координации агентов. |
| [Technical Russian](./technical-russian.md) | Правила технического русского языка и Keep a Changelog. |
| [Runtime discovery](./runtime-discovery.md) | Обнаружение skills в Claude Code и Codex. |

Порядок выпуска описан в [releases.md](./agents/releases.md), рабочий процесс — в
[git-workflow.md](./agents/git-workflow.md). Дизайн публичного сайта и макеты — в
[design/](./design/) и [rfc/docs-site.md](./rfc/docs-site.md).
