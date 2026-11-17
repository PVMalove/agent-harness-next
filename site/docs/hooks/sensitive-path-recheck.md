# sensitive-path-recheck.sh: перепроверка чувствительного пути

## 1. Название и локализация

- **Исходный хук:** [`harness/project/hooks/sensitive-path-recheck.sh`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/sensitive-path-recheck.sh)
  и общее тело [`change_impact_hooks.py`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/change_impact_hooks.py)
- **Русский перевод:** предупреждение о каждой новой правке чувствительного пути с evidence-записью.

## 2. Полное описание

Advisory-hook `PreToolUse(Write|Edit)` профиля `strict` из матрицы ADR 0024, раздел 2a. Hook
предупреждает о правке чувствительного пути из ADR 0024, раздел 2. Набор путей задаёт фиксированная
константа политики `is_sensitive_path` в `harness/orchestration/hook_policy.py`; ключа конфигурации
у набора нет. В набор входят:

- манифесты и lock-файлы по имени на любой глубине: `pyproject.toml`, `uv.lock`, `poetry.lock`,
  `Pipfile`, `Pipfile.lock`, `setup.py`, `setup.cfg`, `requirements*.txt`, `constraints*.txt`,
  `package.json`, `package-lock.json`, `npm-shrinkwrap.json`, `yarn.lock`, `pnpm-lock.yaml`,
  `Cargo.toml`, `Cargo.lock`, `rust-toolchain`, `rust-toolchain.toml`, `go.mod`, `go.sum`, `Gemfile`,
  `Gemfile.lock`, `composer.json`, `composer.lock`;
- CI: `.github/*`;
- миграции, auth и права доступа: сегмент пути или stem файла после разбиения по `.`, `_` и `-`
  содержит токен из `migration`, `migrations`, `migrate`, `alembic`, `auth`, `authn`, `authz`,
  `oauth`, `oauth2`, `authentication`, `authorization`, `permission`, `permissions`, `acl`, `rbac`;
  сюда же входит файл `CODEOWNERS`. Hook сравнивает токены, а не подстроки: `author.py` не совпадает
  с `auth`;
- сами hooks: `.claude/settings*.json`, `.claude/hooks/*`, `.claude/agents/*`, `.codex/hooks.json`,
  `.codex/hooks/*`, `.codex/config.toml`;
- конфиг проекта `.harness/project.json`.

Hook не видит пакет harness, поэтому держит копию набора, а `tests/core/test_change_impact_hooks.py`
сверяет её с `is_sensitive_path`. Путь hook сравнивает так же, как
[impact-first-touch.md](impact-first-touch.md): после `realpath` от ближайшего каталога с `.git`.

Модель получает текст в `hookSpecificOutput.additionalContext` без `permissionDecision`, и hook
никогда не блокирует. Правку `.claude/settings*.json`, `.claude/hooks/` и `.harness/project.json`
по-прежнему блокирует критический `protect-hook-policy`; этот hook его решения не меняет.

- **Профили.** В `minimal` и `standard` hook не работает (тело не запускается). В `strict` hook даёт
  `warn` с кодом `sensitive-path-touched` и обязательным `evidence_ref`.
- **Дедупликация.** Предмет предупреждения состоит из пути, `tool_name` и `tool_input`. Каждую новую
  правку hook проверяет заново, а повтор той же правки в той же операции молчит. Новая операция
  (`session_id` или `agent_id`) даёт новое предупреждение.
- **Evidence.** Файл `.harness/.sandboxes/hook-events/<operation_id>/n-<key>.json` содержит `hook_id`,
  `event`, `path`, `subject_digest`, `operation_id`, `session_id`, `agent_id`, `profile` и
  `recorded_at`. `evidence_ref` вердикта равен пути этого файла от корня проекта.
- **Авторитетная проверка.** Hook только предупреждает. Под `strict` отказывают границы coordinator:
  `dispatch propose` и `dispatch create` для code-review и QA, `qa run` и `dispatch publish` отвечают
  `strict_impact_unknown`, пока VerificationPlan не доказывает ImpactSet чувствительного изменения
  (раздел «Граница strict» в [hook-response.md](hook-response.md)).
- **Остаточное ограничение.** Hardlink на чувствительный файл обходит только это предупреждение:
  `realpath` не раскрывает hardlink. Решают критический `protect-hook-policy` и diff-проверка
  границы strict, которая видит путь из git.
- **Второй runtime.** Hook не подключён, пока нет адаптера `apply_patch`; `harness health` называет
  проверку вне hook: границу strict.

## 3. Контракт

- **Вход:** JSON события `PreToolUse` в stdin, как у `impact-first-touch`. Профиль hook берёт только
  из `hook_policy` в `.harness/project.json`.
- **Выход:** всегда код `0`. Для новой правки чувствительного пути под `strict` hook пишет
  `additionalContext` в stdout, первой строкой stderr `[sensitive-path-touched] <текст>`, строку
  `evidence_ref=<путь>`, и конверт даёт вердикт `warn`. Внутренняя ошибка даёт `warn`
  `internal-error` с пустым stdout.

## Источник

[sensitive-path-recheck.sh](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/sensitive-path-recheck.sh),
[change_impact_hooks.py](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/change_impact_hooks.py),
[hook_policy.py](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/hook_policy.py)
