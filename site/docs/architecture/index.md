# Архитектура

Policy и исполнение разделены. Python принимает решения, Rust runtime хранит operational state
и запускает процессы, а Git остаётся владельцем истории и кандидатов.

## Кто владеет чем

| Сущность | Writer | Что это значит |
| --- | --- | --- |
| Lifecycle batch/dispatch | Rust runtime | Переходы сохраняются транзакцией; Python не пишет в store напрямую. |
| Approvals и policy | Python | Решение принимает человек и policy-слой; runtime исполняет сохранённое решение. |
| Операционный intent | Rust store | Idempotency key, attempt и reconcile живут в одной транзакции. |
| Git-история | Git | Кандидат, ветки и worktree — обычные Git-объекты. |
| Audit | Rust store | Хэш-цепочка с checkpoint для инкрементальной проверки. |

## Rust runtime

`harness-runtime serve` — один процесс на state-каталог. Он слушает Unix domain socket
на Linux или named pipe на Windows, проверяет peer identity и выполняет типизированные операции.

```text
Clients  -> Policy -> IPC -> Rust runtime -> SQLite WAL
```

Runtime не решает policy: он принимает approved brief, проверяет digest-ы и исполняет
только сохранённый план. Python не запускает worker-а или QA-контейнер напрямую.

### IPC и идемпотентность

| Поле | Назначение |
| --- | --- |
| `operation_id` | Детерминированный ключ намерения; повтор возвращает сохранённый результат. |
| `expected_revision` | CAS по строке; конфликт — типизированная ошибка, а не тихая перезапись. |
| `deadline` | Ограничивает ожидание; клиент повторяет с тем же id. |
| `fencing_token` | Защищает singleton QA-lane от двух владельцев. |

Исполнение идёт в три шага: `intent` → запуск → `committed`. Перед повтором runtime делает
reconcile и не запускает второй процесс, если объект уже существует.

## Store

- **Authority.** `ledger.json` версии 4 и `AUTHORITY.json` называют store единственным writer-ом.
- **Audit.** Каждая мутация оставляет запись в хэш-цепочке; `validate --full` пересчитывает всё.
- **Leases.** QA-lane — singleton с fencing token; lease мёртвого владельца снимается
  только по вердикту `owner-dead`.
- **Schema.** Несовместимая версия store отвергается без записи; схема обновляется runtime.

```bash
python3 .harness/orchestration/coordinator.py --repo . ledger validate --full
cat .harness/orchestration/state/AUTHORITY.json
```

## Supervisor

Идентичность процесса — boot, namespace, pid и время старта. Этого достаточно, чтобы не принять
чужой процесс с тем же pid за живой worker.

- Linux: группы процессов и systemd scope, stop по deadline с grace-периодом.
- Windows: Job Objects с именем по операции; исполнение переживает рестарт runtime.
- Контейнеры: OCI-образ, метки dispatch, запрет монтирования сокетов движка и runtime.
- Recovery: после SIGKILL runtime находит исполнение по меткам или пишет `lost`;
  освобождение lease — только после доказанного выхода группы.

## Verification

- `ChangeImpact` строит `ImpactSet` по графу Repo Map; неизвестное влияние расширяет проверку.
- `VerificationPlan` закрепляется digest-ом в approval; developer и review получают focused,
  QA — полный clean-room на финальном SHA.
- Failed-only перезапускает точные nodeid; пустой выбор — `not_run`, а не pass.
- Release Gate подтверждает пару `{candidate_sha, target_sha}` и сверяет дерево после merge.

## Модель поставки

`harness/CAPABILITIES.json` разрешает состав snapshot. Установщик копирует skills, hooks,
агентов и проектные руководства, затем фиксирует lock и `REGISTRY.md`. Целевой проект живёт
автономно: исходный клон harness во время работы не нужен.

```text
capability -> skills -> project snapshot -> .harness/project.json -> runtime
```

## Discovery Pipeline

Контекст передаётся между сессиями через проверяемые артефакты:

1. Grilling записывает в артефакт только явно одобренные пути.
2. Спецификация сохраняет `Relevant Files` в эпике.
3. Декомпозиция назначает пути тикетам и строит Path inventory.
4. Context builder читает pinned commit, собирает diff, стартовые файлы, связанные тесты,
   ADR и precedent cards в immutable Context Package.
5. Coordinator фиксирует package в ledger и проверяет его freshness перед dispatch.

## Backend orchestration

`backend-orchestration` — opt-in capability поверх `engineering-suite`. Coordinator владеет
batch, approval, scope changes, QA lane и принятием reports. Роль получает immutable brief,
подтверждает model self-report и передаёт heartbeat.

Обычный `/implement` проходит `architect → developer → code-review → qa → publish` с отдельным
approval каждого handoff. Review и QA работают с pinned candidate SHA; PR остаётся отдельным
ручным шагом `/to-pull-requests`, merge не автоматизируется.

Batch lifecycle: `planned → awaiting-approval ↔ active → completed | blocked | failed`.
Completion report оставляет dispatch в `reported` до coordinator decision. Только write-роли
могут записать non-terminal checkpoint и продолжить тот же dispatch под новым worker session ID.

## Домены отказов

| Домен | Пример | Что делает harness |
| --- | --- | --- |
| `environment_preparation` | Нет зависимости, не собран образ | Повтор после подготовки |
| `infrastructure` | EPERM, SELinux, недоступный engine | Retry на том же SHA, отдельно от кода |
| `policy` | Нарушен approval или hook | Отказ с remedy, без auto-approve |
| `code_test` | Упал тест или mypy | Возврат developer-у с evidence |
| `timeout` | Истёк deadline | Остановка с grace и частичным evidence |

## Безопасность

| Граница | Правило |
| --- | --- |
| Runtime socket | Только peer uid/SID и capability-токен; каталог 0700. |
| Engine socket | Никогда не монтируется в worker или QA-контейнер. |
| Approval | Immutable brief связывает план, образ и digest-ы. |
| Hooks | Критические guards не отключаются профилем. |
| Secrets | Не попадают в командную строку, логи и audit. |

## Дальше

- [Быстрый старт](../getting-started/index.md)
- [Справочник](../reference/index.md)
- [Демо](../demo/index.md)
