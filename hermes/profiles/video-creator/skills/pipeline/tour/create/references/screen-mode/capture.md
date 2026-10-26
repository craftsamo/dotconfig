# Capture

VideoCreator acquires footage inside the approved create-tour work job. Never
ask Assistant to capture as a fallback. No capture verb/profile is introduced.
Web uses the local narrow wrapper; macOS is explicitly unavailable. Refuse an
unsupported explicit mode and return its blocker, rather than silently recreating
the UI or substituting screenshots.

First propose the steps without visiting the target. Separate consent to
read-only reconnaissance from consent to the stateful demo/recording. A URL,
reference or available browser login is not consent. The proposal includes the
goal, audience, start state, target/origins, allowed actions, demo data,
forbidden actions/regions, time/action/attempt ceilings and privacy decision.
Use proposal-vN.md plus exact approval_sha256, as for MV. If reconnaissance
changes the operation targets or scope, propose a new version before recording.
No per-click approval inside the agreed scope; any new target, credential,
purchase, send, delete, upload or private region stops the job.

Follow the Web reference for acquisition. Read the raw receipt and actual video,
then write job/source.json at the already-approved form's source path:
the supplied-mode clips schema plus `capture_receipt` pointing to receipt.json.
All selected clips must reference that receipt's original raw path/hash. Editing
choices still require exact preview approval; changed creative form fields need
a new proposal. The capture receipt keeps the acquisition proposal hash.
For an edit-only proposal reusing that take, add `acquisition_sha256` alongside
form in its tour block, equal to the original receipt's approval hash. This
authorizes reuse during freeze, never another capture session. Retain the old
acquisition proposal and receipt; do not relabel them as the new approval.

Then follow the supplied-mode preparation and media authoring contract. Raw
takes can exceed final duration, but never raw byte/duration or acquisition
budgets. Private acquisition evidence is not part of published final outputs.
Cancelled/interrupted jobs retain takes and unknown pending actions. Stop/close
only the owned session, reconcile evidence, never automatically replay actions.
