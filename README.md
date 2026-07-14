# zentao-monthly-worklog

从 Codex、NeoCoder 等 AI 对话、Git 提交和人工工作描述中整理月度工作，生成禅道需求、任务、Bug 及逐条 AI 评分备注，并支持批量上传、断点续传和服务端回查。

## 工作链路

```text
AI 对话 + Git 提交 + 部门/工作描述
                -> collect -> evidence.json
                -> Skill 分析 -> draft.json
                -> validate + preview
                -> 用户确认
                -> upload -> 需求 / 已完成任务 / 已解决 Bug
                -> verify -> 标题、状态和 commented 备注回查
```

任务的每条 `【任务完成步骤】`，Bug 的每条 `【bug解决步骤】` 和 `【伪代码】` 都通过网页备注接口单独写入，形成真实的 `commented` 历史记录，以触发备注 AI 评分。上传进度实时写入 manifest，网络中断后可用同一命令续传。

## 环境要求

- Windows 或 Linux，Python 3.10+
- Git 在 `PATH` 中
- 能访问至少一个配置的禅道地址
- 不需要 Docker、浏览器或 `zentao_MCP`

工具可以克隆到任意目录，不依赖业务代码工作区：

```powershell
git clone git@github.com:Max0314/zentao-monthly-worklog.git
cd zentao-monthly-worklog
python -m pip install -e .
powershell -ExecutionPolicy Bypass -File .\scripts\install_skill.ps1
```

安装后可以在任意目录运行 `python -m zentao_tool.cli`。如果 Python 的 Scripts 目录已加入 `PATH`，也可以使用短命令 `zentao-tool`。Skill 默认使用前者，因此不依赖固定业务工作区或 Scripts 的 PATH 配置。

## 首次配置

推荐交互式初始化：

```powershell
python -m zentao_tool.cli init-config --workspace-root D:\your-workspace --git-author "Your Name"
```

程序会依次询问禅道用户名和密码；密码输入时终端不回显。配置默认写入当前用户目录的 `~/.zentao-monthly-worklog/config.local.json`，与工具安装目录、业务代码目录相互独立。

也可以直接让 Agent 配置。用户可以在对话中提供账号、密码、代码根目录和 Git 作者，例如：

```text
使用 $zentao-monthly-worklog 完成首次配置。
禅道账号：your-account
禅道密码：your-password
代码工作区：D:\your-workspace
Git 作者：Your Name、your.email@example.com
先连接禅道并列出我可访问的迭代，不要创建数据。
```

Agent 会通过临时环境变量调用 `init-config`，密码不会写入 Skill 或仓库，但会以明文保存在用户自己的配置文件中。也支持非交互参数，但密码会出现在终端历史中：

```powershell
python -m zentao_tool.cli init-config --account your-account --password your-password --workspace-root D:\your-workspace
```

查看可访问的产品、项目和迭代，然后建立本地分类映射：

```powershell
python -m zentao_tool.cli list-scopes --limit 1000
python -m zentao_tool.cli configure-execution review 1708 "代码评审迭代" 654 `
  --repository "ai_code_review*" --project-id 1292
```

如果测试禅道的迭代 ID 与正式禅道不同，使用环境级映射：

```powershell
python -m zentao_tool.cli --env test configure-execution review 2708 "测试代码评审迭代" 754 `
  --repository "ai_code_review*" --project-id 2292
```

当归属不明确时，Agent 必须把候选迭代给用户确认；不得沿用其他人的个人迭代映射。

默认环境是 `formal_auto`：

1. 先探测正式禅道内网 `http://10.70.33.19/biz`。
2. 内网不可达时自动改用正式禅道外网 `https://itms.changhongnetwork.net:28443/biz`。
3. 只在命令开始前选择一次地址；写入过程中不会切换，避免在网络抖动时重复创建数据。

陈鹏列或获授权的测试人员可显式选择测试禅道：

```powershell
python -m zentao_tool.cli --env test ping
python -m zentao_tool.cli --env test upload output\2026-07\draft.json
```

其他可选值为 `formal_auto`、`formal_internal`、`formal_external`。全局 `--env` 必须放在子命令前。检查配置和连接不会修改禅道数据：

```powershell
python -m zentao_tool.cli show-config
python -m zentao_tool.cli ping
```

## 每月使用

```powershell
python -m zentao_tool.cli collect 2026-07
python -m zentao_tool.cli inspect-evidence output\2026-07\evidence.json --repository bi_center --query 测试 --query 部署
python -m zentao_tool.cli draft output\2026-07\evidence.json
python -m zentao_tool.cli validate output\2026-07\draft.json
python -m zentao_tool.cli preview output\2026-07\draft.json
python -m zentao_tool.cli upload output\2026-07\draft.json
python -m zentao_tool.cli verify records\manifests\2026-07-formal_auto.json `
  --wait-ai-score 180 --require-ai-score
```

`upload` 会显示完整清单，只有输入大写 `YES` 才写入。已确认的自动化场景可加 `--yes`。同一 manifest 重跑时会跳过已完成记录，并先按服务端真实备注恢复进度。禅道已有同范围同标题记录时默认停止；确认该记录确实属于当前清单后，才可使用 `--adopt-existing` 补齐备注和状态。

默认 `collect` 生成紧凑证据：

- `evidence.json` 只包含会话首尾摘要、测试/部署/修复信号和明细路径。
- 完整的用户消息与最终答复保存在 `details/sessions/`，不会丢失。
- 会话按每条消息在配置时区中的月份归档，跨月长会话不会因起始目录不同而漏采或串月。
- Git 提交在采集阶段按 commit hash 去重，同一仓库的多个 worktree 自动归并。
- `draft` 中的 `bug_candidates` 只是待核实索引，不会再把所有 `fix:` 提交伪装成已解决 Bug；对应提交仍保留在任务基线中，避免未晋级 Bug 时工作消失。

需要核实具体上下文时，使用一次有字符预算的 `inspect-evidence`，不要让 Agent 逐个打开所有会话。只有明确进行取证或调试时才使用 `collect --full`。

推荐让 Codex 使用本仓库提供的 `$zentao-monthly-worklog` Skill 完成证据分析和草稿润色，而不是直接采用基础 `draft` 命令生成的机械草稿。

## 无 Codex 记录

可以仅依据 Git 和人工输入整理候选清单：

```powershell
python -m zentao_tool.cli collect 2026-07 `
  --department "研发效能部，负责代码评审、SOP 和禅道 AI 建设" `
  --work-description "本月完善报表导出、评分队列和旧版 Excel 兼容"
```

也可以传入一个或多个外部证据文件：

```powershell
python -m zentao_tool.cli collect 2026-07 --context C:\exports\neocoder.jsonl --context C:\notes\july.md
```

支持 UTF-8 的 `.json`、`.jsonl`、`.md`、`.txt`。JSON/JSONL 中常见的 `role`、`author`、`text`、`message`、`content`、`messages` 和 `sessions` 结构会被归一化，因此可用于 NeoCoder 或其他 AI 编码工具的导出记录。工具不会直接扫描尚未公开或不稳定的 NeoCoder 私有存储格式；无法导出时可先整理成 Markdown 或通用 JSONL。

这里的“兼容”分两层：证据采集和禅道上传 CLI 不依赖 Codex，可以由 NeoCoder 等工具调用；`SKILL.md` 是否能被其他工具原生识别取决于它是否支持 Codex Skill 规范，不支持时仍可让它读取本 README 并执行同一组 CLI 命令。

只有部门职责时，可以生成“待确认的需求/任务/Bug 候选”，但不能据此断言某项工作已经完成或某个 Bug 已解决。已完成状态、问题现象、修复步骤和验证结论应由 Git、对话、测试记录或用户补充证实。

## 推荐提示词

首次分析，只生成清单：

```text
使用 $zentao-monthly-worklog 分析 2026 年 7 月的 AI 对话和 Git 变更。
结合各项目实际提交，整理需求、任务和 Bug，分类到对应迭代。
每项都包含详细描述和逐条独立备注。先给我完整清单确认，不要上传禅道。
```

没有对话记录时：

```text
使用 $zentao-monthly-worklog 整理 2026 年 7 月工作。没有 Codex 对话，请结合 Git 变更和以下部门职责生成候选清单：……。
对缺少完成证据的内容标记“待确认”，不要虚构已解决 Bug，也不要上传禅道。
```

上传测试禅道：

```text
从刚才确认的清单中各选 5 条需求、任务和 Bug，上传测试禅道。
每条完成步骤、解决步骤和伪代码都写成单独备注，完成任务、解决 Bug，并回查 commented 数量和 AI 评分。
```

上传正式禅道：

```text
按已确认清单上传正式禅道。使用 formal_auto 自动选择内外网地址，逐条写备注，完成任务、解决 Bug，最后回查并列出真实 ID。
```

恢复中断：

```text
继续上次 2026 年 7 月的禅道上传。保留并复用原 manifest，先核对服务端已有记录和备注，再续传，禁止重复创建。
```

## 配置项

`~/.zentao-monthly-worklog/config.local.json` 中常用字段：

- `active_environment`：默认 `formal_auto`。
- `account`、`password`：通用禅道账号密码；也可在单个环境节点中覆盖。
- `environment_fallbacks`：环境别名与候选地址顺序。
- `workspace_root`：包含多个 Git 仓库的总目录。
- `codex_sessions_root`：Codex 会话目录。
- `timezone`：消息归月时区，默认 `Asia/Shanghai`。
- `git_authors`：仅保留匹配姓名或邮箱的提交；空数组表示不过滤。
- `executions`：迭代 ID、名称和产品 ID 映射。
- `repositories`：仓库名到迭代的分类，结尾 `*` 表示前缀匹配。
- `project_id`：创建 Bug 和需求时关联的项目 ID。
- 单个 `environments.<name>` 下可以覆盖 `project_id`、`executions` 和 `repositories`，用于测试与正式禅道 ID 不一致的情况。

Skill 自身不保存账号、密码和业务映射，只读取本工具的本地配置。更新 Skill：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_skill.ps1
```

## 使用前还要确认

- 迭代、产品、项目 ID 和仓库映射是否属于当前用户。
- `git_authors` 是否会遗漏别名邮箱，或在共享电脑上误收集他人提交。
- 月份和本地时区是否符合统计口径。
- 正式上传前是否已展示完整清单并得到确认。
- 是否存在同标题旧记录；恢复上传时必须保留原 manifest。
- 外部 AI 导出和人工描述是否包含密码、客户数据等敏感内容；采集器会做基础脱敏，但不能替代人工检查。
- 外部 HTTPS 证书是否被当前机器信任；只有明确了解风险时才关闭 `verify_tls`。

## 实现说明

REST API 用于查询、创建和更新状态；网页登录会话用于调用：

```text
/action-comment-story-{storyID}.html
/action-comment-task-{taskID}.html
/action-comment-bug-{bugID}.html
```

每条备注单独 POST。Manifest 会绑定测试/正式目标、账号、月份和记录内容摘要；恢复时先按服务端 `actions` 中的备注内容摘要对账。上传后必须执行 `verify`，不能只依据 HTTP 200 或本地进度判断成功。`zentao_MCP` 可作为后续接口增强，但不是当前上传主链路依赖。

面向首次试用人员的完整说明见 [docs/trial-guide.md](docs/trial-guide.md)。
