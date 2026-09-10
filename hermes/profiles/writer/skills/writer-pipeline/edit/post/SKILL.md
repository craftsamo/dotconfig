---
name: edit-post
description: >-
  Edit an existing X post/thread draft or Instagram caption within a named
  change scope. Preserve post IDs, factual qualifications and attachments.
  Does not edit a live post, publish, change campaign strategy or analyze only.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: writing
    output: "Complete revised post draft with stable IDs, changes and per-criterion evidence; new approval required for publication"
    form:
      source: {required: true, type: text, label: "Existing draft text, local path or readable URL; never modify the live post"}
      changes: {required: true, label: "Requested changes, including which posts if the target is a thread"}
      platform:
        required: true
        options: [x, instagram]
        references: references/*.md
        label: "Destination of the existing draft"
      scope: {required: false, options: [wording,structure,rewrite], label: "Default wording; broader changes require explicit authorization"}
      format: {required: false, label: "Keep the original single/thread/caption format unless a change is requested"}
      post_ids: {required: false, label: "Post IDs to edit; preserve the other posts"}
      media: {required: false, label: "Existing attachment IDs, paths and descriptions; retain mapping unless changed explicitly"}
      context: {required: false, label: "Surrounding posts and approved message brief"}
      mentions: {required: false, label: "Authorized handle changes; preserve other handles"}
      hashtags: {required: false, label: "Authorized tag changes; no forced count"}
      language: {required: false, label: "Keep the source language unless explicitly changed"}
      tone: {required: false, label: "Requested voice change; otherwise keep the source voice"}
      sources: {required: false, label: "Evidence for corrected or added factual content"}
      style_reference: {required: false, label: "Style example, not a source of facts or testimonials"}
      reference_focus: {required: false, label: "What to borrow from the style example"}
      must_keep: {required: false, label: "Exact text, caveats, claims, IDs or other protected content"}
      avoid: {required: false, label: "Requested exclusions; resolve conflicting instructions before editing"}
      length: {required: false, label: "Target or hard limit and units; never infer current account limits"}
      humanizer: {required: false, options: ["yes", "no"], label: "Default no; only explicit requests enable it"}
      note: {required: false, type: text, label: "Other edit constraints"}
---

<Procedure>

1. Read the entire supplied draft and the change request. Use a readable
   local file instead of asking for reattachment. If source or intended
   change is unavailable, return Q<n>; do not reconstruct a supposed original.
   Read only [X](references/x.md) or [Instagram](references/instagram.md).
2. Identify changed posts and protected text, claims, IDs, order and media.
   Unspecified content is preserved. Rewriting wording does not authorize
   a new offer, promise, stronger certainty or a campaign change. If the
   requested edit needs those decisions, stop that part and ask.
3. Apply the requested changes. Preserve the source language and voice unless
   specified. In Japanese, use `japanese-writing` as language knowledge only;
   this leaf owns QA, not its legacy inspection workflow or scoring tools.
   Do not change natural compounds or uniform phrasing just to add variation.
   Load `humanizer` only on explicit request and still respect protected meaning.
4. Compare the revised draft to the original. Re-read the whole thread or
   caption in context, not only the altered sentence. Keep IDs stable; if
   deleting or splitting a post was authorized, report the ID mapping rather
   than silently renumbering everything. Retain qualifications with claims.
5. Apply QA below and write the complete revised artifact to the requested
   destination, not only a patch or fragments. Do not overwrite an input
   file unless authorized. Any change to publish-approved text invalidates
   that text's prior approval: return the new draft for approval, never post.

</Procedure>

<QA>

- Show which request each change satisfies; identify any authorized order,
  format, handle, tag or media change. Unrequested posts remain unchanged.
- Verify facts, conditions and uncertainty against the source and supplied
  evidence. A shorter sentence must not become a stronger guarantee.
- Body text is separate from post IDs, metadata and production instructions.
  Missing media or insertion markers remain explicit gaps, not publishable text.
- Preserve caption-to-media identity. Do not describe unseen material as
  observed, or imply the media was edited by this text operation.
- Check hard limits only with a reliable available method, recording the
  method. Otherwise unverified; no platform-fit claim from an estimated count.
- Report checked / unmet / unverified for applicable criteria. A hard unmet
  condition is not made acceptable by improved style. This is self-review.

</QA>

<Report>

Name `edit-post`, original and revised paths, affected post IDs, a concise
change summary and criterion evidence. Include sources and open gaps.
Report the complete revised file's path and ID/media mapping for unchanged
consumption by Marketer, not the full draft pasted into the reply. State that
publication needs approval of this version and that no live post was changed.

</Report>
