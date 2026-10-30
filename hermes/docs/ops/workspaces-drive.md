# Workspaces Drive mount

Large Group directories of `~/Workspaces` (by default each Group's `assets/`)
live in Google Drive instead of on the local disk. Read it when setting the
mount up, moving a Group's files to Drive, changing what goes there, or when a
Group link points at nothing.

Part of the Hermes mechanics docs — entry: [`README.md`](../../README.md).

## Shape

```
Drive: <WSD_DRIVE_PATH>/Projects/<Group>/assets/   plain: readable on the web and phone
       <WSD_DRIVE_PATH>/Personal/<Group>/assets/   rclone crypt: names and contents encrypted
                 ▲
                 │  rclone nfsmount, files fetched on demand into a local cache
~/Workspaces/.drive/{Projects,Personal}/…
                 ▲
~/Workspaces/<Tree>/<Group>/assets  →  ../../.drive/<Tree>/<Group>/assets
```

Every Group keeps its usual path, so Hermes and every tool read and write
`<Tree>/<Group>/assets/…` as before; only the link sends them to Drive. The
link is relative and the mount sits inside `~/Workspaces`, so a file's real
path stays inside the workspace and the messaging plugins' send check (a file
must resolve inside `~/Workspaces`) accepts it. Nothing of the moved files
remains locally beyond the cache. `WSD_CACHE_MAX_SIZE` is a soft limit: files
open or still uploading are never evicted, so the cache can exceed it while a
large write is in flight; `WSD_CACHE_MAX_AGE` ages out what was not read.

While the mount is down the links point at nothing: a read or write fails
instead of landing on the local disk, and the mount point refuses to mount
over anything written into it meanwhile.

## Pieces

| Piece                                                                                        | Home                                                                                                        |
| -------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| Launcher (`setup`, `install`, `restart`, `status`, `links`, `migrate`, `uninstall`)          | `launchd/workspaces-drive-launchctl.sh`                                                                     |
| LaunchAgent `local.hermes.workspaces-drive.mount`                                            | `launchd/local.hermes.workspaces-drive.mount.plist.tmpl`, entry `launchd/bin/hermes-workspaces-drive-mount` |
| Foreground run: mount, then a maintenance pass at start and every `WSD_MAINTENANCE_INTERVAL` | `scripts/workspaces-drive-run.sh`                                                                           |
| Settings, defaults and shared helpers                                                        | `scripts/workspaces-drive-env.sh`                                                                           |
| Encrypted rclone config, cache, machine-local settings                                       | `$HERMES_LOCAL/workspaces-drive/` (`rclone.conf`, `cache/`, `settings.env`)                                 |
| Config password, crypt password and salt, optional OAuth client                              | Keychain, project `hermes`, scope `workspaces-drive`                                                        |

## Settings

Each `WSD_*` value resolves from the environment, then
`$HERMES_LOCAL/workspaces-drive/settings.env` (plain `KEY=value` lines; the
private overlay links its own there), then the defaults in
`scripts/workspaces-drive-env.sh`:

| Setting                                    | Default                         | Meaning                                           |
| ------------------------------------------ | ------------------------------- | ------------------------------------------------- |
| `WSD_TREES`                                | `Projects=plain Personal=crypt` | top-level trees on Drive, each `plain` or `crypt` |
| `WSD_LINK_DIRS`                            | `assets`                        | Group directories that live on Drive              |
| `WSD_SKIP_GROUPS`                          | empty                           | `Tree/Group` words never linked                   |
| `WSD_DRIVE_PATH`                           | `Workspaces`                    | folder in My Drive holding the trees              |
| `WSD_DRIVE_SCOPE`                          | `drive`                         | OAuth scope asked at setup (below)                |
| `WSD_CACHE_MAX_SIZE` / `WSD_CACHE_MAX_AGE` | `20G` / `168h`                  | local cache soft limit and age                    |
| `WSD_MAINTENANCE_INTERVAL`                 | `900`                           | seconds between maintenance passes                |
| `WSD_NFS_OPTIONS`                          | see the script                  | NFS mount options (below)                         |

A change takes effect at the next `restart`. The LaunchAgent receives only
`HERMES_LOCAL` (rendered by `install`), so settings for the agent go into
`settings.env`, not the shell environment. Which Groups or trees a person
keeps off Drive is private: it goes into the overlay's `settings.env`, never
into this tree.

**Scope.** `drive` lets the mount see files put into the folder from the web
or a phone; `drive.file` limits the token to what the mount itself created,
so such files stay invisible to it. Either way only `WSD_DRIVE_PATH` is
mounted; the scope decides what the token could reach beyond it.

**Encrypted trees** keep directory names readable on Drive and encrypt file
names and contents. Their password and salt sit in the Keychain and inside the
encrypted config; keep a copy of both off this Mac as well, since without them
those files cannot be read again.

## Credentials

The rclone config (`rclone.conf`) is encrypted with
`WORKSPACES_DRIVE_CONFIG_PASS`, which rclone reads at every start through
`--password-command` from the Keychain: it is never in a process environment
or on a command line, and rclone can save a refreshed Google token back into
the file. `setup` hands the crypt keys and an own OAuth client to rclone as a
JSON body on stdin, through a short-lived `rclone rcd` listening on a unix
socket inside the private state directory, never as arguments. The items are stored `--no-env` in a scope no Hermes profile's
environment receives ([access-common.md](../access-common.md) "Secret
scoping"), so Hermes works with Drive through the mounted folder. A terminal
`secret get … -p hermes` is refused only on profiles whose access plugins
guard that project; this mount adds no guard of its own.

## Setup and use

1. `brew bundle` (or `brew install rclone`). Homebrew's rclone has no FUSE
   `mount` on macOS; `nfsmount` needs neither macFUSE nor root.
2. Optional: an own Google OAuth client (Desktop app, Drive API enabled)
   instead of rclone's shared, rate-limited one, stored as
   `secret set WORKSPACES_DRIVE_CLIENT_ID -p hermes --scope workspaces-drive --no-stage --no-env`
   and the same for `WORKSPACES_DRIVE_CLIENT_SECRET`.
3. `launchd/workspaces-drive-launchctl.sh setup` — generates the config
   password and crypt keys into the Keychain, creates the encrypted config
   and both remotes, runs the Google sign-in (`config reconnect`: answer `y`
   to use the browser, `n` to the shared-drive question), and creates the tree
   folders on Drive. Re-running it skips what already exists.
4. `launchd/workspaces-drive-launchctl.sh install` — loads the agent and waits
   for the mount. Each maintenance pass then gives every Group a link for each
   of `WSD_LINK_DIRS`, creating the folder on Drive; a Group created later gets
   its link at the next pass (or run `links`). A new link can read as missing
   for up to a minute, until the mount sees the folder.
5. A Group that already has a real `assets/` directory is reported, never
   moved: `launchd/workspaces-drive-launchctl.sh migrate <Tree>/<Group>`
   copies it to Drive (empty folders included) and checks the copy by hash (`cryptcheck` for encrypted
   trees), sets the directory aside as `<dir>.migrating` and puts the link in
   its place (from then on a new open of the path reaches Drive), refuses
   while `lsof` finds a file of the set-aside directory still open, waits
   until the mount lists as many files as were copied (Drive's change feed
   shows them within about a minute, the mount's 2-minute directory cache at
   the latest; migrate gives up after 6), checks the set-aside
   directory against Drive again (so a file written after the first check
   fails the move), and only then deletes it. A failure or an interrupt
   before that puts the local directory back and keeps the Drive copy; an
   existing `<dir>.migrating` is refused, never overwritten. Stop whatever
   writes into the directory before migrating it. Migration and every links
   pass run under one `lockf` lock (`links.lock`), which the kernel releases
   when its holder dies, so a pass never links a directory that is being
   moved.

`status` shows the agent, the mount, the cache size and what a links pass
would change, without changing it. `uninstall` unloads the agent and unmounts; Drive data, the
config and the Keychain items stay.

## NFS behaviour

The mount is rclone's built-in NFS server mounted by macOS's NFS client
(`rclone nfsmount`, marked experimental upstream). The default options exist
for these reasons:

- `locallocks` — the server has no lock manager; without it the first file
  created can block in the kernel indefinitely.
- `soft,intr,timeo=50,retrans=2,deadtimeout=30` — when the server dies, calls
  fail with a timeout and the mount is dropped after 30 s instead of hanging
  the processes that touch it; launchd then starts the agent again, which
  clears any leftover mount before mounting. macOS shows a "server connection
  interrupted" dialog in that window.
- `mutejukebox` — slow Drive answers do not list the mount as unresponsive.
- `nonegnamecache` — the client asks again for a name it once found missing;
  without it a folder added on Drive outside the mount (by `migrate`, the web
  or a phone) stays invisible until its parent changes through the mount.
- `nobrowse` — no volume on the Desktop or in Finder's sidebar.

macOS keeps extended attributes it cannot store on NFS in AppleDouble files
(`._<name>`), one per file it creates; the maintenance pass deletes them, and
`.DS_Store` files, on Drive for good (not into its trash). Symlinks are not
kept on Drive, so `migrate` refuses a directory that holds any.

The mount is a network volume to macOS's privacy protection: a program that
launchd starts reaches it only if it holds that permission (Network Volumes
or Full Disk Access under Privacy & Security), and `/bin/sh` started by
launchd is refused with "Operation not permitted". So the maintenance pass
never goes through the mount: it creates Group folders with `rclone mkdir`
and sweeps with `rclone delete`, and the mount sees both through Drive's
change feed. Whatever reads or writes the Group links from a LaunchAgent,
the gateway included, needs that permission for its own program.
