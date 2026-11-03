# gcloud commands without a card only inside a project mandate

Status: in force
Owner doc: docs/google-access.md "gcloud mandates"

## Decision

A `gcloud` command that is not a read runs without its approval card only when
it fits one project mandate the user approved on a card of its own. A mandate
names:

- one project id (a call without `project` is never covered);
- one to five command paths, each the exact leaf path of the installed SDK's
  command tree (`run deploy`, `run services update`, `run jobs update`); a
  release track is part of the path, so `beta run deploy` is not `run deploy`;
- up to 20 flags a covered call may use (`--image`, `--region`, `--memory` …),
  each a long flag the installed SDK's tree declares for at least one of the
  named paths; none when the call needs none;
- how many covered commands an hour it allows (1 to 10, each call counts one),
  a purpose in one line, and an end at most 7 days out.

The check is closed: a command fits only when every part of it is accounted
for. Its project and path are the mandate's, the SDK's tree confirms the path
and the flags, and the hour has room, and its arguments are nothing but:

- long flags the mandate lists, written `--flag=value` or `--flag value` (a
  `--no-` form only if that exact form is listed, and only of a flag the tree
  declares as a switch, and a switch written `--flag=value` is not read); any
  other flag, `--` (the end of flags), a short flag such as `-q`, a flag the
  tree does not list or a flag missing its value makes the call ask;
- flag values that are plain tokens: letters, digits and `. _ , : = @ / -`,
  starting with a letter or digit, up to 300 characters, naming no `gs://` or
  other `://` URL, no `projects/`, `organizations/` or `folders/` resource
  name and no `..`; the project check is case-insensitive;
- images in the mandate's project only. The value of a flag whose last word is
  `image` (`--image`, `--base-image`) or whose last two are `image-url` must
  start exactly with `gcr.io/<project>/`, `<us|eu|asia>.gcr.io/<project>/` or
  `<region>-docker.pkg.dev/<project>/` (the mandate's project; no port, no
  trailing dot, case aside), so `docker.io`, `ghcr.io`, a bare `nginx` and
  another project's image ask. `--pack` must hold an `image=` and every
  `image=` and `builder=` in it must be such a path. Any other value that
  starts like a Google registry (`gcr.io:443/…`, `us-docker.pkg.dev/other/…`)
  must be one too;
- positionals that are plain resource ids: lowercase letters, digits, `.`, `_`
  and `-`, at most 63 characters, so no path, URL or resource name.

Whatever the terms say, these always ask on their card, and a mandate naming
one is refused when it is made:

- a path whose last word starts with `delete`, `remove`, `destroy`, `purge`,
  `reset`, `cancel`, `disable`, `undelete`, `rm`, `restore`, `stop`, `suspend`,
  `undeploy`, `abandon`, `revoke` or `replace` (`run services replace` applies
  a whole YAML);
- a path holding, as a word or a dash-delimited part of one (`set-iam-policy`
  holds `iam`), `iam`, `service-account(s)`, `keys`, `secrets`, `kms`,
  `billing`, `organizations`, `folders`, `projects`, `resource-manager`,
  `auth`, `config`, `ssh`, `scp`, `iap`, `tunnel`, `proxy`, `port-forward`,
  `connect`, `access-approval`, `org-policies`, `identity`, `pam`,
  `access-context-manager`, `firewall-rules`, `access-config`, `metadata`,
  `password`, `scc`, `builds` (`builds submit` runs arbitrary build steps) or
  `storage` (the whole group: it moves local and cross-project data by
  positionals), and every word the read rules keep out
  (`GCLOUD_SENSITIVE`: a command that hands out a credential or key material);
- a flag that can never be on a mandate's list, judged on its dash-delimited
  words once a leading `no-`, `clear-`, `set-`, `update-`, `add-` or `remove-`
  is stripped (`NEVER_FLAG_WORDS`): service-account(s), ingress, egress,
  network(s), vpc, subnet(work), iap, invoker, iam, member, role(s), acl, pap,
  public, authorized-networks, kms, key(s), secret(s), breakglass,
  binary-authorization, security-level, scopes, metadata, ssl, assign-ip,
  address, source-ranges, audiences, cloudsql, workload-pool,
  legacy-authorization, identity, organization, folder, billing-project,
  impersonate, account, configuration, delete (any `--delete-*`),
  unauthenticated, bucket, volume(s), project(s) (`--image-project`,
  `--source-project`, `--host-project` …), namespace and password
  (`--root-password`); any flag ending in `-file`, `-dir`,
  `-directory` or `-path`; `--source`; and every `GCLOUD_WRITE_FLAGS` flag.
  `unauthenticated`, `bucket`, `volume(s)` and `subnetwork` are this
  decision's own additions to the families a review named;
- a read, which never needs a mandate, and any command the tree cannot confirm.

A mandate is never made by another mandate, never where nobody can answer its
card and never for an inbound A2A request; revoking one needs no card and ends
it at once.

The hook decides a command is covered and records which mandate beside the
digest of the command it would run; the engine takes that record, plans the call
again, requires the same digest, checks again that the mandate is in force and
the call still fits, and counts the command (one ledger row) before it starts,
under the store's lock. A command that no longer fits is refused with nothing
run. Inside a mandate a command also runs where nobody can answer a card, such
as a cron job. A command that asked on a card is recorded and checked the same
way, so it runs only as the card showed. A command that runs on a mandate runs
in a fresh, empty, private (0700) temporary directory that is removed
afterwards, so a relative name or an implicit `.` resolves to nothing: a deploy
from local source does not work under a mandate (deploy an image). A command
that asked on its card keeps the process's working directory, since the user
saw it. A read and a command outside every mandate keep the rules of the access
doc.

Mandates are stored by the shared mandate store
(`plugins/_shared/mandate_store.py`) in the plugin's state directory, and the
commands they cover are counted in the shared MAC'd ledger beside them
(`plugins/_shared/mandate_ledger.py`).

## Why

- Redeploying one service in one project, again and again while it is being
  built, needs a card per call otherwise, which trains the user to approve
  without reading. A card's "session" or "always" covers only an identical
  command, so it cannot say "these commands in this project, for a few days".
- The bounds keep an injected agent away from what cannot be taken back or what
  widens access: it cannot delete or stop anything, grant a role, mint a key or
  service account, read or replace a secret, touch billing or the project
  itself, open a shell or tunnel, make a service public or reroute its
  network, or reach another project, a local path or a bucket by a value. What
  is left is a deploy or update of a named command in a named project with the
  few flags the user named, which the next deploy undoes, a few times an hour.
- A command path is exact because neighbouring commands differ by one word
  (`deploy`, `delete`, `set-iam-policy`); the SDK's own tree, not the call's
  wording, says what the path is, and a release track is a different command.
  Without the tree nothing is covered.
- The arguments are an allowlist, not a deny list. A list of flags to refuse
  cannot keep up with a CLI that has hundreds of them per command, many of which
  change identity, access or the network (`--ingress-settings`,
  `--run-service-account`, `--no-iap`, `--breakglass`, `--predefined-acl`,
  `--scopes`, `--assign-ip` …) or read and write local paths (`--source`,
  `--env-vars-file`). So the user names the flags on the card, the tree must
  declare each, a family of words that mean identity, access, network, secrets
  or paths can never be named, and a call carrying anything else asks.
- The one-project bound would be bypassed by values and positionals that name
  another resource (`gs://other/x`, `projects/OTHER/…`, `--organization`, a
  `gcr.io/other/…` image) or a local path, so a value is a plain token of a
  narrow alphabet and a positional a plain lowercase id. An image is a registry
  path of the mandate's project, not merely "not another project's": a public
  image from `docker.io` or `ghcr.io` runs someone else's code with the
  service's identity. Because a positional or value can still be a bare name
  that resolves against the working directory, a covered call runs in an empty
  one. This is a check on the call's text, not a promise about what a listed
  flag does: a user who lists `--set-env-vars`, `--command` or `--args` lets the
  agent choose their values.
- Counting before the run, and also when it fails, keeps the hourly bound
  whatever happens to the command. A deleted, emptied or replaced ledger reads
  as used up, never as unused.
- The 7-day ceiling is the Cloudflare mandate's: a forgotten mandate should
  lapse on its own.

## Do not

- Cover a delete or anything that ends, undoes or moves something, IAM, a
  service account, a key, a secret, billing, a project or organization, storage,
  ssh or a tunnel, a read, a command whose path the tree cannot confirm, or a
  call with no project or another one, whatever the terms say. Match a command
  path by prefix or by wording instead of exactly.
- Run a covered command in the process's working directory, or accept an image
  from outside the mandate's project registry paths.
- Let a call carry an argument the mandate did not name: an unlisted flag, `--`,
  a short flag, a flag the tree does not list, a value or positional that is
  not a plain token, or a flag of the never-covered families; turn the flag
  list back into a deny list, or allow a flag the tree does not declare.
- Let a mandate be made without its own card, from a cron job, a single query
  or an inbound request, or let one raise its own bounds.
- Decide what is in force from the history file: only the MAC'd head does.
- Count a command after it ran, or only when it succeeded; read a missing,
  unreadable or linked ledger as zero uses.
- Skip the digest comparison at the write because a mandate covers it, or run a
  non-read command that has no record from the hook.
- Keep the MAC key anywhere a profile receives, or open the state directory or
  the key's name to file or terminal calls.
- Lengthen the 7-day ceiling, raise the 10 an hour or the five commands, or
  shorten the list of flags and path words above without a decision of its own.
