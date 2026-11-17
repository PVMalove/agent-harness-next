# To Guide: в руководство

## 1. Название и локализация

- **Английское название:** `To Guide`
- **Русский перевод:**

```text
В руководство
```

## 2. Полный перевод текста скилла

<div class="ah-skill-text" markdown="1">

```yaml
name: to-guide
description: Превращает тикет hitl или спецификацию в пошаговое руководство по ручной реализации с готовыми к вставке промптами для ИИ-IDE (Cursor, Copilot Chat). Для тикетов, код которых пишет человек, а не агент.
disable-model-invocation: true
```

### В руководство (подготовка ручной реализации)

Скилл превращает спецификацию или tracer-bullet тикет в руководство для разработчика с готовыми промптами для IDE с ИИ-помощником. Это маршрут `hitl` в пару к `/implement` и `/fast-implement`: те берут тикеты `afk`, и код пишет агент, а `/to-guide` берёт тикеты `hitl` и отдаёт человеку чек-лист навигатора. После этого скилла код, code review, `qa-gate` и PR целиком делает человек. Скилл их не выполняет и по этому тикету больше не вызывается. Точные команды названы в последнем разделе руководства.

#### Процесс

1. **Прочитайте источник.** Получите тикет, который назвал пользователь: номер issue, URL или путь `.scratch/<feature>/issues/NN-*.md` (см. `docs/agents/issue-tracker.md`). Если у тикета `status::blocked`, проверьте блокеры так же, как `/implement`. Если хотя бы один ещё открыт, остановитесь и назовите пользователю эти блокеры: руководство для тикета, который пока нельзя начать, не пишется. Если у тикета `status::specs` вместо `status::ready` или нет метки `hitl`, сообщите об этом пользователю и спросите, продолжать ли. Скилл ждёт полностью описанный тикет, назначенный человеку (см. `docs/agents/triage-labels.md`).
2. **Изучите кодовую базу.** Найдите точные файлы, которые нужно создать или изменить для тикета. Не угадывайте их только по тексту тикета. Используйте глоссарий домена проекта и соблюдайте ADR затронутой области.
3. **Заберите тикет.** До любой другой записи назначьте тикет мейнтейнеру: `gh issue edit <n> --add-assignee @me` в GitHub, `glab issue update <n> -R <project-url> --assignee @me` в GitLab или аналог в локальном трекере. Так же делают `/wayfinder` и `/fast-implement`, чтобы параллельная сессия не взяла тот же тикет `hitl`. В GitLab каждая команда `glab` получает `-R <project-url>`, а каждый вызов `glab api` пишется как `GITLAB_HOST=<host> glab api projects/<project-id>/...`. Эти плейсхолдеры заданы в `docs/agents/issue-tracker.md` → GitLab → Conventions.
4. **Переведите тикет в работу.** У тикета ровно одна метка `status::*` (см. `docs/agents/triage-labels.md`). Поэтому замените текущую метку, а не добавляйте вторую. Текущая метка: `status::ready`, `status::blocked`, если шаг 1 нашёл все блокеры закрытыми, или `status::specs`, если пользователь согласился продолжить.
   - **GitHub:** `gh issue edit <n> --remove-label status::ready --remove-label status::blocked --remove-label status::specs --add-label status::in-progress`, затем проверьте через `gh issue view <n> --json labels --jq '[.labels[].name]'`, что `status::in-progress` осталась единственной меткой `status::*`.
   - **GitLab:** `glab issue update <n> -R <project-url> --unlabel status::ready,status::blocked,status::specs --label status::in-progress`, затем проверьте через `glab issue view <n> -R <project-url> -F json`, что `status::in-progress` осталась единственной меткой `status::*` в `labels`.
   - **Локальный трекер:** запишите в строку `**Workflow:**` файла `status::in-progress`.
   - Если записать метку не удалось, остановитесь и сообщите об этом.
5. **Напишите руководство** по `<guide-template>` ниже. В его разделе 5 оставьте только команды трекера этого проекта и подставьте реальные значения `<project-url>`, `<host>`, `<project-id>`, `<target-branch>`, `<ID>`, `<title>` и `<slug>`. `<title>` остаётся в одинарных кавычках, каждый апостроф записывается как `'\''`, а если у человека shell PowerShell, то как `''`. Человек копирует эти команды без правки. Плейсхолдером остаётся только номер PR/MR `<n>`/`<iid>`, пока PR/MR не создан. Пишите руководство на языке из поля `language` в `.harness/project.json` (если файла или поля нет, то `ru`). В сводной таблице `/to-tickets` это правило действует узко, а здесь на этом языке пишется весь документ, включая промпты: руководство читает человек локально, во внешний трекер оно не публикуется. Сохраните его в `docs/tasks/` по правилу имён из `docs/agents/artifacts.md` (ID тикета и описательный slug). Если тикет входит в эпик, положите руководство в каталог эпика `docs/tasks/issue-<epic-id>-<epic-slug>/` рядом с файлом самого тикета.

#### Правила для промптов

- Каждый промпт явный, самодостаточный и говорит ИИ-IDE человека *точно*, что делать. Человек скопирует его дословно, без правки.
- Отсылайте IDE к существующему коду как к образцу: «следуй шаблону в `<file>`» лучше описания шаблона.
- Каждый шаг должен быть достаточно мал, чтобы его можно было отдельно скомпилировать и проверить. Нужны узкие проверяемые части, как вертикальные срезы в `/to-tickets`.
- В каждом промпте сначала просите тест. Репозиторий требует TDD (`docs/agents/git-workflow.md`), кто бы ни писал код, и каждый маршрут говорит об этом явно (`/fast-implement` через `/tdd`, `/implement` через Definition of Done своего batch). Поэтому напишите это прямо и не надейтесь на настройки ИИ-IDE человека по умолчанию.

&lt;guide-template&gt;

### Руководство по реализации: <название/ID тикета>

#### 1. Контекст и ограничения

Архитектурные правила (ADR), шаблоны и границы для этой задачи: кратко по тикету или спецификации и по кодовой базе, без полного пересказа.

#### 2. Карта файлов

- `[Создать]` path/to/new/file
- `[Обновить]` path/to/existing/file

#### 3. Шаги и промпты

Разбейте реализацию на небольшие компилируемые части. Для каждой:

**Шаг N: <цель>**

```text
<полный промпт для ИИ-IDE человека, готовый к вставке: ссылается на конкретные существующие файлы как на образец и называет критерий приёмки, который выполняет>
```

#### 4. Проверка

Как проверить, что срез работает: точная команда теста, шаг с `curl` или ручной шаг из критериев приёмки тикета или раздела Testing Decisions спецификации.

#### 5. Когда вы закончите

Скилл не проверяет код, не коммитит, не запускает `qa-gate` и не открывает PR за вас: на маршруте `hitl` нет одной команды для всего этого. Когда код написан, сделайте по порядку:

1. Запустите `/code-review` или попросите эту сессию его запустить. Это тот же review по двум осям Standards и Spec, который `/implement` выполнил бы для тикета `afk`. На этом маршруте его больше ничто не запускает. Если его пропустить, diff попадёт в PR без проверки.
2. Закоммитьте работу с Semantic Commit Message (`feat:`, `fix:`, ...) и запушьте её по правилам `docs/agents/git-workflow.md`. Не оставляйте готовую работу без коммита или пуша.
3. Запустите `/qa-gate` или попросите эту сессию его запустить.
4. **Тикет в GitHub или GitLab:** откройте PR/MR в `<target-branch>` по `docs/agents/git-workflow.md`. Тело PR запишите в `.harness/.sandboxes/pr_body/pr-body-<ID>-<slug>.md` прямо по шаблону тела или вручную настройте и запустите `pr-composer` в coding application.
   - **Footer:** `Closes #<ID>` пишите, только если `<target-branch>` это ветка по умолчанию (GitHub: `gh repo view --json defaultBranchRef --jq .defaultBranchRef.name`; GitLab: поле `default_branch` из `GITLAB_HOST=<host> glab api projects/<project-id>`). Иначе пишите `Related to #<ID>`. GitLab закрывает issue по `Closes #<ID>`, только когда MR попадает в ветку по умолчанию.
   - **Откройте PR/MR.** GitHub: `gh pr create --base <target-branch> --title '<title>' --body-file .harness/.sandboxes/pr_body/pr-body-<ID>-<slug>.md`. GitLab: `glab mr create -R <project-url> --target-branch <target-branch> --title '<title>' --description-file .harness/.sandboxes/pr_body/pr-body-<ID>-<slug>.md --yes`. Номер MR `!<iid>` стоит последним сегментом в URL, который печатает команда.
   - **Completion report:** если у тикета есть `task-report::required`, опубликуйте completion report, когда открываете PR/MR. Запишите его в `.harness/.sandboxes/pr_body/issue-comment-<ID>-<slug>.md`, затем GitHub: `gh issue comment <ID> --body-file .harness/.sandboxes/pr_body/issue-comment-<ID>-<slug>.md`; GitLab: `GITLAB_HOST=<host> glab api projects/<project-id>/issues/<ID>/notes -F body=@.harness/.sandboxes/pr_body/issue-comment-<ID>-<slug>.md`.
   - **После вашего мержа:** проверьте мерж. GitHub: `gh pr view <n> --json state,baseRefName`, `state` равен `MERGED`, `baseRefName` равен `<target-branch>`. GitLab: `glab mr view <iid> -R <project-url> -F json`, `state` равен `merged`, `target_branch` равен `<target-branch>`. Для `Related to #<ID>` закройте issue: GitHub `gh issue close <ID> --reason completed`, GitLab `glab issue close <ID> -R <project-url>`. Для `Closes #<ID>` проверьте, что issue закрыт: GitHub `gh issue view <ID> --json state` (`CLOSED`), GitLab `glab issue view <ID> -R <project-url> -F json` (`state` равен `closed`). GitLab закрывает issue асинхронно, поэтому, если там ещё `opened`, прочитайте состояние ещё раз. Если issue не закрылся, закройте его той же командой.

   **Тикет в локальном Markdown-трекере:** шага PR и мержа нет. Когда всё выше прошло, сами запишите в строку `**Workflow:**` файла тикета `done`. Если у тикета есть `**Task report:** required`, добавьте completion summary в то же обновление.

&lt;/guide-template&gt;

</div>

## 3. Контракты

- **Вход (Input/Brief):** тикет `hitl` или спецификация, критерии приёмки, состояние блокировок и соглашения репозитория.
- **Выход (Output/Report):** локальное пошаговое руководство в `docs/tasks/` с картой файлов, TDD-промптами, проверками и ручным маршрутом до PR.

## Источник

[SKILL.md](https://github.com/PVMalove/agent-harness-next/blob/master/skills/first-party/engineering/to-guide/SKILL.md)
