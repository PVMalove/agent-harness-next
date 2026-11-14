# Rust runtime

`harness-runtime serve` запускается одним процессом на state-каталог. Он слушает Unix domain
socket на Linux и macOS или named pipe на Windows, проверяет peer identity и выполняет
типизированные операции. Policy runtime не решает: он принимает уже одобренный brief, сверяет
digest и исполняет только сохранённый план. Python не запускает worker или QA-контейнер напрямую.

## Процесс и IPC

Кадр протокола состоит из длины и JSON. Рукопожатие `hello` согласует версию протокола и
подтверждает identity клиента. Если версия не совпала, runtime отвечает ошибкой
`protocol_unsupported`; на чужой uid или токен он отвечает `unauthorized_peer`.

| Поле конверта | Назначение |
| --- | --- |
| `operation_id` | Детерминированный ключ намерения. Повтор возвращает сохранённый результат, а тот же id с другим payload даёт `idempotency_conflict`. |
| `expected_revision` | CAS по строке состояния: при конфликте runtime возвращает типизированную ошибку и ничего не перезаписывает. |
| `request_deadline` | Ограничивает ожидание ответа; клиент повторяет запрос с тем же `operation_id`. |
| `fencing_token` | Не даёт двум владельцам одновременно держать singleton QA-lane. |

Исполнение идёт в три шага: `intent` → запуск → `committed`. Перед повтором runtime делает
reconcile и не запускает второй процесс, если объект уже существует.

```bash
python3 .harness/orchestration/coordinator.py --repo . runtime status
```

Serve, который запустил hook `runtime-autostart` (`serve --owner-session`), считается «своим». Он
хранит владельцев (`runtime.attach`, `runtime.release`) и сам завершается с кодом 0, когда нет ни
владельцев, ни соединений, а store простаивает. Serve, запущенный вручную, сам не
останавливается ([автозапуск runtime](../guides/orchestration/operations.md#runtime-autostart),
ADR 0031).

## Остановка и перезапуск

`harness-runtime stop --repo <repo>` останавливает runtime репозитория так же, как SIGTERM:
отправляет по его IPC операцию `shutdown` с токеном runtime и ждёт до 30 с, пока runtime
отпустит lock экземпляра. Сокет и token-файл runtime удаляет сам. Исполнения переживают
остановку, как и при SIGTERM. Команда печатает одну строку JSON.

`harness-runtime restart --repo <repo>` выполняет `stop`, а затем `serve` в том же процессе:
печатает строку готовности `serve` и завершается с его кодами. Соединения клиентов старого runtime
закрываются вместе с ним; клиент заново читает новый токен.

| Код | `stop` | `restart` |
| --- | --- | --- |
| 0 | `{"status":"stopped","pid":<pid>}` или `{"status":"not_running"}`; повтор безопасен | runtime остановлен штатно |
| 1 | runtime держит lock, но не ответил за 30 с (`[runtime_unavailable]`), или принял `shutdown`, но не отпустил lock за 30 с (`[deadline_exceeded]`) | `stop` не удался, или запущенный `serve` завершился ошибкой |
| 2 | отказ, ничего не остановлено: неверные аргументы, каталог не репозиторий (`[not_found]`), runtime отказал в `hello` (`[unauthorized_peer]`, `[protocol_unsupported]`) или не знает `shutdown` (`[unknown_operation]`) | `stop` отказал, или `serve` отказался стартовать |

Runtime старой версии без `shutdown` эта команда не остановит. Остановите его один раз сигналом
SIGTERM (на Windows Ctrl+Break), дальше работают `stop` и `restart`. На Windows контракт тот же,
клиент подключается к named pipe runtime.

## Store

Operational state хранится в SQLite WAL. Транзакции короткие, внешних вызовов внутри транзакции
нет. Store версионируется: несовместимую версию схемы runtime отвергает и ничего не пишет.

- **Authority.** `ledger.json` версии 4 и `state/AUTHORITY.json` называют store единственным
  writer operational state.
- **Audit.** Каждая мутация добавляет запись в хэш-цепочку. Checkpoint ускоряет обычную проверку,
  а `validate --full` пересчитывает цепочку целиком.
- **Leases.** Lease хранит владельца, `fencing_token` и `expires_at`. Истёкший срок сам lease не
  снимает: runtime сначала проверяет, жив ли владелец. Аренду освобождает только доказанная
  смерть владельца или его собственная команда с совпадающим токеном.
- **Idempotency.** Таблица операций хранит `operation_id`, digest запроса и результат, поэтому
  повтор после обрыва транспорта возвращает тот же ответ.

```bash
python3 .harness/orchestration/coordinator.py --repo . ledger validate --full
python3 .harness/orchestration/coordinator.py --repo . ledger lock-status
cat .harness/orchestration/state/AUTHORITY.json
```

## Supervisor и OCI

Процесс определяют `boot_id`, inode PID-namespace, pid и время старта. Одного PID недостаточно:
объект из другого namespace или другого boot не считается живым worker.

- **Linux.** Учёт по группе процессов; если доступен systemd, ещё transient scope для cgroup v2.
  Остановка: SIGTERM группе, после grace-периода SIGKILL.
- **Windows.** Именованный Job Object без `KILL_ON_JOB_CLOSE`, чтобы исполнение пережило рестарт
  runtime.
- **Контейнеры.** OCI-образ, метки dispatch и запрет монтировать сокеты движка и runtime. Трафик
  идёт через allowlist proxy; образы harness не собирает и не публикует.
- **Recovery.** После SIGKILL reconcile находит контейнерное исполнение по меткам и снова берёт
  его под надзор, доказывает, что процесса нет, или оставляет состояние `unknown`. Lease
  освобождается после остановки и записи exit evidence.

Состояния исполнения: `launching → running → stopping → exited | lost | unknown`. Терминальны
только `exited` и `lost`. `unknown` остаётся под наблюдением и при следующем наблюдении может
перейти в `running`, `exited` или `lost`.

## Reconcile и восстановление

Reconcile сверяет сохранённый intent с фактическим состоянием хоста. Если объект уже существует,
второй процесс не запускается. Если объекта доказанно нет, исполнение получает терминальное
состояние `lost`. Состояние исполнения наблюдает Rust, а состояние dispatch по этому наблюдению
выбирает Python. Lifecycle batch runtime сам не меняет: он только сохраняет решение Python.

## Verification

- **ChangeImpact** строит `ImpactSet` по графу Repo Map. Неизвестное влияние расширяет проверку,
  а не сужает её.
- **VerificationPlan** закрепляется digest в approval: developer и review получают focused
  проверки, QA получает полный clean-room на финальном SHA.
- **Failed-only** перезапускает точные nodeid; пустой выбор даёт `not_run`, а не успех.
- **Release Gate** подтверждает пару `{candidate_sha, target_sha}` и сверяет дерево после мержа.

## Домены отказов

Ошибка несёт тип домена, чтобы retry не тратил бюджет роли на сбои инфраструктуры.

| Домен | Пример | Что делает harness |
| --- | --- | --- |
| `environment_preparation` | Нет зависимости, не собран образ | Повтор после подготовки окружения. |
| `infrastructure` | EPERM, SELinux, недоступный engine | Retry на том же SHA, отдельно от кода. |
| `policy` | Нарушен approval или hook | Отказ с remedy, без auto-approve. |
| `code_test` | Упал тест или mypy | Возврат developer с evidence. |
| `timeout` | Истёк deadline | Остановка с grace и частичным evidence. |

Кроме этих пяти, словарь runtime содержит домены `tooling`, `cancelled` и `unknown`.

## Безопасность

| Граница | Правило |
| --- | --- |
| Runtime socket | Только peer uid/SID и capability-токен; каталог `0700`, сокет `0600`, токен `0600`. |
| Engine socket | Никогда не монтируется в worker или QA-контейнер. |
| Approval | Неизменяемый brief связывает план, образ, policy digest и verification digest. |
| Hooks | Профиль не отключает критические guards; `strict` не блокирует recovery. |
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
| 0030 | Operational store восстановления и сверка с authority lifecycle |
| 0031 | Автозапуск `harness-runtime serve` на время `/implement` |
| 0032 | Кэш cargo в QA-контейнерах |

## Дальше

- [Обзор архитектуры](overview.md)
- [Быстрый старт](../getting-started/index.md)
- [Справочник](../reference/index.md)
