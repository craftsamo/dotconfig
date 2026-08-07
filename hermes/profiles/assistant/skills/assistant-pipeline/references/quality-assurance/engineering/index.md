# Engineering QA — outcome-level gate

The engineer's own loop already verifies each unit (repo checks +
OpenCode review agent) — do not re-review diffs line by line. Your gate
is outcome-level, applied per unit before the next one is released:

- The reported check/test output is actual (not claimed) — spot-check by
  running the named command or reading the named log.
- The deliverable matches the plan's done criteria.
- Nothing out of scope changed: `git -C <repo> status` /
  `log --oneline` spot check against the Authority's `scope:` /
  `do not touch:` boundaries.
- For UI work, a rendered screenshot exists — code-only inspection is
  not verification.

Defects → feedback turn into the same session. Accepted → GitHub ops
(`../../execute/engineering/index.md`), then close.
