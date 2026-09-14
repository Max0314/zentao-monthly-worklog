# ZenTao MCP Tools

The companion `zentao-mcp` service exposes the ZenTao API as MCP tools. It is optional.
`zentao_tool` remains the only supported engine for the monthly worklog, because the ZenTao
v1 REST API has no endpoint for writing comments, and AI scoring only counts independent
comments.

Use these tools only when the MCP server is already connected in the current session. Never
install, start or configure it on the user's behalf as part of this skill.

## What the MCP offers

Two layers, with different write capability:

- **`zentao_*` composite tools — read only.** `zentao_find_similar_bugs` (symptom text to
  similar historical bugs across products), `zentao_search_bugs`, `zentao_analyze_bug`,
  `zentao_quality_report`, `zentao_user_worklog`, `zentao_ai_score`, `zentao_resolve_scope`.
- **Generated endpoint tools — can write.** Create and modify stories, tasks and bugs, and
  drive status transitions. Deletion is blocked on the production server.

## Division of labour

| Task | Use |
|---|---|
| Collect Codex and Git evidence | `python -m zentao_tool.cli collect` |
| Draft, validate, preview | `python -m zentao_tool.cli draft / validate / preview` |
| Create monthly records **with scoreable comments** | `python -m zentao_tool.cli upload` |
| Authoritative post-upload check | `python -m zentao_tool.cli verify` |
| Discover execution, product and project ids | `zentao_resolve_scope` |
| Check for a duplicate title before drafting | `zentao_search_bugs`, `zentao_find_similar_bugs` |
| Understand an existing bug before drafting | `zentao_analyze_bug` |
| Independent read-only cross-check | `zentao_user_worklog`, `zentao_ai_score` |

## Why the monthly upload cannot move to the MCP

Three reasons, in order of how hard they are to remove:

1. **No comment endpoint.** ZenTao v1 REST cannot write comments at all. They require a web
   session (login page, `user-refreshRandom.html`, double-MD5 password, cookies) posted to
   `action-comment-{type}-{id}.html`. A record created through the MCP therefore has a
   description and no comments, so it earns no AI score and carries no `【任务完成步骤】`
   history. That is not good enough for a monthly record.
2. **No access to the user's machine.** `collect` reads Codex session files and Git
   repositories on the user's own disk. The MCP runs on a shared server and cannot see them.
   This one is structural: a remote service can never do it.
3. **No resumable manifest.** `upload` binds a manifest to environment, account, month and
   per-record content hash, and resumes from the last confirmed comment. The MCP is
   stateless.

So the MCP's create-task and create-bug tools are for **ad hoc single records** raised during
a conversation — "file this defect I just analysed". The monthly batch, with its evidence
chain and scoreable comments, stays with `upload`.

`verify` remains the gate for an upload. An MCP read is a second opinion, not a replacement:
it does not know the manifest, the expected comment hashes, or the target binding.

## Boundaries

- The composite `zentao_*` tools never write. Anything that creates or changes data goes
  through a generated endpoint tool, so say plainly which record is being written and to
  which environment before calling one.
- A record created through the MCP has no comments. If it needs them, add them through
  `upload` or the ZenTao web UI, and do not claim it will be AI scored.
- Retrieval is lexical, not semantic. Confirm that the symptom, device model and version
  actually match before reusing a historical fix, and verify any commit hash, branch or file
  name against the original ZenTao record rather than repeating it from a summary.
- Scans are capped by a budget. Treat a `truncated` flag or a `notes` entry as a reason to
  narrow the scope, not as a complete answer.
- Test and production ZenTao are different MCP servers with different passwords. Read from
  the same environment the upload targets; never compare a production upload against a test
  read.
