# Справочник

Справочник описывает команды и конфигурацию проекта, метки процесса, hooks и каталог скиллов. Он
отвечает на вопрос «как это настроено». Пошаговые сценарии описаны в руководствах.

<div class="ah-cards ah-cards--four">
  <a class="ah-card" href="cli/">
    <span class="i">⌘</span>
    <b>CLI и конфигурация</b>
    <span>Команды установки и обновления, поля конфигурации, health, память, граф проекта.</span>
  </a>
  <a class="ah-card" href="labels/">
    <span class="i">◇</span>
    <b>Метки</b>
    <span>Оси меток, правило одной метки состояния и переходы по пайплайну.</span>
  </a>
  <a class="ah-card" href="hooks/">
    <span class="i">⌁</span>
    <b>Hooks</b>
    <span>Профили, критические guard-ы и таблица подключённых проверок.</span>
  </a>
  <a class="ah-card" href="skills/">
    <span class="i">✓</span>
    <b>Скиллы</b>
    <span>Переопределения, апстримный набор и first-party дополнения.</span>
  </a>
</div>

## Глоссарий

<div class="ah-ref-glossary" id="ah-ref-glossary">
  <div class="ah-ref-glossary-head">
    <div>
      <b>Все термины проекта</b>
      <span>Определения, английские эквиваленты и пометки, как эти понятия не стоит называть. Словарь для документации, CLI и конфигурации.</span>
    </div>
    <a class="md-button md-button--primary" href="glossary/">Открыть глоссарий</a>
  </div>
  <form class="ah-ref-glossary-search" action="glossary/" method="get" role="search">
    <input type="search" name="term" placeholder="Найти термин: capability, lease, supervisor…" aria-label="Поиск по глоссарию" autocomplete="off" spellcheck="false">
    <button type="submit">Найти</button>
  </form>
  <div class="ah-ref-glossary-links" role="group" aria-label="Категории терминов">
    <a href="glossary/?category=architecture">Архитектура и код <span>42</span></a>
    <a href="glossary/?category=files">Файловая система и рантайм <span>23</span></a>
    <a href="glossary/?category=tasks">Задачи и артефакты <span>45</span></a>
    <a href="glossary/?sort=az">По алфавиту А–Я</a>
  </div>
</div>

## Как это устроено

Каждая команда принимает путь к целевому проекту и не зависит от текущего каталога. Конфигурация
проекта задаёт строгий контракт: незнакомое поле считается ошибкой, его не пропускают молча.
Подробности описаны в [справочнике CLI](cli.md).
