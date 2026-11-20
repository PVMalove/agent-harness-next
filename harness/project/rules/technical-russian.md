# Technical Russian

Apply this rule to every Russian text a human reads: chat replies to the user, questions and
options, final summaries, documentation, `CHANGELOG.md`, and completion reports written in Russian.
Agent-to-agent English follows [Technical English](technical-english.md). Code, identifiers, commands,
paths, flags and labels keep their original form and go in code formatting.

## Write as one engineer explains to another

- **Coherent reasoning.** Build a paragraph as claim → cause → consequence. Join related facts with
  connectives («поэтому», «потому что», «если …, то», «в отличие от»). Sentence length follows the
  thought: merge two or three facts of one causal chain into one sentence; split a sentence when the
  reader must hold more than two or three nesting levels.
- **Main point first.** Start a section with what it is and why; details, exceptions and limits follow.
- **Active voice, direct word order.** Name the actor and the action: «Координатор проверяет права
  доступа», not «Проверка прав доступа выполняется координатором». Use the passive when the actor is
  unknown, unimportant or obvious («Хэш записывается в lock-файл»).
- **One term per concept.** Keep the project glossary term and do not alternate synonyms: «каталог»,
  not «папка» or «директория». Keep English names that became project entities (`batch`, `capability`).
- **Verbs over nominalizations.** «проверяет план», not «осуществляет проверку плана»; «проверка плана
  операции перед изменением каталога», not «проверка плана выполнения операции изменения каталога».
  Delete empty words when the meaning survives: «фактически», «является», «осуществляется»,
  «в целях обеспечения», «соответствующий».
- **Exact facts.** Rewriting for style keeps every fact, condition, limit, link and command. Keep a
  precise condition precise: «если задан флаг …», not «всегда».
- **Audience-level detail.** User-facing text describes what changed and the effect for the reader,
  without internal class names, private paths or database structure. References and ADRs name exact
  identifiers and paths: they are the contract.

## Changelog entries (Keep a Changelog)

Every entry under `Added`, `Changed`, `Fixed`, `Deprecated`, `Removed`, `Security` or
`Breaking Changes` has this form:

```markdown
- **[Суть изменения в 2–4 слова]:** Что изменилось для пользователя и к чему это приводит. (#123)
```

- The bold bracketed title states the change in two to four words.
- The body is one or two coherent sentences about the result for the user, not the code layout; a
  third sentence is allowed for an important limit or migration.
- The entry ends with the related issue or PR as `(#...)`.
- Command-line flags and public command names keep their exact spelling in code formatting.
