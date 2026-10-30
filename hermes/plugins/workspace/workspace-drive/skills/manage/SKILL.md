---
name: manage
description: "Use when the Assistant proposes, runs or follows a move of a folder under ~/Workspaces to Google Drive, or a restore back, with workspace_drive. Not for files in a folder already on Drive: read and write them at their usual path."
---

# Workspaces Drive

Every Group's `assets/` lives in Google Drive behind a link, and any other folder
inside a Group can be moved there too. A folder on Drive keeps its usual path:
read and write it as before. Which folders are on Drive is what
`workspace_drive status` lists; nothing else records it.

## When to propose a move

- Large material that is rarely opened: finished footage, exports, archives,
  datasets kept for reference.
- Only canonical folders inside a Group: `docs/`, `data/` or folders under them,
  `assets/` a Mac keeps locally, and the like. Never `github/` (repositories),
  folders whose name starts with `.` (drafts in `.agent/` and the inbox are
  promoted first, tool settings stay with their tool), or a whole Group.
- Not a folder something is writing into right now, and not one a job needs to
  read fast and often: a file not read recently is downloaded when opened.
- `Personal/` is stored encrypted on Drive; `Projects/` is stored as is and is
  readable in Drive's web and phone apps. Say which, when proposing.

Propose in chat first: the folder, its size from `status` or a listing, and why.
Call `move` only once the user agrees.

## Running it

1. `workspace_drive` with `action: move` (or `restore`) and `path:
   <Tree>/<Group>/<folder>`. The user answers an approval card showing the folder,
   its size and what happens to the local copy. A denied card means no: do not
   ask again unchanged.
2. The approved call only queues the work. The Drive mount's agent runs it: a
   copy, two hash checks, then the local copy is deleted (move) or the Drive copy
   goes to Drive's trash (restore). A few MB take a minute; several GB take up to
   an hour. Tell the user it is running and go on with other work.
3. The outcome arrives as a notification. Report it in one line. Until then,
   `status` shows it under queued, running or recent jobs; do not poll in a loop.

## When it does not finish

Nothing is lost when a move or restore fails: a move that stops puts the local
folder back, and a restore that stops leaves the folder on Drive. Relay the
reason and what the user can do:

- Files open in another app: close the app, then ask again.
- The folder changed while it was copied: let whatever writes it finish, then ask
  again.
- Files still uploading: try again in a few minutes.
- The mount is down, or `status` lists interrupted work, foreign links or
  leftovers: tell the user; restarting or repairing the mount (`ws-drive
  restart`) is theirs, not yours.

Never move, copy or delete through the terminal, `ws-drive`, rclone or
`~/Workspaces/.drive` to work around a failure.
