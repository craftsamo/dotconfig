# workspaces — the ~/Workspaces skill cluster (maintainer note)

Skills rooted in the `~/Workspaces` data domain, grouped so their tight coupling is legible and
their shared helper has an obvious home.

| skill | CLI | role |
|---|---|---|
| `people/` | `pp` | canonical person registry (SQLite) |
| `household-budget/` | `hb` | multi-currency ledger (SQLite) |
| `projects/` | `pj` | projects registry: identity/repos/links/memberships/tags (SQLite) |
| `message-reply/` | — (prose) | draft replies using People context |
| `_cross.py` | — (lib) | shared cross-skill contract + resolver (imported, never executed) |

The three registries cross-reference each other; `_cross.py` is the single place that defines how.

## Cross-skill contract (`_cross.py`)
- **Reads cross domains via the sibling CLI** — never open another skill's DB/files, and never
  call its `validate` (prevents recursion). Writes never cross domains.
- **Producers** answer with an envelope: `{"contract_version": 1, "skill": "<name>", "data": {…}}`
  (`_cross.emit`). **Consumers** (`_cross.call`) check `contract_version` and **skip with a
  warning** on absence / error / version skew (returns `None`).
- **`call()` execs the CLI directly** (argv0 = `pp`/`hb`/`pj`, allowlist-friendly), falling back
  to the interpreter only if the file is not directly executable.

### Resolution order (`resolve(skill)`)
1. env override `<CLI>_BIN` (e.g. `PP_BIN`, `HB_BIN`, `PJ_BIN`)
2. manifest `workspaces/cross.json` → `{ "people": "/abs/pp", … }` (optional)
3. convention `workspaces/<name>/scripts/<cli>` (siblings share this dir)

`REGISTRY` maps logical name → cli basename; the skill dir == the logical name. Add a new
cross-participant by adding one row there.

## Ports & wiring (current)
| skill | exposes (producer) | consumes (consumer) |
|---|---|---|
| people (`pp`) | `list --json`, `show --json` | `pj members` (import-projects); `pj members` + `hb counterparties` (validate) |
| household-budget (`hb`) | `projects --json`, `counterparties --json` | `pp list` (validate) |
| projects (`pj`) | `projects/members/repos/links --json` | `pp list` + `hb projects` (validate) |

## Usage
```python
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # skills/workspaces/
try:
    import _cross
except Exception:
    _cross = None
# producer:  _cross.emit("people", {"persons": [...]})
# consumer:  data = _cross.call("projects", ["members", "--json"])  # None => skip with warning
```
