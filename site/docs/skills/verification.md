# Verification: повтор проверки candidate

Источник: [manifest роли](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/verification.md)
и [общий контракт](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/_common.md).

## Перевод манифеста

```yaml
name: verification
mode: read-only
required_capabilities:
  - backend-development
risk_triggers:
  - verification-infrastructure
```

Используй роль только после того, как отчёт developer остановился по операционной причине
(`verification-infrastructure`, `transport` или `context-pressure`), а candidate commit уже существует
и остался неизменным. Повтори утверждённые команды проверки на закреплённом candidate.
Не меняй исходники, тесты, fixtures или состояние Git.

Успешный отчёт позволяет передать зарегистрированный candidate на обычную оценку риска.
Он не принимает candidate, не пропускает ревью или QA и не меняет прежние доказательства.

Если часть задания не выполнена, перечисли каждый пункт в `incomplete_items` по общему контракту.
`target_role` может быть `verification` для суженного повтора на том же candidate,
`code-review` или `qa`. Суженный повтор verification всё равно запускает все утверждённые команды проверки.

## Когда использовать

Операционная ошибка помешала проверке уже созданного candidate. Если нужен новый код,
работа возвращается к developer по решению coordinator.
