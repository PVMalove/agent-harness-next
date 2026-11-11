# Контекст для ролей

Context Package закрепляет исходники, тесты и решения для роли. Coordinator проверяет его размер и свежесть до отправки. Пакет помогает выбрать материал для чтения, но не заменяет проверку результата.

[Обзор оркестрации](../../backend-orchestration.md)

## Discovery Context и Context Package {#discovery-context-context-package}

Discovery Pipeline переносит проверенный контекст от проектирования к dispatch. `/grilling` ведёт
`Live Artifact` с кандидатными путями, но добавляет путь только после явного согласия пользователя.
`/to-spec` сохраняет утверждённый список в эпике под `## Relevant Files (Discovery Context)`.
`/to-tickets` назначает каждый путь подходящему tracer-bullet тикету и строит Path inventory. Один
cheap advisory-вызов может добавить только точные зависимости из этого Path inventory. Его вывод —
не evidence и не authority.

Перед первым dispatch coordinator может зарегистрировать детерминированный Context Package в
ledger:

```bash
python .harness/orchestration/coordinator.py --repo . context-package register \
  --batch <batch-id> --candidate-commit <candidate-sha> \
  --symbol-graph-depth 1 --min-starting-files 5 --max-starting-files 10 \
  --max-package-tokens 60000
```

`context_builder.py` не вызывает LLM и работает по pinned base/candidate commits. Package содержит
точный diff, 5–10 стартовых файлов с причинами, bounded symbol/dependency graph, связанные тесты,
краткие карточки ADR/precedent, SHA-256 каждого включённого файла, byte size и консервативную token
estimate. Побайтно идентичные файлы (например, зеркало `docs/agents/*` ↔
`harness/project/docs-agents/*`) остаются стартовыми файлами, но оценка учитывает их содержимое один
раз; причина второй копии называет оригинал и требует держать копии идентичными. Markdown-файл
входит в пакет как оглавление, если его оценка не меньше
`context_package_policy.section_index_min_tokens` (по умолчанию 20000). `sections` перечисляет
заголовки уровней 1–3 (вне fenced code) с `start_line`/`end_line`; оценка учитывает только это
оглавление, а роль читает лишь нужные ей диапазоны строк. Файл без заголовков учитывается целиком.

Python-файл при том же пороге входит как индекс символов. Он состоит из верхнеуровневых функций,
классов и методов классов; вложенное в функции и методы не перечисляется. Остальной код файла
покрывают указатели `module header` (до первого определения) и `module code` (между определениями,
после последнего и блоки вроде `if TYPE_CHECKING:`), поэтому индекс ничего не скрывает. Скрытые
`repo_map_policy.redact_symbols` символы в заголовках остаются маркером `[REDACTED-SYMBOL]`. Индекс
применяется, только если он дешевле файла. Файл без определений, с синтаксической ошибкой или другого
формата учитывается целиком. Если пакет не помещается в лимит, самые тяжёлые стартовые файлы, для
которых можно построить индекс, заменяются индексом по одному, пока пакет не уложится в лимит.
Добавленный файл так не сократить: его текст уже лежит в diff, а связанные тесты и ADR остаются в
пакете целиком.

Карточки прямых локальных зависимостей используют сигнатуры из Repo Map. Если сигнатур нет, пакет берёт первые 30 строк файла. Этот контекст одного уровня отделён от графа связей: глубину графа задаёт `symbol_graph_depth`. Если и после замены файлов индексами пакет не помещается
в token limit, сборка завершается ошибкой и не обрезает пакет молча. Legacy `--max-package-size-bytes` можно задать как дополнительную диагностику,
но он не заменяет token limit.

Запись package immutable, versioned и hash-проверяема. Она shared внутри batch. Один и тот же
base/candidate переиспользует один package ID между architect, developer и continuation sessions.
Новый package создаётся только после нового candidate. Coordinator не переиспользует package, если
его frozen источник из `memory.pointers` после регистрации изменился, стал недоступен или отозван.
Тогда следующий dispatch регистрирует новый package с актуальными указателями. Старый package
остаётся неизменным для уже выданных brief. Coordinator проверяет freshness до handoff и не создаёт
brief со stale package. Если и новый package не свежий по памяти, ошибка называет путь, ожидаемый и
фактический `source_hash`. Remedy предлагает `harness memory rebuild .` из основного checkout или
`--no-memory`. Brief передаёт compact summary (starting files, related tests, precedents и pinned
commits). Полный diff остаётся в package один раз. Package не заменяет immutable brief и не
отменяет обязательные self-report, heartbeat, review или QA.
