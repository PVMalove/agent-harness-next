# QA gate и Release Gate

QA gate запускает полный набор проверок проекта. В backend-оркестрации независимая роль QA
проверяет закреплённый candidate в чистой среде. Release Gate сверяет пару candidate/target и
получившееся дерево. Сам по себе локальный `/qa-gate` не доказывает изоляцию clean-room.

## QA gate

`/qa-gate` читает `qa_gate_commands` и `shell` из `.harness/project.json`, затем выполняет команды
по порядку в текущем checkout. Если в связанном worktree нет конфигурации, он берёт её и обёртку
сводки из основного worktree, но проверяет текущий checkout. Первый сбой останавливает прогон.
Если файла или списка команд нет, сначала нужно заполнить конфигурацию.

Обёртка возвращает PASS либо краткую сводку сбоя с упавшими тестами, диагностикой и путём к
очищенному от секретов логу. Успех точечных проверок не означает прохождение полного gate.

В `backend-orchestration` команда `qa run` использует `verification_commands`, готовит чистый
checkout точного candidate и отделяет QA-окружение от работы developer.
Сбой подготовки и дефект кода ведут к разным повторам; подробности находятся в [главе QA](orchestration/qa.md).
Поля команд и правила fallback описаны в [настройках проверок](../getting-started/settings/orchestration/verification.md).

## Инкрементальная verification

Полный прогон на каждый шаг слишком дорог, поэтому план проверок вычисляется, а не выбирается на
глаз.

- **ChangeImpact** строит множество затронутого по графу проекта. Неизвестное влияние расширяет
  проверку, а не сужает её.
- **VerificationPlan** фиксируется digest-ом в approval, поэтому подменить набор проверок после
  согласования нельзя.
- Developer и review получают точечные проверки по плану, QA — полный прогон на финальном SHA.
- Повтор после падения запускает **только упавшие узлы** по их точным идентификаторам. Пустой выбор
  не считается успехом: это `not_run`, и он требует отдельного решения.

## Release Gate

Gate подтверждает пару `{candidate_sha, target_sha}` и сверяет дерево после merge. «Примерно тот же
коммит» не принимается: если дерево в целевой ветке отличается от проверенного кандидата, gate не
пройден, даже когда коммит-предок совпадает. Так squash-merge и ручная правка при разрешении
конфликта не проходят незамеченными.

<figure class="ah-diagram">
  <div class="ah-diagram-bar">
    <figcaption>План проверок, полный прогон на финальном SHA и сверка дерева в Release Gate.</figcaption>
    <button class="ah-diagram-expand" type="button" aria-haspopup="dialog">Развернуть</button>
    <a class="ah-diagram-open" href="../../assets/diagrams/qa-release-gate.html" target="_blank" rel="noopener">Открыть отдельно ↗</a>
  </div>
  <iframe class="ah-diagram-frame" data-theme-sync src="../../assets/diagrams/qa-release-gate.html" title="QA gate и Release Gate" loading="lazy"></iframe>
</figure>

## CI-доказательство вместо локального прогона

Если трекер отдаёт полный прогон CI, вместо локального QA принимается CI-доказательство для
объединённого результата pull request. Принимается только завершённое доказательство: пройденное или
проваленное. Когда набор проверок неполный, команда ничего не записывает и сообщает, что нужен
локальный прогон.

Команды и поле конфигурации описаны в [справочнике CLI](../reference/cli.md#ci-evidence).

## Дальше

- [Code review](code-review.md)
- [CLI и конфигурация](../reference/cli.md#ci-evidence)
- [«/implement»](implement.md)
