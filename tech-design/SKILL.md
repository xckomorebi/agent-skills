---
name: tech-design
description: Draft concise technical design documents (技术文档) in this engineering team's established style — background, implementation broken out by DB/API/edge-case, and a closing 上线单 rollout checklist with focused schema and API examples. Use when asked to write a tech design doc, 技术文档, 技术方案, 技术设计文档, or "write up the technical doc for this feature".
---

# Tech Design Doc (技术文档)

Write engineer-to-engineer technical design docs for internal discussion: concise, code-first,
organized by implementation area rather than narrative, and ending in a checklist an on-call
engineer can execute without re-reading the doc. This is a working design shared between teammates,
not a formal technical manual.

**Write the document itself in Chinese** — headings, prose, inline comments, everything except
code identifiers and standard technical terms. This SKILL.md is written in English for whoever
maintains the skill; that's a documentation-language choice, not a signal about the output. Only
switch the output to English if the user explicitly asks for it.

Use the language engineers naturally use with each other. Prefer direct statements such as
`这里复用现有的计费逻辑，只新增价格区间的匹配` over stiff explanatory prose. Avoid translationese,
especially long sentences built around `通过……从而……以实现……`, and avoid internet-industry
buzzwords such as `赋能`, `抓手`, `闭环`, `沉淀`, or `拉通` when a concrete verb says the same thing.
Technical terms that are normal and precise in the codebase are fine; the goal is natural language,
not forced colloquialism.

Write the resulting design, not the conversation or reasoning process that produced it. Review
comments, preference changes, and ordinary implementation revisions should be folded into the
current design without narrating the discarded version. Avoid sentences shaped like
`不再使用旧方案 X，改为 Y` when the only reason was preference; state `使用 Y` and move on.

For a feature of ordinary complexity, target a document that an engineer can read end to end in
about 12 minutes. This is a readability budget, not permission to omit behavior that affects
correctness. Keep the shortest explanation that makes the schema, API contract, core flow, edge
cases, and rollout operations unambiguous.

## Usage

```
/tech-design <feature name or short description>
```

- Argument given → treat it as the feature to design. If it also contains or names a PRD link, use
  that for the `PRD:` line; if there's no PRD yet, leave `PRD: TODO` rather than blocking on it.
- No argument → ask what feature this doc is for, and whether there's a PRD to link, before drafting.
- If the conversation already established what's being built (a plan, a prior message, an open PRD),
  that context takes precedence over asking again.

## Unresolved decisions

Before committing to a design, check whether any material choice is still open and has not already
been discussed. If two or more reasonable options would lead to meaningfully different behavior,
data models, API contracts, compatibility constraints, scope, or rollout plans, ask the user for
their preference instead of silently choosing one.

Prefer an available structured ask-user/question tool. Keep the interruption small: ask only the
decision needed now, offer 2-3 mutually exclusive options, put the recommended option first, and
state each option's practical impact in one sentence. If no such tool is available, ask one concise
direct question. Do not put the unanswered questionnaire or the process of choosing into the
technical document.

Do not ask about facts that can be resolved from the codebase or requirements, choices with one
clearly correct engineering answer, or minor reversible details that do not affect the design. For
those, use the simplest reasonable option and document only the result. If a material preference
cannot be obtained and guessing would substantially change the design, leave a concise owner-specific
`【TODO】` instead of inventing a preference.

## Document skeleton

```
# [技术文档] <feature name>

PRD: <link to the PRD/需求文档>

## 1. 背景
<2-4 short sentences: what's inconsistent/missing today, why it matters. No filler.>

## 2. 实现
### 2.1 <subsystem or module 1>
#### 2.1.1 DB结构更改
...
#### 2.1.2 <interface/API> 修改
...

### 2.2 <subsystem or module 2>
...

### 2.3 <edge case / cross-cutting concern>
...

## 3. 上线单
<final, copy-pasteable migration SQL>
<ordered deployment steps as a flat bullet list>
```

Only `背景`, `实现`, and `上线单` are mandatory top-level (`##`) sections, in that order. Everything
under `实现` is organized **by implementation area** (DB → backend API → business logic → edge
cases → display layer), not chronologically and not by "what I did first."

Use one full outline-numbering system throughout the document. The three top-level sections are
logically `1. 背景`, `2. 实现`, and `3. 上线单`, in that order. Everything nested under `实现`
continues from `2`: subsystem/module sections are `2.1`, `2.2`, `2.3`, and their children are
`2.1.1`, `2.1.2`, and so on.

How those numbers are represented depends on the output target:

- In Markdown or plain-text output, include the outline number in the heading text as shown in the
  skeleton.
- When creating or updating a Lark document, use `lark-doc`'s native structured numbering blocks:
  nested `<ol>` elements with `<li seq="auto">`. Do not fake the sequence by writing the number into
  a heading such as `<h3>3.5</h3>` or `<h3>3.5 标题</h3>`; that produces ordinary heading text rather
  than Lark's structured sequence styling. Keep the section nesting in the list structure so Lark
  owns the numbering and continuation behavior.

## Section-by-section rules

### Title and PRD link
- Title is always `# [技术文档] <feature name>` — the `[技术文档]` tag prefix is literal, not a
  placeholder to drop.
- Immediately below the title, one line linking the source requirements doc: `PRD: <link>`. If
  authoring directly in Lark via the `lark-doc` skill, use a `<cite>` embed to the PRD wiki doc
  instead of a bare URL.

### 背景 (Background)
Short and blunt. State the current inconsistency/gap and the mechanism that will resolve it in a
sentence or two each. Do not restate the PRD's motivation in detail — that's what the PRD link is
for. Example register (generic illustration, not a real feature):

> 同一商品在不同购买数量下应使用不同单价，目前系统只支持单一价格。需要按购买数量区间匹配对应价格。

### 实现 (Implementation) — the bulk of the doc
Open with a short design-overview paragraph before the subsystem breakdown: one sentence naming the
overall approach (`基于 X 设计本方案，包含以下重点：`), then a flat bullet list of the 3-6 decisions
that shape everything below — what's reused, what's genuinely new, what's explicitly deferred. A
reviewer who only reads this bullet list should already know the shape of the solution; the
subsections that follow are where those bullets get proven out in schema and API detail.

Then break into `###` subsections per subsystem/module, each optionally split further into `####`
subsections for DB vs. API vs. validation. Use these recurring subsection shapes as needed:

- **Diagrams** — add a Mermaid diagram only when it makes an architecture, data flow, state change,
  or multi-step interaction materially easier to discuss than prose. Keep it small and label nodes
  with concrete system/module names. Do not add a diagram as decoration or repeat a sequence already
  clear from a short list. In Lark, use a Mermaid whiteboard block through `lark-doc` rather than
  pasting Mermaid source as a normal code block.

- **New entities/tables** — a sentence of *why this exists* before the schema, e.g.
  `为了给各个租户创建“XX类”订单，需要一个新的产品规格...`. Don't let a `CREATE TABLE`/`ALTER TABLE`
  block be the reader's first encounter with a new concept. When the entity is better expressed as
  application code than a schema (a struct that's assembled in memory, not a new table), show that
  instead — a Go/language struct with field tags is a legitimate substitute for SQL when it's more
  representative of what's actually being built.
- **`#### 2.<n>.1 DB结构更改`** (numbered relative to its parent module) — schema changes as fenced
  ` ```SQL ` blocks using real `ALTER TABLE`
  statements. **Every new column gets an inline `COMMENT`** in Chinese stating its semantics, unit,
  and bounds, e.g.:

  ```SQL
  ALTER TABLE `pricing_tier`
    ADD COLUMN `tier_seq`   INT NOT NULL DEFAULT 0   COMMENT '同一 product_id 下的匹配优先级（1..N），小者优先',
    ADD COLUMN `qty_min`    INT NOT NULL DEFAULT 0   COMMENT '购买数量区间下界（含），左闭右开 [min,max)',
    ADD COLUMN `qty_max`    INT NOT NULL DEFAULT 999999 COMMENT '购买数量区间上界（不含），999999 视为无上界',
    ADD COLUMN `new_tier_seq` INT DEFAULT NULL         COMMENT '待生效的 tier_seq';
  ```

  When a change needs staged rollout, mirror each live column with a `new_<column>` shadow column
  (nullable, "待生效" in the comment) rather than inventing a separate staging table. Index changes
  get their own short label line (e.g. `uk变更`) before their own SQL block — don't bury them in the
  same block as column additions.
- **API change sections** (`#### 2.<n>.2 <后台/服务> 创建/更新<资源>的接口修改` or similar) — for each
  endpoint:
  1. One bullet with the path: `- api/admin/catalog/v1/pricing_tier/batch_create`
  2. Request body as a fenced ` ```JSON ` example immediately below, using **real-looking sample
     values**, not schema descriptions. Mark optional fields with a trailing `// optional` comment
     directly in the JSON (comments aren't valid JSON — that's fine, these blocks are illustrative,
     not executable).
  3. If documenting the response, label it with an inline bold marker on its own line —
     `**响应示例:**` — then the JSON block (see Prose micro-conventions below for bold's other use).
  4. One short prose line under the block for any non-obvious side effect (e.g.
     `创建价格档立刻生效`).
- **Validation-only endpoints** (a `_valid_check` sibling of a write endpoint) — document the
  warning/error contract as two short standalone lines, not a table:
  `warning信息: <what it means, that it's non-blocking>` and
  `error信息：<what it means, that it blocks the action>`, then state the enforcement rule in plain
  prose (e.g. `原则上，只要error信息非空，前端应该禁止提交`).
- **Pure business-logic sections** (no DB/API split needed) — just short prose facts, one per
  paragraph, blank line between them. No bullets unless enumerating genuinely parallel items. Name
  a section after the effect it describes when that's what it's documenting, e.g.
  `### 2.<n> 受<字段/状态>影响的业务逻辑` for "here's what changes when this value flips."
- **Sequential processes** — when a subsection is describing an algorithm or a pipeline (compute a
  value, then settle it, then record it), use a numbered list, one step per number, with nested
  unordered bullets for each step's inputs/fields. Reserve plain unordered bullets for flat,
  order-independent facts (config fields, parallel options) — the ordered/unordered choice itself
  signals whether sequence matters.
- **Config-manifest entries** — for a new business-config object that isn't a raw schema change
  (an admin-configured campaign, a feature-gate, a rule row someone will click through a UI to
  create), spec it as `新增一个<配置对象>：` followed by a flat `字段：取值` bullet list, rather than
  forcing it into SQL. Keep it concrete — real values, not placeholders — so it can be copied
  straight into `上线单` later.
- **Edge cases** — enumerate as inline-labeled paragraphs, not a bullet list:
  `特殊场景1: <condition>, <behavior>` / `特殊场景2: <condition>, <behavior>`.
- **Concurrency/risk analysis** — give it its own `###` section named for the exact race
  (e.g. `2.<n> 由于并发问题导致 同时改价与下单的 情况分析`), open with the real numbers that ground the
  risk assessment (order-of-magnitude counts, not hand-waving), then walk the worst case as short
  causal chains: `如果 <trigger>，有概率 <bad outcome>，影响是 <blast radius and duration>`.
- **Open items and deferred scope** — leave `TODO`s in place rather than tracking them elsewhere.
  Inline in code as `// TODO: <question>`; in prose as `【TODO】 待<owner>确认` when blocked on a
  specific person. Mark work that's deliberately out of scope for this iteration inline, right next
  to the thing it's scoping, with a parenthetical prefix — `（本期不做）`/`（本期不实现）` before a
  heading or bullet — so the reader never has to guess whether something is planned or already
  excluded.
- **Design decisions and discarded alternatives** — default to the final design only. Do not preserve
  review history, the author's thought process, or superseded SQL/JSON with strikethrough. Pure
  preference changes need no explanation. Include alternatives only when the team repeatedly weighed
  material trade-offs and the reason for the final choice will matter to implementation or future
  maintenance. In that case, summarize the viable options, decisive trade-offs, and final choice in
  the smallest useful form; do not replay the chronological discussion.

Do not add generic sections such as `测试建议`, `测试方案`, `验收建议`, or a standard test-case list.
Normal cases are covered by the regular development and test process. Keep only validation rules,
compatibility constraints, and exceptional failure handling that directly affect the design itself.

### 上线单 (Rollout checklist) — always last
The rollout checklist contains executable operations, not a second testing plan. It has two parts:
1. The **final, consolidated migration** — copy the authoritative `ALTER TABLE`/`CREATE TABLE`
   statements from `实现` again here in full, and turn every config-manifest bullet list
   (`新增一个<配置对象>：...`) from `实现` into the literal `INSERT` statement or concrete admin-panel
   values needed to create it — real IDs, real field values, not a restatement of the field list.
   Don't make ops re-read the whole doc, or re-derive values, to execute the rollout; this section
   must be self-contained and copy-pasteable end to end.
2. A flat, ordered bullet list of deployment steps, one line per system/component, in strict
   execution order:
   ```
   - Mysql
   - <service A>
   - <service B>
   - 最后上新配置
   ```
   Coarse-grained on purpose — this is a run order, not a task breakdown.

Do not add routine verification steps such as checking normal API responses, UI behavior, logs,
metrics, or regression results. Those belong to normal testing. Include a brief verification step
only when the rollout has an unusually easy-to-miss failure mode that could leave production in a
bad partial state; say exactly what to check and keep it to one line.

## Prose micro-conventions
- Short sentences, subjects frequently dropped — write like an engineer discussing the change with
  teammates, not a manual, press release, or translated specification. Read every sentence once for
  translationese and buzzwords; replace abstract nouns with the concrete component and action.
- Prefer one precise statement over setup, recap, or repeated rationale. Remove details already clear
  from the PRD, code sample, diagram, or another section. Before delivery, do a compression pass and
  cut anything that does not change implementation, review decisions, or rollout operations.
- Table/column/field names and API paths: inline code (`` `pricing_tier` ``) or bare literal
  text at the start of a line, never quoted in prose.
- No em-dashes. Use Chinese full-width punctuation (，。；：) naturally in Chinese sentences.
- Bold has exactly two jobs: an inline section micro-label (`**响应示例:**`), or wrapping a whole
  sentence to flag a forward-looking caveat the reader shouldn't skim past
  (`**未来还是需要将账单改成异步创建的模式。**`). Don't use it for ordinary emphasis.
- For a lighter aside that doesn't need a full bold callout — a scope caveat, a "don't forget"
  — prefix the sentence with a literal `*注意：` instead of a blockquote or admonition block.
- Blank line between most paragraphs/facts, even short ones — mirrors Feishu's one-idea-per-block
  convention. When the doc will live in Lark, author it there directly (see below) rather than
  writing Markdown and pasting, since Feishu block spacing doesn't survive a naive paste.

## Publishing to Lark
If the user wants the doc created or updated in Feishu/Lark, hand off to the `lark-doc` skill and
follow its XML authoring rules (`lark-doc-xml.md`) rather than emitting raw Markdown. In particular,
use a `<cite>` block for the PRD link at the top, native nested `<ol><li seq="auto">` blocks for the
outline sequence, and `<whiteboard type="mermaid">` when a Mermaid diagram is useful.
