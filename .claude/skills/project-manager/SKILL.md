---
name: project-manager
description: Manage project vault dashboard, OKR tracking, reports, risks, daily TODO generation, task planning, and read-only git scanning of managed projects.
trigger: /project-manager
---

# /project-manager

Manage the project management vault: dashboard, OKR tracking, reports, risks, kanban board, daily TODO generation, task planning, velocity tracking, and Feishu Bitable bidirectional sync.

## 启动流程（每次加载本 skill 时必须执行）

**当本 skill 被加载时，Agent 必须先执行以下前置检查，确保本地代码与远程仓库同步：**

```bash
cd "$(git rev-parse --show-toplevel)"
git status
git pull --ff-only 2>&1 || echo "PULL_FAILED"
```

**处理逻辑：**
- 如果 `git pull` 成功（输出包含 "Already up to date" 或 "Fast-forward"）：本地已是最新，继续正常操作
- 如果 `PULL_FAILED`（如有未提交变更导致冲突）：
  1. 告知用户："本地有未提交的变更，与远程存在冲突"
  2. 显示 `git diff --stat` 让用户了解冲突范围
  3. 建议用户先 `git commit` 或 `git stash` 后再 pull
  4. **不要自动执行 git reset 或 --force**
- 如果命令本身报错（如不是 git 仓库、网络错误）：记录错误，继续执行（不阻塞用户操作）

**注意**：auto-pull 只影响 vault 自身的代码同步，不影响 managed projects（managed projects 的 git 操作始终只读）。

### Config Loading (before any Feishu/Bitable operation)

Read config in priority order:
1. `.env` — environment variables for Feishu/Bitable tokens
2. `.claude/team-registry.json` — team member open_ids + group chat IDs
3. `.claude/sync-state.yaml` — folder_mappings, file_mappings, stats
4. `.claude/feishu-local.yaml` (personal override, may not exist)

Agent must check `.env` first for tokens, then fall back to `sync-state.yaml` for mapping data.

**If any config file is missing**: suggest running `/setup` to complete initial configuration.

## Usage

```
/project-manager                              # Show dashboard (OKR, projects, kanban, risks)
/project-manager report weekly                # Generate weekly report
/project-manager report monthly               # Generate monthly report
/project-manager risk add <desc>              # Add new risk
/project-manager risk review                  # Review active risks
/project-manager okr update <KR> <val>        # Update KR progress
/project-manager sync                         # Git commit + push (vault only)
/project-manager export <format>              # Export for sharing (html/pdf/canvas)
/project-manager track <path>                 # Add project to managed registry
/project-manager untrack <id>                 # Remove project from registry
/project-manager list                         # Show managed projects
/project-manager scan                         # Scan all managed projects (read-only git)
/project-manager kanban                       # Show local kanban board
/project-manager kanban sync                  # Bidirectional sync: local kanban ↔ Feishu Bitable
/project-manager parse-meeting <file>         # Parse meeting notes, extract decisions + actions + risks
/project-manager task add <task>              # Add task to local kanban
/project-manager task status <id> <status>    # Update task status
/project-manager daily                        # Generate today's TODO for all members
/project-manager daily <person>               # Generate daily TODO for specific member
/project-manager daily <date> <person>        # View historical daily TODO for a date
/project-manager check-deadlines              # Check upcoming and overdue deadlines
/project-manager check-status                 # Check task status sync accuracy
/project-manager follow-up                    # Generate follow-up reminders for incomplete tasks
/project-manager velocity                     # View team productivity + trends
/project-manager velocity <person>            # View specific member's productivity details
/project-manager plan-sprint <goals...>       # Decompose goals into Sprint task list
/project-manager plan-task <description>      # Break a large task into sub-tasks
/project-manager retro agent                  # Record Agent evolution/changes
/project-manager retro lesson <topic>         # Record team Lessons Learned
/project-manager retro decision <topic>       # Record key decisions (ADR format)
/project-manager retro list                   # List all retrospective records
/project-manager retro sprint <N>             # Auto-generate Sprint retrospective report
```

## Vault Registry

| Vault ID | Path | Role |
|----------|------|------|
| `project-management` | `$(git rev-parse --show-toplevel)` | Team PM |

## Kanban Board Management

### Kanban File Location
`0-Projects/Kanban.md` — single-source-of-truth markdown kanban board synced with Feishu Bitable.

### Kanban Structure
```markdown
---
type: kanban
project: "AI Automotive Consulting Agent"
last_sync: "2026-04-16T00:00:00"
bitable_url: "<bitable_url>"
bitable_token: "<bitable_token>"
bitable_project_table: "🚩 项目"
bitable_task_table: "✅ 任务"
---

# Project Kanban

## Projects
| 项目名称 | 状态 | 总负责人 | 截止时间 | 对应任务IDs |

## Tasks
| 任务 | 状态 | 优先级 | 执行人 | 所属项目 | 开始时间 | 截止时间 |
```

### Task Status Mapping
| Local | Feishu Bitable |
|-------|----------------|
| `未开始` | `未开始` |
| `进行中` | `进行中` |
| `已完成` | `已完成` |
| `已取消` | `已取消` |

### Project Status Mapping
| Local | Feishu Bitable |
|-------|----------------|
| `未启动` | `未启动` |
| `进行中` | `推进中` |
| `已完成` | `已完成` |

### Kanban Commands

**Show Kanban** (`/project-manager kanban`):
1. Read `0-Projects/Kanban.md`
2. Parse frontmatter for bitable config
3. Display projects and tasks grouped by status
4. Show sync status

**Sync Kanban** (`/project-manager kanban sync`) — Bidirectional:
1. Read local `0-Projects/Kanban.md`
2. Fetch current data from Feishu Bitable:
   ```bash
   lark-cli base +record-list --base-token <token> --table-id "🚩 项目" --limit 100
   lark-cli base +record-list --base-token <token> --table-id "✅ 任务" --limit 200
   ```
3. **Diff detection**: Compare local vs remote records by task/project name
4. **Local → Feishu** (push):
   - New local tasks → `lark-cli base +record-create`
   - Updated local tasks → `lark-cli base +record-update`
5. **Feishu → Local** (pull):
   - New remote tasks → append to Kanban.md
   - Updated remote tasks → update Kanban.md
6. Write merged data to `0-Projects/Kanban.md`
7. Update frontmatter `last_sync` timestamp
8. Update `sync-state.yaml` with new stats

**Parse Meeting** (`/project-manager parse-meeting <meeting-file>`):
1. Read meeting notes from `3-Meetings/<file>`
2. Extract **5 categories** of information:
   - **决策（Decisions）**：谁决定了什么，结论是什么
   - **Action Items**：含负责人、截止日期、状态、优先级
   - **风险信号（Risk Signals）**：谁说了"有风险"、"来不及"、"搞不定"
   - **人员变更（Assignment Changes）**：任务换人了、新增负责人
   - **依赖关系（Dependencies）**：A 等 B 完成才能开始
3. Cross-reference with existing Kanban (skip duplicates by name match)
4. Add new tasks/projects to Kanban
5. Update statuses of existing items if meeting indicates completion
6. Record decisions and risk signals in `8-Retrospective/Decisions/` and `4-Risks/`
7. Run `kanban sync` to push changes to Feishu Bitable

**Add Task** (`/project-manager task add <task>`):
1. Parse task description for metadata (assignee, deadline, priority, project)
2. Add to Kanban.md tasks table
3. Sync to Feishu Bitable
4. Define deliverable type (code/doc/meeting) for verification

**Update Task** (`/project-manager task status <task-name> <status>`):
1. Find task in Kanban.md by name
2. Update status field
3. Sync to Feishu Bitable
4. If status → 已完成，run deliverable verification

### Feishu Bitable Integration

Read Bitable config from `.env` (tokens) and `.claude/sync-state.yaml` (mappings), with optional override from `.claude/feishu-local.yaml`.

## Git Safety Rules

### STRICT READ-ONLY POLICY

The agent **NEVER** modifies managed projects. Only these read commands are allowed:

| Safe Command | Purpose |
|--------------|---------|
| `git status` | Check working tree state |
| `git branch -a` | List all branches |
| `git log --oneline -n 20` | Recent commits |
| `git log <branch> --oneline` | Branch commit history |
| `git diff --stat` | Uncommitted changes summary |
| `git remote -v` | Remote repository URLs |

### Forbidden Actions on Managed Projects
- `git commit` - NEVER
- `git push` - NEVER
- `git reset` - NEVER
- `git checkout` - NEVER
- Any destructive git operation

### Git Sync (Vault Only)
The agent **CAN** commit/push the management vault itself:
```bash
cd "$(git rev-parse --show-toplevel)"
git status
git add -A
git commit -m "Vault sync: $(date '+%Y-%m-%d') - Weekly update"
git push origin main
```

## Commands

### Dashboard (`/project-manager`)

When invoked without arguments, show the project dashboard:

1. **Read OKR Progress**
   Use Dataview query from `Dashboard.md` to aggregate OKR status.

2. **Read Project Status**
   Use Dataview query from `Dashboard.md` to show active projects.

3. **Read Risk Alert**
   Use Dataview query from `Dashboard.md` for critical/high risks.

4. **Output Format**
   ```
   ## Project Vault Dashboard

   ### OKR Progress
   - Overall: X%
   - Top KRs: {list}
   - At-risk KRs: {below 50%}

   ### Active Projects ({count})
   | Project | Status | Progress | Owner | Risk |

   ### Risk Alert
   - Critical/High count
   - Escalating risks

   ### Next Actions
   {AI recommendations}
   ```

### Weekly Report (`/project-manager report weekly`)

1. Create new weekly report file in `2-Reports/Weekly/`
2. Use Template: `Weekly_Report_Template.md`
3. Filename: `YYYY-W{n}_Weekly_Report.md`
4. Populate with Dataview queries
5. Summarize changes from last week

### Monthly Report (`/project-manager report monthly`)

1. Create new monthly report file in `2-Reports/Monthly/`
2. Use Template: `Monthly_Report_Template.md`
3. Filename: `YYYY-MM_Monthly_Report.md`
4. Analyze OKR execution, milestones, resources
5. Generate strategic recommendations

### Risk Management

**Add Risk** (`/project-manager risk add <description>`):
1. Create file in `4-Risks/` using `Risk_Template.md`
2. Filename: `R{timestamp}_{short-desc}.md`
3. Auto-assign risk_id
4. Extract severity/probability from context

**Review Risks** (`/project-manager risk review`):
1. Query all active risks
2. Sort by severity
3. Check mitigation status
4. Recommend actions for stale risks

### OKR Update (`/project-manager okr update <KR-id> <value>`)

1. Find target OKR file
2. Update specified KR progress value
3. Update frontmatter `progress` field
4. Add entry to progress tracking table

### Git Sync (`/project-manager sync`)

**Vault Only** - Never sync managed projects:
```bash
cd "$(git rev-parse --show-toplevel)"
git status
git add -A
git commit -m "Vault sync: $(date '+%Y-%m-%d') - Weekly update"
git push origin main
```

### Managed Projects Registry

**Track** (`/project-manager track <path>`):
1. Read `managed-projects.yaml`
2. Add new project entry
3. Generate unique project ID
4. Set default tracking options

**Untrack** (`/project-manager untrack <id>`):
1. Read `managed-projects.yaml`
2. Remove project entry by ID
3. Keep historical data (don't delete files)

**List** (`/project-manager list`):
Show all managed projects from registry.

### Scan (`/project-manager scan`)

**Read-Only Git Scanning** of managed projects:

1. Read `managed-projects.yaml` for project list
2. For each project with `track_status: true`:
   - Run `git status` (safe)
   - Run `git log --oneline -n 10` (safe)
   - Run `git branch -a` (safe)
3. Calculate stale days from last commit
4. Generate scan report:

```
## Managed Projects Scan - {date}

### Project Status Overview
| Project | Branch | Last Commit | Uncommitted | Stale Days |

### Stale Project Alert
- {projects with stale > 3 days}

### Branch Activity
- {branch counts per project}

### Weekly Commit Summary
- {commit counts per project}

### Recommendations
- {AI recommendations based on scan}
```

---

## Daily TODO Generation & Tracking

### Tracking Storage (Dual-Write)

每日任务分配需**同时写入两个地方**：

1. **本地 MD 文件**：`0-Projects/Daily/YYYY-MM-DD.md` — 可被 Obsidian 查看、Dataview 查询、Git 追踪
2. **飞书 Bitable 表**：`📅 每日任务` — 团队在线查看、实时更新、筛选过滤

每日首次生成时自动创建当日文件，后续再次运行 `daily` 追加/更新记录。

### Bitable `📅 每日任务` 表字段定义

| 字段名 | 类型 | 说明 |
|--------|------|------|
| 日期 | 日期 | 任务分配日期 |
| 成员 | 人员 | 被分配的团队成员 |
| 所属任务 | 关联字段 → `✅ 任务` | 关联到现有任务表的原始任务 |
| 今日优先级 | 单选: P0/P1/P2 | 当天的优先级，可能与原任务不同 |
| 预计耗时 | 数字（小时） | 今天预计花费的时间 |
| 交付物类型 | 单选: code/doc/meeting | 任务完成需要提交的交付物类型 |
| 状态 | 单选: 待完成/进行中/已完成 | 今日任务状态 |
| 阻塞原因 | 文本 | 如果有阻塞，说明原因 |
| 完成时间 | 日期时间 | 实际完成时间 |
| 备注 | 文本 | AI 生成的建议或备注 |

### Local MD File Format (`0-Projects/Daily/YYYY-MM-DD.md`)

```markdown
---
type: daily
date: YYYY-MM-DD
generated: "2026-04-18T09:00:00"
updated: "2026-04-18T09:00:00"
---

# Daily Tasks — 2026-04-18

## Ray

| 任务 | 优先级 | 所属项目 | 截止 | 预计耗时 | 交付物 | 状态 | 备注 |
|------|--------|----------|------|----------|--------|------|------|
| 发布日历+hook日历 | P0 | Develop Sprint | 4/28 | 4h | code | 待完成 | |

## Jingchuang
...

## Kat Jiang
...

## 吴雨柔
...
```

### `/project-manager daily` — Generate today's TODO for all members

**核心逻辑**：首次运行时，AI 基于对项目的理解，将 Kanban 上的大任务拆解到天粒度的子任务。后续每次运行时 review 之前的拆解结果，更新状态、调整未完成的任务。

1. Read Kanban from `0-Projects/Kanban.md`
2. Read velocity data from `.claude/velocity-data.json`
3. Get today's date
4. Check if `0-Projects/Daily/task-breakdown.json` exists:
   - **If YES** (已拆解过): 读取 + 执行增量扫描 + Review 状态
   - **If NO** (首次运行): AI 对每个未开始的任务进行天粒度拆解，生成 `0-Projects/Daily/task-breakdown.json`
5. **增量扫描（每次运行都执行）**:
   - 读取 Kanban 所有未完成（未开始/进行中）任务的 record_id
   - 与 `task-breakdown.json` 中已有的父任务 record_id 对比
   - 新增任务（在 Kanban 但不在 breakdown）→ AI 立即拆解为子任务 → 追加到 breakdown.json
   - 已消失任务（在 breakdown 但不在 Kanban）→ 标记 status: removed
   - 注意：增量扫描覆盖 Kanban 中**所有**未完成任务（单人任务 + 多人任务），不限于团队成员
6. For **首次运行 - 任务拆解**:
   - 对每个任务，基于 AI 对项目技术栈、依赖关系、任务描述的理解，拆解为 0.5~2 天粒度的子任务
   - 每个子任务包含：子任务标题、具体执行步骤、预估耗时、依赖项、交付物
   - 按任务截止时间和优先级排序，分配到具体日期
   - 保存为 `0-Projects/Daily/task-breakdown.json` 作为持久化拆解计划
   - 父任务的 `assignee` 字段：如果含逗号分隔的多人（如 "Ray, Jingchuang"），存为数组 `["Ray", "Jingchuang"]`；单人存为数组 `["Ray"]`
   - 每个子任务增加 `assignees` 数组字段，标明该子任务涉及的所有人（默认继承父任务 assignees）
7. For **后续运行 - Review 和更新**:
   - 读取 `task-breakdown.json` 中分配到今天的子任务
   - 检查之前日期的子任务完成情况（从 Bitable `📅 每日任务` 表读取状态）
   - 未完成的任务自动顺延到今天，AI 判断是否需要调整拆解
   - 如发现任务进度与预期不符（连续多天未完成），标记风险并建议重新拆解
8. **多人任务拆分规则**:
   - 检查每个子任务所属父任务的 `assignees` 字段
   - 如果 `assignees` 包含多人（如 `["Ray", "Jingchuang"]`）：
     a. 拆分为每人一条独立的 Bitable 记录（同一 record_id 的所属任务，但成员字段不同）
     b. 本地 MD 中每人的 TODO 列表都出现该子任务
     c. 如果子任务有明确的个人分工描述，在备注中标注 "与 XXX 协作"
   - 如果 `assignees` 只有一人：保持原逻辑
9. For each team member, compile today's sub-tasks:
   - Tasks from breakdown assigned to today
   - Overdue sub-tasks from previous days (⚠️)
   - Blocked sub-tasks
10. Sort by priority (P0 > P1 > P2), then deadline
11. **Dual-write**:
   - Write to `0-Projects/Daily/YYYY-MM-DD.md` (local tracking)
   - Write to Feishu Bitable `📅 每日任务` table (create new records or update existing)
   - 多人任务：每个成员创建独立的 Bitable 记录（同一所属任务，不同成员字段）
12. Update `task-breakdown.json` with completion status
13. Format output per member for display

**首次运行拆解示例**：
```
urlparser+llm-wiki (4/16-5/1, P0, ~8 天工作量)
→ 4/18-4/19: urlparser 路由设计和实现（解析 URL 结构）→ 交付：API endpoint
→ 4/21-4/22: wiki 搜索逻辑实现（关键词匹配 + 相似度搜索）→ 交付：搜索函数
→ 4/23-4/24: LLM prompt 工程（上下文组装 + 输出格式化）→ 交付：prompt 模板
→ 4/25-4/28: 集成测试 + 错误处理 → 交付：测试用例
→ 4/29-5/1: Bug 修复 + 性能优化 → 交付：性能基准
```

**后续运行 Review 示例**：
```
检查 4/18 拆解结果：
- urlparser 路由设计 ✅ 已完成（commit abc123）
- wiki 搜索逻辑 ⏳ 进行中（顺延到 4/19）
- 发现 wiki 搜索比预期复杂 → 建议拆分 4/19-4/22 两阶段

4/19 今日任务：
- [P0] wiki 搜索逻辑 - 阶段1（关键词匹配）← 从 4/18 顺延
```

**Output format:**
```
Ray，以下是你今天的任务（2026-04-18）：

📋 今日任务：
1. [P0] 发布日历+hook日历
   项目：Develop Sprint | 截止：4/28
   说明：建立发布会数据源接入框架
   预计耗时：4小时
   📎 交付物要求：代码提交到 automotive-consulting-agent 仓库（commit 记录）

⏰ 阻塞提醒：
- front-design 依赖 Kat Jiang 的设计稿（4/30 交付）

💡 建议：
- MVP 需求评审已过期，建议今天优先完成
```

### `/project-manager daily <person>` — Generate daily TODO for specific member

Same as above, but only output for the specified person.
Match person name case-insensitively against task assignees.
Still writes to both local MD and Bitable for tracking completeness.

### `/project-manager daily <date>` — View historical daily TODO

Read `0-Projects/Daily/YYYY-MM-DD.md` to see what was assigned on that date.
Also fetches from Bitable `📅 每日任务` table for comparison.

### `/project-manager daily <date> <person>` — View historical daily TODO for specific member

Same as above, filtered to a specific person.

---

## Deadline Checking

### `/project-manager check-deadlines` — Check upcoming and overdue deadlines

1. Read Kanban from `0-Projects/Kanban.md`
2. Get today's date
3. Categorize tasks:
   - **已过期（Overdue）**：deadline < today AND status != `已完成`
   - **3 天内到期（Due Soon）**：today <= deadline <= today + 3 days AND status != `已完成`
   - **本周到期（This Week）**：today <= deadline <= end of week AND status != `已完成`
4. Generate report:
   - Overdue tasks: mark ⚠️, show assignee + days overdue
   - Due soon tasks: show assignee + days remaining
   - Summary stats
5. Recommend actions: suggest reprioritizing overdue tasks

**Output format:**
```
## 截止日期检查（2026-04-17）

⚠️ 已过期任务（3 项）：
1. [P0] MVP 需求评审 — Ray | 截止：4/16 | 过期 1 天
2. [P0] 生成快速原型给Kat Jiang参考 — Ray | 截止：4/24 | 过期 0 天
...

⏰ 3 天内到期任务（2 项）：
1. [P1] brain storming — Kat Jiang | 截止：4/22 | 剩余 5 天
...

建议：
- 以上过期任务建议今天优先处理
```

---

## Status Checking

### `/project-manager check-status` — Check task status sync accuracy

1. Read local Kanban from `0-Projects/Kanban.md`
2. Fetch remote data from Feishu Bitable
3. Compare each task's status, assignee, deadline
4. Identify discrepancies:
   - Status mismatch (local vs remote)
   - Assignee mismatch
   - Deadline mismatch
5. Report findings and offer to sync

---

## Follow-up Reminders

### `/project-manager follow-up` — Generate follow-up reminders

1. Read Kanban from `0-Projects/Kanban.md`
2. Read velocity data
3. Generate reminders per member:
   - Tasks that are `进行中` for > 7 days without update (stuck risk)
   - Overdue tasks not yet completed
   - Tasks due within 3 days
   - Blocked tasks waiting on dependencies
4. Format as actionable reminders

**Output format:**
```
## 跟进提醒（2026-04-17）

🔴 Ray（3 项跟进）：
- [P0] MVP 需求评审 — 已过期 1 天，请尽快完成
- [P0] 生成快速原型给Kat Jiang参考 — 截止 4/24，剩余 7 天
- [P0] urlparser+llm-wiki — 截止 5/1，进行中超 7 天

🟡 Kat Jiang（2 项跟进）：
- [P1] brain storming — 截止 4/22，剩余 5 天
```

---

## Velocity Tracking

### `/project-manager velocity` — View team productivity overview

1. Read `.claude/velocity-data.json`
2. For each member:
   - Calculate current capacity (tasks/week)
   - Show velocity trend (last 4 weeks)
   - Identify underestimate patterns
3. Generate team summary:
   - Total tasks completed this sprint
   - Average velocity per member
   - Sprint capacity recommendation

### `/project-manager velocity <person>` — View specific member's productivity

1. Read `.claude/velocity-data.json`
2. Show member details:
   - Completed tasks history with estimated vs actual
   - Velocity trend chart (weekly)
   - Underestimate pattern analysis
   - Current capacity
3. Suggest adjustments for future Sprint planning

**Data source:** `.claude/velocity-data.json`

```json
{
  "members": {
    "Ray": {
      "completed_tasks": [
        {
          "task": "需求分析表和思维导图",
          "estimated_days": 1,
          "actual_days": 1,
          "completed": "2026-04-14",
          "deliverable_type": "code",
          "deliverable_verified": true,
          "deliverable_ref": "commit a84ca4d"
        }
      ],
      "velocity_trend": [
        {"week": "W16", "completed_count": 2, "avg_actual_days": 1.5}
      ],
      "current_capacity": "2 任务/周",
      "underestimate_pattern": "涉及外部沟通的任务通常慢 1.5x"
    }
  }
}
```

---

## Task Planning

### `/project-manager plan-sprint <goals...>` — Decompose Sprint goals into task list

1. Parse the goal description
2. Break into deliverables (each deliverable = 1-2 days of work)
3. For each deliverable, define:
   - Title, description
   - Assignee (suggest based on skills/availability)
   - Priority (P0/P1/P2)
   - Deadline (within Sprint range)
   - Dependencies
   - Deliverable type (code/doc/meeting)
4. Output as structured task list ready for Kanban entry
5. Suggest Sprint capacity based on velocity data

### `/project-manager plan-task <description>` — Break a large task into sub-tasks

1. Parse the task description
2. Break into sub-tasks (each = 0.5-2 days)
3. For each sub-task, define:
   - Title, description
   - Estimated time
   - Dependencies (order matters)
   - Deliverable type
4. Output as checklist

---

## Deliverable Verification Rules

When a task is marked as `已完成`, the Agent MUST verify the deliverable:

| Task Type | Deliverable | Verification Method |
|-----------|------------|---------------------|
| 开发类（代码/功能） | Code commit | `git log` check for relevant commits |
| 文档/设计类 | Feishu doc update | `docs +fetch` check last_modified time |
| 会议/沟通类 | Meeting notes/decisions doc | Check `3-Meetings/` or `8-Retrospective/` |
| 测试类 | Test files/results | Check test file existence + pass status |

**Rule: No deliverable = task not complete.** The Agent will not mark a task as completed based on verbal confirmation alone.

When verification succeeds: record `deliverable_verified: true` + `deliverable_ref` in velocity data.
When verification fails: remind the user that deliverable is missing, do not mark complete.

---

## Retrospective Mechanism

### `/project-manager retro agent` — Record Agent evolution

1. Create/update entry in `8-Retrospective/Agent_Evolution/`
2. Filename: `{date}_{short-title}.md`
3. Record: what changed, why, expected impact
4. Auto-triggered when SKILL.md itself is modified

### `/project-manager retro lesson <topic>` — Record Lessons Learned

1. Create entry in `8-Retrospective/Lessons_Learned/`
2. Use template from `Lesson_Template.md`
3. Auto-prompt user for: event description, root cause, action items
4. Auto-triggered when a task is marked complete — Agent checks if worth recording

### `/project-manager retro decision <topic>` — Record key decisions (ADR)

1. Create entry in `8-Retrospective/Decisions/`
2. Use template from `Decision_Template.md`
3. Auto-assign DEC-ID: `DEC-{date}-{seq}`

### `/project-manager retro list` — List all retrospective records

1. List files in `8-Retrospective/` subdirectories
2. Group by type: Agent Evolution, Lessons Learned, Decisions
3. Show date and title

### `/project-manager retro sprint <N>` — Auto-generate Sprint N retrospective

1. Read Kanban for tasks completed in Sprint N date range
2. Calculate: planned vs completed, velocity, overdue count
3. Generate report:
   - Sprint N summary (tasks completed, velocity, issues)
   - Lessons learned candidates
   - Recommendations for Sprint N+1
4. Save to `8-Retrospective/Agent_Evolution/sprint-{N}-retro.md`

### Auto-trigger Rules
- **SKILL.md modified** → auto-generate `Agent_Evolution` record
- **Task marked complete** → AI checks for notable Lessons Learned, prompts user
- **Sprint end date reached** → auto-generate Sprint retrospective draft

---

## Managed Projects Registry File

Located at: `.claude/managed-projects.yaml`

```yaml
managed_projects:
  - id: {unique-id}
    path: {absolute-path}
    name: {display-name}
    owner: {owner-name}
    priority: P0|P1|P2
    tracked_branches: [main, develop]
    track_commits: true
    track_status: true
```

## Memory System

| File | Purpose | Update Frequency |
|------|---------|------------------|
| `Context.md` | Current vault state | Daily |
| `Decision_Log.md` | Strategic decisions | When made |
| `WORKLOG.md` | Activity log | Weekly |
| `Strategic_Decisions.md` | Policy decisions | Monthly |

## Notes

- Obsidian CLI syntax available: `obsidian <command> vault=project-management`
- Graphify integration via `/graphify` skill
- Vault can be synced with team via Git
- All managed project git operations are **READ-ONLY**
