# Workspaces Drive mount

Large folders of `~/Workspaces` live in Google Drive instead of on the local
disk: every Group's `assets/`, and any folder inside a Group moved there with
`ws-drive move`. Read it when setting the mount up, moving a folder to Drive or
back, or when a link points at nothing.

Part of the Hermes mechanics docs — entry: [`README.md`](../../README.md).

## Shape

```
Drive: Workspaces/Projects/<Group>/<folder>/   plain: readable on the web and phone
       Workspaces/Personal/<Group>/<folder>/   rclone crypt: file names and contents encrypted
                 ▲
                 │  rclone nfsmount, files fetched on demand into a local cache
~/Workspaces/.drive/{Projects,Personal}/…
                 ▲
~/Workspaces/<Tree>/<Group>/assets      →  ../../.drive/<Tree>/<Group>/assets
~/Workspaces/<Tree>/<Group>/data/raw    →  ../../../.drive/<Tree>/<Group>/data/raw
```

Every folder keeps its usual path, so Hermes and every tool read and write it
as before; only the link sends them to Drive. The link is relative and the
mount sits inside `~/Workspaces`, so a file's real path stays inside the
workspace and the messaging plugins' send check (a file must resolve inside
`~/Workspaces`) accepts it. Nothing of a moved folder remains locally beyond
the cache. The cache's 20 GB limit is soft: files open or still uploading are
never evicted, so it can exceed the limit while a large write is in flight;
what was not read for a week ages out.

Which folders are on Drive is read from the links themselves; nothing else
records it. A real local `assets/` is a folder this Mac keeps: it is reported,
never linked over.

While the mount is down the links point at nothing: a read or write fails
instead of landing on the local disk, and the mount point refuses to mount
over anything written into it meanwhile.

## Pieces

| Piece                                                                           | Home                                                                                                        |
| ------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| Engine: setup, LaunchAgent, links, move, restore, status, the agent's run loop  | `plugins/workspace/workspace-drive/drive.py` (stdlib only)                                                  |
| Command for a person (`ws-drive`), on Hermes' own Python                        | `bin/ws-drive`                                                                                              |
| LaunchAgent `local.hermes.workspaces-drive.mount`                               | `launchd/local.hermes.workspaces-drive.mount.plist.tmpl`, entry `launchd/bin/hermes-workspaces-drive-mount` |
| Encrypted rclone config, cache, the links lock, the journal of interrupted work | `$HERMES_LOCAL/workspaces-drive/` (`rclone.conf`, `cache/`, `links.lock`, `journal/`)                       |
| Config password, crypt password and salt, optional OAuth client                 | Keychain, project `hermes`, scope `workspaces-drive`                                                        |

## Layout

The layout is fixed in `drive.py`, the same on every Mac, so a change is a
reviewed edit there rather than a per-machine setting:

| What                  | Value                                                                             |
| --------------------- | --------------------------------------------------------------------------------- |
| Trees                 | `Projects` stored as is, `Personal` through rclone crypt                          |
| Linked in every Group | `assets/`                                                                         |
| Never moved           | `github/` (repositories), any folder whose name starts with `.`, the Group itself |
| Folder in My Drive    | `Workspaces`                                                                      |
| OAuth scope           | `drive`                                                                           |
| Cache                 | 20 GB soft limit, a week's age                                                    |
| Maintenance pass      | at start and every 15 minutes                                                     |

Changing a tree's storage would leave what is already on Drive unreadable
through the new mapping, so it needs a move of that data, not only an edit.

**Scope.** `drive` lets the mount see files put into the folder from the web
or a phone (`drive.file` would limit the token to what the mount itself
created). Only `Workspaces/` is mounted; the scope decides what the token
could reach beyond it.

**Encrypted trees** keep folder names readable on Drive and encrypt file names
and contents. Their password and salt sit in the Keychain and inside the
encrypted config; keep a copy of both off this Mac as well, since without them
those files cannot be read again.

## Credentials

The rclone config (`rclone.conf`) is encrypted with
`WORKSPACES_DRIVE_CONFIG_PASS`, which rclone reads at every start through
`--password-command` from the Keychain: it is never in a process environment
or on a command line, and rclone can save a refreshed Google token back into
the file. `setup` hands the crypt keys and an own OAuth client to rclone as a
JSON body through a short-lived `rclone rcd` listening on a unix socket inside
the private state directory, never as arguments, and stops it on every way
out. The items are stored `--no-env` in a scope no Hermes profile's
environment receives ([access-common.md](../access-common.md) "Secret
scoping"); only the LaunchAgent's rclone and the person running `ws-drive`
read them.

## Setup

1. `brew bundle` (or `brew install rclone`). Homebrew's rclone has no FUSE
   `mount` on macOS; `nfsmount` needs neither macFUSE nor root.
2. Optional: an own Google OAuth client (Desktop app, Drive API enabled)
   instead of rclone's shared, rate-limited one, stored as
   `secret set WORKSPACES_DRIVE_CLIENT_ID -p hermes --scope workspaces-drive --no-stage --no-env`
   and the same for `WORKSPACES_DRIVE_CLIENT_SECRET`.
3. `ws-drive setup` — generates the config password and crypt keys into the
   Keychain, creates the encrypted config and both remotes, runs the Google
   sign-in (`config reconnect`: answer `y` to use the browser, `n` to the
   shared-drive question), and creates the tree folders on Drive. Re-running
   it skips what already exists.
4. `ws-drive install` — renders and loads the agent and waits for the mount.
   Run it again after a Hermes update: the agent runs on the Python that ran
   `install`, and `status` says when that interpreter is gone.

`uninstall` unloads the agent and unmounts; Drive data, the config and the
Keychain items stay.

## Links

Each maintenance pass gives every Group an `assets/` link, creating the folder
on Drive; a Group created later gets its link at the next pass (`ws-drive
links` does it at once). A new link can read as missing for up to a minute,
until the mount sees the folder.

The first pass after the agent starts, and every `ws-drive links`, also links
each folder that is on Drive but missing here, at the highest missing level
below a real local folder: a new Mac gets every moved folder back, and a link
removed by hand comes back. To take a folder off Drive, restore it.

## Moving a folder

`ws-drive move <Tree>/<Group>/<folder>[/…]` takes any folder inside a Group
but the ones the layout keeps here, and refuses a folder holding symlinks
(Drive cannot keep them) or a Git repository. It copies the folder to Drive
(empty folders included) and checks the copy by hash (`cryptcheck` for
encrypted trees), sets the folder aside as `<folder>.migrating` and puts the
link in its place (from then on a new open of the path reaches Drive), refuses
while `lsof` finds a file of the set-aside folder still open, waits until the
mount lists as many files as were copied (Drive's change feed shows them
within about a minute, the mount's 2-minute directory cache at the latest; the
move gives up after 6), checks the set-aside folder against Drive again (so a
file written after the first check fails the move), and only then deletes it.
A failure or a stop before that puts the local folder back and keeps the Drive
copy; an existing `<folder>.migrating` is refused, never overwritten. Stop
whatever writes into the folder before moving it.

`ws-drive restore <path>` brings a moved folder back: it checks there is room,
waits until no file written through the mount is still uploading (the mount's
cache marks such a file dirty, and a read of Drive would miss it), copies the
folder from Drive into `<folder>.restoring`, checks it against Drive both ways,
refuses while `lsof` finds a file of it open through the mount, replaces the
link with the folder, waits for uploads and checks again (so nothing written
to Drive in between is lost), and only then sends the Drive copy to Drive's
trash. A failure before the swap leaves the folder on Drive; when the second
check differs, both copies are kept for a person to compare. An edit made on
Drive from another device during a restore goes to the trash with the folder,
where Drive keeps it for 30 days.

Moves, restores and links passes run under one lock (`links.lock`), which the
kernel releases when its holder dies, so a pass never links a folder that is
being moved. Each move and restore writes where it stands to `journal/`; a
process killed halfway (a power cut, a `kill -9`) is finished or undone by the
next maintenance pass or `ws-drive move`, `restore` or `links`, so a half-moved folder never
stays half-moved. `restart` refuses while the lock is held (`--force` stops the
work, which the next pass then undoes).

`status` (`--json` for tools) lists the agent, the mount, the cache size, the
folders on Drive, the `assets/` kept here, foreign links, interrupted work and
what a links pass would add, without changing anything.

## NFS behaviour

The mount is rclone's built-in NFS server mounted by macOS's NFS client
(`rclone nfsmount`, marked experimental upstream). The options exist for these
reasons:

- `locallocks` — the server has no lock manager; without it the first file
  created can block in the kernel indefinitely.
- `soft,intr,timeo=50,retrans=2,deadtimeout=30` — when the server dies, calls
  fail with a timeout and the mount is dropped after 30 s instead of hanging
  the processes that touch it; launchd then starts the agent again, which
  clears any leftover mount before mounting. macOS shows a "server connection
  interrupted" dialog in that window.
- `mutejukebox` — slow Drive answers do not list the mount as unresponsive.
- `nonegnamecache` — the client asks again for a name it once found missing;
  without it a folder added on Drive outside the mount (by a move, the web or
  a phone) stays invisible until its parent changes through the mount.
- `nobrowse` — no volume on the Desktop or in Finder's sidebar.

macOS keeps extended attributes it cannot store on NFS in AppleDouble files
(`._<name>`), one per file it creates; the maintenance pass deletes them, and
`.DS_Store` files, on Drive for good (not into its trash).

The mount is a network volume to macOS's privacy protection: a program that
launchd starts reaches it only if it holds that permission (Network Volumes
or Full Disk Access under Privacy & Security), and `/bin/sh` started by
launchd is refused with "Operation not permitted". The agent therefore runs
the engine on Hermes' own Python, which holds it, and still creates and sweeps
Drive folders through rclone rather than the mount. Whatever reads or writes
the links from a LaunchAgent, the gateway included, needs that permission for
its own program.
