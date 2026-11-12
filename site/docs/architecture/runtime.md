# Rust runtime

`harness-runtime serve` — один процесс на state-каталог. Он слушает Unix domain socket на Linux и
macOS или named pipe на Windows, проверяет peer identity и выполняет типизированные операции.
Runtime не решает policy: он принимает уже approved brief, сверяет digest-ы и исполняет только
сохранённый план. Python не запускает worker-а или QA-контейнер напрямую.

## Процесс и IPC

Кадр протокола — длина и JSON. Рукопожатие `hello` согласует версию протокола и подтверждает
identity клиента; несовпадение версии — ошибка `protocol_unsupported`, чужой uid или токен —
`unauthorized_peer`.

| Поле конверта | Назначение |
| --- | --- |
| `operation_id` | Детерминированный ключ намерения; повтор возвращает сохранённый результат, а тот же id с другим payload — `idempotency_conflict`. |
| `expected_revision` | CAS по строке состояния; конфликт — типизированная ошибка, а не тихая перезапись. |
| `request_deadline` | Ограничивает ожидание ответа; клиент повторяет с тем же `operation_id`. |
| `fencing_token` | Защищает singleton QA-lane от двух владельцев. |

Исполнение идёт в три шага: `intent` → запуск → `committed`. Перед повтором runtime делает
reconcile и не запускает второй процесс, если объект уже существует.

```bash
python3 .harness/orchestration/coordinator.py --repo . runtime status
```

## Остановка и перезапуск

`harness-runtime stop --repo <repo>` останавливает runtime репозитория тем же путём, что SIGTERM:
отправляет по его IPC операцию `shutdown` с токеном runtime и ждёт, пока runtime отпустит lock
экземпляра (до 30 с). Сокет и token-файл runtime удаляет сам. Исполнения переживают остановку, как
и при SIGTERM. Команда печатает одну строку JSON.

`harness-runtime restart --repo <repo>` выполняет `stop`, затем `serve` в том же процессе: печатает
строку готовности `serve` и завершается его кодами. Соединения клиентов старого runtime
закрываются вместе с ним; клиент заново читает новый токен.

| Код | `stop` | `restart` |
| --- | --- | --- |
| 0 | `{"status":"stopped","pid":<pid>}` или `{"status":"not_running"}`; повтор безопасен | runtime остановлен штатно |
| 1 | runtime держит lock, но не ответил за 30 с (`[runtime_unavailable]`), или принял `shutdown`, но не отпустил lock за 30 с (`[deadline_exceeded]`) | `stop` не удался, или запущенный `serve` завершился ошибкой |
| 2 | отказ, ничего не остановлено: неверные аргументы, каталог не репозиторий (`[not_found]`), runtime отказал в `hello` (`[unauthorized_peer]`, `[protocol_unsupported]`) или не знает `shutdown` (`[unknown_operation]`) | `stop` отказал, или `serve` отказался стартовать |

Runtime версии без `shutdown` команда не останавливает: его один раз останавливают сигналом SIGTERM
(на Windows — Ctrl+Break), дальше работают `stop` и `restart`. На Windows контракт тот же, клиент
подключается к named pipe runtime.

## Store

Operational state — SQLite WAL с короткими транзакциями и без внешних вызовов внутри транзакции.
Store версионируется: несовместимая версия схемы отвергается без записи.

- **Authority.** `ledger.json` версии 4 и `state/AUTHORITY.json` называют store единственным
  writer-ом operational state.
- **Audit.** Каждая мутация оставляет запись в хэш-цепочке; checkpoint ускоряет обычную проверку,
  а `validate --full` пересчитывает цепочку целиком.
- **Leases.** Lease хранит владельца, `fencing_token` и `expires_at`. Истёкший срок сам lease не
  снимает: сначала проверяется живость владельца, и только доказанная смерть или собственная команда
  с совпадающим токеном освобождают аренду.
- **Idempotency.** Таблица операций хранит `operation_id`, digest запроса и результат, поэтому
  повтор после обрыва транспорта возвращает тот же ответ.

```bash
python3 .harness/orchestration/coordinator.py --repo . ledger validate --full
python3 .harness/orchestration/coordinator.py --repo . ledger lock-status
cat .harness/orchestration/state/AUTHORITY.json
```

## Supervisor и OCI

Идентичность процесса — `boot_id`, inode PID-namespace, pid и время старта. PID сам по себе ничего
не доказывает: объект другого namespace или другого boot не считается живым worker-ом.

- **Linux.** Учёт по группе процессов; там, где доступен systemd, — transient scope для cgroup v2.
  Остановка — SIGTERM группе, после grace-периода SIGKILL.
- **Windows.** Именованный Job Object без `KILL_ON_JOB_CLOSE`, чтобы исполнение пережило рестарт
  runtime.
- **Контейнеры.** OCI-образ, метки dispatch и запрет монтировать сокеты движка и runtime. Egress
  идёт через allowlist proxy; образы harness не собирает и не публикует.
- **Recovery.** Reconcile после SIGKILL усыновляет контейнерное исполнение по меткам, доказывает
  отсутствие процесса или оставляет состояние `unknown`. Lease освобождается после остановки и
  записи exit evidence.

Состояния исполнения — `launching → running → stopping → exited | lost | unknown`. Терминальны
только `exited` и `lost`; `unknown` остаётся наблюдаемым и может перейти в `running`, `exited` или
`lost` при следующем наблюдении.

## Reconcile и восстановление

Reconcile сверяет сохранённый intent с фактическим состоянием хоста. Если объект уже существует,
второй процесс не запускается; если объект доказанно отсутствует, исполнение получает `lost` и
становится терминальным. Состояние исполнения — наблюдение Rust, а состояние dispatch выбирает
Python по этому наблюдению: runtime никогда не пишет lifecycle batch напрямую.

## Verification

- **ChangeImpact** строит `ImpactSet` по графу Repo Map; неизвестное влияние расширяет проверку,
  а не сужает её.
- **VerificationPlan** закрепляется digest-ом в approval: developer и review получают focused
  проверки, QA — полный clean-room на финальном SHA.
- **Failed-only** перезапускает точные nodeid; пустой выбор — `not_run`, а не успех.
- **Release Gate** подтверждает пару `{candidate_sha, target_sha}` и сверяет дерево после merge.

## Домены отказов

Ошибка типизирована, чтобы retry не тратил бюджет роли на инфраструктуру.

| Домен | Пример | Что делает harness |
| --- | --- | --- |
| `environment_preparation` | Нет зависимости, не собран образ | Повтор после подготовки окружения. |
| `infrastructure` | EPERM, SELinux, недоступный engine | Retry на том же SHA, отдельно от кода. |
| `policy` | Нарушен approval или hook | Отказ с remedy, без auto-approve. |
| `code_test` | Упал тест или mypy | Возврат developer-у с evidence. |
| `timeout` | Истёк deadline | Остановка с grace и частичным evidence. |

## Безопасность

| Граница | Правило |
| --- | --- |
| Runtime socket | Только peer uid/SID и capability-токен; каталог `0700`, сокет `0600`, токен `0600`. |
| Engine socket | Никогда не монтируется в worker или QA-контейнер. |
| Approval | Immutable brief связывает план, образ, policy digest и verification digest. |
| Hooks | Критические guards не отключаются профилем; `strict` не блокирует recovery. |
| Secrets | Не попадают в командную строку, логи, audit и отчёты. |

## Решения

| ADR | Тема |
| --- | --- |
| 0019 | Единый Rust runtime и incremental verification |
| 0020 | Переход operational state на runtime store |
| 0021 | Authority, IPC и идемпотентность |
| 0022 | Supervisor процессов и OCI-контейнеров |
| 0023 | Инкрементальные проверки |
| 0025 | Встроенный контейнерный исполнитель |
| 0026 | Консолидация Harness Next и Release Gate |

## Дальше

- [Обзор архитектуры](overview.md)
- [Быстрый старт](../getting-started/index.md)
- [Справочник](../reference/index.md)
