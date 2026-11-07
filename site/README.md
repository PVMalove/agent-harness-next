# Публичный сайт Agent Harness Next

Сайт на MkDocs Material. Исходники — `site/docs/`, конфигурация — `site/mkdocs.yml`,
сборка — `site_build/` (в `.gitignore`).

```bash
make docs-serve   # локальный предпросмотр
make docs-build   # строгая сборка
```

Публикация — `.github/workflows/pages.yml` через GitHub Actions Pages. Версия на сайте — `beta`.
