# block-public-attribution

## 1. Название и локализация

- **Английское название:** block-public-attribution
- **Русский перевод / Суть:**

```text
Блокировка AI-атрибуции в публичных Git-метаданных
```

## 2. Полное описание

Хук `PreToolUse(Bash)` проверяет публичный текст, который агент публикует: сообщения коммитов, title и body PR/MR, push и тексты трекера (issue, комментарии и notes в GitHub и GitLab).

Имена ассистентов и моделей (Claude, Codex, OpenAI, ChatGPT, GPT, Copilot, Gemini) разрешены как словарь проекта, в том числе в путях `.claude/` и `CLAUDE.md`. Трейлеры `Co-Authored-By` разработчиков тоже разрешены. Когда агент формирует коммит, он не добавляет себя в авторы или соавторы.

Для всех поверхностей действует одно правило. Хук запрещает:

- подписи известных ассистентов в `Co-Authored-By`;
- фразы "generated/written/created/authored/produced by/with/using/via <ассистент>";
- пометку `AI-generated`;
- ссылки на сессии ассистентов (`claude.ai/`, `chatgpt.com/`, `chat.openai.com/`).

Хук узнаёт известные подписи по имени ассистента, но не устанавливает личность автора. Обычные упоминания названий и трейлеры соавторов-разработчиков хук пропускает. `FORBIDDEN` и `TRACKER_ATTRIBUTION` используют один шаблон.

Как хук проверяет команду:
1. Python разбирает JSON и берёт команду из `tool_input.command`.
2. Хук вырезает тела heredoc: это stdin, а не слова команды. На месте оператора остаётся маркер. Тело хук проверяет, только если оператор стоит внутри проверяемого аргумента, например `-m "$(cat <<'EOF' ... EOF)"` или `--body "$(cat <<'EOF' ... EOF)"`.
3. По тексту команды без тел heredoc хук определяет операцию: `git commit`, `git push`, `gh pr` и `glab mr` `create`/`new`/`edit`/`update`, `gh`/`glab issue` `create`/`new`/`edit`/`update`, комментарии `gh issue|pr comment`, notes `glab issue|mr note`, `glab api`.
4. Аргументы найденной операции хук разбирает модулем `shlex` (Python). У `git commit` он проверяет `-m`/`--message`, `--trailer` и файл `-F`/`--file`. Для каждой команды публикации таблица флагов задаёт, какие короткие и длинные флаги несут текст именно в этом CLI:
   - `gh pr create|new|edit`, `gh issue create|new|edit|comment`, `gh pr comment`: `-t`/`--title`, `-b`/`--body` и файл `-F`/`--body-file`;
   - `glab mr create|new|edit|update`, `glab issue create|new|update`: `-t`/`--title`, `-d`/`--description` и файл `--description-file`;
   - `glab issue note`, `glab mr note`: `-m`/`--message`;
   - `glab api`: поля `-F`/`--field` и `-f`/`--raw-field` с ключом `body`, `description` или `title`; значение `-F key=@<path>` хук читает из файла.

   У gh флаг `-d` означает `--draft`, у glab `-b` означает `--target-branch`, а `-m` вне notes задаёт milestone. Такие флаги хук текстом не считает. Хук читает все формы: `-t X`, `-tX`, `-t=X`, кластер `-dt X`, `--title=X` и повторы флага.
5. Строковые значения и содержимое файлов хук сверяет с общим шаблоном атрибуции. Файл должен быть доступен по literal-пути. Если вместо пути стоит переменная shell, `-` или `@-` (stdin) или путь не существует, хук блокирует команду.
6. Для push и для создания или правки PR/MR хук ещё проверяет сообщения локальных, не отправленных коммитов, достижимых из `HEAD` (`git log --no-merges HEAD --not --remotes`).
7. Если хук нашёл запрещённый текст или не смог прочитать файл или значение, он прерывает команду кодом `2` и пишет причину в stderr.

## 3. Контракты

- **Вход (Input/Brief):** JSON вызова инструмента через `stdin`; хук читает `tool_input.command`. Если нужно, хук читает файлы сообщений по путям из аргументов команды и историю локальных коммитов.
- **Выход (Output/Report):** код `0`, если проверка прошла и команду можно выполнить. Если хук нашёл AI-атрибуцию, он пишет сообщение в `stderr` и завершается кодом `2`. Сообщение называет уровень: Git-метаданные или текст трекера. Если payload не содержит строковой `tool_input.command` или Python 3.9+ не найден, хук тоже возвращает код `2`.

## Источник

[block-public-attribution.sh](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/block-public-attribution.sh)
