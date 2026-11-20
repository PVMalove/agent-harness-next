# Набор проверок CI на Windows в pull request

**Статус: ACCEPTED (2026-10-11).** Подмножество тестов Windows в pull request отменено (#1062):
CI гоняет на Windows полный набор.

## Контекст системы

Прогон `make verify` на `windows-latest` с полным набором из ~2 700 тестов занимает больше
часа: процессы на Windows запускаются на порядок медленнее, чем на Linux, а тесты координатора
(`tests/orchestration/test_coordinator.py`) вызывают `git` ~90 раз каждый. Такое задание упирается в
лимит времени и не доходит до clean-room прогона. Подмножество тестов в pull request откладывало
Windows-сбои до слияния, где их исправлял отдельный тикет. Поэтому pull request проверяет на Windows
полный набор, а время ограничивают разбиение на задания и длинный лимит.

## Действующий контракт

- **Группы тестов в pull request.** Любой pull request, в том числе в `integration/**`, запускает
  pytest на Windows двумя заданиями: `verify-windows-unit` и `verify-windows-integration`. Такие же
  группы идут на Linux (`verify-linux-unit`, `verify-linux-integration`). Задание
  `verify-test-groups` сводит результаты четырёх групп.
- **Два параллельных задания Windows на полном пути.** `verify-windows (tests)` и
  `verify-windows (clean-room)` идут для pull request в ветку, кроме `integration/**`, для push в
  `master` и для вызова из другого workflow. Время одного не расходует лимит другого. Разбиение
  задают `scripts/verify.py --only tests` и `--only clean-room`; `make verify` передаёт их через
  `VERIFY_ARGS`. В pull request часть `tests` сама pytest не запускает: она проверяет, что прошли
  обе Windows-группы. На `master` и при вызове workflow часть `tests` запускает полный набор. Лимит
  части `tests` 180 минут, части `clean-room` 30 минут.
- **Без подмножества.** CI не передаёт `--platform-subset`. Ключ и список
  `WINDOWS_PR_IGNORED_TESTS` в `scripts/verify.py` остаются только для локального запуска.
- **Diff-coverage отдельно.** Задание `diff-coverage` (только pull request вне `integration/**`) измеряет покрытие своим
  прогоном pytest параллельно с `verify`, а не после него.
- **Git на Windows.** Задание задаёт `core.autocrlf=false`, `core.fscache=true`,
  `core.preloadindex=true` до checkout.
- **Обратная связь в pull request.** Группы pytest не останавливаются на первом падении: один
  прогон показывает все Windows-сбои. Часть `clean-room` в pull request останавливается на первом
  падении (`--fail-fast`). Полный прогон вне pull request получает `--failed-first <каталог>`: кэш
  pytest лежит в `.harness/.sandboxes/pytest-cache`, workflow сохраняет и восстанавливает его по
  ключу ветки, и ранее упавшие тесты идут первыми. Каждое новое обновление ветки pull request
  отменяет прежний запуск (`concurrency` с `cancel-in-progress` только для `pull_request`).
- **Сводка и дашборд.** `--junit-xml` пишет отчёт pytest; `scripts/ci_summary.py tests` кладёт в
  сводку задания итоги, упавшие тесты с причиной и самые медленные тесты, а задание `dashboard`
  (всегда после остальных) собирает одну страницу: результаты всех заданий, тесты по заданиям и
  все упавшие тесты.

## Операционные последствия

- Новый тест, зависящий от платформы (пути, блокировки файлов, процессы, оболочка), не добавляется
  в `WINDOWS_PR_IGNORED_TESTS`; в список попадает только файл, у которого нет платформенной логики.
- Задания Windows в CI: `verify-windows` (части `tests` и `clean-room`), `verify-windows-unit`
  (`Windows / Unit`) и `verify-windows-integration` (`Windows / Integration`).
- `windows-latest` в матрице `memory-vector-probe.yml` закомментирован (#753).
