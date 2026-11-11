# Backend-оркестрация {#backend-}

Используйте `backend-orchestration`, когда задаче нужны независимые роли или отдельная проверка. Capability расширяет `engineering-suite`. Управляющая сессия coordinator планирует работу и ведёт её по выбранной политике согласования. Роли не выбирают себе модель и не мержат PR.

## Выберите задачу {#choose-task}

- <span id="1"></span><span id="2-harnessorchestrationjson"></span><span id="_3"></span><span id="preflight"></span><span id="tool-policy-context-budget-brief"></span><span id="attention-approval-ttl-extensions"></span>[Включить и настроить](guides/orchestration/setup.md).
- <span id="access_policy-runtime_access"></span><span id="docker"></span><span id="worker"></span><span id="qa-git-publish"></span>[Подготовить доступ и контейнер](guides/orchestration/access.md).
- <span id="discovery-context-context-package"></span>[Подготовить контекст роли](guides/orchestration/context.md).
- <span id="_4"></span><span id="3-batch"></span><span id="4-coordinator-cli-lifecycle"></span><span id="5-adapter"></span><span id="6-pilot"></span>[Запустить batch и принять отчёт](guides/orchestration/run.md).
- <span id="retry-abandon"></span><span id="approval_policy-auto"></span><span id="approval-digest"></span><span id="idempotency-read-only-retry"></span><span id="context-pressure"></span><span id="attention-state"></span>[Выбрать решение или повтор](guides/orchestration/decisions.md).
- <span id="_5"></span><span id="batch"></span><span id="model-self-report-dispatch-watchdog"></span><span id="ledger-report-complete-ledger-release-lock"></span><span id="lifecycle-runtime-store"></span><span id="dispatch-telemetry"></span><span id="checkpoint-worker-session"></span>[Проверить состояние и диагностику](guides/orchestration/operations.md).
- <span id="clean-room-qa-lane"></span>[Выполнить чистый QA](guides/orchestration/qa.md).
- <span id="integration-accounting-publish"></span><span id="advisory-tool-call"></span>[Опубликовать candidate и подготовить PR](guides/orchestration/publish.md).
- <span id="_8"></span><span id="batch-recovery"></span>[Восстановить остановленную работу](guides/orchestration/recovery.md).

## Кто задаёт правила {#_1}

Coordinator применяет правила из установленного `.harness/orchestration/playbook.md`.
Manifest-файлы в `roles/` задают границы ролей. Проектный `orchestration.json` выбирает назначения,
проверки и политики в этих границах. Runtime adapter передаёт утверждённые задания.

`/implement` ведёт порядок `architect → developer → code-review → qa → publish`.
Как принимать отчёт, решает `approval_policy`. PR агент открывает только после отдельного
подтверждения, merge делает человек.

## Что устанавливается {#_2}

- `.harness/orchestration/roles/`: manifest-файлы ролей и общий контракт.
- `.harness/orchestration/playbook.md`: порядок работы и правила передачи заданий.
- `.harness/orchestration/pilot.md`: наблюдение за первыми batch.
- `.harness/orchestration/coordinator.py`: CLI для batch, dispatch, approval и report.
- `.harness/orchestration.json`: настройки проекта.

После миграции Rust хранит рабочие записи в `.harness/orchestration/state/runtime.db`.
Python читает и меняет их через протокол runtime. Пути вида `reports/<id>.json` обозначают
логические записи, а не JSON-файлы для ручной правки. Используйте CLI для чтения и изменений.
Локальное состояние не публикуется в Git; очистка требует отдельного решения coordinator.

## Язык и доказательства {#language-evidence}

Перед первым английским handoff прочитайте [Technical English](https://github.com/PVMalove/agent-harness-next/blob/master/harness/docs/technical-english.md).
Передача между ролями, checkpoint и state evidence пишутся на английском; completion report для
coordinator пишется на русском с `"report_language": "ru"`. Команды, пути и SHA не переводятся.

Токены учитываются только по наблюдаемой telemetry provider или runtime с указанием источника.
Оценка роли не заменяет отсутствующую telemetry. Значения секретов не входят в конфиг, brief или report.

## С чего начать {#start-here}

Для первого запуска откройте [включение и конфигурацию](guides/orchestration/setup.md).
Если нужно выбрать значения с агентом, используйте [стартовый промпт настройки](getting-started/settings/orchestration/index.md#agent-setup).
