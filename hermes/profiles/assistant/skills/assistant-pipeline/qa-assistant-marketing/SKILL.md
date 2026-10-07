---
name: qa-assistant-marketing
description: "QA marketing: check Marketer's advice, your own acceptance and the reopened unpublished draft. A clean review is not acceptance; a saved draft is not publication or marketing success."
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: assistant-pipeline
    tags: ["quality-assurance", "marketing"]
---

<ReadBeforeWork>

Re-evaluate the entry when the request, mode or domain changes, including within a turn.
Reuse full-body instructions only while present in the current context, not a past load or summary.
Check the kernel and common mode procedure independently. Load each whose full body is missing:

```text
skill_view(name="assistant-pipeline")
skill_view(name="assistant-pipeline", file_path="references/quality-assurance/index.md")
```

These dependencies also apply to direct entry. Loading does not restart an approved plan or expand a grant.
If a tool returns unchanged while the earlier body is unavailable, use read_file on `${HERMES_SKILL_DIR}/../SKILL.md` and `${HERMES_SKILL_DIR}/../references/quality-assurance/index.md`.
Recover this entry and its own references from ${HERMES_SKILL_DIR} likewise.
Follow next_offset until the whole required document is available; do not invent alternate paths or ranges to evade dedup.
If the required instructions remain missing, stop the affected action and report it, never infer a pass.
Read only applicable detail references below.

</ReadBeforeWork>

# Marketing acceptance

You execute marketing work, so this is your own acceptance, not a client check
of someone else's save. The common floor in
[QA](../references/quality-assurance/index.md) still applies.

For Marketer's strategy or review, read the actual answer and distinguish
evidence, hypotheses, unknowns and user decisions. A product need not already
exist. Approval of a proposal does not prove demand or authorize paid
production or remote uploads, and a clean Marketer review is advice, not
acceptance.

Before asking for remote-save consent, the package must have passed your
independent [writing QA](../qa-assistant-writing/SKILL.md) under the shared
requester contract and the relevant media/factual/legal evidence; Writer
self-review is not acceptance. Changes go back to the responsible producer,
never a local rewrite. Marketer's review findings that you did not resolve
are reported to the user with the consent request, not dropped.

For a service-side draft, require the actual private editor identity, same-object
reopen evidence, content/attachment comparison and unpublished-state check.
For note that evidence is the `note` tool's result (key, `edit_url`,
`verified`) and a fresh `draft` read showing `status: draft`; for Substack the
tool's result and a fresh `draft` read. No local-file substitution, guessed URL
or sharing-preview link as completion. Report limitations; no publication,
scheduling or sending is part of acceptance. For uncertainty or unexpected
effects follow [service drafts](../execute-assistant-marketing/references/publish-ops.md).

For results, check source/time/definition and limits of interpretation. A saved
draft is not a published post or a marketing success. The user publishes; later
public URLs and measurements must be observed rather than inferred.
