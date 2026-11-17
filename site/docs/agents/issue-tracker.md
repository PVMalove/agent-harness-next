# Трекер задач { #issue-tracker }

Поток доставки описан в [git-workflow.md](git-workflow.md). Это руководство определяет операции, специфичные для трекера.

Нужный раздел ниже определяется по трекеру проекта так же, как это делает `check-branch-name.sh`: по полю `tracker` в `.harness/project.json`, если оно задано; иначе по `git remote -v`. Remote на `github.com` означает GitHub, remote на хосте `gitlab.` означает GitLab, всё остальное (в том числе отсутствие remote) означает Local markdown. Для совсем другого трекера (Jira, Linear, ...) замените содержимое этого файла описанием его процесса (см. `/setup-matt-pocock-skills`).

Словарь меток триажа в этом репозитории представляет собой собственную таксономию с пространствами имён: категория `type::*`, режим выполнения `hitl`/`afk`, состояние pipeline `status::*`, необязательный контекст `priority::*`/`severity::*` и контекстные метки `task-report::required`/`resolution::wontfix`. Перед тем как ставить метки или искать по ним, прочитайте [triage-labels.md](triage-labels.md); это относится к любому разделу ниже.

## GitHub

Задачи и спецификации этого репозитория живут как GitHub issues. Для всех операций используйте CLI `gh`.

### Соглашения { #conventions }

- **Создать задачу:** `gh issue create --title "..." --body-file <path>`. Сначала запишите тело в файл: inline heredoc-ы `--body` ломаются на вложенных кавычках и обратных апострофах (см. `/to-spec`, `/to-tickets`).
- **Прочитать задачу:** `gh issue view <number> --comments`; комментарии фильтруйте через `jq` и получайте метки.
- **Список задач:** `gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'` с подходящими фильтрами `--label` и `--state`.
- **Прокомментировать задачу:** `gh issue comment <number> --body-file <path>`; путь берите по [git-workflow.md](git-workflow.md) §1 (`.harness/.sandboxes/pr_body/issue-comment-<issue>-<slug>.md`).
- **Поставить или снять метки:** `gh issue edit <number> --add-label "..."` / `--remove-label "..."`.
- **Заменить метку статуса:** `gh issue edit <number> --repo <host>/<owner>/<name> --remove-label <every previous status::*> --add-label <status::new>` одним вызовом, чтобы у задачи осталась ровно одна метка `status::*`. Так `harness ticket-status` записывает перемещения доски задач.
- **Закрыть:** сначала опубликуйте пояснение через `gh issue comment <number> --body-file <path>`, затем выполните `gh issue close <number>`; inline `--comment "..."` не используйте.

Репозиторий определяется по `git remote -v`: `gh` делает это сам, если запущен внутри клона.

### Pull request как поверхность триажа { #pull-requests-as-a-triage-surface }

**PR как поверхность запросов: нет.** _(Поставьте `yes`, если репозиторий считает внешние PR запросами функций; флаг читает `/triage`.)_

При значении `yes` PR проходят через те же метки и состояния, что и задачи, с эквивалентами `gh pr`:

- **Прочитать PR:** `gh pr view <number> --comments`, а diff: `gh pr diff <number>`.
- **Список внешних PR для триажа:** `gh pr list --state open --json number,title,body,labels,author,authorAssociation,comments`, затем оставьте только `authorAssociation` со значениями `CONTRIBUTOR`, `FIRST_TIME_CONTRIBUTOR` или `NONE` (отбросьте `OWNER`/`MEMBER`/`COLLABORATOR`).
- **Комментировать, метить, закрывать:** `gh pr comment <number> --body-file <path>`, `gh pr edit --add-label`/`--remove-label`, `gh pr close`.

На GitHub задачи и PR делят одно пространство номеров, поэтому голое `#42` может быть и тем, и другим: проверьте `gh pr view 42` и при ошибке `gh issue view 42`.

### Когда скилл говорит «опубликовать в трекере задач» { #when-a-skill-says-publish-to-the-issue-tracker }

Создайте GitHub issue.

### Когда скилл говорит «получить нужную задачу» { #when-a-skill-says-fetch-the-relevant-ticket }

Выполните `gh issue view <number> --comments`.

## GitLab

Задачи и спецификации этого репозитория живут как GitLab issues. Для всех операций используйте CLI [`glab`](https://gitlab.com/gitlab-org/cli).

### Соглашения { #conventions_1 }

- **Адресация проекта.** Называйте проект явно в каждой команде, а не доверяйте выбор `glab`. Сам по себе `glab` выбирает remote в порядке `upstream` > `gitlab` > `origin`, а `glab api` подставляет проект из репозитория текущего каталога и по умолчанию использует `--hostname` `gitlab.com` или хост этого репозитория. Это руководство и скиллы записывают проект тремя плейсхолдерами:
  - `<host>`: `tracker.host` из `.harness/project.json`, включая web-порт, отличный от 443 (`gitlab.example.com`, `gitlab.example.test:4443`);
  - `<project-url>`: `https://<host>/<tracker.project>` (`https://gitlab.example.com/group/project`); каждая команда `glab` принимает `-R <project-url>`;
  - `<project-id>`: `tracker.project` в URL-кодировке (`group%2Fproject`, `group%2Fsub%2Fproject`); каждый вызов `glab api` пишется как `GITLAB_HOST=<host> glab api projects/<project-id>/...`. `GITLAB_HOST` сохраняет порт и приоритетнее репозитория текущего каталога, тогда как `glab api --hostname` отклоняет хост с портом (`invalid hostname`), а хост без порта отправляет на порт 443. В PowerShell перед вызовом выполните `$env:GITLAB_HOST = '<host>'`, а после него `Remove-Item Env:GITLAB_HOST`.

  Если поля `tracker` нет, используйте хост и проект, которые `harness health` определяет по `origin`; его предупреждение `tracker.project` печатает готовый фрагмент `tracker` для вставки.
- **Создать задачу:** `glab issue create -R <project-url> --title "..." --description-file <path>`, где `<path>` ведёт к уже написанному файлу черновика (по [git-workflow.md](git-workflow.md) §1, «Тело из файла, а не в команде»); inline `--description "..."` и heredoc не используйте.
- **Прочитать задачу:** `glab issue view <number> -R <project-url> --comments`. Для машиночитаемого вывода добавьте `-F json`.
- **Список задач:** `glab issue list -R <project-url> --output json` с подходящими фильтрами `--label`. В `glab issue list` флаг `-F` означает `--output-format` (`details`/`ids`/`urls`), а не JSON.
- **Прокомментировать задачу:** `GITLAB_HOST=<host> glab api projects/<project-id>/issues/<number>/notes -F body=@<path>`; путь берите по [git-workflow.md](git-workflow.md) §1 (`.harness/.sandboxes/pr_body/issue-comment-<issue>-<slug>.md`). GitLab называет комментарии «notes». Подкоманда `note` в `glab issue` принимает только inline `--message` и не читает файл, поэтому тело комментария через неё не публикуется.
- **Поставить или снять метки:** `glab issue update <number> -R <project-url> --label "..."` / `--unlabel "..."`. Несколько меток можно перечислить через запятую или повторением флага. В отличие от `gh`, `--label` с именем метки, которой нет в проекте, не падает: GitLab создаёт её с цветом по умолчанию, поэтому перед первой записью с метками запустите `/setup-labels`.
- **Заменить метку статуса:** `glab issue update <number> -R <project-url> --label <status::new> --unlabel <every previous status::*>`. `--unlabel` нужен явно, потому что scoped-метка заменяет своё пространство имён только в GitLab Premium. Так `harness ticket-status` записывает перемещения доски задач.
- **Закрыть:** `glab issue close <number> -R <project-url>`. `glab issue close` не принимает закрывающий комментарий, поэтому сначала опубликуйте пояснение комментарием (см. выше), затем закрывайте.
- **Merge request.** GitLab называет PR «merge requests». Используйте `glab mr create -R <project-url> --target-branch <target-branch> --title '<title>' --description-file <path> --yes` (правила целевой ветки и заголовка описаны в [git-workflow.md](git-workflow.md) §2), `glab mr update`, `glab mr view` и так далее. Форма та же, что у `gh pr ...`, но с `mr` вместо `pr`, `--target-branch` вместо `--base`, `--description-file` вместо `--body-file` и `-R <project-url>` в каждой команде. Комментарий к MR идёт через `GITLAB_HOST=<host> glab api projects/<project-id>/merge_requests/<number>/notes -F body=@<path>` (`pr-comment-<issue>-<slug>.md`), а не через `glab mr note --message`.

### Настройка `glab` { #glab-setup }

- **Минимальная версия: `glab` 1.117.0.** Если трекер проекта GitLab, `harness health` завершает локальную проверку `environment.glab` с ошибкой для более старого `glab --version`; обновите его по [руководству по установке](https://gitlab.com/gitlab-org/cli#installation).
- **Хост с портом.** Хост трекера задан в `tracker.host` в `.harness/project.json`, включая web-порт, если он не 443, например `gitlab.example.test:4443`. Входите именно на этот хост: `glab auth login --hostname gitlab.example.test:4443`, проверяйте командой `glab auth status --hostname gitlab.example.test:4443`. Ту же проверку запускает `harness health --online`. Проект указывайте явно: `glab <command> -R https://gitlab.example.test:4443/group/sub/project` и `GITLAB_HOST=gitlab.example.test:4443 glab api projects/group%2Fsub%2Fproject` с URL-кодированным путём проекта.
- **Личный CA и прокси.** Храните их в собственной конфигурации и окружении `glab`, но не в `.harness/project.json` и не в репозитории: для внутреннего CA `glab config set ca_cert /path/to/ca.pem --host gitlab.example.test:4443`, для прокси стандартные переменные окружения `HTTPS_PROXY`/`NO_PROXY`. Токены остаются в хранилище, которое использует `glab auth login`.

### Merge request как поверхность триажа { #merge-requests-as-a-triage-surface }

**MR как поверхность запросов: нет.** _(Поставьте `yes`, если репозиторий считает внешние merge request запросами функций; флаг читает `/triage`.)_

При значении `yes` MR проходят через те же метки и состояния, что и задачи, с эквивалентами `glab mr`:

- **Прочитать MR:** `glab mr view <number> -R <project-url> --comments`, а diff: `glab mr diff <number> -R <project-url>`.
- **Список внешних MR для триажа:** `glab mr list -R <project-url> -F json`, затем оставьте только MR, чей автор не участник и не владелец проекта (MR контрибьютора, а не текущая работа мейнтейнера).
- **Комментировать, метить, закрывать:** `GITLAB_HOST=<host> glab api projects/<project-id>/merge_requests/<number>/notes -F body=@<path>`, `glab mr update <number> -R <project-url> --label`/`--unlabel`, `glab mr close <number> -R <project-url>`.

В отличие от GitHub, GitLab нумерует задачи и MR отдельно, поэтому `#42` однозначно, как только известно, о какой поверхности говорит мейнтейнер.

### Когда скилл говорит «опубликовать в трекере задач» { #when-a-skill-says-publish-to-the-issue-tracker_1 }

Создайте GitLab issue.

### Когда скилл говорит «получить нужную задачу» { #when-a-skill-says-fetch-the-relevant-ticket_1 }

Выполните `glab issue view <number> -R <project-url> --comments`.

## Local markdown { #local-markdown }

Задачи и спецификации этого репозитория живут как markdown-файлы в `.scratch/`.

### Соглашения { #conventions_2 }

- Каждая функция получает свой каталог: `.scratch/<feature-slug>/`.
- Спецификация: `.scratch/<feature-slug>/spec.md`.
- Задачи реализации: по файлу на задачу в `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, нумерация с `01`; единый файл со всеми задачами недопустим.
- Состояние триажа записывается строкой `Workflow:` в начале каждого файла задачи со словарём `status::*` (точные строки см. в [triage-labels.md](triage-labels.md)).
- `harness ticket-status` перемещает локальную задачу: переписывает на месте её первую строку `**Workflow:**` (или добавляет её после заголовка `# `). Команда пишет только внутри `.scratch/` и никогда через symlink.
- Комментарии и история обсуждения дописываются в конец файла под заголовком `## Comments`.

### Когда скилл говорит «опубликовать в трекере задач» { #when-a-skill-says-publish-to-the-issue-tracker_2 }

Создайте новый файл в `.scratch/<feature-slug>/` (при необходимости создайте каталог).

### Когда скилл говорит «получить нужную задачу» { #when-a-skill-says-fetch-the-relevant-ticket_2 }

Прочитайте файл по указанному пути. Обычно пользователь передаёт путь или номер задачи напрямую.

## Операции wayfinding { #wayfinding-operations }

Используются `/wayfinder`. **Карта** хранит тело Notes / Decisions-so-far / Fog; **дочерние** задачи подвешены к ней. Механика зависит от раздела трекера выше:

**GitHub:**

- **Карта:** одна задача с меткой `wayfinder:map`, в теле которой Notes / Decisions-so-far / Fog. `gh issue create --label wayfinder:map`.
- **Дочерняя задача:** задача, связанная с картой как GitHub sub-issue (`gh api` на endpoint sub-issues), тем же механизмом, которым `/to-tickets` связывает задачи с эпиком (см. [triage-labels.md](triage-labels.md)). Если sub-issues недоступны, добавьте дочернюю задачу в список задач в теле карты и поставьте `Part of #<map>` в начало тела дочерней. Метки: `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`). Это пространство имён отдельно от меток триажа этого репозитория, не смешивайте их. Если карта представляет более крупный эпик, к которому относятся и другие, не-Wayfinder задачи, свяжите их как sub-issues задачи эпика так же, как это делает `/to-tickets`, а не меткой `wayfinder:*`. После взятия в работу задача назначается ведущему разработчику.
- **Блокировка:** каноническое представление, видимое в UI, дают **нативные зависимости задач** GitHub. Добавьте связь командой `gh api --method POST repos/<owner>/<repo>/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>`, где `<blocker-db-id>` означает числовой **database id** блокирующей задачи (`gh api repos/<owner>/<repo>/issues/<n> --jq .id`, _не_ `#number` и не `node_id`). GitHub сообщает `issue_dependencies_summary.blocked_by` (только открытые блокеры, поэтому это живой гейт). Если зависимости недоступны, вернитесь к строке `Blocked by: #<n>, #<n>` в начале тела дочерней задачи. Задача разблокирована, когда закрыты все блокеры (блокер закрывается после подтверждённого merge, но не при push, публикации, принятом QA или открытом PR).
- **Запрос frontier:** перечислите открытые дочерние задачи родительской (`gh issue list --state open`, ограниченный её sub-issues или списком задач; родитель означает карту для `/wayfinder` и эпик для `/to-tickets`), отбросьте задачи с открытым блокером (`issue_dependencies_summary.blocked_by > 0` или открытая задача в строке `Blocked by`) либо с исполнителем; побеждает первая в порядке родителя. `/fast-implement`, получив ссылку на эпик вместо конкретной задачи, выполняет тот же запрос и оставляет только задачи `afk` + `pipeline::fast`, но никогда `hitl` (см. [triage-labels.md](triage-labels.md)): задачи `hitl` идут через `/to-guide`, а не через автоподбор. Задачу `pipeline::fast`+`afk`, названную явно, `/implement` по-прежнему принимает и без отказа проводит через полный цикл с гейтами: полный цикл всегда остаётся безопасным запасным вариантом, а метка сужает только автоподбор, но не названную задачу.
- **Взять в работу:** `gh issue edit <n> --add-assignee @me` первой записью сессии, до любой другой. Это не даёт двум параллельным сессиям (например, в разных worktree) выбрать одну и ту же frontier-задачу.
- **Завершить:** `gh issue comment <n> --body-file <path>` (путь по git-workflow.md §1), затем `gh issue close <n>`, затем допишите в Decisions-so-far карты указатель на контекст (суть и ссылка).

**GitLab:**

Всё ниже работает на GitLab Free. Эпики, связи задач `blocks`/`is_blocked_by` и быстрые действия блокировки относятся к функциям Premium и не используются. Иерархия хранится в описании дочерней задачи плюс одной связи `relates_to`. `<host>`, `<project-url>` и `<project-id>` взяты из плейсхолдеров [GitLab](#gitlab) → «Соглашения».

- **Карта:** одна задача с меткой `wayfinder:map`, в теле которой Notes / Decisions-so-far / Fog. `glab issue create -R <project-url> --label wayfinder:map`.
- **Дочерняя задача:** задача, описание которой открывается разделом `## Parent: #<parent>` (карта для `/wayfinder`, эпик для `/to-tickets`), плюс ровно одна связь `relates_to` от дочерней к родительской: `GITLAB_HOST=<host> glab api --method POST projects/<project-id>/issues/<child>/links -F target_project_id=<numeric-project-id> -F target_issue_iid=<parent> -F link_type=relates_to`. `<numeric-project-id>` берётся из поля `id` в `GITLAB_HOST=<host> glab api projects/<project-id>`; прочитайте его один раз и используйте для всех дочерних. Связь показывает дочернюю задачу на странице родительской, но не имеет направления, поэтому сторону родителя фиксирует строка `## Parent`. Метки: `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`). После взятия в работу задача назначается ведущему разработчику.
- **Блокировка:** раздел `## Blocked by` в описании дочерней задачи, по строке `Blocked by #<M>` на каждый блокер, либо `None — can start immediately`. Между задачей и её блокерами связь не создаётся. Задача разблокирована, когда закрыты все блокеры (блокер закрывается после подтверждённого merge, но не при push, публикации, принятом QA или открытом PR).
- **Запрос frontier:** перечислите связи родителя командой `GITLAB_HOST=<host> glab api --paginate projects/<project-id>/issues/<parent>/links`. Оставьте связанные задачи, у которых `project_id` равен `<numeric-project-id>` (связь может указывать на задачу другого проекта), `state` равен `opened`, нет исполнителя, а в описании есть `## Parent: #<parent>` (читайте через `glab issue view <iid> -R <project-url> -F json`). Так отбрасываются посторонние связи `relates_to`. Отбросьте любую задачу, у которой в строках `Blocked by` есть ещё открытый `#<M>` (`state` из `glab issue view <M> -R <project-url> -F json`); прежняя единая строка `Blocked by: #<n>, #<n>` читается так же. Побеждает наименьший iid, потому что `/to-tickets` публикует задачи в порядке зависимостей. `/fast-implement`, получив эпик, выполняет этот запрос и оставляет только задачи `afk` + `pipeline::fast`, но никогда `hitl` (см. [triage-labels.md](triage-labels.md)).
- **Взять в работу:** `glab issue update <n> -R <project-url> --assignee @me` первой записью сессии.
- **Завершить:** `GITLAB_HOST=<host> glab api projects/<project-id>/issues/<n>/notes -F body=@<path>` (путь по git-workflow.md §1), затем `glab issue close <n> -R <project-url>`, затем допишите в Decisions-so-far карты указатель на контекст (суть и ссылка).

**Local markdown:**

- **Карта:** `.scratch/<effort>/map.md`.
- **Дочерняя задача:** `.scratch/<effort>/issues/NN-<slug>.md`, нумерация с `01`, вопрос записан в теле. Строка `Type:` записывает тип задачи (`research`/`prototype`/`grilling`/`task`), строка `Status:` записывает `claimed`/`resolved`.
- **Блокировка:** строка `Blocked by: NN, NN` в начале файла. Задача разблокирована, когда каждый перечисленный в ней файл имеет статус `resolved` (выставляется после подтверждённого merge предшественника).
- **Frontier:** просмотрите `.scratch/<effort>/issues/` в поисках файлов, которые открыты, не заблокированы и не взяты; побеждает первый по номеру.
- **Взять в работу:** выставьте `Status: claimed` и сохраните до начала работы.
- **Завершить:** допишите ответ под заголовком `## Answer`, выставьте `Status: resolved`, затем допишите в `map.md` указатель на контекст (суть и ссылка) в Decisions-so-far карты.
