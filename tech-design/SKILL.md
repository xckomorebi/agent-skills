---
name: tech-design
description: Draft or revise concise technical design documents (技术文档、技术方案、技术设计文档) for a mixed review audience of backend, QA, and product, organized by affected service and functional change, with concrete SQL and config changes and an executable rollout list. Use when asked to write a tech design doc for a feature.
---

# Tech Design Doc (技术文档)

## 读者与目标

The readers are backend peers, QA, and product. Backend peers may implement from it; QA and
product need the behavior, the boundary, and the risk. Everyone needs to see where the change
lands: which service, which interface, which table, which config.

Write the change and the mechanism. Do not transcribe the code path.

Write the document in Chinese unless the user asks for another language. Keep code identifiers and
standard technical terms unchanged.

## Starting point

Use the feature, requirements, and decisions already established in the conversation. Ask for the
feature only when it is missing. Link the PRD when one is available; a missing PRD does not block
writing.

Ground claims about existing behavior, tables, and interfaces in the provided material or relevant
code. Mark a material unknown briefly where it affects the proposal; do not invent IDs, schemas,
traffic numbers, or operational requirements.

Before drafting, settle three things for yourself. Do not put them in the document:

1. Which services change, and which functional points each one contains.
2. Which 3-6 conclusions shape the design.
3. Which material only the implementer needs, and therefore gets cut.

## 默认结构

```markdown
# [技术文档] <feature name>

PRD: <link, when available>

## 1. 背景
<2-4 sentences: the current gap and the intended outcome.>

## 2. 实现
### 2.1 <service, e.g. MaaS>
#### 2.1.1 <functional change, e.g. 租户配置创建、编辑、查询接口适配新增字段>
#### 2.1.2 <functional change>

### 2.2 <service, e.g. maas-gateway>
#### 2.2.1 <functional change, e.g. 增加 ZDR 请求入口与路由缓存标记>
#### 2.2.2 <functional change>

## 3. 配置示例
<Optional. The actual config the reader can copy.>

## 4. 待讨论
<Optional. Only open questions that block implementation or rollout.>

## 5. 上线单
<Short checklist of what to execute, in order: service updates, SQL, config values, manual steps.
Omit only when there is nothing to deploy or configure.>
```

`实现` is organized by service first, then by functional change. One `###` per service that
changes; a service that only consumes the result does not get a section. Never organize by
DB / API / frontend layer.

When a service contains more than one change, split it into `####` sub-points numbered
`2.<service>.<n>`. Each sub-point is one coherent change, and its heading must say what that
change does, so a reader knows from the heading alone what the paragraph is about. Use verb plus
object, for example `增加 ZDR 请求入口与路由缓存标记` or `用户侧模型列表按租户配置过滤 Tag`. A
generic label such as `接口调整`, `DB变更`, `配置变更`, or `其他` is not a heading; rename it after
the change it contains. Never use `#####`.

Within each sub-point, or within a service that has a single change, cover what applies in this
order:

1. Schema change: the real `ALTER TABLE` / `CREATE TABLE` block. Every new column carries a
   Chinese `COMMENT` with its meaning, unit, and default.
2. Config change: the config key, the actual value, and a JSON block when the shape matters.
3. Interface change: method and path, plus a small request/response example only when the contract
   is not obvious.
4. Behavior change: observable result plus one sentence of mechanism, defined below.

`上线单` is a short checklist of what to execute, in order. Repeat the final SQL and config values
from `实现`; do not explain them.

Prefer existing patterns and the simplest approach that meets the current requirement. Additional
abstractions, fallback paths, compatibility layers, or rollout mechanisms need a concrete reason.

## 写变更和机制，不写代码路径

Every change states two things: what the reader can observe, and where it is implemented.

Write:

- Behavior the user, QA, or caller can observe, and which services are affected.
- One sentence of mechanism per behavior change: which interface or component makes the decision,
  which table or config it reads, and how the result is filtered, rewritten, or routed. Example:
  `用户侧 model/tag/list、模型列表和详情的 tag_list 在返回前读 maas_tenant_config.zdr_policy；
  值为 disabled 时过滤“支持ZDR”，模型本身照常返回。`
- Schema changes as real DDL. Config changes as the actual key and value.
- Conditions that change the design or correctness (edge case, concurrency, compatibility),
  stated next to the decision they affect.

Do not write:

- Function call chains, how the handler / service / DAL layers reuse existing code, cache
  structures or invalidation sequences, lock design, or concurrency derivations. Summarize the
  observable convergence or isolation result instead.
- Per-field validation lists, or the same rule repeated for every endpoint. When N endpoints share
  a rule, state it once and list the endpoints compactly.
- Struct definitions or Go/Java/other language code blocks.
- Full test plans, per-case acceptance lists, or generic rollout checklists.
- The PRD motivation again, rejected alternatives, or the decision process.

Test: after reading a paragraph, the reviewer should be able to say "it changes here, reads this,
and the result becomes that." If not, add one sentence of mechanism. If yes, and you still want
function-level detail, you are writing too much.

## 词汇边界

Use the vocabulary the reviewers share: 模型、Endpoint、SVC、租户、Gateway、权限点、动态配置, plus
the actual interface paths, table names, and config keys.

Internal type names (`XxxEngine`, `XxxCache`, `XxxRepo`, `DAL`, `Handler`) stay out by default.
Include one only when the reviewer must decide something about that type specifically. Otherwise
describe the capability in business terms.

## 上线单

A memo of what to execute, in order. One entry per action. The operator reads this to click through,
not to understand the design.

- Service release: `maas更新服务` or `maas-gateway更新服务镜像`. Do not describe what the release
  contains.
- SQL: `MySQL：执行以下 DDL。` followed by the statement block.
- Config: the config path and the value to add, in a block.
- Manual data step: the action itself, e.g. `添加 zdr model tag`.

Write each entry as an action. Include verification, monitoring, rollback, backup, or approval
steps only when the design or the user requires them.

## 硬预算

For an ordinary feature:

- Total 1500-2500 Chinese characters, no more than 3 pages. A larger feature may exceed this, but
  keep the structure and cut the code-path detail.
- Headings go at most three levels deep (`##`, `###`, `####`).
- Code blocks: SQL, JSON, or config only. Use one concise block per change in `实现` by default.
  Use separate blocks when the same change requires distinct artifacts, such as executable DDL
  and a JSON config. Repeat them in `上线单` where the executor needs them.
- Tables: at most 5 rows. Longer uniform data becomes one sentence plus the exceptions.
- No `测试关注重点` section unless the user explicitly asks for test points. If one test point
  defines an easily misused business rule, state that rule in the relevant implementation paragraph.

## 范例

坏：`#### 接口调整` / `#### DB变更` / `#### 配置变更`

好：`#### 2.2.1 增加 ZDR 请求入口与路由缓存标记` / `#### 2.2.2 pipeline 按 ZDR 标记过滤 SVC`
/ `#### 2.1.3 用户侧 Tag 列表、模型列表与详情按租户配置过滤展示`

坏：基于现有模型管理、隐藏模型权限和 Gateway `TrafficReplicationEngine` 能力设计本方案

好：复用现有模型管理与权限体系；线上模型引用测试模型，Gateway 异步复制一份请求到测试 SVC。

坏：用户侧 `model/tag/list`、模型列表及详情的 `tag_list` 按租户开关隐藏或展示 ZDR Tag

好：`model/tag/list`、模型列表和详情在返回前读 `maas_tenant_config.zdr_policy`；值为
`disabled` 时过滤“支持ZDR”Tag，`enabled` 时展示，模型本身照常返回。

坏：租户配置表新增 `zdr_policy`，存量租户默认关闭

好：

```sql
ALTER TABLE `maas_tenant_config`
  ADD COLUMN `zdr_policy` VARCHAR(32) NOT NULL DEFAULT 'disabled'
    COMMENT '租户ZDR策略：disabled=关闭展示，enabled=开启展示，默认disabled';
```

坏：platform-gateway 新增 models 路由

好：

```json
{
  "path": "/maas/zdr/v1/models",
  "match_type": "exact",
  "http_methods": ["GET"],
  "downstream_service": "http://maas-svc:9998",
  "middleware_chain": [{"type": "AuthN_APIKey"}]
}
```

坏：处理逻辑：1. 按 `source_model_name` 查询源模型，校验 `model_env = "online"`。2. 解析 RFC3339 的 `base_updated_at`……（共 6 步）

好：创建时校验源模型为线上、目标模型为测试；用 `base_updated_at` 做乐观锁，冲突时要求前端重拉；重复提交按成功返回。

坏：`EngineEffectiveUpdatedAt` 的四步计算、cache 结构体、70 秒上界推导

好：目标模型或其 Channel 变更后约 1 分钟内生效，期间可能新旧复制规则并存。

坏：`2. MaaS：发布 zdr_policy 字段、用户侧 Tag 过滤和 GET /maas/zdr/v1/models。`

好：`2. maas更新服务`

坏：`5. platform-gateway：注意稳定版和灰度版的下游不同，配置后检查路由是否生效。`

好：`5. platform-gateway：gateway_config_stable.routes 与 gateway_config_canary.routes 各追加以下路由。`

完整示例：

1. MySQL：执行以下 DDL。

   ```sql
   ALTER TABLE `maas_tenant_config`
     ADD COLUMN `zdr_policy` VARCHAR(32) NOT NULL DEFAULT 'disabled'
       COMMENT '租户ZDR策略：disabled=关闭展示，enabled=开启展示，默认disabled';
   ```

2. maas更新服务
3. 添加 zdr model tag
4. maas-gateway更新服务
5. platform-gateway：`gateway_config_stable.routes` 与 `gateway_config_canary.routes` 各追加以下路由。

   ```json
   {
     "path": "/maas/zdr/v1/models",
     "match_type": "exact",
     "http_methods": ["GET"],
     "downstream_service": "http://maas-svc:9998",
     "downstream_path": "",
     "middleware_chain": [{"type": "AuthN_APIKey"}]
   }
   ```

   灰度版 `downstream_service` 使用 `http://maas-pre-svc:9998`。

## 交付前自查

Run these checks and delete, do not reword:

- Is `实现` split by service, then by functional sub-point? Regroup if it is organized by
  DB / API / frontend, not split at all, or lumped into one block per service when there are
  several changes.
- Does each `####` heading name the change itself rather than a template label like `接口调整` or
  `DB变更`? Rename it.
- Does every schema change have the real SQL, and every config change the real key and value? Add
  them if not.
- Does every behavior change state where it happens, what it reads, and what changes? Add one
  sentence of mechanism if not.
- Any `1. 2. 3.` step-by-step 处理逻辑 in prose? Compress it to one contract paragraph.
- Any function call chain, layer-reuse note, cache structure, lock design, or timing derivation?
  Replace it with the observable result.
- Any Go, Java, or other language code block, or a struct definition? Delete it.
- Any table longer than 5 rows? Compress it.
- Any `*注意：` or bolded reminder? Delete it.
- Did you add `测试关注重点` without being asked? Delete it.
- Is every `上线单` entry an action? Keep verification and recovery actions when the design or
  the user requires them.
- Does `上线单` contain the final SQL and config values, repeated from `实现`?
- If an ordinary feature exceeds 2500 characters, cut detail that does not affect review or rollout.
- Does every remaining paragraph change a reviewer's decision? If not, delete it.

## 修订已有文档

Simplify the structure and remove detail rather than appending another explanation. Keep only the
current design and do not narrate superseded versions. Mention deferred work or an open question
only when it affects the current scope.

## 发布到飞书

When the user requests creation or editing in Feishu/Lark, use the `lark-doc` skill for its document
format and editing workflow. Use its supported PRD citation format. Otherwise, return Markdown.
