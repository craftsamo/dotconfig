---
name: write-post
description: >-
  Draft an X post or ordered thread, or an Instagram feed/reel caption,
  from a decided message and supplied evidence. Not X Articles, private
  replies, in-image lettering, media production, strategy or publishing.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: writing
    output: "Complete post/thread/caption draft with stable post IDs and separate media notes; never a published post"
    form:
      platform:
        required: true
        options: [x, instagram]
        references: references/*.md
        label: "X posts/threads or Instagram captions; X Articles are a different subject"
      message: {required: true, label: "The decided content this post must communicate"}
      audience: {required: true, label: "Who this post is for"}
      format: {required: true, label: "X single/thread or Instagram feed/reel caption; infer from the request"}
      context: {required: false, label: "Series, surrounding posts, reply context or occasion"}
      media: {required: false, label: "Media IDs, supplied paths and verified descriptions, mapped to post IDs"}
      action: {required: false, label: "Requested reader action and actual destination, if any"}
      mentions: {required: false, label: "Requested account handles; do not invent identities"}
      hashtags: {required: false, label: "Requested tags or permission to propose relevant tags; no fixed count"}
      language: {required: false, label: "Output language; Japanese unless the request specifies otherwise"}
      tone: {required: false, label: "Desired voice in ordinary words, not model temperature"}
      sources: {required: false, label: "Paths, URLs or excerpts supporting facts, numbers and quotations"}
      style_reference: {required: false, label: "Example wording, not a source of client facts or experiences"}
      reference_focus: {required: false, label: "What to borrow from the example, such as tone or progression"}
      must_keep: {required: false, label: "Exact wording, facts, caveats and other non-negotiable content"}
      avoid: {required: false, label: "Content or wording to exclude; conflicts with must_keep require a decision"}
      length: {required: false, label: "Target or hard limit with units; account-specific limits are not assumed"}
      humanizer: {required: false, options: ["yes", "no"], label: "Default no; use only when explicitly requested"}
      note: {required: false, type: text, label: "Other constraints or preferences"}
---

<Procedure>

1. Respect the pipeline's released unit and durable destination. Read the
   supplied message, sources and context before drafting. Infer answered
   fields; ask one Q<n> block only for unresolved decisions. A promised
   result, price, quotation or personal experience without support is not
   filled from a style example. Conflicting constraints return to the caller.
2. Read only [X](references/x.md) or [Instagram](references/instagram.md).
   A thread consists of separate X posts; an Instagram caption accompanies
   media, and an X Article is neither of those. Unsupported destinations
   are not silently converted. Do not select a campaign, schedule or offer.
3. Draft in the requested voice and language. Follow only the requested
   aspects of a style reference. Natural wording is not changed merely
   because an alternative exists. For Japanese, use `japanese-writing`
   as language/notation knowledge, not as a second workflow: this leaf
   owns review and does not run legacy layers, lint or scoring.
   Load `humanizer` only for an explicit request, preserve meaning and
   commitments, and do not report an authorship or naturalness score.
4. For a thread, assign stable post IDs and preserve the intended order.
   Keep each post's exact plain-text body separate from IDs and production
   notes. Use supplied handles; propose hashtags only if requested, without
   padding to a count. An action is included only when part of the brief.
5. Map supplied media IDs to the posts that use them. Distinguish inspected
   media from a supplied description; never claim to have seen unavailable
   material. Unresolved insertion markers such as `[[image:hero]]` are
   internal draft instructions, not post text. A missing required asset
   remains needs-media; do not remove its marker to pretend completion.
6. Read the complete candidate and apply QA below. Save the complete draft
   at the requested path. For a thread, use labelled plain-text body blocks;
   IDs, media assignments and notes stay outside them. Marketer receives
   the exact bodies, not a rewrite brief. Never send, schedule or publish.

</Procedure>

<QA>

- For an outline unit, check proposed message/order and tone against the
  brief, then stop for approval. Complete post bodies and publication fit
  are not claimed or required before the draft unit is released.
- Quote the wording carrying the decided message; check required caveats,
  claims, handles and action against the brief and supplied evidence.
  A source supplied by the caller is not independently verified research.
- Check format, post order and the ID-to-media mapping. A caption describing
  an unseen image needs evidence or correction, not a confident guess.
- Plain-text bodies contain no unintended Markdown formatting or production
  markers. Keep body text distinct from metadata so it can be consumed verbatim.
- Check each specified hard limit with an available reliable method and
  name that method. If it cannot be counted or current account constraints
  are unavailable, mark it unverified; no terminal capability is implied.
  Meeting an authoring target is not proof of platform acceptance.
- Review naturalness and tone without altering facts, scope, uncertainty
  or approved wording. No mandatory humanizer pass or statistical thresholds.
- Missing required media, unsupported hard constraints or unverified
  required checks prevent a ready-to-publish claim. A text draft may be
  delivered with those gaps explicitly open; it is not an accepted post.

</QA>

<Report>

Name `write-post`, platform, format and the complete draft path. Identify
post IDs and their media assignments. For applicable criteria report
checked / unmet / unverified with a quote, source or actual count and method.
List unresolved assets and decisions; distinguish text complete from a
publishable unit. The requester performs independent acceptance; Marketer
performs its platform/claim inspection and Publish gate. Nothing was posted.

</Report>
