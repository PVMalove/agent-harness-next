<p align="center">
  <img src="./docs/assets/harness-banner.svg" alt="Agent Harness Next: портативный harness для Claude Code и Codex" width="800">
</p>

<p align="center">
  <a href="https://github.com/PVMalove/agent-harness-next/releases"><img src="https://img.shields.io/github/v/release/PVMalove/agent-harness-next?label=Version&labelColor=34312E&color=D97757" alt="Version"></a>
  <img src="https://img.shields.io/badge/Runtime-Claude%20Code%20%7C%20Codex-E5A04B?labelColor=34312E" alt="Runtime: Claude Code | Codex">
  <img src="https://img.shields.io/badge/Python-3.12%2B-8FB573?labelColor=34312E" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/Rust-1.89%2B-CE6F45?labelColor=34312E" alt="Rust 1.89+">
  <a href="https://github.com/PVMalove/agent-harness-next/actions/workflows/verify.yml"><img src="https://github.com/PVMalove/agent-harness-next/actions/workflows/verify.yml/badge.svg" alt="CI"></a>
  <a href="./LICENSE"><img src="https://img.shields.io/badge/License-BSL%201.1-9C958C?labelColor=34312E" alt="License: BSL 1.1"></a>
</p>

# Agent Harness Next

Agent Harness Next разворачивает в проект скиллы, hooks и документы для coding-агентов и ведёт тикеты через этапы оркестрации. Состояние оркестрации хранит Rust runtime в локальном runtime store, а правила и проверки остаются на Python.

[Сайт](https://pvmalove.github.io/agent-harness-next/) · [Быстрый старт](https://pvmalove.github.io/agent-harness-next/getting-started/) · [Архитектура](https://pvmalove.github.io/agent-harness-next/architecture/) · [Демо](https://pvmalove.github.io/agent-harness-next/demo/) · [Справочник](https://pvmalove.github.io/agent-harness-next/reference/)

## Сборки (Capabilities)

| Сборка | Для чего |
| --- | --- |
| `project-foundation` | Лёгкая доменно-нейтральная база из пяти ключевых скиллов. Вариант по умолчанию. |
| `mattpocock-suite` | Полный upstream-набор, закреплённый на проверенном коммите. |
| `engineering-suite` | Эпики и тикеты, триаж, двухосевое review, `qa-gate` и подготовка PR. |
| `backend-orchestration` | Роли и coordinator для распределённых систем: briefs, worktrees и ledger. |

## Быстрый старт

Требуются Python 3.12+ и Git. Глобальный слой устанавливается однократно для выбранных runtime:

```bash
python3 bin/install-global.py --target-home "$HOME" --runtime claude --runtime codex
```

Затем подключите harness к проекту и проверьте окружение:

```bash
python3 harness/bin/harness.py init /path/to/repository --capability engineering-suite \
  --project-type software --stack python --base-branch main --language ru \
  --qa-gate-command "make test"
python3 harness/bin/harness.py health /path/to/repository
```

Без `--capability` устанавливается `project-foundation`. `harness diff` показывает изменения
управляемого snapshot, `harness update` обновляет его и сохраняет локальные правки.

## Как это работает

- `harness init` копирует в проект скиллы выбранной сборки, hooks и руководства для агентов.
- Claude Code и Codex находят скиллы в `.claude/skills` и `.agents/skills`. Hooks проверяют команды и правки агента до того, как они выполнятся.
- В сборке `backend-orchestration` скилл `/implement` проводит тикет через этапы architect, developer, review и QA. Состояние хранит процесс `harness-runtime serve`: пока он не запущен, команды оркестрации отказывают с `[runtime_unavailable]`.
- Состав сборок задаёт [`harness/CAPABILITIES.json`](./harness/CAPABILITIES.json), архитектурные решения записаны в [ADR](./docs/adr/).

## Документация

- [Быстрый старт](https://pvmalove.github.io/agent-harness-next/getting-started/): требования, установка и `health`.
- [Миграция на 2.0](https://pvmalove.github.io/agent-harness-next/guides/upgrade-2-0/): переход с 1.x, `harness-runtime migrate` и откат.
- [Архитектура](https://pvmalove.github.io/agent-harness-next/architecture/): слои, runtime, store и безопасность.
- [Справочник](https://pvmalove.github.io/agent-harness-next/reference/): CLI, конфигурация, hooks и агенты.
- [Демо](https://pvmalove.github.io/agent-harness-next/demo/): веб-консоль на демонстрационных данных.
- [ADR](./docs/adr/) и [правила Git](./docs/agents/git-workflow.md): действующие контракты и рабочий процесс.
- [CONTEXT.md](./CONTEXT.md): глоссарий проекта; [docs/README.md](./docs/README.md): индекс внутренней документации.

## Участие в разработке

Каждое изменение проходит путь issue → ветка → PR по [правилам Git](./docs/agents/git-workflow.md). Перед PR запустите полный гейт `make verify`. Заметки о выпуске пишутся в [CHANGELOG.md](./CHANGELOG.md), порядок выпуска описан в [releases.md](./site/docs/agents/releases.md).

Проект распространяется по лицензии [Business Source License 1.1](./LICENSE): некоммерческое использование разрешено, коммерческое требует письменного разрешения автора. Лицензия закреплённого upstream-snapshot лежит в [`third_party/mattpocock-skills/LICENSE`](./third_party/mattpocock-skills/LICENSE).
