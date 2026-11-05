# Быстрый старт

Agent Harness Next — набор скиллов, hooks и контекстных документов, который разворачивается
в проект как проверяемый snapshot. После установки проект живёт автономно: skills и hooks
работают через нативные механизмы Claude Code и Codex, а оркестрация использует Rust runtime
и локальный runtime-store.

!!! note "Ранний доступ"

    Публичные страницы описывают текущую архитектуру. Перед установкой в рабочий проект
    сделайте backup и проверьте требования.

## Требования

| Компонент | Требование |
| --- | --- |
| Python | 3.12 или новее; `uv` для окружения проекта |
| Git | 2.40+; проект — Git-репозиторий |
| Runtime | Claude Code или Codex; для веб-консоли — браузер |
| ОС | Linux; Windows — через поддерживаемый runtime и named pipe |
| Опционально | Docker или rootless Podman для контейнерного worker/QA |

## 1. Установите глобальный слой

Глобальный слой ставится один раз для выбранных runtime и даёт команды `start-project`
и `integrate-project`.

```bash
python3 bin/install-global.py --target-home "$HOME" \
  --runtime claude --runtime codex
```

В PowerShell:

```powershell
python bin\install-global.py --target-home $HOME `
  --runtime claude --runtime codex
```

## 2. Подключите harness к проекту

Для нового проекта используйте `start-project`; для существующего — `integrate-project`.
Прямая установка в Git-репозиторий:

```bash
python3 harness/bin/harness.py init /path/to/repository \
  --capability engineering-suite \
  --project-type software --stack python --base-branch main --language ru \
  --qa-gate-command "make test"
```

`init` разрешает capability, копирует skills, hooks и проектные руководства в `.harness/`
и записывает lock. Исходный клон harness после этого не нужен.

## 3. Проверьте окружение

```bash
python3 harness/bin/harness.py health /path/to/repository
```

В разделе «Оркестрация» должно быть `authority=runtime-store` и `schema_version=4`,
а критические hooks — подключены. Если проверка не проходит, health назовёт причину
и команду исправления.

```bash
python3 harness/bin/harness.py diff /path/to/repository
python3 harness/bin/harness.py update /path/to/repository
```

`diff` показывает расхождения с залоченным snapshot; `update` обновляет управляемые файлы,
сохраняя локальные правки.

## 4. Проверьте store и audit

```bash
python3 .harness/orchestration/coordinator.py --repo . ledger validate --full
cat .harness/orchestration/state/AUTHORITY.json
```

`ledger validate --full` пересчитывает audit-цепочку и сверяет строки store.
`AUTHORITY.json` называет store единственным writer-ом operational state.

## 5. Настройте hooks

Профиль задаётся в `.harness/project.json` и не может быть понижен агентом.

```json
{
  "hook_policy": {
    "profile": "standard"
  }
}
```

`minimal` — быстрый цикл, `standard` — поведение по умолчанию, `strict` — fail-closed
границы для чувствительных путей. `harness health` показывает действующий профиль,
источник, эскалации и подключение критических hooks для каждого runtime.

## Что дальше

- [Архитектура](../architecture/index.md) — слои, store, IPC и supervisor.
- [Справочник](../reference/index.md) — CLI, конфигурация и hooks.
- [Демо](../demo/index.md) — веб-консоль.
