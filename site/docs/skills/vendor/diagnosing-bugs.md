# diagnosing-bugs: диагностика ошибок

## 1. Название и локализация

- **Английское название:** `diagnosing-bugs`
- **Русский перевод:** Диагностика ошибок.
- **Исходный скилл:** [`SKILL.md`](https://github.com/PVMalove/agent-harness-next/blob/master/skills/vendor/mattpocock/engineering/diagnosing-bugs/SKILL.md)

## 2. Русское описание

Ведёт диагностику сложного сбоя или регрессии производительности по циклу: воспроизведение, гипотезы, наблюдения, проверка причины.

## 3. Применение

Порядок шагов, входные условия и ограничения задаёт исходный `SKILL.md`. Эта страница только кратко описывает по-русски закреплённую upstream-версию.

В `engineering-suite` работает [first-party override](../diagnosing-bugs.md). Если память проекта
включена, он ищет прошлые фиксы через `harness memory search`. Vendor-снапшот не меняется.
