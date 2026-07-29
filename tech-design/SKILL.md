---
name: tech-design
description: Draft technical design documents (技术文档) in this engineering team's established style — background, implementation broken out by DB/API/edge-case, and a closing 上线单 rollout checklist, with heavy inline-commented code blocks. Use when asked to write a tech design doc, 技术文档, 技术方案, 技术设计文档, or "write up the technical doc for this feature".
---

# Tech Design Doc (技术文档)

Write engineer-to-engineer technical design docs the way this team actually writes them: terse,
code-first, organized by implementation area rather than narrative, and ending in a checklist an
on-call engineer can execute without re-reading the doc.

**Write the document itself in Chinese** — headings, prose, inline comments, everything except
code identifiers and standard technical terms. This SKILL.md is written in English for whoever
maintains the skill; that's a documentation-language choice, not a signal about the output. Only
switch the output to English if the user explicitly asks for it.

## Usage

```
/tech-design <feature name or short description>
```

- Argument given → treat it as the feature to design. If it also contains or names a PRD link, use
  that for the `PRD:` line; if there's no PRD yet, leave `PRD: TODO` rather than blocking on it.
- No argument → ask what feature this doc is for, and whether there's a PRD to link, before drafting.
- If the conversation already established what's being built (a plan, a prior message, an open PRD),
  that context takes precedence over asking again.

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

**Number every heading with full outline numbering**, dotted to the heading's depth. The three
top-level (`##`) sections are `1. 背景`, `2. 实现`, `3. 上线单` — fixed, in that order, always these
three numbers since each appears exactly once. Everything nested under `实现` continues the outline
from `2`: each `###` subsystem/module is `2.1`, `2.2`, `2.3`, ... (business-logic, edge-case, and
risk-analysis sections count as modules too, so they keep taking the next number in the same
sequence), and each `####` under a module extends its parent by one more segment — `2.1.1`, `2.1.2`
under module `2.1`, then `2.2.1` under module `2.2`, and so on. If a submodule needs its own
breakdown, go one level deeper the same way (`2.1.1.1`).

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
- **Superseded design decisions** — don't delete them, strike them through with `~~...~~` (keep
  the rejected SQL/JSON alternative visible below the strikethrough line) so the doc preserves *why*
  the current design won, not just what it is. When there were genuinely multiple options on the
  table, label them explicitly — `方案一: ...` / `方案二: ...` — strike the rejected ones, and if the
  final call is a deliberate compromise rather than a clean win, say so plainly
  (`本期为了把相关工作量控制到最小，采用折中方案：`) followed by the reasoning as bullets. Naming the
  compromise as a compromise is more useful to a future reader than presenting it as the obviously
  correct design.

### 上线单 (Rollout checklist) — always last
Two parts:
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

## Prose micro-conventions
- Short sentences, subjects frequently dropped — write like an engineer leaving notes for a
  teammate, not documentation prose.
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
follow its XML authoring rules (`lark-doc-xml.md`) rather than emitting raw Markdown — in
particular, use a `<cite>` block for the PRD link at the top rather than a plain hyperlink.
