# zentao_tool

Codex 工作记录转禅道任务/Bug 工具。

这个工程用于把本地 Codex 对话记录和各项目 Git 变更整理成禅道任务、Bug，并按“单条备注”写入任务完成步骤、Bug 解决步骤和伪代码，确保禅道历史记录产生真实的 `commented` 动作。

## 能力边界

- 查询禅道任务、Bug、迭代列表。
- 创建任务、创建 Bug。
- 将任务置为已完成，将 Bug 置为已解决。
- 通过禅道网页端接口逐条写备注，触发备注评分。
- 校验批量创建结果是否存在、状态是否正确。
- 保留历史批量创建脚本，便于复盘和复用。

## 环境要求

- Python 3.10+
- 能访问 `http://10.70.33.19/biz`
- 禅道账号密码通过环境变量提供

不需要 Docker，不需要浏览器，不依赖 zentao_MCP 服务启动。

## 快速使用

PowerShell:

```powershell
cd D:\code_CPL\zentao_tool
$env:ZENTAO_ACCOUNT='chenpenglie'
$env:ZENTAO_PASSWORD='你的禅道密码'
python -m zentao_tool.cli verify-june-2026
```

添加一条真实备注:

```powershell
python -m zentao_tool.cli comment task 88926 "【任务完成步骤】补充回归验证，确认旧版 Excel 可正常解析。"
python -m zentao_tool.cli comment bug 63812 "【bug解决步骤】验证方式：回归旧版 xls、新版 xlsx 和历史模板。"
```

## 关键设计

禅道 REST API 适合创建和改状态，但备注评分依赖网页端历史动作。备注必须走:

```text
/action-comment-task-{taskID}.html
/action-comment-bug-{bugID}.html
```

并且每条备注单独提交:

```text
actioncomment=<p>备注内容</p>
```

这样禅道历史记录里会产生 `由 陈鹏列 添加备注。`，对应动作是 `commented`。

## 目录说明

```text
zentao_tool/
  zentao_tool/                 可复用 Python 包
    client.py                  禅道 REST API 客户端
    web_comments.py            禅道网页备注客户端
    batch.py                   批量创建/校验辅助函数
    cli.py                     命令行入口
  scripts/
    zentao_june_records_helper.py  2026-06 已创建记录校验脚本迁移版
    verify_2026_06.py              2026-06 校验入口
  records/
    record-schema.example.json     批量记录配置格式样例
  config.example.json          迭代与产品映射样例
```

## 和 zentao_MCP 的关系

`zentao_MCP` 更适合作为 OpenAPI → MCP 的通用代理。这个工程沉淀的是“月度工作总结 → 禅道任务/Bug → 单条备注评分”的业务流程。

后续可以把 `web_comments.py` 的能力反哺到 zentao_MCP，新增 `add_task_comment`、`add_bug_comment`、`create_completed_task_with_comments`、`create_resolved_bug_with_comments` 等业务级 MCP 工具。

