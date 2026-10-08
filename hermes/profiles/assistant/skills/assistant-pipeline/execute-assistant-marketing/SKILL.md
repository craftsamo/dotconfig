---
name: execute-assistant-marketing
description: "Execute marketing: commission parts, accept them and save the approved service draft yourself. Marketer advises; preserve accepted Writer text and exact upload consent, never publish or duplicate drafts."
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: assistant-pipeline
    tags: ["execute", "marketing"]
---

<ReadBeforeWork>

Re-evaluate the entry when the request, mode or domain changes, including within a turn.
Reuse full-body instructions only while present in the current context, not a past load or summary.
Check the kernel and common mode procedure independently. Load each whose full body is missing:

```text
skill_view(name="assistant-pipeline")
skill_view(name="assistant-pipeline", file_path="references/execute/index.md")
```

These dependencies also apply to direct entry. Loading does not restart an approved plan or expand a grant.
If a tool returns unchanged while the earlier body is unavailable, use read_file on `${HERMES_SKILL_DIR}/../SKILL.md` and `${HERMES_SKILL_DIR}/../references/execute/index.md`.
Recover this entry and its own references from ${HERMES_SKILL_DIR} likewise.
Follow next_offset until the whole required document is available; do not invent alternate paths or ranges to evade dedup.
If the required instructions remain missing, stop the affected action and report it, never infer a pass.
Read only applicable detail references below.

</ReadBeforeWork>

# Marketing: execute

You run marketing work; Marketer advises. Keep one Marketer conversation per
job for strategy questions and reviews (`kind="inquiry"` for a bounded
question, `kind="work"` when it needs several turns or its browser), and pass
it the same goal, constraints and record location each time. Marketer starts
no Writer, Creator or service work; its briefs are inputs you release.

1. **Direction.** Unknown strategy goes to Marketer's Plan, not a spec-gap
   loop. Relay its material questions and the user's actual answers; do not
   choose commercial commitments for the user.
2. **Parts.** Release Writer units through
   [writing Execute](../execute-assistant-writing/SKILL.md): write-post /
   edit-post / analyze-post, write-copy / edit-copy / analyze-copy, or the
   article leaves, with Marketer's decided claims, conditions and evidence
   carried in. Media goes through [creative Execute](../execute-assistant-creative/SKILL.md)
   with its own budget and approval. Perform independent writing QA with the
   shared requester contract ([writing QA](../qa-assistant-writing/SKILL.md));
   Writer self-review is not acceptance. The job consumes accepted text
   unchanged; findings go back to the same Writer, never local shortening, claim removal
   or stronger urgency. Analysis is decision input, not publishable copy.
3. **Marketing review (optional).** For a consequential piece, ask Marketer's
   review on the accepted package: fit, claims, platform and legal triage.
   Its findings are advice; a defect goes back to its producer through you,
   and a clean review is not acceptance.
4. **Consent.** Before any editor entry, present the exact content/assets,
   account/service and create/update target with acceptance evidence, and
   get the user's explicit approval. Autosave is already an upload; approval
   of an outline or a local file is not remote-save consent. The browser
   routes (X, Zenn) have no approval card: right before opening the editor,
   confirm once more with `clarify`, quoting the account, the target and the
   content's first line. A tool's card (note, Substack) is that last gate.
5. **Save** through the destination's route and the rules in
   [service drafts](references/publish-ops.md):
   - X post or thread: `skill_view(name="x-access:x-twitter-drafts", file_path="references/post-draft.md")`;
   - X Article: `skill_view(name="x-access:x-twitter-drafts", file_path="references/article-draft.md")`,
     into an Article draft the user created and named by its edit URL;
   - Substack: the `substack` tool's `create_draft` / `update_draft`, per
     `skill_view(name="substack-access:substack-drafts")` (Write);
   - note: the `note` tool, per `skill_view(name="note-access:note-com-drafts")` (Save);
   - Zenn: `skill_view(name="zenn-dev")`.
   Reopen the same object and verify content and unpublished status. Never
   use Marketer's browser or another login profile as a fallback.
6. **Deliver.** Check [marketing QA](../qa-assistant-marketing/SKILL.md) and
   report the actual private draft identity, evidence and remaining
   limitations. A local file alone does not fulfill a service-draft request.
   When the job follows a Marketer plan, pass the saved identity back to the
   same Marketer conversation for its record.

No Publish/P1 grant, publishing, scheduling, sending/test-send or sharing-link
generation belongs to this pipeline, even where a tool could do it. The user
publishes. Ambiguous side effects are reconciled before retrying, never by
creating another draft or deleting one. Results questions go to Marketer's
Analyze ([analysis handoff](references/improvement.md)).
