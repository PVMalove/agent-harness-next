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
только сохранённый план.

## Store

- **Authority.** `ledger.json` версии 4 и `AUTHORITY.json` называют store единственным writer-ом.
- **Audit.** Каждая мутация оставляет запись в хэш-цепочке; `validate --full` пересчитывает всё.
- **Leases.** QA-lane — singleton с fencing token; lease мёртвого владельца снимается
  только по вердикту `owner-dead`.

## Безопасность

| Граница | Правило |
| --- | --- |
| Runtime socket | Только peer uid/SID и capability-токен; каталог 0700. |
| Engine socket | Никогда не монтируется в worker или QA-контейнер. |
| Approval | Immutable brief связывает план, образ и digest-ы. |
| Hooks | Критические guards не отключаются профилем. |
| Secrets | Не попадают в командную строку, логи и audit. |
