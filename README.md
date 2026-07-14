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

可直接在仓库内运行：

```powershell
cd D:\code_CPL\zentao_tool
.\zentao.cmd show-config
```

也可以执行 `python -m pip install -e .`，然后全局使用 `zentao-tool`。

## 首次配置

推荐交互式初始化：

```powershell
zentao-tool init-config --workspace-root D:\code_CPL
```

程序会依次询问禅道用户名和密码；密码输入时终端不回显。配置写入被 Git 忽略的 `config.local.json`。也支持非交互参数，但密码会出现在终端历史中：

```powershell
zentao-tool init-config --account your-account --password your-password --workspace-root D:\code_CPL
```

默认环境是 `formal_auto`：

1. 先探测正式禅道内网 `http://10.70.33.19/biz`。
2. 内网不可达时自动改用正式禅道外网 `https://itms.changhongnetwork.net:28443/biz`。
3. 只在命令开始前选择一次地址；写入过程中不会切换，避免在网络抖动时重复创建数据。

陈鹏列或获授权的测试人员可显式选择测试禅道：

```powershell
zentao-tool --env test ping
zentao-tool --env test upload output\2026-07\draft.json
```

其他可选值为 `formal_auto`、`formal_internal`、`formal_external`。全局 `--env` 必须放在子命令前。检查配置和连接不会修改禅道数据：

```powershell
zentao-tool show-config
zentao-tool ping
```

## 每月使用

```powershell
zentao-tool collect 2026-07
zentao-tool draft output\2026-07\evidence.json
zentao-tool validate output\2026-07\draft.json
zentao-tool preview output\2026-07\draft.json
zentao-tool upload output\2026-07\draft.json
zentao-tool verify records\manifests\2026-07-formal_auto.json
```

`upload` 会显示完整清单，只有输入大写 `YES` 才写入。已确认的自动化场景可加 `--yes`。同一 manifest 重跑时会跳过已完成记录；禅道已有同迭代同标题记录时也会防止重复创建。

推荐让 Codex 使用本仓库提供的 `$zentao-monthly-worklog` Skill 完成证据分析和草稿润色，而不是直接采用基础 `draft` 命令生成的机械草稿。

## 无 Codex 记录

可以仅依据 Git 和人工输入整理候选清单：

```powershell
zentao-tool collect 2026-07 `
  --department "研发效能部，负责代码评审、SOP 和禅道 AI 建设" `
  --work-description "本月完善报表导出、评分队列和旧版 Excel 兼容"
```

也可以传入一个或多个外部证据文件：

```powershell
zentao-tool collect 2026-07 --context D:\exports\neocoder.jsonl --context D:\notes\july.md
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

`config.local.json` 中常用字段：

- `active_environment`：默认 `formal_auto`。
- `account`、`password`：通用禅道账号密码；也可在单个环境节点中覆盖。
- `environment_fallbacks`：环境别名与候选地址顺序。
- `workspace_root`：包含多个 Git 仓库的总目录。
- `codex_sessions_root`：Codex 会话目录。
- `git_authors`：仅保留匹配姓名或邮箱的提交；空数组表示不过滤。
- `executions`：迭代 ID、名称和产品 ID 映射。
- `repositories`：仓库名到迭代的分类，结尾 `*` 表示前缀匹配。
- `project_id`：创建 Bug 和需求时关联的项目 ID。

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

每条备注单独 POST。上传后必须执行 `verify`，以服务端对象 `actions` 中真实的 `commented` 数量为准，不能只依据 HTTP 200 或本地 manifest 判断成功。`zentao_MCP` 可作为后续接口增强，但不是当前上传主链路依赖。
