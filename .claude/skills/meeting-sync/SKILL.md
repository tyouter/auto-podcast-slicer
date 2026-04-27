---
name: meeting-sync
description: 'Auto-sync Feishu meeting minutes (妙记) → structured minutes → Kanban/Bitable tasks → wiki push → group notification. Trigger: /meeting-sync'
trigger: /meeting-sync
---

# /meeting-sync

Auto-discovers new Feishu meeting minutes (妙记), deduplicates, generates structured meeting minutes, extracts action items & decisions, maps them to Kanban/Bitable tasks, syncs to Feishu wiki, and sends group notifications with @mentions.

## Cross-Skill Dependencies

This SKILL inherits and MUST follow these hard rules from existing skills:

| Inherited Rule | Source |
|----------------|--------|
| Git safety: `git pull --ff-only` before any file modification | project-manager |
| Config cascade: `.env` → `sync-state.yaml` | feishu-sync |
| Kanban ↔ Bitable sync order: pull → Bitable→Kanban → edit → Kanban→Bitable → update timestamp | feishu-sync |
| Strip YAML frontmatter before Feishu doc push | feishu-sync |
| Use `folder_mappings` for wiki parent node (NOT root `wiki_token`) | feishu-sync |
| lark-cli 3-step health check | lark-shared |

## File Structure

| Path | Purpose |
|------|---------|
| `.claude/minutes-registry.json` | Dedup registry: processed `minute_token` + metadata |
| `Meetings/Video/` | Video meeting directory |
| `Meetings/Video/<YYYY-MM-DD>_<title-slug>/` | Per-meeting subdirectory |
| `Meetings/Video/<YYYY-MM-DD>_<title-slug>/transcript.md` | Structured transcript |
| `Meetings/Video/<YYYY-MM-DD>_<title-slug>/minutes.md` | Meeting minutes (decisions + actions) |

## Config Loading

Before any operation, load config in this priority:

1. **`.env`** — Read environment variables for Feishu/Bitable tokens:
   - `FEISHU_SPACE_ID`, `FEISHU_WIKI_TOKEN`
   - `BITABLE_BASE_TOKEN`, `BITABLE_BASE_URL`
   - `BITABLE_PROJECT_TABLE_ID`, `BITABLE_TASK_TABLE_ID`, `BITABLE_DAILY_TABLE_ID`, `BITABLE_DASHBOARD_ID`
   - `FEISHU_GROUP_CHAT_ID`

2. **`.claude/team-registry.json`** — Team member open_ids and group chat IDs

3. **`.claude/sync-state.yaml`** — Sync state: `folder_mappings`, `file_mappings`, `stats`

4. **`.claude/feishu-local.yaml`** — Personal overrides (optional, may not exist)

## Team Members

Read team member open_ids from `.claude/team-registry.json`:
```json
{
  "team": {
    "Ray": { "open_id": "ou_xxx" },
    "Jingchuang": { "open_id": "ou_xxx" }
  },
  "groups": {
    "BIT_AI": { "chat_id": "oc_xxx", "name": "BIT AI team" }
  }
}
```

For @mentions in group notifications, use `<at user_id="open_id">name</at>` format.

---

## Workflow

### Phase 0: Startup Checks (MUST execute first)

1. **Git safety**:
   ```bash
   cd "$(git rev-parse --show-toplevel)"
   git status
   git pull --ff-only 2>&1 || echo "PULL_FAILED"
   ```
   If PULL_FAILED: inform user, show `git diff --stat`, suggest `git commit` or `git stash`. **Do NOT auto reset/force.**

2. **Health check**:
   ```bash
   lark-cli --version
   lark-cli config show
   lark-cli auth list
   ```
   If any fails, prompt user to `lark-cli auth login`.

3. **Load config** (.env → team-registry.json → sync-state.yaml → feishu-local.yaml cascade)

4. **Check config exists**:
   - Verify `.env` exists with required variables
   - Verify `.claude/team-registry.json` exists
   - Verify `.claude/sync-state.yaml` exists
   - If any missing: suggest running `/setup` to complete initial configuration

5. **Initialize registry** if not exists:
   - Read `.claude/minutes-registry.json`
   - If not exists, write `{}`

### Phase 1: Minutes Discovery + Dedup

1. **Search minutes**:
   ```bash
   lark-cli minutes +search --query "BIT" --page-size 50
   ```
2. **Auto-paginate**: if `has_more=true`, continue fetching with next page until `has_more=false`
3. **Compare with registry**: filter out `minute_token`s already in `.claude/minutes-registry.json`
4. **If no new minutes**: output "无新会议" and exit

### Phase 2: Transcript Download + Minutes Generation (per new minute)

For each new `minute_token`:

1. **Get AI summary + transcript**:
   ```bash
   lark-cli vc +notes --minute-tokens <token>
   ```
   Returns AI summary + transcript file path (.txt)

2. **Read transcript .txt** → convert to Markdown format with speaker + timestamp:
   ```markdown
   ### [HH:MM:SS] Speaker Name
   transcript text here
   ```

3. **Create meeting directory**:
   ```
   Meetings/Video/<YYYY-MM-DD>_<title-slug>/
   ```
   - `<title-slug>`: simplified title (remove spaces, special chars, max 50 chars)

4. **Write `transcript.md`** with frontmatter:
   ```markdown
   ---
   type: meeting-transcript
   date: YYYY-MM-DD
   source: https://...feishu.cn/minutes/<token>
   minute_token: <token>
   ---
   ```

5. **Generate `minutes.md`** using AI analysis:
   - Read the AI summary from `lark-cli vc +notes` output
   - Read the full transcript
   - Analyze to extract: decisions, action items, task completions, new tasks/resolutions
   - Write using the template below

### Phase 3: Structured Content Extraction

From the generated minutes, extract:

- **Decisions**: agreements/decisions made in meeting (with project context, proposer)
- **Action Items**: tasks assigned to specific people (with owner, deadline, project, related task)
- **Task Completion Mentions**: cases where someone says "已完成 XX 任务"
- **New Tasks/Resolutions**: not in current Kanban or task-breakdown.json

### Phase 4: Map + Validate

1. **Map to existing tasks**:
   - Match action items against `0-Projects/Kanban.md` tasks and `0-Projects/Daily/task-breakdown.json`
   - Match rules: keyword similarity + assignee + date proximity
   - Record mapping in `minutes.md` table

2. **Completion validation** (for "已完成" mentions):
   - Check `task-breakdown.json` subtask status == "completed"
   - Check Bitable daily task table record status == "已完成"
   - Check local deliverable files exist (query by deliverable type)
   - If inconsistent: @assignee in group to remind

3. **New task/resolution handling**:
   - Generate structured resolution: `[项目] → [任务] → [Daily 拆解]`
   - **暂不写入** `task-breakdown.json`（留到 Phase 4b 确认后写入）
   - Record in `minutes.md` table（标记为 "待确认"）

### Phase 4b: Human Review（人工确认，必须）

**在写入 Kanban / Bitable / task-breakdown.json 之前，必须暂停并等待用户确认。**

1. **向用户展示拟变更内容**，按以下格式：

   ```
   ## 拟写入 Kanban 的变更

   ### 新增项目（如有关联）
   | 项目名称 | 负责人 | 截止时间 | 状态 |
   |----------|--------|----------|------|

   ### 新增任务
   | 任务 | 负责人 | 优先级 | 所属项目 | 截止时间 | 来源会议 |
   |------|--------|--------|----------|----------|----------|

   ### 关联到现有任务
   | 会议行动项 | → 关联任务 | 状态变更 |
   |------------|-----------|----------|

   ### 决策项（仅记录，不写入 Bitable）
   | 决策 | 所属项目 | 提出人 |
   |------|----------|--------|

   ### 任务完成校验
   | 提及完成项 | 校验结果 |
   |------------|----------|
   ```

2. **逐项确认**：用户可选择
   - `全部确认` → 进入 Phase 5
   - `跳过 X 项` → 排除指定项后继续
   - `修改 X 项` → 用户给出修正，重新生成后再确认
   - `取消` → 终止本次 sync，不写入任何文件

3. **用户确认后才可执行后续 Phase 5 的写入操作。未确认前，禁止修改 Kanban.md、task-breakdown.json、Bitable。**

### Phase 5: Write Kanban + Sync + Notify

> 仅在 Phase 4b 用户确认后才执行。

1. **Update Kanban（strict order）**:
   a. `git pull --ff-only`
   b. **Bitable → Kanban sync**:
      ```bash
      lark-cli base +record-list --base-token <token> --table-id "🚩 项目" --limit 100
      lark-cli base +record-list --base-token <token> --table-id "✅ 任务" --limit 200
      ```
      Merge into local `0-Projects/Kanban.md`（append new records, update status changes）
   c. **Append confirmed new tasks** to local Kanban（仅写入 Phase 4b 用户确认的条目）
   d. **Kanban → Bitable sync**:
      - New projects → `lark-cli base +record-create` to "🚩 项目" table
      - New tasks → `lark-cli base +record-create` to "✅ 任务" table
      - Updated records → `lark-cli base +record-update`
   e. **Update Kanban frontmatter** `last_sync` timestamp
   f. **Update Meeting Source Tracking** table: append row for this meeting

2. **Update `task-breakdown.json`** with confirmed new entries.

4. **Git commit** local changes:
   ```bash
   git add Meetings/ .claude/minutes-registry.json 0-Projects/Kanban.md 0-Projects/Daily/task-breakdown.json
   git commit -m "meeting-sync: <meeting-title> (<YYYY-MM-DD>)"
   ```

5. **Push minutes to Feishu wiki**:
   - Strip YAML frontmatter from `minutes.md`:
     ```python
     import re
     stripped = re.sub(r'^---\n.*?\n---\n', '', content, flags=re.DOTALL, count=1)
     ```
   - Determine parent folder from `sync-state.yaml` → `folder_mappings` (use the `feishu_node` for `3-Meetings` or equivalent folder)
   - Create document:
     ```bash
     lark-cli docs +create --markdown "$(cat stripped-minutes.md)"
     lark-cli wiki nodes +create --parent "<folder_feishu_node>" --obj_type docx --obj_token "<new_doc_token>"
     ```

6. **Update registry**:
   - Add entry to `.claude/minutes-registry.json`:
     ```json
     {
       "<minute_token>": {
         "title": "<meeting title>",
         "date": "YYYY-MM-DD",
         "minutes_doc_url": "<feishu wiki url>",
         "local_path": "Meetings/Video/<slug>/",
         "tasks_extracted": N,
         "processed_at": "ISO-8601 timestamp"
       }
     }
     ```

7. **Group notification** (read chat_id from `.claude/team-registry.json` or `FEISHU_GROUP_CHAT_ID` in `.env`):
   ```bash
   lark-cli im +messages-send --chat-id "<chat_id>" --markdown "<message>"
   ```

   Message format (Markdown):
   ```markdown
   ## 新会议纪要 — <title>

   📅 日期：YYYY-MM-DD | ⏱ 时长：XX 分钟
   🔗 [查看完整纪要](<feishu_doc_url>)

   ### 决策项
   - [decision 1]
   - [decision 2]

   ### 行动项
   - [ ] @<assignee1> task 1 (截止: YYYY-MM-DD)
   - [ ] @<assignee2> task 2 (截止: YYYY-MM-DD)

   ### 任务完成校验
   - <item>: <result>

   <at user_id="ou_xxx">name</at> 请关注以上行动项。
   ```

   Use `<at user_id="open_id">name</at>` format for @mentions based on team member open_ids from `.claude/team-registry.json`.

---

## Meeting Minutes Template (`minutes.md`)

```markdown
---
type: meeting-minutes
date: YYYY-MM-DD
duration: XX
attendees: [from transcript]
source: https://...feishu.cn/minutes/<token>
minute_token: <token>
---

# 会议纪要 — <会议标题>

**日期**：YYYY-MM-DD | **时长**：XX 分钟 | **来源**：[妙记链接](source_url)

## AI 总结
<AI summary from minutes>

## 章节摘要
<chapters if available>

## 决策项（Decisions）
| 决策 | 所属项目 | 提出人 |
|------|----------|--------|
| ... | ... | ... |

## 行动项（Action Items）
| 行动项 | 负责人 | 截止日期 | 所属项目 | 关联任务 | 状态 |
|--------|--------|----------|----------|----------|------|
| ... | ... | ... | ... | ... | 待执行 |

## 任务完成校验
| 提及完成项 | 负责人 | 本地状态 | Bitable状态 | 交付物 | 校验结果 |
|------------|--------|----------|-------------|--------|----------|
| ... | ... | ... | ... | ... | 一致/不一致 |

## 新增任务/决议
| 内容 | 所属项目 | 所属任务 | Daily 拆解 | Bitable 状态 |
|------|----------|----------|------------|-------------|
| ... | ... | ... | ... | 已创建/待创建 |

## 逐字稿
详见 `transcript.md`
```

---

## Lark CLI Reference

| Command | Purpose |
|---------|---------|
| `lark-cli minutes +search --query "..." --page-size 50` | Search minutes (paginate with `has_more`) |
| `lark-cli vc +notes --minute-tokens <token>` | Get AI summary + transcript file |
| `lark-cli docs +create --markdown "..."` | Create Feishu doc |
| `lark-cli wiki nodes +create --parent "<node>" --obj_type docx --obj_token "<token>"` | Add doc to wiki folder |
| `lark-cli im +messages-send --chat-id "<chat_id>" --markdown "..."` | Send group message |
| `lark-cli base +record-list --base-token <t> --table-id "<name>" --limit N` | List Bitable records |
| `lark-cli base +record-create --base-token <t> --table-id "<name>" --record '{...}'` | Create Bitable record |
| `lark-cli base +record-update --base-token <t> --table-id "<name>" --record-id <id> --record '{...}'` | Update Bitable record |

## Verification Checklist

1. `/meeting-sync` → auto-discovers new minutes, generates minutes, sends group notification
2. Second run → "无新会议" (dedup working)
3. `Meetings/Video/` → subdirectory with `transcript.md` + `minutes.md`
4. `.claude/minutes-registry.json` → processed tokens recorded
5. Feishu wiki → new minutes document created
6. BIT AI team group → Markdown summary with @mentions
7. `Kanban.md` → Meeting Source Tracking table updated
8. Bitable → task table + project table new records created
