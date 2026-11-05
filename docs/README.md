# Документация Agent Harness Next

Публичная документация живёт на сайте: [pvmalove.github.io/claude-agent-harness](https://pvmalove.github.io/claude-agent-harness/).
Исходники сайта — `site/`, локальный предпросмотр — `make docs-serve`.

Корневой `docs/` — внутренняя документация исходного репозитория. Она не устанавливается в целевые
проекты; агентам доставляются проектные руководства из `harness/project/docs-agents/`, контракты
`harness/docs/` и роли оркестрации из `harness/orchestration/`.

| Публичная страница | Содержимое |
| --- | --- |
| [Быстрый старт](../site/docs/getting-started/index.md) | Требования, установка, init/adopt, health |
| [Архитектура](../site/docs/architecture/index.md) | Слои, ownership, Rust runtime, store, безопасность |
| [Справочник](../site/docs/reference/index.md) | CLI, конфигурация, hooks, агенты |
| [Демо](../site/docs/demo/index.md) | Веб-консоль, ключевые экраны |

| Внутренний раздел | Содержимое |
| --- | --- |
| [ADR](./adr/) | Действующие архитектурные контракты |
| [Руководства и агенты](./agents/README.md) | Git, тикеты, артефакты, worktrees, релизы, агенты |
| [Skills](./skills/README.md) | Русские описания first-party, global, role и vendor skills |
| [Hooks](./hooks/) | Проектные hooks и вспомогательные скрипты |
| [Backend-оркестрация](./backend-orchestration.md) | Конфиг, coordinator, роли, lifecycle batch |
| [Диаграммы](./diagrams/README.md) | Archify JSON, HTML и PNG |
| [Technical English](../harness/docs/technical-english.md) | Контракт английской координации |
| [Technical Russian](./technical-russian.md) | Правила русского языка и Keep a Changelog |
| [Runtime discovery](./runtime-discovery.md) | Обнаружение skills в Claude Code и Codex |

Порядок выпуска и проверка приватных терминов — в [releases.md](./agents/releases.md).
Правила Git и PR — в [git-workflow.md](./agents/git-workflow.md).
