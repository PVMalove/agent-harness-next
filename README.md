<p align="center">
  <img src="./docs/assets/harness-banner.svg" alt="Agent Harness Next — for coding agents" width="800">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Version-beta-D97757?labelColor=34312E" alt="Version: beta">
  <img src="https://img.shields.io/badge/Runtime-Claude%20Code%20%7C%20Codex-E5A04B?labelColor=34312E" alt="Runtime: Claude Code | Codex">
  <img src="https://img.shields.io/badge/Python-3.12%2B-8FB573?labelColor=34312E" alt="Python 3.12+">
  <a href="https://github.com/PVMalove/claude-agent-harness/actions/workflows/verify.yml"><img src="https://github.com/PVMalove/claude-agent-harness/actions/workflows/verify.yml/badge.svg" alt="CI"></a>
  <a href="./LICENSE"><img src="https://img.shields.io/badge/License-MIT-9C958C?labelColor=34312E" alt="License: MIT"></a>
</p>

# Agent Harness Next

Портативный harness для Claude Code и Codex: скиллы, системные правила, hooks и контекстные
документы разворачиваются в целевой проект как проверяемый snapshot. Оркестрация работает через
Rust runtime и локальный runtime-store; Python остаётся policy-слоем.
Текущий статус — `beta`. Совместимость проверена для Claude Code и Codex.

## Capabilities

| Сборка | Назначение |
| --- | --- |
| `project-foundation` | Лёгкая доменно-нейтральная база из пяти скиллов. |
| `mattpocock-suite` | Полный upstream-набор Matt Pocock / aihero.dev, закреплённый на коммите. |
| `engineering-suite` | Инженерный workflow: эпики и тикеты, триаж, review, PR, QA-gate. |
| `backend-orchestration` | `engineering-suite` плюс coordinator, роли и batch lifecycle. |

`harness/CAPABILITIES.json` — источник правды по составу сборок. Установщик копирует выбранные
скиллы, hooks, агентов и проектные руководства из `harness/project/`; корневой `docs/` в целевой
проект не переносится.

В `engineering-suite` переопределены в `skills/first-party/engineering/`: `ask-matt`, `code-review`, `diagnosing-bugs`, `grill-me`, `grill-with-docs`, `grilling`, `implement`, `tdd`, `to-spec`, `to-tickets`, `triage`, `wayfinder`; доп. скиллы: `architect`, `delivery-stats`, `fast-implement`, `qa-gate`, `setup-labels`, `to-guide`, `to-pull-requests`.

## Быстрый старт

Требуются Python 3.12+ и Git. Глобальный слой ставится один раз для выбранных runtime:

```bash
python3 bin/install-global.py --target-home "$HOME" --runtime claude --runtime codex
```

Прямая установка в Git-репозиторий:

```bash
python3 harness/bin/harness.py init /path/to/repository \
  --capability engineering-suite \
  --project-type software --stack python --base-branch main --language ru \
  --qa-gate-command "make test"

python3 harness/bin/harness.py health /path/to/repository
```

`start-project` создаёт новый проект, `integrate-project` встраивает harness в существующий.
`harness diff` показывает изменения snapshot, `harness update` обновляет управляемые файлы,
`harness uninstall` удаляет harness из проекта.

## Документация

- **Публичный сайт:** [pvmalove.github.io/claude-agent-harness](https://pvmalove.github.io/claude-agent-harness/)
  (исходники — `site/`, локальный предпросмотр — `make docs-serve`).
- **Быстрый старт:** [site/docs/getting-started/index.md](./site/docs/getting-started/index.md).
- **Архитектура:** [site/docs/architecture/index.md](./site/docs/architecture/index.md).
- **Демо веб-консоли:** [site/docs/demo/index.md](./site/docs/demo/index.md).
- **Внутренние документы:** [docs/README.md](./docs/README.md), [ADR](./docs/adr/),
  [агенты](./docs/agents/README.md), [скиллы](./docs/skills/README.md), [hooks](./docs/hooks/).
- **Изменения:** [CHANGELOG.md](./CHANGELOG.md).

Агентские руководства: `docs/agents/{artifacts,git-workflow,issue-tracker,test-author,triage-labels,worktrees}.md`.
Контракт английской координации — [harness/docs/technical-english.md](./harness/docs/technical-english.md).

Полный QA — `make verify`; локальный сайт — `make docs-serve`, строгая сборка — `make docs-build`.
Правила работы с Git, тикетами и PR — в [docs/agents/git-workflow.md](./docs/agents/git-workflow.md).
Лицензия — [MIT](./LICENSE).
