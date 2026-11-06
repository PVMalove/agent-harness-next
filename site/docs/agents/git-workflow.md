# Git workflow: feature-ветка и PR

Руководство описывает только правила Git, задач и PR. Opt-in backend-оркестрация, которую ведёт `/implement`, следует `.harness/orchestration/playbook.md`.

### 1. Базовые ограничения и инструменты { #1-fundamental-constraints-tooling }

* **Zero Direct Commits (никаких прямых коммитов).** `base_branch` и каждая ветка `integration/*` — защищённые цели. Агенты коммитят и пушат только из изолированной ветки задачи, подходящей под `branch_pattern`. У `/to-spec` есть два исключения для новой ветки `integration/*`, которой нет в удалённом репозитории. Первое: `/to-spec` может закоммитить в неё grill-документы — `CONTEXT.md`, `CONTEXT-MAP.md`, `**/CONTEXT.md`, `docs/adr/**` и `**/docs/adr/**`. Коммит должен быть отдельным `git commit` только с опциями сообщения, а в индексе должны лежать только grill-документы. Второе: `/to-spec` может запушить эту ветку, чтобы создать её. Для коммита hook проверяет `origin`, для push — remote из команды. Если ветка там уже есть или remote проверить не удаётся, hook блокирует команду.
* **Только CLI.** Для операций с репозиторием и задачами используйте исключительно `git` и CLI трекера — GitHub CLI (`gh`) или GitLab CLI (`glab`). На GitLab называйте проект явно в каждой команде: каждая команда `glab` принимает `-R <project-url>`, а каждый вызов `glab api` пишется как `GITLAB_HOST=<host> glab api projects/<project-id>/...`. `<host>`, `<project-url>` и `<project-id>` определены в [issue-tracker.md](issue-tracker.md) → GitLab → Conventions.
* **Тело — из файла, а не в команде.** Каждое тело или комментарий, публикуемые через `gh`/`glab`, ОБЯЗАНЫ браться из файла по читаемому буквальному пути. Нельзя использовать inline `--body "..."`, `--description "..."` или `--message "..."`, shell heredoc, shell-переменную и `-` (stdin). Вложенные кавычки, обратные апострофы и правила экранирования PowerShell непредсказуемо ломают inline-текст, а hook публичных метаданных (`block-public-attribution.sh`) проверяет содержимое файла и отклоняет shell-переменную, stdin и отсутствующий путь. Оба трекера следуют одному контракту публикации:
  * **GitHub:** тела задач, PR и комментариев передаются через `--body-file <path>` (`gh issue create`/`edit`, `gh pr create`/`edit`, `gh issue comment`, `gh pr comment`).
  * **GitLab:** тела MR и задач передаются через `--description-file <path>` (`glab mr create`/`update`, `glab issue create`/`update`). Комментарии к задачам и MR идут через notes API: `GITLAB_HOST=<host> glab api projects/<project-id>/issues/<iid>/notes -F body=@<path>` и `GITLAB_HOST=<host> glab api projects/<project-id>/merge_requests/<iid>/notes -F body=@<path>`, потому что `glab issue note` и `glab mr note` принимают только inline `--message` и не читают файл.

  Для задачи или спецификации путь — это уже написанный файл черновика (см. [issue-tracker.md](issue-tracker.md)). Для тела PR/MR или комментария (включая отчёт о завершении `task-report::required`, опубликованный комментарием к задаче) используйте только репозиторные черновики: `.harness/.sandboxes/pr_body/pr-body-<issue>-<slug>.md` для тела PR/MR или `.harness/.sandboxes/pr_body/issue-comment-<issue>-<slug>.md` / `pr-comment-<issue>-<slug>.md` для комментария. Hook `block-scratch-outside-docs-tasks.sh` проверяет basename и разрешает только имя с `pr-body`, `pr-comment` или `issue-comment`; любое другое имя в том же каталоге он отклоняет. Выполняйте одну команду публикации за вызов shell. Никогда не используйте `docs/tasks/`; удаляйте файл только после успешной команды, а при ошибке оставляйте его для повторной попытки.
* **Метаданные только о проекте.** Сообщения коммитов и заголовки/тела PR/MR содержат только изменение проекта. Атрибуция автоматизированного агента, имена моделей, URL сессий и трейлеры `Co-Authored-By` запрещены; локальный hook (`block-public-attribution.sh`) их отклоняет. Harness не устанавливает CI-проверку в целевой проект, поэтому проект, которому нужна серверная проверка, добавляет её сам. Заголовки и тела задач и каждый комментарий к задаче, PR или MR — это текст трекера: имена runtime и пути вроде `.claude/` или `CLAUDE.md` там обычная лексика проекта, поэтому локальный hook отклоняет в нём только атрибуцию — трейлер `Co-Authored-By`, утверждение «generated/written by <assistant>», пометку AI-generated или URL сессии ассистента.
* **Сначала задача.** Разработка не начинается без зарегистрированной задачи. Все задачи реализации ОБЯЗАНЫ быть созданы заранее через `gh issue create` (на GitLab — `glab issue create -R <project-url>`). Для локального markdown-трекера это условие выполняет создание файла задачи в `.scratch/<feature-slug>/issues/` — см. [issue-tracker.md](issue-tracker.md). `/implement` запускает pipeline architect → developer → code-review → qa → publish с гейтами и заканчивается после публикации принятого candidate, а затем предлагает отдельную ручную команду `/to-pull-requests <ticket>` для завершения PR и задачи; `/fast-implement` заканчивается так же после собственных commit и push.
* **Zero Auto-Merge (никакого автоматического merge).** Агент никогда не делает merge pull request сам (`gh pr merge`/`glab mr merge` или аналог). Merge в `integration/*` или `base_branch` — исключительно ручное действие разработчика после его подтверждения на шаге «Human QA и Merge» ниже. Правило безусловно и не зависит от режима выполнения задачи `hitl`/`afk` (см. `docs/agents/triage-labels.md`): `afk` означает, что агент может реализовать работу без присмотра, но не что он может выпустить её без присмотра.
* **Подтверждение перед PR.** Агент не запускает `gh pr create`/`glab mr create`, не получив явного согласия разработчика, что ветка готова стать PR. Эта точка проверки отдельная и более ранняя, чем «Human QA и Merge» ниже (он покрывает ревью *после* создания PR): завершённые реализация, тесты и code-review сами по себе согласия на открытие PR не означают. Как и Zero Auto-Merge, этот гейт не ослабляется для задач с меткой `afk`.

### 2. Последовательность работы { #2-workflow-sequence }

Эпик выбирает одну integration-ветку с именем `integration/<service-or-team>`. `/to-spec` создаёт её от `origin/<base_branch>` после публикации эпика, если её нет, записывает её в эпик и не переключает текущее worktree. `/to-tickets` копирует точное значение в каждую дочернюю задачу. Integration-ветка — цель PR для дочерней работы; `base_branch` — цель релиза в отдельном PR.

1. **Инициализация (ветвление).**
   Для каждой задачи создаётся изолированная ветка от точной integration-ветки эпика — не от той ветки, которая случайно уже выбрана. Если у задачи нет эпика, используйте `base_branch`.
   * **Формат:** должен соответствовать `branch_pattern` из `.harness/project.json` (по умолчанию `feature/issue-<ID>-<short-slug>`, где `<ID>` — номер задачи в трекере, а `<short-slug>` — короткое описание задачи, транслитерированное, слова через дефис или подчёркивание).
   * **Команда:** `git fetch origin <integration-branch> && git switch -c feature/issue-<ID>-<slug> --track origin/<integration-branch>`. Для задачи без эпика замените `<integration-branch>` на обязательный `base_branch` из `.harness/project.json`. Coordinator создаёт ветку через `git worktree add --no-track` (см. [worktrees.md](worktrees.md#coordinator-issue-worktree)); `git push -u` на шаге 2 затем задаёт upstream.
2. **Push после создания ветки.**
   * Сразу после создания ветки отправьте её в удалённый репозиторий (`origin`), чтобы она там существовала: `git push -u origin feature/issue-<ID>-<slug>`.
3. **Реализация и контроль качества (TDD).**
   * Пишите код сначала с тестов (TDD) и запускайте локальные тесты перед каждым коммитом.
4. **Коммиты.**
   * Коммиты делаются только в текущую ветку задачи. Перед первой правкой и перед каждым коммитом проверяйте, что текущая ветка соответствует `branch_pattern` и не является `base_branch` или `integration/*`.
   * Сообщения коммитов следуют стандарту **Semantic Commit Messages** (например, `feat: ...`, `fix: ...`, `refactor: ...`).
5. **Непрерывный push.**
   * Отправляйте коммиты в удалённый репозиторий (`origin`) и во время реализации, и после исправления замечаний code-review: `git push origin feature/issue-<ID>-<slug>`. Не оставляйте готовые коммиты только в локальном репозитории.
6. **Интеграция (Pull Request).** *(Локальный markdown-трекер: пропустите этот шаг и шаг 7 — см. «Сначала задача» выше; `/to-pull-requests` переводит `**Workflow:**` задачи в `done` после подтверждения merge разработчиком.)*
   * **Подтвердите перед открытием.** До создания PR явно спросите разработчика, готова ли ветка стать pull request. Не запускайте `gh pr create`/`glab mr create` только потому, что реализация, тесты и code-review завершены, — дождитесь явного согласия. Молчание или сам факт, что задача в остальном завершена, согласием не считаются.
   * После подтверждения запустите скилл `qa-gate` (как ссылаться на задачи, см. соглашения «When a skill says…» в [issue-tracker.md](issue-tracker.md)) и продолжайте, только если он прошёл.
   * Если шаблон тела PR в [§3](#3-pr-body-template) сложнее короткой сводки, следуйте ему напрямую. Разработчик может вместо этого настроить и запустить `pr-composer` вручную в приложении для кодинга: передайте ему `.harness/.sandboxes/pr_body/pr-body-<issue>-<slug>.md`, этот же путь укажите в `--body-file` (`--description-file` на GitLab) ниже и удалите файл только после успешного создания PR/MR.
   * PR/MR создаётся через CLI из checkout ветки задачи с явной целевой веткой — без неё оба CLI берут default-ветку. `<target-branch>` — integration-ветка эпика или `base_branch` для задачи без эпика:
     * **GitHub:** `gh pr create --base <target-branch> --title '<title>' --body-file <path>`.
     * **GitLab:** `glab mr create -R <project-url> --target-branch <target-branch> --title '<title>' --description-file <path> --yes`.

     Держите `<title>` в одинарных кавычках и записывайте каждый апостроф в нём как `'\''` в POSIX shell или как `''` в PowerShell. Тело берётся из файла — см. §1 («Тело — из файла, а не в команде»); inline `--body` или `--description` не используйте. GitLab печатает URL MR `.../-/merge_requests/<iid>`: называйте MR как `!<iid>`, а задачу как `#<iid>`, потому что GitLab нумерует их отдельно. На GitHub оба — `#<n>`.
   * **Футер задачи.** Дочерний PR нацелен на integration-ветку эпика. Перед написанием тела определите default-ветку репозитория через CLI трекера: GitHub — `gh repo view --json defaultBranchRef --jq .defaultBranchRef.name`; GitLab — поле `default_branch` в `GITLAB_HOST=<host> glab api projects/<project-id>`. `Closes #<ID>` используйте только если целью PR/MR является эта default-ветка; иначе пишите `Related to #<ID>`. GitHub игнорирует закрывающие ключевые слова для любой другой целевой ветки. GitLab закрывает задачу по закрывающему шаблону (шаблон по умолчанию принимает `Closes #<ID>`), только если MR или коммит попадает в default-ветку проекта: MR в `integration/*` или в любую другую ветку ничего не закрывает, а `Related to #<ID>` закрывающим шаблоном не является. Проект может отключить это автозакрытие настройкой «Auto-close referenced issues on default branch», а сам шаблон меняет только администратор self-managed инстанса, поэтому после merge в default-ветку состояние задачи всегда проверяется (шаг 7). PR integration → `base_branch` — отдельное релизное действие, оно не заменяет дочерние PR.
   * **Обязательное требование.** Тело pull request ОБЯЗАНО следовать шаблону из [§3 «Шаблон тела PR»](#3-pr-body-template) ниже.
7. **Human QA и Merge.**
   * Когда PR/MR открыт, верните ссылку на него (на GitLab — также как `!<iid>`) и явно спросите разработчика, хочет ли он сам проверить изменение, прежде чем оно будет считаться готовым. Молчание не считайте одобрением.
   * **Если разработчик подтверждает:** сообщите, что PR готов, и остановитесь. Merge не делайте — он всегда остаётся ручным действием разработчика.
   * **Если разработчик просит изменений или пояснений:** устраните их новыми коммитами в той же ветке (повторите шаги 3–5: реализация, коммит, push), затем спросите снова. Повторяйте, пока разработчик не подтвердит.
   * **Закройте задачу после merge.** Единственный триггер — подтверждение разработчика, что PR/MR слит. Эти шаги выполняет разработчик, когда работает один; агент может выполнить их только после того, как разработчик подтвердил merge в активной сессии. Сначала проверьте merge — GitHub: `gh pr view <n> --json state,baseRefName` (`state` равен `MERGED`, `baseRefName` — ожидаемая цель); GitLab: `glab mr view <iid> -R <project-url> -F json` (`state` равен `merged`, `target_branch` — ожидаемая цель). Если слияния в эту цель не было, оставьте задачу открытой и сообщите разработчику. Затем:
     * **`Related to #<ID>`:** закройте задачу явно — GitHub: `gh issue close <ID> --reason completed`; GitLab: `glab issue close <ID> -R <project-url>`. `glab issue close` не принимает комментарий, поэтому опубликуйте закрывающий комментарий заранее через notes API (§1).
     * **`Closes #<ID>`:** проверьте, что трекер закрыл задачу — GitHub: `gh issue view <ID> --json state` (`state` равен `CLOSED`); GitLab: `glab issue view <ID> -R <project-url> -F json` (`state` равен `closed`). GitLab закрывает её асинхронно после merge, поэтому если там всё ещё `opened`, прочитайте состояние ещё раз; если задача по-прежнему открыта, закройте её явной командой выше и объясните разработчику, почему трекер этого не сделал.

     Не закрывайте задачу, когда её PR/MR только открылся или закрылся без merge.

### 3. Шаблон тела PR { #3-pr-body-template }

Каждое тело PR (или MR) ОБЯЗАНО начинаться с приведённого ниже HTML-комментария дословно. Комментарий одинаков для любого языка проекта. Трекер его не отображает; это чек-лист для автора и навигатор для ревьюера. После комментария напишите семь разделов для фактического изменения; пункты комментария по порядку соответствуют заголовкам разделов. Передавайте тело через `--body-file` (`--description-file` на GitLab), как требует §1.

```html
<!--
This commented block in the Pull Request body serves as a checklist for the author and a navigator for the reviewer. Each item should give a clear picture of the change's context.

1. Summary
A short summary of the end goal this pull request achieves. Reading only this point, the reviewer should understand the gist of the PR without diving into the code.

2. Affected parts of the project
The modules, architectural layers, services, or databases that were changed.

3. Business logic
Which business rules were added, changed, or removed. How the system should now behave from a business perspective.

4. What changed
A technical description of the implementation — patterns used, classes/interfaces added, signature changes.

5. Verification
How the functionality was tested (unit, integration, e2e, manual) — use the `qa-gate` result if one ran this session.

6. Not verified & risks
Edge cases not covered by tests, potential performance issues, remaining workarounds.

7. Integration
What needs to happen when deploying to other environments — DB migrations, new env vars, dependencies on other PRs.
-->
```

Язык заголовков разделов берите из поля `language` в `.harness/project.json` (по умолчанию `ru`). Заголовки — это выходной текст на языке проекта. Не переводите их.

**`language: ru`**:

```markdown
## Итог

## Затронутые части проекта

## Бизнес-логика

## Что изменено

## Проверка

## Не проверено и риски

## Интеграция

<!-- Выбрать ровно один footer: `Closes #<ID>` для PR в default branch; `Related to #<ID>` для любого другого target. -->
Related to #<ID>
```

**`language: en`**:

```markdown
## Summary

## Affected parts of the project

## Business logic

## What changed

## Verification

## Not verified & risks

## Integration

<!-- Choose exactly one footer: `Closes #<ID>` for a PR targeting the default branch; `Related to #<ID>` for every other target. -->
Related to #<ID>
```
