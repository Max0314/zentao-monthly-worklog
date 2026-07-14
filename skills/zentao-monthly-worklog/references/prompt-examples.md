# Prompt Examples

Recommend the confirmation-first prompt unless the user already approved a complete list.

## Analyze Only

```text
使用 $zentao-monthly-worklog 分析 2026 年 7 月的 AI 对话和 Git 变更。
结合各项目实际提交，整理需求、任务和 Bug，分类到对应迭代。
每项包含详细描述和逐条独立备注。先给我完整清单确认，不要上传禅道。
```

## No Codex Records

```text
使用 $zentao-monthly-worklog 整理 2026 年 7 月工作。没有 Codex 对话，请结合 Git 变更和以下部门职责生成候选清单：……。
缺少完成或修复证据的内容标记“待确认”，不要虚构已解决 Bug，不要上传禅道。
```

## Test Upload

```text
从已确认清单中各选 5 条需求、任务和 Bug 上传测试禅道。
每条完成步骤、解决步骤和伪代码都作为单独备注，完成任务、解决 Bug，并回查真实 commented 数量和 AI 评分。
```

## Formal Upload

```text
按已确认清单上传正式禅道。使用 formal_auto 自动选择内外网地址，逐条写备注，完成任务、解决 Bug，最后回查并列出真实 ID。
```

## Resume

```text
继续上次月度禅道上传。复用原 manifest，先核对服务端已有记录和备注再续传，禁止重复创建。
```
