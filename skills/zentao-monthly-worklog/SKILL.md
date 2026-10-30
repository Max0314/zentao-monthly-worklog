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
3. Run `python -m zentao_tool.cli ping`, then `python -m zentao_tool.cli list-scopes --limit 1000`. If execution ownership is not explicit, show likely iterations and ask the user to choose.
4. Configure confirmed mappings with `python -m zentao_tool.cli configure-execution <alias> <execution-id> <name> <product-id> --repository <pattern> [--project-id <id>]`. Use `--env test` before the command when test ZenTao uses different IDs; environment mappings override global mappings.
5. Never copy another user's execution, product, project, repository, or Git-author mappings into a new user's configuration.

## ZenTao Addresses

- Formal intranet: `http://10.70.33.19/`; formal internet: `https://itms.changhongnetwork.net:28443/`. Both Web pages and `/api.php/v1` now start at the site root. Do not append `/biz` to formal links or comment endpoints.
- Existing per-user configs may still contain `path_prefix: "/biz"` or a `/biz/api.php/v1` override. Inspect the selected environment with `show-config`; update only the formal internal/external entries to `path_prefix: ""` and a root API path. Keep the test environment's independently verified routing unchanged.
- HTTP 200 alone is not proof that a route works: the retired `/biz/user-login.html` serves a 200 `illegal` page. Run `ping` for the exact upload environment and require a real Web login, as well as REST access, before record creation. Build UI links from the verified `base_web`, not from a remembered `/biz` URL.

## Workflow

1. Run `python -m zentao_tool.cli show-config` and confirm the selected user configuration and workspace.
2. Run `python -m zentao_tool.cli collect YYYY-MM` with a timeout of at least 60 seconds. It creates compact `output/YYYY-MM/evidence.json` plus complete extracted messages under `output/YYYY-MM/details/sessions/`. Collection follows each message timestamp in the configured timezone, including conversations started in an earlier month. Add `--context`, `--department`, or `--work-description` when Codex records are absent or incomplete. Do not use `--full` for routine monthly work.
3. Read only the compact evidence first:
   - Use `stats` for source counts and deduplication totals; Git commits are already unique by hash and worktrees are already merged into repository families.
   - Use sampled `codex_sessions[].turns`, `signals`, and mapped repositories to recover likely intent, results, tests, deployments, and pending work.
   - Treat `external_contexts` as additional AI exports or user-supplied work evidence.
   - Do not open every detail file or repeatedly parse the evidence with many small shell commands.
   - When a fact needs confirmation, batch the relevant sessions into one `inspect-evidence` call. Keep the default 30,000-character budget or lower; normally inspect no more than 2-6 sessions per business objective.
4. Run `python -m zentao_tool.cli draft output/YYYY-MM/evidence.json` for a baseline. Entries in `bug_candidates` are not resolved Bugs; promote only candidates supported by symptom, diagnosis/fix, and validation evidence. Fix-like commits remain in the baseline task sources so unsupported Bug candidates still have a task fallback. Remove duplicate source coverage when promoting one to a Bug. Rewrite `output/YYYY-MM/draft.json` once after decisions are settled; avoid placeholder records and repeated whole-file patches.
5. Run `validate` and `preview`. Show the complete proposed story/task/bug list to the user before any upload unless the user explicitly authorized the complete list in the current request. If the user requests dedicated executions, confirm project ownership and read back each created execution ID; do not silently reuse a technically related platform's execution.
6. After confirmation, run `upload` with `formal_auto` or an explicit environment and a dedicated manifest. Do not replace this command with ad hoc REST calls; it writes each scoreable comment separately and persists resume state.
7. Run `verify --wait-ai-score 180 --require-ai-score` against the generated manifest when scoring is required. Treat the upload as successful only when titles, final task/Bug statuses, expected comment hashes, duplicate counts, and scores match.

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

Write each comment as a substantive business work note: identify the affected workflow or symptom, the evidence used to locate it, the concrete change, or the verification and remaining boundary. Keep these as separate chronological actions; avoid generic one-line claims such as “优化完成” or invented test/production results.

For each bug, provide a title stating component, symptom, and impact; a `detail` beginning with `【bug详细描述】`; separate `【bug解决步骤】` comments for verification, location, analysis, fix, and regression validation; and an independent `【伪代码】` comment.

For each story, provide a business-facing title, a `【需求详细描述】`, product ID, estimate, and optional independent implementation comments.

Never put all completion or resolution steps into the description. Never rely on finish-task or resolve-bug remarks for scoreable history. The upload command must create one `commented` action per comment through the ZenTao web action endpoint.

## Commands

```powershell
python -m zentao_tool.cli collect 2026-07
python -m zentao_tool.cli inspect-evidence output\2026-07\evidence.json --repository bi_center --query 测试 --query 部署
python -m zentao_tool.cli draft output\2026-07\evidence.json
python -m zentao_tool.cli validate output\2026-07\draft.json
python -m zentao_tool.cli preview output\2026-07\draft.json
python -m zentao_tool.cli upload output\2026-07\draft.json
python -m zentao_tool.cli verify records\manifests\2026-07-formal_auto.json --wait-ai-score 180 --require-ai-score
```

The default `formal_auto` probes the formal intranet first and uses the formal external endpoint when intranet access is unavailable. Selection happens before a command; never switch endpoints halfway through an upload. Place `--env test`, `--env formal_external`, or another global option before the subcommand. Use `test` only when the user explicitly requests or is authorized for the test system.

## Token Budget Rules

- Compact evidence is the default. If `mode` is `full` or the main evidence exceeds 500 KB, stop and recollect without `--full`.
- Never load all files under `details/sessions`. Use the compact turns to shortlist evidence, then call `inspect-evidence` once with multiple `--session` or a repository filter.
- Avoid one shell/model round trip per commit or session. Prefer one structured query per repository family.
- Treat `bug_candidates` as an index, not content ready for upload. Do not draft template resolution steps for unsupported candidates.
- Preserve source hashes from the baseline instead of repeatedly rediscovering them.

Read [references/prompt-examples.md](references/prompt-examples.md) when recommending a new-session prompt. Read [references/evidence-sources.md](references/evidence-sources.md) when Codex records are absent or another AI coding tool supplied the evidence. Read [references/mcp-tools.md](references/mcp-tools.md) when a ZenTao MCP server is already connected in the session and its tools could resolve execution ids, check for a duplicate title, inspect an existing Bug, or cross-check an upload. The `zentao_*` composite tools only read, but the MCP also exposes endpoint tools that create and modify records; neither replaces `upload` or `verify`.

For a partial trial, create a separate draft containing only the approved records and use a separate manifest. Never reuse the full-month manifest for a subset upload.

## Upload Integrity

- Always run `show-config`, `ping`, `validate`, and `preview` with the same explicit environment that will receive the upload.
- Do not trust HTTP 200 or `comments_written` in the manifest by itself. ZenTao can return the comment form again without creating an action.
- Require `verify` to report `commented_actions == expected_comments` for every record.
- Preserve the manifest across retries. The uploader resumes from the last confirmed comment and must not recreate records with an existing ID.
- The manifest is bound to the test/formal target, account, month, and per-record content hash. Never bypass a mismatch.
- Before resuming, the uploader reconciles expected comment hashes with the server's actual `actions` list.
- Read [references/upload-compatibility.md](references/upload-compatibility.md) before changing client, comment, authentication, resume, or verification behavior.
- Never create a monthly record through a connected ZenTao MCP. Its endpoint tools can create a story, task or Bug, but ZenTao v1 has no comment endpoint, so such a record carries no `【任务完成步骤】` or `【bug解决步骤】` history and earns no AI score. Everything belonging to the month's record set goes through `upload`. If the user explicitly asks for a single ad hoc record through the MCP, create it only after saying plainly that it will have no comments and no AI score.

## Failure Handling

- On upload failure, inspect the manifest entry and rerun the same upload command after fixing the cause. Preserve the manifest so completed comments are not repeated.
- If a title already exists, stop by default. Use `--adopt-existing` only after confirming that the object belongs to this user and should receive the draft comments and final state.
- If test and production credentials differ, set `account` and `password` inside the corresponding environment node in the user's config file.
- If `verify` reports zero comments, stop before retrying. Confirm whether the server returned a comment form instead of creating `commented` actions, then reconcile actual counts.
