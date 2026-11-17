---
name: tech-design
description: Draft or revise concise technical design documents (技术文档、技术方案、技术设计文档) focused on key decisions and necessary changes. Use when asked to write a tech design doc for a feature.
---

# Tech Design Doc (技术文档)

Write a concise engineer-to-engineer proposal that lets a reviewer understand the approach,
important decisions, and what needs to change. Match detail to the feature and the user's request.

Write the document in Chinese unless the user asks for another language. Keep code identifiers
and standard technical terms unchanged.

## Starting point

Use the feature, requirements, and decisions already established in the conversation. Ask for the
feature only when it is missing. Link the PRD when one is available; a missing PRD does not block
writing or require a placeholder.

Ground claims about existing behavior, tables, and interfaces in the provided material or relevant
code. Mark a material unknown briefly where it affects the proposal; do not invent IDs, schemas,
traffic numbers, or operational requirements to make the document look complete.

## Default structure

```markdown
# [技术文档] <feature name>

PRD: <link, when available>

## 1. 背景
<The current gap and intended outcome, in a few sentences.>

## 2. 实现
<The chosen approach and its key decisions.>

### 2.1 <area that changes, only if a subsection helps>
<Necessary changes and any non-obvious rationale.>
```

Organize implementation by the areas that actually change. A small feature may need only a few
paragraphs under `实现`. Use numbered headings, but keep the hierarchy shallow. Do not create
DB, API, frontend, or edge-case subsections merely to fill a template.

## Choosing detail

- Explain observable behavior, affected components, and decisions the reviewer needs to assess.
  Leave routine implementation choices to the code.
- Prefer existing patterns and the simplest approach that meets current requirements. Additional
  abstractions, fallback paths, compatibility layers, or rollout mechanisms need a concrete reason.
- Describe schema changes through the relevant fields, types, and semantics. Include SQL only when
  exact DDL matters to the decision or the user requests an executable migration.
- Describe API changes through the changed contract. Use a small request/response example only
  when it clarifies that change; omit full payloads and unchanged fields.
- Include code or pseudocode only when prose would leave an important mechanism ambiguous. Avoid
  full structs, function bodies, file-by-file edits, and line-by-line implementation instructions
  unless requested.
- Address edge cases, concurrency, security, or compatibility when an evidenced condition changes
  the design or correctness. Explain that condition beside the relevant decision. Dedicated risk
  analysis and speculative failure catalogs are not default sections.
- Present the current chosen design. Keep a brief tradeoff explanation when it helps review;
  remove obsolete proposals and rejected code instead of accumulating design history.
- Mention deferred work or open questions only when they affect the current scope or decision.

## Optional material

Add these only when requested or when there is a concrete design dependency:

- **上线单:** Include when deployment order, data migration, or configuration activation requires
  coordination. Keep it to the necessary actions and order. Ordinary service deployment does not
  require a section. Do not add routine backup, monitoring, approval, rollback, or verification
  checklists by default. Avoid duplicating SQL or configuration already documented elsewhere;
  provide a self-contained execution sheet only when requested.
- **Testing:** Omit testing methodology and test plans by default. If a particular acceptance case
  defines a subtle business rule, state that behavior in the relevant implementation paragraph.
  Provide a separate test plan when the user asks for one.

## Writing and editing

Use short, direct sentences and concrete names. Use bullets for parallel facts and numbered lists
when execution order matters. State each fact once. Avoid repeated summaries, generic best-practice
advice, caution callouts, and exhaustive scope exclusions.

When revising an existing document, simplify its structure and remove unnecessary detail rather
than appending another explanation. Before delivering, remove anything that does not help a
reviewer understand the requested change or make a necessary decision.

## Publishing to Lark

When the user requests creation or editing in Feishu/Lark, use the `lark-doc` skill for its document
format and editing workflow. Use its supported PRD citation format. Otherwise, return Markdown.
