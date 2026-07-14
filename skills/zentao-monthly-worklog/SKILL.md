---
name: zentao-monthly-worklog
description: Collect and analyze Codex or other AI conversations, Git changes, and manual work context; draft monthly ZenTao stories, tasks, bugs, and individually scored comments; then upload and verify them with zentao_tool. Use when the user asks to summarize monthly work, generate work candidates from department context, classify work into ZenTao executions, create ZenTao records, add AI-scored comments, or verify a previous monthly upload.
---

# ZenTao Monthly Worklog

Use the installed `zentao_tool` Python package as the deterministic collection and upload engine. Invoke it as `python -m zentao_tool.cli`; the shorter `zentao-tool` entry point is optional because user-level Scripts directories may not be on `PATH`. Never assume a checkout path or require the user's repositories to live beside this skill. Keep per-user configuration in `~/.zentao-monthly-worklog/config.local.json`; never write credentials into the skill or a Git repository.

## Tool And Agent Setup

1. Run `python -m zentao_tool.cli --help`. If unavailable, check `ZENTAO_TOOL_HOME` for a checkout and install it with `python -m pip install -e <path>`. If neither exists, tell the user that the companion repository must be installed; do not search arbitrary business workspaces for it.
2. Run `python -m zentao_tool.cli show-config`. If configuration is absent, configure it on the user's behalf:
   - Reuse account, password, workspace root, and Git author aliases already supplied in the conversation.
   - Ask only for missing required values. The password may be supplied to the process as `ZENTAO_PASSWORD`; do not repeat it in progress or final messages.
   - Run `python -m zentao_tool.cli init-config --workspace-root <path> --git-author <name-or-email>`. `ZENTAO_ACCOUNT` and `ZENTAO_PASSWORD` are accepted for unattended Agent setup.
3. Run `python -m zentao_tool.cli ping`, then `python -m zentao_tool.cli list-scopes`. If execution ownership is not explicit, show likely iterations and ask the user to choose.
4. Configure confirmed mappings with `python -m zentao_tool.cli configure-execution <alias> <execution-id> <name> <product-id> --repository <pattern> [--project-id <id>]`.
5. Never copy another user's execution, product, project, repository, or Git-author mappings into a new user's configuration.

## Workflow

1. Run `python -m zentao_tool.cli show-config` and confirm the selected user configuration and workspace.
2. Run `python -m zentao_tool.cli collect YYYY-MM` to create `output/YYYY-MM/evidence.json`. Add `--context`, `--department`, or `--work-description` when Codex records are absent or incomplete.
3. Read the evidence and analyze both sources:
   - Use Codex user requests and final answers to recover intent, implementation steps, validation, and resolved symptoms.
   - Treat `external_contexts` as additional AI exports or user-supplied work evidence.
   - Use Git commits and changed files to confirm scope, repositories, implementation evidence, and project ownership.
   - Deduplicate commits repeated across worktrees by commit hash.
4. Run `python -m zentao_tool.cli draft output/YYYY-MM/evidence.json` for a baseline, then rewrite `output/YYYY-MM/draft.json` using the rules below.
5. Run `validate` and `preview`. Show the complete proposed story/task/bug list to the user before any upload unless the user explicitly authorized the complete list in the current request.
6. After confirmation, run `upload` with `formal_auto` or an explicit environment and a dedicated manifest. Do not replace this command with ad hoc REST calls; it writes each scoreable comment separately and persists resume state.
7. Run `verify` against the generated manifest. Treat the upload as successful only when titles, final task/Bug statuses, and every expected `commented` action match.
8. Spot-check `aiScore` on at least one story, task, and Bug when comment scoring is required.

## Draft Rules

- Group commits and conversations by business objective, not by individual file or commit.
- Create a story for a distinct new business capability or explicit requirement. Do not invent stories for routine refactoring.
- Create a task for implemented features, integrations, engineering improvements, migrations, or substantial analysis work.
- Create a bug only when evidence shows an incorrect behavior, reproducible symptom, regression, exception, data error, or compatibility problem that was fixed.
- Map each record through the current user's repository and execution mappings. Leave uncertain items in `unclassified` and explain the missing mapping.
- Do not claim work that is unsupported by either conversations or Git evidence.
- Department responsibilities alone may support proposed stories/tasks/Bugs, but label them `待确认`; never mark a task done or a Bug fixed without implementation and validation evidence.
- A Bug requires an observed symptom plus diagnosis/fix evidence. Do not turn every department responsibility or feature idea into a resolved Bug.
- Avoid duplicate titles in the same execution or product. Merge repeated worktree evidence.
- Preserve useful detail while excluding passwords, tokens, cookies, private keys, and unrelated personal data.

## Content Rules

For each task, provide `title`, a `detail` beginning with `【任务详细描述】`, and 3-8 independent comments beginning with `【任务完成步骤】`.

For each bug, provide a title stating component, symptom, and impact; a `detail` beginning with `【bug详细描述】`; separate `【bug解决步骤】` comments for verification, location, analysis, fix, and regression validation; and an independent `【伪代码】` comment.

For each story, provide a business-facing title, a `【需求详细描述】`, product ID, estimate, and optional independent implementation comments.

Never put all completion or resolution steps into the description. Never rely on finish-task or resolve-bug remarks for scoreable history. The upload command must create one `commented` action per comment through the ZenTao web action endpoint.

## Commands

```powershell
python -m zentao_tool.cli collect 2026-07
python -m zentao_tool.cli draft output\2026-07\evidence.json
python -m zentao_tool.cli validate output\2026-07\draft.json
python -m zentao_tool.cli preview output\2026-07\draft.json
python -m zentao_tool.cli upload output\2026-07\draft.json
python -m zentao_tool.cli verify records\manifests\2026-07-formal_auto.json
```

The default `formal_auto` probes the formal intranet first and uses the formal external endpoint when intranet access is unavailable. Selection happens before a command; never switch endpoints halfway through an upload. Place `--env test`, `--env formal_external`, or another global option before the subcommand. Use `test` only when the user explicitly requests or is authorized for the test system.

Read [references/prompt-examples.md](references/prompt-examples.md) when recommending a new-session prompt. Read [references/evidence-sources.md](references/evidence-sources.md) when Codex records are absent or another AI coding tool supplied the evidence.

For a partial trial, create a separate draft containing only the approved records and use a separate manifest. Never reuse the full-month manifest for a subset upload.

## Upload Integrity

- Always run `show-config`, `ping`, `validate`, and `preview` with the same explicit environment that will receive the upload.
- Do not trust HTTP 200 or `comments_written` in the manifest by itself. ZenTao can return the comment form again without creating an action.
- Require `verify` to report `commented_actions == expected_comments` for every record.
- Preserve the manifest across retries. The uploader resumes from the last confirmed comment and must not recreate records with an existing ID.
- If the manifest and server disagree, reconcile progress from the server's actual `actions` list before retrying.
- Read [references/upload-compatibility.md](references/upload-compatibility.md) before changing client, comment, authentication, resume, or verification behavior.

## Failure Handling

- On upload failure, inspect the manifest entry and rerun the same upload command after fixing the cause. Preserve the manifest so completed comments are not repeated.
- If a title already exists, accept `skipped_existing` and verify the existing ID before deciding whether comments are missing.
- If test and production credentials differ, set `account` and `password` inside the corresponding environment node in the user's config file.
- If `verify` reports zero comments, stop before retrying. Confirm whether the server returned a comment form instead of creating `commented` actions, then reconcile actual counts.
