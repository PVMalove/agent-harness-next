# Grill Me: прожарь меня

## 1. Название и локализация

- **Английское название:** `grill-me`
- **Русский перевод:**

```text
Прожарь меня
```

## 2. Полный перевод текста скила

<div class="ah-skill-text" markdown="1">

```yaml
name: grill-me
description: Проводит интервью /grilling, чтобы проверить идею или план, и собирает согласованный Discovery Context, не меняя CONTEXT.md и ADR. Используйте явно перед /to-spec; чтобы также обновлять доменные документы, используйте /grill-with-docs.
disable-model-invocation: true
```

Запустите `/grilling`. Если работаете в репозитории, соберите согласованный Discovery Context. Читайте доменные документы для контекста, а предложенные термины и решения оставляйте в итоговом сообщении.

</div>

## 3. Контракты

- **Вход (Input/Brief):** план, решение или дизайн, которые нужно проверить интервью.
- **Выход (Output/Report):** согласованные решения и пути, открытые вопросы и следующий шаг.

## Источник

[SKILL.md](https://github.com/PVMalove/agent-harness-next/blob/master/skills/first-party/engineering/grill-me/SKILL.md)
