# Engineering - delivery and optional close-out

Implementation normally completes with a real task-branch PR, accurate
description, verification evidence and remaining risks. Check current CI state;
pending/unavailable checks are not green, and a required failed check prevents
unqualified acceptance. PR creation never means it was merged or deployed.

Only when the user separately asks to merge: read `github_pr` `view` and report
the actual base/head, draft state, required CI checks, review state, GitHub's
merge state and what the closing references will close. For a stack, verify the
target layer and dependent layers. A first layer must not close an Issue whose
remaining scope belongs to later layers. The merge itself is `pr_merge`
(`skill_view(name="github-access:github-pr")`): its card, pinned to the head
commit it shows, is the user's explicit go; follow [GitHub
operations](../../execute-assistant-engineering/references/github-ops.md).

After an authorized merge, check the actual resulting PR/Issue state. Do not
claim an Issue closed merely because a closing keyword exists. For a job the
user chose to track, acceptance ties each criterion of its issue to evidence,
and the close-out follows [GitHub boundaries](../../execute-assistant-engineering/references/github-ops.md):
the Phase's sub-issue closed and its Status Done, read back from GitHub. An
untracked job gets no Issue or board close-out.
