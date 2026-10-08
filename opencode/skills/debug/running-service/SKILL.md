---
name: debug-running-service
description: >-
  Use when a long-running service (gateway, daemon, supervisor, worker pool)
  silently drops, misroutes or fails to deliver work while its code reads
  correct on inspection (サービスが黙ってメッセージを落とす, 修正したのに再発する,
  デーモン調査, "service silently drops", "fix merged but still failing",
  "contextvars leak", "live service diagnosis"). Produces a proven cause with a
  causal chain, a repro under the service's own interpreter, and ranked fix
  options.
license: MIT
---

<Goal>

Use when a long-running service (gateway, daemon, supervisor, worker pool)
silently drops, misroutes, or fails to deliver work while its code reads
correct on inspection.

Produce a **proven** cause, not a plausible one. The deliverable is a causal
chain where every link is backed by real output: process state, the service's
own log line, the source that emits it, and a reproduction you ran yourself.

The defining constraint of this class: **you cannot stop, restart, or attach a
debugger to the thing you are diagnosing.** It is serving the user right now —
often it is the process you yourself are running inside. So the method is
read-only observation plus offline reproduction.

</Goal>

<Scope>
<UseWhen>

- A service completes work but the notification / reply / delivery never
  arrives ("it finished but nothing woke up").
- A fix was merged and deployed, yet the symptom persists — a second bug hides
  behind the first.
- Behaviour differs between contexts that "should" be identical (per-profile,
  per-tenant, per-worker), suggesting state resolution rather than logic.
- The suspect code path has passing tests, which makes the tests themselves a
  clue rather than a defence.

</UseWhen>
<DoNotUseWhen>

- A reproducible failure in code you can run directly in the foreground — just
  run it.
- A crash with a stack trace pointing at the fault; read the trace.
- The service is simply not running or not configured. Check liveness first
  (step 1); a dead process is an ops problem, not this method.

</DoNotUseWhen>
</Scope>

<Method>

**1 — Establish it is actually running, and since when.**
Supervisor state and process start time bound the search window and tell you
whether the deployed binary even contains the fix you think it does.

```
launchctl list | grep <label>          # or systemctl status / pgrep -fl
ps -o pid,lstart,etime,command -p <pid>
git -C <repo> log --oneline -5         # what shipped
git -C <repo> log --grep <fix-slug>    # did the fix survive the last update?
```

A process older than the fix commit explains everything; stop there. Compare
the process start time against the commit time **explicitly** — do not assume a
restart happened.

**2 — Read the service's own log, windowed to the current life.**
Slice from the restart timestamp forward, then grep for the drop. Do not read
the whole file; do not pipe long output through `tail` to shorten it.

```
awk '$0 >= "YYYY-MM-DD HH:MM"' service.log > /tmp/current_life.log
```

Then grep for `Drop|drop|no live|refus|fail|fatal|ERROR`. A well-written
service names its own failure — a line like *"Dropping X for Y: no live Z (not
falling back)"* is the single most valuable artifact in the whole
investigation. **Count occurrences and check they continue after the restart**:
that is what distinguishes "fix didn't land" from "fix landed, second bug".

**3 — Grep the source for the exact log string.**
The emitting branch tells you which resolver returned nothing. Read that
resolver and every helper it calls, especially anything that answers *"which
tenant / profile / instance am I?"* at call time.

**4 — Form ONE falsifiable hypothesis, phrased as a difference.**
Good hypotheses in this class read: *"resolver R answers A when called from
context X and B from context Y; the delivery path runs in X, the tests in Y."*
A hypothesis you cannot express as a two-context comparison is not sharp enough
yet — go back to step 3.

**5 — Prove it with a standalone repro (see below). Then check why the tests
passed** — the answer is usually that the test harness constructs the object in
the neutral context and so never reproduces the difference. Say so in the
report; it is what stops the same fix being "re-landed" a third time.

</Method>

<TheDecisiveMove>

A **standalone repro script that imports the real modules under the service's
own interpreter**. Not a mental argument, not a unit test inside the suite —
a script whose printed output a reader can check in two lines.

Rules that make it decisive:

- **Use the service's own venv**, not the system Python:
  `cd <repo> && ./venv/bin/python /tmp/repro.py`. Plugins and internal imports
  usually fail anywhere else.
- **Import the real symbols** (`from gateway.authz_mixin import ...`), never a
  paraphrase of the logic. A paraphrase proves your reading, not the code.
- **Build the minimal host object.** `object.__new__(Cls)` plus only the
  attributes the path touches sidesteps a heavyweight `__init__`. A tiny
  subclass of the real mixin is even better.
- **Mirror the live configuration**, and say so in a comment with the evidence
  ("root config has `platforms: {}` and the launcher strips the tokens, so the
  default profile owns no adapter here").
- **Print both contexts side by side.** One line each, same call, only the
  context differing. That single block of output is the proof you paste into
  the report.

Escalate the probe when the first one only shows *that* contexts differ: a
second script that reproduces *how the wrong context got there* (e.g. spawning
a task inside the scope and resolving after the scope exited) converts a
correlation into a mechanism.

</TheDecisiveMove>

<KnownBugClasses>

- **Async context leak into long-lived tasks** — the highest-yield pattern in
  this class, and the one that makes a correct-looking fix fail in production.
  `asyncio.create_task()` copies the *current* context; a task created inside a
  scoped `with` block keeps that scope for its whole life, long after the block
  exits. Any identity resolved *dynamically* inside that task then answers with
  the stale scope.
- **Fail-closed resolvers that log nothing** — a security-correct "never fall
  back" branch returning `None` silently. Symptom is total silence, which reads
  like the event was never generated. Grep for the resolver, not the symptom.
- **Two-layer bugs** — the merged fix is genuinely correct and genuinely
  landed, but it calls a resolver that is wrong one level down. The tell is a
  drop that now logs (thanks to the fix) but still drops.

</KnownBugClasses>

<ReportShape>

For this class the user wants a diagnosis they can act on, in this order:

1. **Verdict first**, one line — including whether the previous fix landed.
2. **Symptom, quoted from the log**, with timestamps and a count.
3. **Mechanism as a numbered causal chain**, each step naming the concrete
   function/file involved. No prose paragraphs.
4. **Proof** — the repro's actual output, verbatim, in a code block.
5. **Why the existing tests pass** — one short paragraph.
6. **Fix options, ranked, with a recommendation and its blast radius.**

Keep it compact; no restating the request, no hedging padding.

</ReportShape>

<Pitfalls>

- **Assuming a merged fix is the running fix.** Check the process start time
  against the commit time, every time.
- **Stopping at the first fix that matches the symptom description.** If the
  drop still happens after that fix deployed, the fix is a *layer*, not the
  cause.
- **Trusting a green test suite.** Ask what context the test builds the object
  in. A test that never enters the leaking scope cannot fail.
- **Reasoning about `contextvars` instead of executing them.** Context
  propagation is exactly where careful reading goes wrong; run it.
- **Running the probe on the system interpreter** and misreading an
  `ImportError` as evidence about the service.
- **Restarting or reloading the service to "test" a theory.** If it is
  single-instance and supervised, a second instance can break it; diagnose
  from logs and a separate repro instead.
- **Dumping a whole log file into context.** Window it by timestamp first.
- Leaking secret values while inspecting a credential-related fault: name keys,
  never print them.

</Pitfalls>

<Verification>

- The verdict names a specific function and a specific context difference.
- Every claim in the report maps to real output: `ps`/`launchctl`, a quoted log
  line, a source excerpt, or the repro's stdout.
- The repro ran under the service's own interpreter and imported real symbols.
- The "why tests pass" question is answered, not skipped.
- Nothing was restarted.

</Verification>
