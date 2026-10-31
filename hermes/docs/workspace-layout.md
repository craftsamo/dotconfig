# Workspace layout

Where the Workspaces root is and which areas it holds, defined once for every
tool that reads `~/Workspaces`. Read it when a tool needs the root or the
areas, or when a machine uses names other than the defaults. Part of the
Hermes design docs — index: [`PROFILES.md`](../PROFILES.md).

## The definition

`~/.config/workspaces/layout.json` (`$XDG_CONFIG_HOME/workspaces/layout.json`
when that is set; `WORKSPACES_LAYOUT` names another file). Without the file
the public defaults apply:

```json
{
  "root": "~/Workspaces",
  "areas": [
    { "name": "Projects", "role": "projects", "sensitive": false },
    { "name": "Personal", "role": "personal", "sensitive": true }
  ]
}
```

| Field               | Meaning                                                                                                                                        |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `root`              | Absolute or `~` path of the Workspaces root. `WORKSPACES_ROOT`, when set, overrides it (a relative value is taken from the working directory). |
| `areas[].name`      | A top-level folder of Groups: a plain name, not starting with `.`, unique regardless of case.                                                  |
| `areas[].role`      | `projects` for the one area the workspace registry creates project Groups in; `personal` for any other.                                        |
| `areas[].sensitive` | `true` for an area whose data must not leave the machine unprotected (default `false`).                                                        |

Both keys are optional; a file that sets only `root` keeps the default areas. A
`layout.json` link whose target is gone counts as unreadable, not as absent.
Unknown keys, a relative root, a duplicate area or anything but exactly one
`projects` area make the file invalid, and an invalid file is refused rather
than worked around: the root bounds what a message may attach, so it never
falls back to a guess.

What lives inside a Group (`github/`, `docs/`, `data/`, `assets/`, `.agent/`)
and at the root (`.agent/`, `.inbox/`, `.registry/`) is a fixed convention of
the tools, not part of the layout; the Assistant's
`pipeline/references/workspace-layout.md` describes it.

## Pieces

| Piece                                       | Home                                  | Reader                  |
| ------------------------------------------- | ------------------------------------- | ----------------------- |
| Reader (`load()`, the defaults, validation) | `plugins/_shared/workspace_layout.py` | plugins, launchers      |
| Launcher printing the layout in force       | `../bin/ws-layout`                    | people, shell functions |
| A machine's own layout (optional)           | `~/.config/workspaces/layout.json`    | all                     |

The reader is stdlib only and runs on the system Python 3.9 too, because the
`ws-*` launchers run `python3` from `PATH`. It reads the file on every call,
so a change applies without a restart. Siblings load it by path like the
other `_shared` modules.

`ws-layout` prints the resolved layout as JSON; `--root`, `--areas`,
`--projects` and `--path` print one value each for shell use.

## Who reads it

| Reader                                    | Uses                                                                     |
| ----------------------------------------- | ------------------------------------------------------------------------ |
| Draft scanner (`workspace-drafts`)        | the root, and every area's Groups for their `.agent/`                    |
| Repository scanner (`workspace-repos`)    | the root, and every area's Groups for their `github/`                    |
| Workspace registry (`workspace-registry`) | the root (unless `WSREG_ROOT`), and the projects area for project Groups |
