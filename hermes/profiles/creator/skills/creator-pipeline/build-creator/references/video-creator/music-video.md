# Build — video-creator: music-video

Read [common build](../../SKILL.md) first.

## Transport

`generate-music-video` is metered and multi-turn: both proposal and generation
rounds use the generic `generate` row (`kind="work"`) in
[common build](../../SKILL.md)'s transport table, kept in ONE specialist work
conversation — never separate conversations per round.

## Supervising

For generate-music-video, a `pending-inputs` proposal is valid preliminary
work with zero media calls, not a refusal to produce a plan. Keep its path/hash
and the client's selected direction. Release missing music production only
with separate approval, then return the real music_file and consent decisions
to VideoCreator for a NEW proposal/hash. A preliminary hash never releases
video_generate. Preserve spent attempts and the same work conversation; no
dummy WAV, silent-mode substitution or bypass through another tool.

For generate-music-video, use kind="work" for BOTH rounds in one conversation. First
release proposal-only work without approval fields, preserving the client's
form and budget ceiling. A proposal report's zero spend is expected. Do not
ask it to produce video merely because the budget was supplied. After the
client approves the proposal, continue with the same target/conversation_id,
intent: revise, full unchanged form, approved_plan and approval_sha256 copied
from that exact report. The hash binds the approved content, not the caller's
identity. Do not compute a fresh digest to approve a silently changed file.
Changed fields/inputs or a new creative revision return to proposal approval,
remaining call allowance never resets. Changing pace/transition is a creative revision, not
an automatic corrective or an authorized global playback-speed change. Old
approved proposals lacking those fields retain their recorded prompt; do not
inject defaults into the approval-bound form. A rejected proposal is sent with
approval fields omitted, not sent for generation with a corrective budget.
Check the proposed exact prompt-only file is 1..1800 UTF-8 bytes and bound to
the approved proposal by its hash. Never send the full proposal or append
reference text to that prompt. An oversized approved prompt must be shortened
in a new proposal and approved before a newly granted attempt, not retried
automatically after a provider rejects it.
Native-audio availability is checked before spend, not guessed from a prompt.
If the report says needs finishing, release only the agreed existing edit or
legacy assembly with its own inputs/grant. Exact text and supplied music are
not magically handled by edit-clip; never invent an editing capability. Do not
close a visual-master job as a complete musical MV while its finish is pending.
