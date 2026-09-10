# X Posts And Threads

Documentary check: 2026-09-08. No logged-in composer test was performed.

| Expression | Draft representation |
| --- | --- |
| Body and line breaks | Plain text |
| Lists | Literal bullets or numbers, not semantic Markdown lists |
| Links | Actual URLs; do not emit `[label](URL)` as native formatting |
| Emphasis, headings, code, tables | No portable Markdown rendering contract; account-specific editor features need confirmation |
| Media | Attachment IDs outside the body; not an inline Markdown image |
| Thread | Ordered, individually identifiable post bodies |
| X Article | A different rich-text editor; not a long post or thread |

Each post must make its place in the progression understandable. Do not
force a hook, sales pitch or CTA on a factual update. Preserve uncertainty
and qualifications when splitting a claim across posts; do not put the
qualification only in a later post if the earlier one becomes misleading.

Long-post eligibility, media limits and weighted character counting depend
on the publishing surface/account. Do not hard-code remembered limits or
assume a plain character count models URL handling. The publishing owner
checks actual fit; an unverified limit is not an invitation to post a test.

Sources:
- https://help.x.com/en/using-x/how-to-post
- https://help.x.com/en/using-x/create-a-thread
- https://help.x.com/en/using-x/articles

## Craft Decisions

Make each unit understandable alone: include its essential subject and claim
qualifier even when the thread gives fuller context elsewhere. Give the unit
a role in the progression, such as main update or explanation, outside its body.
If compressing context, cut redundant setup before eligibility, uncertainty or
source scope. An unsupported hook is not a substitute for a concrete subject.
Use an action/destination only when requested; no mandatory hashtag or CTA.
Core information must remain textual, not depend on emoji or color alone.

## Worked Example (Fictional, MATERIAL-COMPLETE)

Supplied material: the fictional West shuttle runs on Saturdays during a trial;
there is no Sunday service in that trial. Audience: prospective passengers.
Requested structure: P10 main update, P20 service-context reply; no media,
handles, tags or reader action. Voice is plain and informative.
Creative-fiction allowance: wording this notice, not extra routes or promises.
Draft; IDs and roles below are metadata, not part of the exact bodies:
```text
P10 (main update): The West shuttle runs on Saturdays during the trial.
P20 (service context): The West shuttle trial does not include Sunday service.
```
Rationale: each body names the shuttle and trial; P20 adds context without
holding back a condition that would make P10 misleading when shared alone.
Retain: repeating "West shuttle" is useful identification, not verbal clutter.
Counterexample: "It is finally here!" with details only in a reply loses the
essential subject; "Your weekend travel is sorted" overstates Saturday service.
QA: quote the subject/qualifier in both bodies and map P10/P20 to their roles;
check against supplied service facts. No hashtag, CTA or personal story is needed.
Account fit and audience response remain unverified; textual standalone clarity
is inspectable, not a measured engagement result or permission to publish.

LOCAL adaptation; upstream has no specialized X-post guide. Selectively use
[writing-constitution.md](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/writing-constitution.md) for evidential scope,
[genre-notes.md](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/genre-notes.md) for conditional pacing, and
[revision-guide.md](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/revision-guide.md) for supplied voice and selective changes.
[ONS social media](https://service-manual.ons.gov.uk/content/content-types/social-media) supports standalone posts and main/context thread roles, not current limits or mandatory CTAs/counts.
[W3C sensory characteristics](https://www.w3.org/WAI/WCAG22/Understanding/sensory-characteristics.html) requires an alternative to graphical-symbol-only instructions; applying this to meaningful emoji is a local adaptation.
No mandatory scores, review loops, conclusion-first template or personal anecdote is imported.
