---
name: setup
description: 'Guided one-prompt setup wizard for new project vaults. Creates skeleton, distributes skills, scaffolds config, runs health checks. Trigger: /setup'
trigger: /setup
---

# /setup

Guided setup wizard. Run this once after cloning the feishu-project-skills repo to set up a new project vault.

## Workflow

### Step 1: Detect Vault Path

Ask the user:

> What is the target vault directory? (Or press Enter to use the current working directory)

- If user provides a path, validate it exists (or offer to create it)
- If empty, use `$(pwd)` as the vault root

Store as `VAULT_ROOT`.

### Step 2: Create Vault Skeleton

Create the following directory structure under `VAULT_ROOT` (skip existing dirs):

```
VAULT_ROOT/
├── 0-Projects/Daily/
├── 1-Goals/
├── 2-Reports/Weekly/
├── 2-Reports/Monthly/
├── 3-Meetings/
├── 4-Risks/
├── 5-Team/
├── 6-Templates/
├── 7-Archive/
├── 8-Retrospective/
│   ├── Agent_Evolution/
│   ├── Decisions/
│   └── Lessons_Learned/
├── Meetings/Video/
└── .claude/skills/
```

Create `.claude/sync-state.yaml` from template (empty mappings):

```yaml
folder_mappings: []
file_mappings: []
feishu_only_docs: []
root_mappings: []
stats:
  total_syncs: 0
  successful_push: 0
  successful_pull: 0
  conflicts_detected: 0
  last_full_sync: ""
```

Confirm to user: "Vault skeleton created at `<VAULT_ROOT>`"

### Step 3: Create .gitignore

Create `.gitignore` at `VAULT_ROOT/.gitignore` from this content:

```
# Secrets — DO NOT commit
.env
*.secret

# Token-bearing configs
.claude/sync-state.yaml
.claude/team-registry.json
.claude/minutes-registry.json
.claude/feishu-local.yaml

# AI/IDE caches
.obsidian/copilot-index-*.json
.obsidian/.gitbook/
.obsidian/workspace-mobile.json

# OS junk
.DS_Store
Thumbs.db
desktop.ini

# Temporary files
*.tmp
*.swp
*~
```

### Step 4: Distribute Skills

Ask the user:

> Install skills at which level?
> - `local` — project-level (VAULT_ROOT/.claude/skills/) — recommended
> - `global` — system-level (~/.claude/skills/) — for multi-project use

Copy all 5 skills from this repo's `.claude/skills/` directory to the target:

- `meeting-sync/SKILL.md`
- `feishu-sync/SKILL.md`
- `project-manager/SKILL.md`
- `lark-shared/SKILL.md`
- `setup/SKILL.md`

Use the following commands:

```bash
# Determine source: the .claude/skills/ directory in THIS repo
SKILLS_SRC="$(git rev-parse --show-toplevel)/.claude/skills"

# For local install:
mkdir -p "${VAULT_ROOT}/.claude/skills"
cp -r "${SKILLS_SRC}"/* "${VAULT_ROOT}/.claude/skills/"

# For global install:
cp -r "${SKILLS_SRC}"/* ~/.claude/skills/
```

Confirm: "5 skills installed to `<target_path>`"

### Step 5: Generate .env Scaffold

Create `VAULT_ROOT/.env` from this repo's `templates/.env.example` (all values empty).

Show the user the file and explain each token:

```
.env created with empty values. Here's what each token means:

| Variable              | Where to find it                           |
|-----------------------|--------------------------------------------|
| FEISHU_SPACE_ID       | 飞书知识库 → 空间设置                        |
| FEISHU_WIKI_TOKEN     | 飞书知识库 → 根节点 URL 最后一段             |
| BITABLE_BASE_TOKEN    | 飞书多维表格 URL 中 /base/ 后面的部分        |
| BITABLE_BASE_URL      | 飞书多维表格完整域名 (feishu.cn 或 larksuite.com) |
| BITABLE_PROJECT_TABLE_ID | 多维表格项目表 ID                        |
| BITABLE_TASK_TABLE_ID | 多维表格任务表 ID                          |
| BITABLE_DAILY_TABLE_ID | 多维表格每日任务表 ID                      |
| BITABLE_DASHBOARD_ID  | 多维表格仪表盘 ID                          |
| FEISHU_GROUP_CHAT_ID  | 飞书群聊 URL 中的 oc_xxx 部分               |
```

### Step 6: Guide .env Filling

For each token, prompt the user one by one:

1. Ask: "Please provide `<TOKEN_NAME>` (来源: <source>)"
2. User provides value → write to `.env`
3. If user says "skip" or "not ready", leave empty and continue

After all tokens: show the filled `.env` (mask values) and ask for confirmation.

### Step 7: Generate team-registry.json Scaffold

Ask the user: "How many team members?" → then for each member:

1. Ask: "Member name?"
2. If lark-cli is available, offer to look up open_id:
   ```bash
   lark-cli contact user +search --query "<name>"
   ```
3. If not, ask user to provide open_id manually
4. Ask: "Role? (developer/designer/pm/other)"
5. Add to registry

Then ask: "What is the Feishu group chat ID? (oc_xxx)"

Create `VAULT_ROOT/.claude/team-registry.json`:

```json
{
  "team": {
    "MemberName": { "open_id": "ou_xxx", "role": "developer" }
  },
  "groups": {
    "BIT_AI": { "chat_id": "oc_xxx", "name": "Team name" }
  },
  "last_updated": "YYYY-MM-DD"
}
```

### Step 8: Create managed-projects.yaml

Create `VAULT_ROOT/.claude/managed-projects.yaml` from template (empty registry):

```yaml
managed_projects: []
```

Ask: "Any projects to track now? (provide paths, or skip)"

If paths provided, add entries with auto-generated IDs.

### Step 9: Run lark-cli Health Check

Run the 3-step health check (from lark-shared rules):

```bash
lark-cli --version
lark-cli config show
lark-cli auth list
```

For each failed step:
- **CLI not installed**: guide `npm install -g @larksuite/cli`
- **Config not initialized**: guide `lark-cli config init --new`
- **Not authenticated**: guide `lark-cli auth login --scope "docs:docs:readonly"`

If all pass: proceed.

### Step 10: Verify & Report

Output a summary:

```
## Setup Complete

Vault: <VAULT_ROOT>
Skills: installed to <local|global>
.env: <filled|partial> (<N>/<total> tokens)
Team: <N> members configured
lark-cli: <ready|needs attention>

Next steps:
- Run `/project-manager` to view dashboard
- Run `/meeting-sync` to discover meeting minutes
- Run `/sync-status` to check Feishu sync state
```

If any step was skipped or partially completed, clearly list what needs manual attention.
