---
name: lark-shared
version: 1.0.0
description: "飞书/Lark CLI 共享基础：应用配置初始化、认证登录（auth login）、身份切换（--as user/bot）、权限与 scope 管理、Permission denied 错误处理、安全规则。当用户需要第一次配置(`lark-cli config init`)、使用登录授权(`lark-cli auth login`)、遇到权限不足、切换 user/bot 身份、配置 scope、或首次使用 lark-cli 时触发。"
---

# lark-cli 共享规则

本技能指导你如何通过lark-cli操作飞书资源, 以及有哪些注意事项。

## 前置检查（每次使用本 skill 前必须执行）

**在调用任何飞书 API 之前，Agent 必须先运行健康检查，确保当前电脑已正确安装并配置 lark-cli。**

### Step 1: 检查 lark-cli 是否已安装

```bash
lark-cli --version
```

**如果命令不存在或报错**：说明 lark-cli 未安装。告知用户并引导安装：

> 当前电脑尚未安装 lark-cli（飞书 CLI）。请先执行以下命令安装：
> ```bash
> npm install -g @larksuite/cli
> ```
> 安装完成后，我们可以继续配置飞书连接。

**如果版本正常**：进入下一步。

### Step 2: 检查配置是否已初始化

```bash
lark-cli config show
```

**如果返回错误**或**缺少 appId**：说明尚未配置。引导用户初始化：

> 当前电脑尚未配置飞书应用。请提供飞书应用的 App ID 和 App Secret，我来帮你初始化。
> 或者你可以直接运行：
> ```bash
> lark-cli config init --new
> ```

**如果配置正常**：进入下一步。

### Step 3: 检查用户认证状态（如需 user 身份）

当操作需要 user 身份（如访问云空间文档、日历等），需确认用户已授权：

```bash
lark-cli auth list 2>/dev/null || echo "NOT_AUTHENTICATED"
```

**如果输出为空或报错**：说明用户尚未授权。引导用户登录：

> 当前电脑尚未完成飞书用户授权。我来帮你发起授权流程。
> ```bash
> lark-cli auth login --scope "docs:docs:readonly"
> ```

**如果已认证**：跳过认证步骤，直接使用。

### 检查总结

| 检查项 | 命令 | 失败处理 |
|--------|------|----------|
| CLI 安装 | `lark-cli --version` | 引导 `npm install -g @larksuite/cli` |
| 应用配置 | `lark-cli config show` | 引导 `lark-cli config init --new` |
| 用户认证 | `lark-cli auth list` | 引导 `lark-cli auth login --scope "..."` |

**重要规则**：
- 每次使用飞书相关功能前，Agent 应先执行上述检查，而不是直接调用 API 并等待报错
- 检查应在第一次调用飞书 skill 时执行，不需要每次操作都重新检查
- 如果用户说 "init" 或 "初始化"，直接执行完整的前置检查流程
- 如果用户已配置过，检查会秒级完成，不会产生额外开销

## 配置初始化

首次使用需运行 `lark-cli config init` 完成应用配置。

当你帮用户初始化配置时，使用background方式使用下面的命令发起配置应用流程，启动后读取输出，从中提取授权链接并发给用户：

```bash
# 发起配置（该命令会阻塞直到用户打开链接并完成操作或过期）
lark-cli config init --new
```

## 认证

### 身份类型

两种身份类型，通过 `--as` 切换：

| 身份 | 标识 | 获取方式 | 适用场景 |
|------|------|---------|---------|
| user 用户身份 | `--as user` | `lark-cli auth login` 等 | 访问用户自己的资源（日历、云空间等） |
| bot 应用身份 | `--as bot` | 自动，只需 appId + appSecret | 应用级操作,访问bot自己的资源 |

### 身份选择原则

输出的 `[identity: bot/user]` 代表当前身份。bot 与 user 表现差异很大，需确认身份符合目标需求：

- **Bot 看不到用户资源**：无法访问用户的日历、云空间文档、邮箱等个人资源。例如 `--as bot` 查日程返回 bot 自己的（空）日历
- **Bot 无法代表用户操作**：发消息以应用名义发送，创建文档归属 bot
- **Bot 权限**：只需在飞书开发者后台开通 scope，无需 `auth login`
- **User 权限**：后台开通 scope + 用户通过 `auth login` 授权，两层都要满足


### 权限不足处理

遇到权限相关错误时，**根据当前身份类型采取不同解决方案**。

错误响应中包含关键信息：
- `permission_violations`：列出缺失的 scope (N选1)
- `console_url`：飞书开发者后台的权限配置链接
- `hint`：建议的修复命令

#### Bot 身份（`--as bot`）

将错误中的 `console_url` 提供给用户，引导去后台开通 scope。**禁止**对 bot 执行 `auth login`。

#### User 身份（`--as user`）

```bash
lark-cli auth login --domain <domain>           # 按业务域授权
lark-cli auth login --scope "<missing_scope>"   # 按具体 scope 授权（推荐,符合最小权限原则）
```

**规则**：auth login 必须指定范围（`--domain` 或 `--scope`）。多次 login 的 scope 会累积（增量授权）。

#### Agent 代理发起认证（推荐）

当你作为 AI agent 需要帮用户完成认证时，使用background方式 执行以下命令发起授权流程, 并将授权链接发给用户：

```bash
# 发起授权（阻塞直到用户授权完成或过期）
lark-cli auth login --scope "calendar:calendar:readonly"

```


## 更新检查

lark-cli 命令执行后，如果检测到新版本，JSON 输出中会包含 `_notice.update` 字段（含 `message`、`command` 等）。

**当你在输出中看到 `_notice.update` 时，完成用户当前请求后，主动提议帮用户更新**：

1. 告知用户当前版本和最新版本号
2. 提议执行更新（CLI 和 Skills 需要同时更新）：
   ```bash
   npm update -g @larksuite/cli && npx skills add larksuite/cli -g -y
   ```
3. 更新完成后提醒用户：**退出并重新打开 AI Agent**以加载最新 Skills

**规则**：不要静默忽略更新提示。即使当前任务与更新无关，也应在完成用户请求后补充告知。

## 安全规则

- **禁止输出密钥**（appSecret、accessToken）到终端明文。
- **写入/删除操作前必须确认用户意图**。
- 用 `--dry-run` 预览危险请求。
