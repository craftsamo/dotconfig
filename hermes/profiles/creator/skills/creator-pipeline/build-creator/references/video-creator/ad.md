# Build — video-creator: ad

Read [common build](../../SKILL.md) first.

## Transport

| Leaf | Transport |
| --- | --- |
| video-creator's `create-ad` / `analyze-ad` | `specialist_call(target="video-creator", message=<the text>, kind="work")`; approval turns or bounded multi-pass evidence extraction, not an inquiry |

## Supervising

For analyze-ad relay the evidence-backed report, not a request for an output
movie. Optional deliver retains report/evidence for the next work unit. Do not
promote source-ad claims into approved client claims or re-upload/re-analyze
the same file yourself. Missing listening/continuous-motion evidence stays
unverified. A reference analysis is not authorization to produce a new ad.

For create-ad, keep all three turns in one specialist work conversation:
proposal-only (no approval fields), approved_plan + approval_sha256 for source
authoring/preview, then preview + preview_sha256 for final render. Preserve
the full form and target/conversation_id. Relay the exact hashes only AFTER
client approval; never recompute a hash to approve changed bytes. Review exact
copy, claim qualifications, asset usage and action before content approval;
review the frozen preview before rendering. A hash is integrity, not caller
authentication. Changed copy/assets/direction require a new plan and preview.
Changing aspect also requires re-layout, a new plan/source/preview and both
approvals; never apply an old portrait preview to a landscape/square output.
Do not inject aspect into an existing approval-bound portrait plan that lacks it.
No media generation, TTS, capture or arbitrary API call is hidden in create-ad.
Do not require a separate analyze-ad call for its self-QA; use it when the
client asks for deeper advertising review or a reference breakdown.

For `audio_workflow: mix`, request preliminary timing from VideoCreator, relay
it to AudioCreator, then return the verified Mix bundle before formal video
approval — see [common build](../../SKILL.md) "Supervising" and, for the optional
Mix leaf itself, [Mix build](../audio-creator/mix.md).
