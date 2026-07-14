# ZenTao Upload Compatibility

Use these rules for the current ZenTao Biz 12.3 environments.

## Record creation

- Create stories with payload field `product`, not `productID`.
- Map collection names explicitly: `stories -> story`, `tasks -> task`, `bugs -> bug`. Do not singularize by removing the last character.
- Use the configured project, execution, and product IDs for the selected environment. Discover or confirm them before a new environment's first upload.

## Scoreable comments

- REST `Token` authentication is sufficient for v1 record APIs but is not sufficient for the web comment POST.
- Establish a ZenTao Web session first: load the login page, request `user-refreshRandom.html`, submit the double-MD5 password with browser headers, and retain the returned cookies.
- Post each comment independently to `/action-comment-{story|task|bug}-{id}.html` with `actioncomment` and `uid`.
- Include the Web session cookies plus realistic `Origin`, `Referer`, `User-Agent`, and `X-Requested-With` headers.
- A successful comment response normally contains the page-reload script. If the response contains `zin_action_comment_form`, the comment was not submitted and must be treated as an error.

## Resume and verification

- Persist the created object ID before writing comments, and persist progress after every comment.
- Bind each manifest to its target, account, month, and record hashes. Reject cross-environment or changed-record reuse.
- After an interruption, query the object's `actions` and match normalized comment hashes in order before resuming.
- Do not use manifest progress as proof of server state.
- Verify every object after upload:
  - story exists and title matches;
  - task status is `done`;
  - Bug status is `resolved` with resolution `fixed`;
  - every expected comment hash is present once, with no duplicate expected comments;
  - newly created objects contain exactly the expected number of `commented` actions.
- When AI scoring is expected, use `verify --wait-ai-score 180 --require-ai-score`.

## Existing titles

- A same-title object is a conflict by default; title equality alone does not prove ownership.
- Use `upload --adopt-existing` only after manual ownership confirmation. Adoption reconciles existing comments, adds missing comments, and applies the requested final task/Bug state.

## Expected runtime

Once compatibility is established, creation and roughly 60 independent comments should normally complete in tens of seconds on the intranet. Evidence collection and monthly content analysis remain the slower phase because they require reading conversations, deduplicating Git worktrees, and validating business ownership.
