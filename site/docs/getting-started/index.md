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

```bash
python3 harness/bin/harness.py init /path/to/repository \
  --capability engineering-suite \
  --project-type software --stack python --base-branch main --language ru \
  --qa-gate-command "make test"

python3 harness/bin/harness.py health /path/to/repository
```

Проверьте вывод `health`: в разделе «Оркестрация» должно быть
`authority=runtime-store` и `schema_version=4`, а критические hooks — подключены.

## 3. Проверьте verification

```bash
python3 .harness/orchestration/coordinator.py --repo . dispatch preflight
python3 .harness/orchestration/coordinator.py --repo . ledger validate --full
```

Дальше — [архитектура](../architecture/index.md) и [справочник](../reference/index.md).
