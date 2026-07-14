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
- After an interruption, query the object's `actions` and count `action == commented`. Reconcile the manifest to that count before resuming.
- Do not use manifest progress as proof of server state.
- Verify every object after upload:
  - story exists and title matches;
  - task status is `done`;
  - Bug status is `resolved` with resolution `fixed`;
  - `commented_actions` equals the draft comment count.
- When AI scoring is expected, wait briefly and spot-check object `aiScore` values.

## Expected runtime

Once compatibility is established, creation and roughly 60 independent comments should normally complete in tens of seconds on the intranet. Evidence collection and monthly content analysis remain the slower phase because they require reading conversations, deduplicating Git worktrees, and validating business ownership.
