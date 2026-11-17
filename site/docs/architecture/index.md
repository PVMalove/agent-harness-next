# Архитектура

Политика и исполнение разделены: Python принимает решения, Rust runtime хранит operational state
и запускает процессы, а Git владеет историей и кандидатами.

<div class="ah-cards">
  <a class="ah-card" href="overview/">
    <span class="i">◇</span>
    <b>Обзор</b>
    <span>Слои и ownership, модель поставки, Discovery Pipeline и границы доверия.</span>
  </a>
  <a class="ah-card" href="runtime/">
    <span class="i">⌁</span>
    <b>Rust runtime</b>
    <span>Процесс и IPC, runtime store, supervisor и OCI, reconcile, verification и безопасность.</span>
  </a>
  <a class="ah-card" href="../getting-started/">
    <span class="i">✓</span>
    <b>Быстрый старт</b>
    <span>Требования, установка, подключение к проекту и первые команды.</span>
  </a>
</div>

## Как читать

Начните с обзора: он объясняет, кто чем владеет и почему runtime store единственный пишет
operational state. Затем откройте страницу Rust runtime: на ней процесс, IPC, store, supervisor и
домены отказов. Полные нормативные контракты остаются в ADR репозитория; эти страницы объясняют
модель и не заменяют ADR.
