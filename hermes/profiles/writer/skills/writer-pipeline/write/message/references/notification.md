# Notification text

Identify the actual event, affected object, current state and any known action
the recipient can take. Distinguish an event being queued, processed or
completed. Do not infer completion from a request being accepted or create
urgency/deadlines that were not supplied.

When title and body are needed, make their roles clear without duplicating
the whole message. Put the relevant change first, then the known action or
destination if useful. A notification does not always need a call to action.

Avoid exposing unnecessary private details on a surface that may be visible
to others. Use the supplied privacy/display constraints; if sensitive content
is essential and the surface is unknown, ask rather than disclose by default.

QA: event and state match the evidence, any action really exists, and title/body
can be extracted without instructions. Character fit, truncation and notification
delivery are unverified without the corresponding measurement or rendered test.
