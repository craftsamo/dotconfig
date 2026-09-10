# Scoped Web Recording

## Authority And Limits

Only an explicitly approved **sanitized demo site** qualifies. No copied daily
browser cookies, shared Hermes Brave/CDP, auth vault, login recording, downloads,
uploads, eval, injected script, arbitrary shell, native desktop, or real-user
data operations. Dedicated authenticated sessions are NOT implemented yet;
request an unauthenticated sanitized demo or supplied sanitized recording.

The thin `capture.py` wrapper uses installed agent-browser, not a second browser
runtime. It enforces exact command/selector/dummy-data lists, job/proposal binding,
an exclusive flock lease, independent budgets of <=2 takes and <=4 reconnaissance
sessions per job, browser-operation wall time <=180 s and <=50 actions. Failed
sessions count against their respective budget; neither count resets on a new
proposal. Logs redact typed values. Pending action
records are fsynced before dispatch. New sessions isolate namespace/config and
discard inherited profile/CDP/proxy/plugin/init-script environment settings.
Recording creates a fresh context: only the exact old owned tab may be closed;
reacquire a snapshot and compare visible text before acting.

These are WRAPPER guarantees, not a terminal or website sandbox. Existing
terminal tools can bypass the wrapper; operating contracts forbid doing so.
Agent-browser's domain filter plus before/after exact-origin and one-tab checks
are defense in depth, not proof arbitrary websites are safe. Redirects/popups
may start loading before the post-action check; allowed-origin GET requests and
page scripts can have side effects. Choose controlled demo environments with
known behavior, never describe reconnaissance as inherently side-effect-free.
There is no cross-profile desktop action lock because native capture remains
disabled; Assistant's existing computer_use is not silently covered by this lease.

## Proposal Scope

The single fenced `tour` JSON block contains a fully defaulted `form` plus:

```json
{"scope":{"platform":"web","target":"http://127.0.0.1:8000/",
"origins":["http://127.0.0.1:8000"],"start_state":"Settings, no name selected",
"allowed_actions":{"click":["#customize","#apply"],"type":["#name"],"scroll":["down"]},
"demo_data":["Demo Workspace"],
"forbidden":["credentials","purchases","send","delete","uploads","private-regions"],
"privacy":"sanitized-demo-only","max_seconds":120,"max_attempts":2,
"max_actions":20,"read_only_recon":true}}
```

This is a scope excerpt, not a complete proposal. Target/start_state must equal
the form. `source` must equal `<job>/source.json`. Creator/VideoCreator derive
exact selectors during consented reconnaissance; do not require the client to
know DOM ids. Unknown selectors mean reconnaissance-only scope first, then a
new proposal with stateful actions. Sites without stable ids need supplied
footage until another bounded targeting strategy is implemented.
Each recording still needs completed reconnaissance under its exact proposal
hash; earlier proposals are not reused as consent. The independent budgets allow
v1 discovery recon, v2 recon plus interrupted take 1, then v3 recon plus approved
take 2 after reconciliation. All proposal/lease/raw evidence remains intact.
A third take is refused even with another proposal. A fifth recon is refused
without consuming or waiving the remaining take budget.

```sh
python3 ${HERMES_SKILL_DIR}/scripts/capture.py --job <private-job> --proposal <proposal-vN.md> --approval-sha256 <hash> --recon
python3 ${HERMES_SKILL_DIR}/scripts/capture.py --job <private-job> --proposal <proposal-vN.md> --approval-sha256 <hash> --commands <commands.json>
```

Run each invocation through Hermes `terminal` with `background: true` **from
the outset**, including reconnaissance and recovery. The profile's foreground
terminal timeout is 180 s; a scope may legitimately use all 180 s before
stop/close, probing and full decode. Do not lower the approved max_seconds or
first try foreground and then restart a timed-out capture. For recording, pass:

```json
{"command":"python3 ${HERMES_SKILL_DIR}/scripts/capture.py --job <private-job> --proposal <proposal-vN.md> --approval-sha256 <hash> --commands <commands.json>","background":true,"notify":true}
```

Save the returned terminal `session_id` separately from the browser session in
lease.json. Poll only that process with `process`:

```json
{"action":"poll","session_id":"<terminal-session-id>"}
```

While running, use `process` with `{"action":"wait","session_id":
"<terminal-session-id>","timeout":30}` for bounded waits, then inspect status
and new output. A wait timeout is not process completion and is not permission
to launch again. Completion notification supplements polling; require exited
status, exit code 0, receipt.json and complete closed.json before editing.
For recon, require exit code 0 and its complete closed.json before reviewing
recon.json/targets.json; recovery instead reports recovered/interrupted state.

Inspect reconnaissance evidence and targets.json (bounded visible-ref to DOM-id
readback) against the client's start state before the
second command. Commands are tool-level argv, not a new scene/action language:
`[["click","#customize"],["type","#name","Demo Workspace"],["wait","1000"],
["click","#apply"],["scroll","down","600"]]`. Type accepts only approved dummy
values and text/search fields. No Enter/submit shortcut. Wait <=5 s, vertical
scroll <=1200 px. Batch actions are chosen by VideoCreator within approved scope;
the client supplies goals, not this file.

Every ordinary browser subprocess has a <=20 s timeout capped by the remaining
approved browser-operation lease. Stop and close have separate <=20 s command
timeouts. The owned browser is closed before media validation: ffprobe has a
180 s timeout and full decode a 360 s timeout, at most 540 s of validation
subprocess work. The longest normal capture path therefore budgets at most
180 + 20 + 20 + 180 + 360 = 760 s of subprocess work, plus bounded-size local
file IO and scheduling. Decode failure/termination retains the raw and marks
the attempt interrupted; it does not leave a browser open for decoding.
Background mode has no automatic lifetime limit from terminal's timeout field.
Supervise for at most 900 s elapsed; if still running, terminate only the saved
terminal session with `process(action="kill", session_id=...)`, then reconcile
its lease instead of starting a replacement. This supervisory cutoff is an
operating rule, not a hard filesystem/host deadline guaranteed by the wrapper.

SIGTERM/interrupt attempt cleanup. SIGKILL cannot run a
finally block: the private daemon has a 20 s idle timeout, and the next call
refuses an unclosed lease. After harness termination, first poll the saved
terminal session if it remains registered. A still-running process must be
supervised or explicitly stopped, not duplicated. If it exited or is lost,
inspect the job's closed.json/action journal; an unclosed lease requires the
original approved proposal with `--recover`
to close only its session. Recovery never replays actions or deletes evidence.
A failed/interrupted approval cannot run again; reconcile unknown actions and
request a new proposal. Attempts do not reset on proposal changes. Expiry is a
command deadline, not a host-level disk quota. Raw byte/duration validation runs
after stop; resource exhaustion is still a host operational risk.

Inspect receipt.json, closed.json, actions.jsonl and raw.webm. Complete receipt
is required for capture-mode freeze. A successful recording is not a verified
edit or a live Creator handoff. Use the common preview/render pipeline next.
