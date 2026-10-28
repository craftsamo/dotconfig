# Webhooks — tracked routes

Hermes design docs — index: [`../../PROFILES.md`](../../PROFILES.md).

An inbound webhook (a service POSTing to this machine when something happened)
that should outlive the machine it was set up on is a **directory**,
`profiles/<profile>/webhook.d/<name>/`, in the repository that owns it (this
one for a neutral route, the private overlay for a personal one), in the same
shape as a tracked cron job ([cron.md](cron.md)). Hermes' own route store,
`~/.hermes/webhook_subscriptions.json`, is derived from those directories by
`scripts/webhook-sync.py` and is never edited by hand or tracked.

## The listener

Hermes' webhook platform is one HTTP listener, the root profile's
(`platforms.webhook` in the root `config.yaml`, loopback `127.0.0.1:8644`);
under multiplex a served profile's routes answer under
`POST /p/<profile>/webhooks/<name>`. The listener reads its routes from the
subscriptions file on every POST (a `stat` check, no restart), so adding or
changing a route never restarts the gateway; enabling the platform itself does,
once.

Every POST is checked against the gateway's global HMAC secret,
`WEBHOOK_SECRET`, a Keychain item in the `hermes` layer the gateway launcher
injects ([install.md](install.md)). The runtime accepts GitHub's
`X-Hub-Signature-256`, GitLab's token, Svix / Standard Webhooks, Linear, and
its own generic `X-Webhook-Signature-V2` (HMAC-SHA256 of `<timestamp>.<body>`
with `X-Webhook-Timestamp`), all against that one secret. A route carries no
secret of its own, so a manifest holds nothing a repository must not — and
without `WEBHOOK_SECRET` in the gateway's environment the listener skips every
such route with a log warning (`[webhook] Dynamic route … skipped`), which is
how a missing Keychain item shows. Stripe's signature is not among the
accepted ones: a Stripe event needs an intermediary that verifies it and
re-signs.

webhook-sync walks `profiles/*/webhook.d/`; the root profile keeps `default`
neutral and tracks no routes of its own.

The listener is loopback only. A public hostname reaches it through a tunnel
run as a service ([services.md "Webhook tunnel"](services.md#webhook-tunnel));
the hostname itself is machine-local and lives in the private overlay.

## A route directory

```
webhook.d/<name>/
  route.yaml           what a signed POST does
  filter.sh | filter.py   optional: the payload on stdin, the verdict on stdout
```

The route's name is the directory name (`[a-z0-9][a-z0-9._-]*`) and the last
segment of its URL; `route.yaml` never repeats it. One route name is one URL,
so two profiles cannot track the same name. `route.yaml`:

| Key                 | Meaning                                                                                                                                                                                                                                                                                                                                          |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------ | -------- | ----- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `mode`              | `notify`: the rendered `prompt` is sent as the message; no model runs. `agent`: the profile runs with `prompt` / `skills` in a session of its own and the result is delivered. `job`: the `cron.d/` job named by `cron_job` is fired, with the rendered `prompt` as that run's context; the job's own prompt, skills, delivery and thread apply. |
| `events`            | Event types to accept (GitHub's `X-GitHub-Event`, else the payload's `event_type` / `type`); absent accepts all.                                                                                                                                                                                                                                 |
| `filters`           | The runtime's declarative filters: a list of `{field, in                                                                                                                                                                                                                                                                                         | equals | contains | regex | exists | missing}`specs (all must hold) or one spec with`all`/`any`/`not`. `field` is a dotted path into the payload (`alert.security_advisory.severity`). |
| `prompt`            | A template with `{dotted.payload.refs}`, `{event_type}` and `{__raw__}`. Required for `notify`; `agent` needs it or `skills`. Written as plain Markdown prose: the substituted fields are escaped by the adapter ([telegram-markdown.md](telegram-markdown.md)).                                                                                                                                                                                                                    |
| `skills`            | Skills loaded before the prompt (`agent` only).                                                                                                                                                                                                                                                                                                  |
| `deliver`           | Where the message or the result goes: `telegram`, `discord`, `slack`, `github_comment`, `log` (the default for `agent`; `notify` needs a real target). A bare platform is its home channel.                                                                                                                                                      |
| `deliver_extra`     | `chat_id`, `thread_id` / `message_thread_id` for the delivery (a private overlay's manifest only: a chat id names a person's conversation).                                                                                                                                                                                                      |
| `mirror_to_session` | `notify` and `agent`: also append the delivered text to the target chat's session, so a reply there has it in context.                                                                                                                                                                                                                           |
| `cron_job`          | `job` only: the name of a `cron.d/` directory of the same profile (webhook-sync checks it exists).                                                                                                                                                                                                                                               |
| `coalesce`          | The runtime's debounce block for rapid same-entity events, passed through.                                                                                                                                                                                                                                                                       |
| `toolsets`          | `agent`: the toolset allowlist of the run (a manifest-only key by the runtime's design: a route cannot grant itself tools from a chat).                                                                                                                                                                                                          |
| `paused`            | `true` writes the route disabled (the listener answers 403); absent or `false` enables it. The manifest owns the switch: a route turned off in the dashboard is on again at the next sync.                                                                                                                                                       |

What each mode means for the person: `notify` is a line in the Inbox; `agent`
is an unattended run whose report lands in a chat (the runtime classes a
webhook run as unattended, so a write that needs an approval card is refused —
reading, summarising and reporting are what it does); `job` is the way to a
run that opens its own thread, since a cron job with `attach_to_session: true`
and an explicit `deliver: telegram:<chat>` does that ([cron.md "A job
directory"](cron.md#a-job-directory)). A job fired only by events keeps a
schedule that never comes round (`0 0 29 2 *`): a paused job cannot be fired
by an event, and a far-future one-shot completes after its first run.

### The filter and its profile

The runtime runs a route's script only from inside `<HERMES_HOME>/scripts/`,
by real path, so a `filter.*` is reached through a wrapper webhook-sync
generates at `scripts/webhook/<name>.sh` of the route's profile. The wrapper
exports that profile's home as `HERMES_HOME` and execs
`$HERMES_HOME/webhook.d/<name>/filter.sh` (or `.py`) — the link, so no checkout
path is written anywhere. The runtime hands the payload as JSON on stdin and
reads stdout: empty, `[SILENT]` or a nonzero exit drops the event; a JSON
object replaces the payload; other text is attached as `script_output`.

## webhook-sync

`bin/hermes-python hermes/scripts/webhook-sync.py [--root <dir>] [sync|validate|adopt|…]`
(`install.sh` runs `sync` right after cron-sync; the runtime's own
subscriptions writer takes its lock and publishes by atomic rename).

For each manifest the sync keeps exactly one record in the root home's
subscriptions file carrying `managed: {manifest, source, profile, synced_at}`
and bound to its profile:

- missing → created; definition fields differ → rewritten to the manifest;
  `source` or profile changed → restamped. The runtime's own fields on an
  adopted record (`description`, `created_at`, a secret of its own) survive.
- the manifest is gone → the record is **disabled** (`enabled: false`, with
  the reason in the marker); the listener answers 403 for it. `--prune`
  removes such orphans instead. Restoring the directory enables it again.
- a record **without** the marker is never touched (one made with
  `hermes webhook subscribe`). One that shares a manifest's name is a
  **conflict**: the sync reports it and skips that manifest until
  `webhook-sync adopt <profile> <name>` stamps the marker on it — never
  automatically.
- a manifest that fails validation is reported by name and its record, if any,
  is left exactly as it was.

`--check` prints what a sync would do and exits 1 when anything is pending or
broken, writing nothing; `verify-work-continuity.py` runs it after
`cron-sync --check`. `validate [--profile <p>]` loads every manifest and
touches no record. A profile's own route is written by hand with
`webhook-sync add <profile> <name>` (the spec as JSON on stdin, `--filter
<file>`) and dropped with `remove`; nothing ever writes the subscriptions file
directly.

## Public, private, local

As for cron ([cron.md "Public, private, local"](cron.md#public-private-local)):
a neutral route is `hermes/profiles/<p>/webhook.d/<name>/` here and arrives in
`~/.hermes/profiles/<p>/webhook.d/` as a link from `install.sh`; a personal one
is the same directory in the private overlay, linked by its `install.sh`; a
route the profile wrote for itself is a real directory (`source: local`).
Promotion copies the directory into a repository, deletes the real one, and
runs `install.sh`.

## First contact

The tracked `assistant/webhook.d/ping` route sends the test payload to the
Assistant's Telegram home. Once `WEBHOOK_SECRET` is in the Keychain and the
gateway has restarted with the platform enabled, one signed POST checks the
listener, the route and (through the public hostname) the tunnel:

```sh
body='{"message":"hello","event_type":"test"}'
sig="sha256=$(printf '%s' "$body" | openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" | sed 's/^.* //')"
curl -sS -X POST "http://127.0.0.1:8644/p/assistant/webhooks/ping" \
  -H "Content-Type: application/json" -H "X-GitHub-Event: test" -H "X-Hub-Signature-256: $sig" \
  -d "$body"
```

(`WEBHOOK_SECRET` in that shell comes from `secret env`, never typed;
`hermes webhook test` signs with a secret stored on the route, which a tracked
route does not have.) A `202` with `"status": "accepted"` — or `200` for a
`notify` route — means the message is on its way.

## Cutover from hand-made subscriptions

A route that was made with `hermes webhook subscribe` before its manifest
existed is adopted, not recreated: run `install.sh` (the sync reports the
conflict), `webhook-sync adopt <profile> <name>`, run `install.sh` again. The
record keeps its own secret, so the sender's configuration need not change.
