---
name: zentao-monthly-worklog
description: Collect and analyze local Codex conversations and Git changes, draft monthly ZenTao stories, tasks, bugs, and individually scored comments, then upload and verify them with zentao_tool. Use when the user asks to summarize monthly work, find completed tasks or fixed bugs, classify work into ZenTao executions, create ZenTao records, add AI-scored comments, or verify a previous monthly upload.
---

# ZenTao Monthly Worklog

Use `D:\code_CPL\zentao_tool` as the deterministic collection and upload engine. Keep business configuration in its ignored `config.local.json`; do not put ZenTao addresses or credentials in this skill.

## Workflow

1. Enter `D:\code_CPL\zentao_tool` and run `python -m zentao_tool.cli show-config`.
2. Run `python -m zentao_tool.cli collect YYYY-MM` to create `output/YYYY-MM/evidence.json`.
3. Read the evidence and analyze both sources:
   - Use Codex user requests and final answers to recover intent, implementation steps, validation, and resolved symptoms.
   - Use Git commits and changed files to confirm scope, repositories, implementation evidence, and project ownership.
   - Deduplicate commits repeated across worktrees by commit hash.
4. Run `python -m zentao_tool.cli draft output/YYYY-MM/evidence.json` for a baseline, then rewrite `output/YYYY-MM/draft.json` using the rules below.
5. Run `validate` and `preview`. Show the complete proposed story/task/bug list to the user before any upload unless the user explicitly authorized the complete list in the current request.
6. After confirmation, run `upload`. Do not replace this command with ad hoc REST calls; it writes each scoreable comment separately and persists resume state.
7. Run `verify` against the generated manifest and report IDs, statuses, skipped duplicates, and failures.

## Draft Rules

- Group commits and conversations by business objective, not by individual file or commit.
- Create a story for a distinct new business capability or explicit requirement. Do not invent stories for routine refactoring.
- Create a task for implemented features, integrations, engineering improvements, migrations, or substantial analysis work.
- Create a bug only when evidence shows an incorrect behavior, reproducible symptom, regression, exception, data error, or compatibility problem that was fixed.
- Map each record through `config.local.json` repository and execution mappings. Leave uncertain items in `unclassified` and explain the missing mapping.
- Do not claim work that is unsupported by either conversations or Git evidence.
- Avoid duplicate titles in the same execution or product. Merge repeated worktree evidence.
- Preserve useful detail while excluding passwords, tokens, cookies, private keys, and unrelated personal data.

## Content Rules

For each task, provide `title`, a `detail` beginning with `【任务详细描述】`, and 3-8 independent comments beginning with `【任务完成步骤】`.

For each bug, provide a title stating component, symptom, and impact; a `detail` beginning with `【bug详细描述】`; separate `【bug解决步骤】` comments for verification, location, analysis, fix, and regression validation; and an independent `【伪代码】` comment.

For each story, provide a business-facing title, a `【需求详细描述】`, product ID, estimate, and optional independent implementation comments.

Never put all completion or resolution steps into the description. Never rely on finish-task or resolve-bug remarks for scoreable history. The upload command must create one `commented` action per comment through the ZenTao web action endpoint.

## Commands

```powershell
cd D:\code_CPL\zentao_tool
python -m zentao_tool.cli collect 2026-07
python -m zentao_tool.cli draft output\2026-07\evidence.json
python -m zentao_tool.cli validate output\2026-07\draft.json
python -m zentao_tool.cli preview output\2026-07\draft.json
python -m zentao_tool.cli upload output\2026-07\draft.json
python -m zentao_tool.cli verify records\manifests\2026-07-formal_internal.json
```

Place `--env test`, `--env formal_external`, or another global option before the subcommand.

## Failure Handling

- On upload failure, inspect the manifest entry and rerun the same upload command after fixing the cause. Preserve the manifest so completed comments are not repeated.
- If a title already exists, accept `skipped_existing` and verify the existing ID before deciding whether comments are missing.
- If test and production credentials differ, set `account` and `password` inside the corresponding environment node in `config.local.json`.
