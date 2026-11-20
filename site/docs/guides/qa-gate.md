# QA gate и Release Gate

QA gate запускает полный набор проверок проекта. В backend-оркестрации независимая роль QA
проверяет закреплённый candidate в чистой среде. Release Gate сверяет пару candidate/target и
получившееся дерево. Локальный `/qa-gate` сам по себе не доказывает изоляцию clean-room.

## QA gate

`/qa-gate` читает `qa_gate_commands` и `shell` из `.harness/project.json`, затем выполняет команды
по порядку в текущем checkout. Если в связанном worktree нет конфигурации, скилл берёт её и обёртку
сводки из основного worktree, но команды запускает в текущем checkout. На первом сбое прогон
останавливается. Если файла или списка команд нет, сначала заполните конфигурацию.

Обёртка возвращает PASS либо краткую сводку сбоя с упавшими тестами, диагностикой и путём к
очищенному от секретов логу. Если прошли точечные проверки, это ещё не значит, что прошёл полный gate.

В `backend-orchestration` команда `qa run` берёт `verification_commands`, готовит чистый
checkout точного candidate и отделяет QA-окружение от работы developer.
Сбой подготовки и дефект кода ведут к разным повторам, подробности в [главе QA](orchestration/qa.md).
Поля команд и правила fallback описаны в [настройках проверок](../getting-started/settings/orchestration/verification.md).

## Инкрементальная verification

Полный прогон на каждом шаге слишком дорог. Поэтому, если в `orchestration.json` задана
`verification_plan_policy`, coordinator вычисляет план проверок, а не выбирает его на глаз.

- **ChangeImpact** по графу проекта находит всё, что затронуло изменение. Если влияние неизвестно,
  проверка расширяется, а не сужается.
- **VerificationPlan** закрепляется в approval своим digest, поэтому подменить набор проверок после
  согласования нельзя.
- Developer и review получают точечные проверки по плану, QA получает полный прогон на финальном SHA.
- Повтор после падения запускает **только упавшие узлы** по их точным идентификаторам. Пустой выбор
  не считается успехом: это `not_run`, и по нему нужно отдельное решение.

## Release Gate

Gate подтверждает пару `{candidate_sha, target_sha}` и после мержа сверяет дерево. «Примерно тот же
коммит» не принимается: если дерево в целевой ветке отличается от проверенного кандидата, gate не
пройден, даже когда коммит-предок совпадает. Поэтому squash-merge и ручная правка при разрешении
конфликта не пройдут незамеченными.

<figure class="ah-diagram">
  <div class="ah-diagram-bar">
    <figcaption>План проверок, полный прогон на финальном SHA и сверка дерева в Release Gate.</figcaption>
    <button class="ah-diagram-expand" type="button" aria-haspopup="dialog">Развернуть</button>
    <a class="ah-diagram-open" href="../../assets/diagrams/qa-release-gate.html" target="_blank" rel="noopener">Открыть отдельно ↗</a>
  </div>
  <iframe class="ah-diagram-frame" data-theme-sync src="../../assets/diagrams/qa-release-gate.html" title="QA gate и Release Gate" loading="lazy"></iframe>
</figure>

## CI-доказательство вместо локального прогона

Если трекер отдаёт результат полного прогона CI, вместо локального QA принимается CI-доказательство для
объединённого результата pull request. Принимается только завершённое доказательство: пройденное или
проваленное. Если набор проверок неполный, команда ничего не записывает и сообщает, что нужен
локальный прогон.

Команды и поле конфигурации описаны в [справочнике CLI](../reference/cli.md#ci-evidence).

## Дальше

- [Code review](code-review.md)
- [CLI и конфигурация](../reference/cli.md#ci-evidence)
- [«/implement»](implement.md)
