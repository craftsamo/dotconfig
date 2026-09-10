# Error message

Identify the affected operation, what is actually known about its result, and
which recovery actions are established. A timeout or missing acknowledgement
can leave completion unknown. Do not say "not sent", "not saved" or "not
charged" merely because no success response was received.

State the known problem in user-facing terms. Include a reason only when
supported and a next action only when available and appropriate. A retry
button's existence does not prove repeating an operation avoids duplicates
or double charges. A missing recovery path is a gap, not a template slot to fill.

For a supplied unknown send result, "送信結果を確認できませんでした。" can
state that uncertainty without inventing failure or a safe retry. Add a
history-check instruction only if such a control and its use are confirmed.
Do not blame the user or expose raw errors, secret values or internal paths.

QA: outcome, cause and recovery claims retain their actual evidence level.
Error codes/placeholders stay exact when required. No false data-loss,
restoration-time or safe-retry guarantee; the draft is not a system fix.
