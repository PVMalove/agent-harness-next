# Обнаружение skills в Claude Code и Codex

Claude Code и Codex находят скиллы проекта по ссылкам на `.harness/skills/`, где лежит установленный
набор. Hooks проекта подключаются к этим двум runtime отдельно, через их файлы настроек.

| Runtime | Проектный путь | Глобальные `start-project` и `integrate-project` |
| --- | --- | --- |
| Claude Code | `.claude/skills` → `.harness/skills` | `~/.claude/skills/start-project`, `~/.claude/skills/integrate-project` |
| Codex | `.agents/skills` → `.harness/skills` | `~/.agents/skills/start-project`, `~/.agents/skills/integrate-project` |

`harness init`, `adopt` и `update` создают или проверяют проектные ссылки и записывают
`.harness/skills/REGISTRY.md` с именами, путями и описаниями установленного набора.
`harness health` проверяет целостность файлов и ссылок. `bin/install-global.py` создаёт
глобальный профиль и ссылки на `global-skills/start-project` и `global-skills/integrate-project`
для выбранного runtime.

Runtime не загружает полный текст скилла в каждую сессию. Он выбирает скилл по метаданным
и только потом читает его `SKILL.md`. Закреплённые upstream-файлы хранятся побайтно, поэтому
их frontmatter и настройки вызова остаются такими же, как в исходном скилле. Интеграции, которыми
владеет проект, записаны в `.harness/integrations.json`: путь, SHA-256, runtime-цель и проверка
активации. Значения секретов там не хранятся.

Hooks проекта подключаются не через ссылки на `.harness/skills/`. `harness init`, `adopt` и `update`
дописывают управляемые записи в `.claude/settings.local.json` для Claude Code и в `.codex/hooks.json`
для Codex. Записи пользователя они не трогают.

В Codex подключены:

- критические guards и `require-bounded-check` на `PreToolUse` для `Bash`;
- advisory `targeted-check-reminder` на `Stop` и `SubagentStop`;
- критические guards `protect-hook-policy` и `block-scratch-outside-docs-tasks` группой
  `apply_patch|Write|Edit`. Codex присылает правки файлов как `apply_patch`, и эти guards
  проверяют пути патча через адаптер `apply_patch_payload.py`.

Hooks ChangeImpact из строк `Write` и `Edit` к `apply_patch` не подключаются. Проектные hooks
Codex работают, только когда пользователь доверил слою `.codex/` и каждому hook по хэшу. Проверка
`hooks.policy` в `harness health` показывает подключённые и отсутствующие hooks каждого runtime.
Подробности: [install-and-update](hooks/install-and-update.md).

Если в CLI есть маршрут для другого runtime, это ещё не подтверждает совместимость. Здесь описаны
только два runtime из таблицы, остальные сочетания нужно проверять отдельно.
