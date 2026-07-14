# Evidence Sources

## Supported Inputs

- Codex sessions are discovered from `codex_sessions_root` by month.
- Git repositories are discovered recursively below `workspace_root`.
- Repeatable `--context` accepts UTF-8 JSON, JSONL, Markdown, and text files.
- `--department` and `--work-description` add explicit manual context.
- Generic JSON fields include `sessions`, `messages`, `role`, `author`, `text`, `message`, and `content`.

Example:

```powershell
python -m zentao_tool.cli collect 2026-07 `
  --context C:\exports\neocoder.jsonl `
  --department "研发效能部" `
  --work-description "完善代码评审和报表能力"
```

## Evidence Strength

1. Git diff/commit plus conversation or test result: may support completed tasks and fixed Bugs.
2. Git commit alone: may support a draft, but verify behavior and validation details before upload.
3. AI conversation or work note alone: support only claims explicitly stated in it.
4. Department description alone: generate candidates marked `待确认`; do not claim completion or resolution.

NeoCoder and other AI tools are compatible through exported JSON/JSONL/Markdown/text. Do not guess or scan undocumented private storage formats; ask for an export or a plain work summary.
