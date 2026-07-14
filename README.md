# zentao_tool

把本地 Codex 对话和多个 Git 仓库的月度变更整理为禅道需求、任务和 Bug，并批量上传、逐条写评分备注、完成任务、解决 Bug、回查结果。

## 已具备的完整链路

```text
Codex 会话 + Git 提交
        ↓ collect
    evidence.json
        ↓ draft / Codex Skill 整理
      draft.json
        ↓ validate + preview
      人工确认
        ↓ upload
禅道需求 / 已完成任务 / 已解决 Bug
        ↓ verify
      上传校验结果
```

任务的每条“完成步骤”、Bug 的每条“解决步骤”和“伪代码”都会单独调用网页备注接口，生成真实的 `commented` 历史动作，供备注 AI 评分。上传进度实时写入 manifest；网络中断后重跑可继续执行。

## 环境要求

- Windows 或 Linux，Python 3.10+
- 能访问所选禅道地址
- 不需要 Docker、浏览器或运行 `zentao_MCP`

不安装也可直接使用：

```powershell
cd D:\code_CPL\zentao_tool
.\zentao.cmd show-config
```

下文的 `zentao-tool` 均可替换为 `.\zentao.cmd` 或 `python -m zentao_tool.cli`。如希望全局使用 `zentao-tool`，可执行 `python -m pip install -e .`，并确保 Python 用户 Scripts 目录已加入 `PATH`。

## 一次性配置

交互式创建配置：

```powershell
zentao-tool init-config
```

程序会创建被 Git 忽略的 `config.local.json`，密码可以直接明文填写。也可以复制 `config.example.json` 后修改。

内置三套地址：

- `formal_external`：`https://itms.changhongnetwork.net:28443/biz`
- `formal_internal`：`http://10.70.33.19/biz`
- `test`：`http://10.70.33.18/biz`

默认环境由 `active_environment` 控制。单次切换环境时，把全局参数放在命令前：

```powershell
zentao-tool --env test ping
zentao-tool --env formal_external show-config
```

检查当前配置和连接，不会修改禅道数据：

```powershell
zentao-tool show-config
zentao-tool ping
```

## 每月使用

以 2026 年 7 月为例。

1. 采集 Codex 和 Git 证据：

```powershell
zentao-tool collect 2026-07
```

输出为 `output/2026-07/evidence.json`。采集器只读取 Codex 的用户消息、最终答复和 Git 提交，不读取推理内容；常见密码、Token 字段会自动脱敏。

2. 生成可编辑草稿：

```powershell
zentao-tool draft output/2026-07/evidence.json
```

输出为 `output/2026-07/draft.json`。命令行使用提交信息生成基础草稿；推荐让 Codex 调用 `zentao-monthly-worklog` Skill 结合对话上下文进一步合并、拆分和润色。

3. 校验与预览：

```powershell
zentao-tool validate output/2026-07/draft.json
zentao-tool preview output/2026-07/draft.json
```

校验规则包括：标题与描述必填、迭代/产品必填、任务至少两条完成备注、Bug 至少四条解决备注且必须包含伪代码、同一范围内标题不得重复。

4. 上传：

```powershell
zentao-tool upload output/2026-07/draft.json
```

程序先显示清单，输入大写 `YES` 后才写入。自动化场景可使用：

```powershell
zentao-tool upload output/2026-07/draft.json --yes
```

默认进度清单为 `records/manifests/2026-07-formal_internal.json`。同一清单可重复运行；已处理记录会跳过。若禅道中已存在同迭代、同标题记录，也会标记为 `skipped_existing`，避免重复创建。

5. 回查：

```powershell
zentao-tool verify records/manifests/2026-07-formal_internal.json
```

## 单独补备注

```powershell
zentao-tool comment task 88926 "【任务完成步骤】补充回归验证，确认旧版 Excel 可正常解析。"
zentao-tool comment bug 63812 "【bug解决步骤】回归旧版 xls、新版 xlsx 和历史模板。"
zentao-tool comment story 19422 "【需求实现说明】已确认验收口径。"
```

## 配置说明

`config.local.json` 中最常修改的字段：

- `active_environment`：默认环境。
- `account`、`password`：禅道账号密码。
- 环境节点内也可写 `account`、`password`，用于测试禅道和正式禅道账号不一致的情况。
- `workspace_root`：需要扫描 Git 仓库的总目录。
- `codex_sessions_root`：Codex 会话目录。
- `git_authors`：仅保留匹配这些姓名或邮箱的提交；空数组表示不过滤。
- `executions`：迭代 ID、名称和产品 ID 映射。
- `repositories`：仓库名称到迭代的分类；结尾 `*` 表示前缀匹配。
- `path_prefix`：当前三套环境均使用 `/biz`。如果某环境根路径直接就是禅道，将其改成空字符串。

Skill 的 `agents/openai.yaml` 只有显示名称和默认提示词，不保存业务配置。地址、账号、密码和迭代映射只维护在本工程的 `config.local.json`，Skill 会读取它。

安装后的 Skill 名称是 `$zentao-monthly-worklog`。在 Codex 中可以直接说：

```text
使用 $zentao-monthly-worklog 分析 2026-07 的 Codex 对话和 Git 变更，先列出需求、任务和 Bug 给我确认，不要立即上传。
```

确认清单后再说：

```text
按刚才确认的清单上传正式内网禅道，逐条写评分备注，完成任务、解决 Bug，并回查结果。
```

## 关键实现

REST API 用于查询、创建需求/任务/Bug和修改状态；网页 Token 接口用于写入真实备注：

```text
/action-comment-story-{storyID}.html
/action-comment-task-{taskID}.html
/action-comment-bug-{bugID}.html
```

每条备注单独 POST 一次：

```text
actioncomment=<p>单条备注内容</p>
```

`zentao_MCP` 可作为后续通用接口增强，但不是当前主链路依赖。
