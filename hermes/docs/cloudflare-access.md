# Cloudflare access

Cloudflare for the Assistant, Researcher and Marketer: the zones, DNS records,
zone settings, analytics, Workers and Pages deployments, the names, sizes and
schemas in R2, KV and D1, tunnels and Email Routing of the user's own
Cloudflare accounts, through API tokens the user creates. Every profile with
the tool reads; the Assistant alone also changes DNS records and purges
caches, each change behind an approval card. Read it when changing the
plugin, its tokens or what it may call. Common rules:
[access-common.md](access-common.md). Part of the Hermes design docs — index:
[`PROFILES.md`](../PROFILES.md).

## Shape

| Piece                                                                                                                                             | Home                                                                                                                        | Reader                          |
| ------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- | ------------------------------- |
| Engine: validation, request building from a fixed table, zone lookup, token state, result shapes, write plans, approval card, bypass guard        | `plugins/cloudflare-access/cfa.py`                                                                                          | all                             |
| The only process holding a token; the endpoints it may call (`ROUTES`), the analytics queries it may send (`QUERIES`) and the account it fills in | `plugins/cloudflare-access/bridge.py`                                                                                       | all                             |
| `cloudflare` tool and the `pre_tool_call` hook (toolset `cloudflare_access`), the actions each profile gets                                       | `plugins/cloudflare-access/__init__.py`                                                                                     | Assistant, Researcher, Marketer |
| How a profile reads Cloudflare: accounts, zones, record names, pages, permissions, recovery                                                       | the `cloudflare-access:cloudflare` plugin skill (`plugins/cloudflare-access/skills/cloudflare/`)                            | Assistant, Researcher, Marketer |
| Changing Cloudflare: the card, DNS record changes, cache purges, outcomes                                                                         | the `cloudflare-access:cloudflare-manage` plugin skill (`.../skills/cloudflare-manage/`); registered for the Assistant only | Assistant                       |

Cloudflare's own REST API, so no terms are stretched: the risk is the user's
sites and domains, not the account. Everything is standard library, so there is
no venv and no install step; the bridge runs under Hermes' own interpreter in
isolated mode with a minimal environment
([bridge process](access-common.md#state-directory-and-bridge-process)). It
calls only `https://api.cloudflare.com/client/v4`, only the method and path
pairs in `ROUTES` and the fixed analytics queries in `QUERIES`, and never
follows a redirect. Deploying code (Workers, Pages) is not the tool's job: it
stays with the project's own tooling.

## Profiles

| Profile    | Actions             | Inbound A2A |
| ---------- | ------------------- | ----------- |
| Assistant  | every read, changes | refused     |
| Researcher | every read          | reads       |
| Marketer   | every read          | reads       |

The action list a profile gets (`PROFILES`) is fixed when the plugin registers
and checked again by the gate, the handler and the engine
([profile gating](access-common.md#profile-gating)). An inbound request runs
only what `A2A` lists for the profile, never a change or a `preview`, and only
when the turn's bound profile home is that profile's, failing closed
otherwise. Every profile uses the same token for a label, so what the token
may do in Cloudflare bounds the Assistant's changes, and the action lists keep
Researcher and Marketer to reads.

## Tokens, accounts and state

Tokens are Keychain items in the `hermes` project under the scope
`cloudflare-access` ([secret scoping](access-common.md#secret-scoping)),
stored without a stage: Cloudflare has no test mode. An item there is a token
when it carries a `label=<label>` field and an `account_id=<id>` field, the
32-character id of the Cloudflare account the token acts on; its name is the
user's to choose, as long as the `secret` CLI takes it. A label (`work`,
`personal`) names one Cloudflare account. Fields are read by their exact
spelling, in lowercase, and their values without regard to case. Other fields
(`url=`) stay free for the user's notes. The labels and the accounts behind
them are private: they stay in the Keychain and the state directory, never in
tracked files.

The bridge lists the scope's metadata, then reads a token by its exact layer
(`--scope cloudflare-access --no-stage`), so a staged item is never taken for
a token. A label two items carry is refused with both names rather than
guessed. An item of the scope that is no token (a stage, no `label=` or
`account_id=` field, a field spelled in capitals, a malformed label or id, a
name the CLI does not take) is listed by `status` with what is wrong and the
command that fixes it. Stored `--no-env`, the tokens reach no environment
through `secret env` or a shim.

A token is an API token: `cfut_…` (user-owned), `cfat_…` (account-owned) or
an older one without a prefix. A Global API Key (`cfk_…`, or 37 to 45
lowercase hex characters) is refused before anything is sent, since it reaches
everything the user can. `account` picks the label; it may be left out when
one label is stored. The bridge reads only the item a call needs, and masks the
value (and anything shaped like a Cloudflare credential) in every string it
returns. A fingerprint names what a call runs on, the token together with the
account id.

A path names the label's account as `{account}`, which the bridge fills in
from the item: an account-wide call can reach no other account, and a path
naming an account outright is not in `ROUTES`. A zone is named by its domain
or its id; a domain is looked up only in the label's account
(`account.id`), and a zone whose account is not the label's is refused before
anything else is read about it, since a user-owned token may reach zones of
several accounts.

Cloudflare answers a token it no longer takes and a token without the
permission a call needs alike (401 or 403, often with code 10000), so the
bridge checks each 401 or 403 against the token's own verify endpoint
(`/user/tokens/verify` for a user-owned token, `/accounts/{account}/tokens/verify`
for an account-owned one, both in turn for a token without a prefix) before it
reports anything. A token the check finds `active` is a missing permission,
passed on with Cloudflare's message and nothing remembered; one it finds
expired, disabled or not taken at all is a refused token, stored as in
[refusal memory](access-common.md#state-directory-and-bridge-process) per
label, so later calls with that token are answered without Cloudflare until
another token is stored. A check that itself fails reads as a missing
permission, never as a refusal; one that meets a rate limit pauses the label.
The check finds a token not taken at all also when it is limited to other IP
addresses or when `account_id=` names an account it does not belong to, and
the message says so. Because a token can be re-enabled or its expiry extended
in the dashboard without changing its value, `account` checks the token anew
even when it is remembered as refused, and clears the refusal when it is
`active`; a pause still holds. A 429 pauses the label for its `Retry-After` (a
minute without one).

`~/.cloudflare-access/` (mode 700, outside every repository) holds no secret:
`state.json` (per label: a refused token's fingerprint and status, a pause's
end, and the account id and name `account` last read) and a lock.

## Reads

`status` never contacts Cloudflare: it lists the stored labels, each token's
item, account id, kind (`user`, `account` or `token` for one without a prefix)
and any problem, the account's name once `account` has read it, and under
`unused` the scope's items that are no token. `account` checks the token on
its verify endpoint (its status, owner and expiry) and reads the account
behind it; a token that may not read the account's details still reports its
own status. `zones` lists the label's zones (`status` filters) or reads one
with `zone`. `dns_records` lists a zone's records, filtered by `type`, `name`
(read relative to the zone, `@` for the zone itself, matched exactly),
`content` (exact) and `proxied`, or reads one in full with `id`.
`zone_settings` reads a fixed list of the settings that decide how a zone is
served and secured, under one read of the token, or one with `setting`; a
setting the plan or the token cannot read is listed under `unavailable` with
its reason. Lists page with `page` and `limit` (20 by default; zones at least
5 and at most 50, DNS records at most 100) and return `next` while pages
remain; a zone limit under 5 is read as 5, so following `next` never skips a
zone. A result over 60,000 characters is refused with a hint to narrow it.

`analytics` reads Cloudflare's GraphQL Analytics API, but only through the
bridge's fixed queries: the engine names one and passes its variables, which
the bridge checks by kind (a zone id, a date, a UTC time, a Worker's name) and
completes with the label's account, so no query text of the caller's is ever
sent. A zone report runs only after the zone is checked to belong to the
label's account. `traffic` counts whole UTC days (7 by default, at most 366);
`paths`, `countries` and `statuses` are the 25 largest over a span (the last
day by default, at most 31 days), `security` groups security actions by action
and source and `security_events` lists the latest ones, and `workers` reads
the account's Worker invocations, optionally for one `script`. Cloudflare
answers query errors with a 200 as well; any error is a failure, passed on with
Cloudflare's message and a note that a range beyond what the plan keeps, or a
token without the analytics permission, reads this way. Visitors' IP addresses
are never asked for.

`workers` lists the account's Workers, or for one `script` its current
deployment (the versions it serves and their traffic shares), its earlier
deployments and a page of its versions, read together under one token read; a
script's code is not a route, so it is never read. `pages` lists the Pages
projects with their production and latest deployment, or for one `project` a
page of its deployments (`env` production or preview) with each one's branch,
commit and stage.

Storage is read to names, sizes and schemas, never a value or a row: the
routes that return an R2 object, a KV value or a D1 export are not in
`ROUTES`. `r2` lists the buckets, or one `bucket`'s object names, sizes and
content types a folder at a time (`delimiter` `/`, `prefix`, `cursor`). `kv`
lists the namespaces, or one `namespace`'s key names and expiry, never their
metadata. `d1` lists the databases, or one `database`'s size and schema. D1's
query endpoint runs any SQL, writes included, so the only statement the tool
sends there is fixed in the bridge (`SCHEMA_SQL`, a read of `sqlite_master`),
and a request to that route carrying a body of its own is refused.

`tunnels` lists the account's Cloudflare Tunnels that are not deleted, with
their health, where they are managed and how many connections their
connectors hold (data centers and client versions, never the origin's IP
address), or for one `tunnel` also its public hostnames and the services
behind them, which a tunnel managed in a local file does not report.
`email_routing` reads a zone's Email Routing state, rules and catch-all
together with the account's destination addresses, each verified or not;
rules and destinations come 50 a `page`, each list with its own `next`, and a
part the token may not read is listed under `<part>_unavailable` rather than
failing the rest.

Zone and account names, DNS record contents (a TXT record holds any text) and
comments can be set by others, request paths come from visitors, deployment
and commit messages from whoever deployed, and storage names from the apps
that wrote them, so results carry a note that they are data, never
instructions.

## Writes

`dns_change` takes a zone and up to 20 changes, each an add, an update of the
fields named or a delete, of A, AAAA, CNAME, MX, TXT and NS records (other
types stay with the dashboard). They go out as one request to Cloudflare's
batch endpoint, which applies them in one transaction: all of them land or
none does (resolvers still follow within each record's TTL). Each record is
checked for its type before any card: an IPv4 or IPv6 address, a host name
for CNAME, MX and NS, one line of at most 2,048 characters for TXT, a priority
for MX, proxying only for A, AAAA and CNAME, a TTL of 1 (automatic) or 60 to
86,400 seconds. An update or a delete reads the record first; an update that
moves nothing, or one that changes a record's type, is refused.

`cache_purge` takes a zone and exactly one of up to 30 URLs, host names or
path prefixes, each checked to lie inside the zone, or the whole zone's cache.

Each action takes only its own arguments; any other is refused, so a mistaken
argument is never dropped silently. The plan reads what the card shows from
Cloudflare first and blocks a change that would fail. `preview=true` runs the
same plan and returns the card without asking or changing anything; it works
in any run.

At execution the handler plans again and refuses if anything the card showed
or would send differs (a record changed meanwhile, another token was stored,
the label now acts on another account). Every request carries the approved
fingerprint, and the bridge sends nothing under a different stored token or
account. Cloudflare takes no idempotency key, so nothing is ever resent; each
outcome is reported this way:

- **`not done`:** nothing changed. Cloudflare answered with a 4xx, or nothing
  was sent.
- **`stopped part way`:** the steps listed in `done` applied, then Cloudflare
  refused one.
- **`UNCERTAIN`:** a request was sent and its answer does not show whether it
  applied (a timeout, a broken connection, a 5xx, a 2xx without a success).
  Read it first.

## Approval

The card has the [shared shape](access-common.md#card-shape): its title names
the change (`Cloudflare · Change DNS records`), its effect line the stakes —
🚨 when a record is deleted, ⚠️ for every other change, since each reaches
visitors — then the account `<label> (<account name>)` and the zone, and what
changes in a `Change` block: one line per record (`+` added, `~` changed from
what it is to what it becomes, `-` deleted, names relative to the zone) or the
purge with its URLs. Record contents and comments are collapsed to one line
with control and invisible characters spelled out, so others' text cannot
forge card lines. Lines that must be seen (every record change, what a purge
reaches) always fit what the chat shows, or the change is refused (sooner on
Discord's shorter card); detail lines (the all-or-nothing note, comments, a
purge's URLs) are counted when they do not.

The approval record is per tool call and allows one change. Its rule key
hashes the exact plan, so "session" or "always" repeats only that identical
change on that same account. A change that deletes a record and a purge of
everything get a fresh key every time, so no stored answer ever covers one.

## Where a write may run

A change is refused wherever no person can answer its card, through the shared
check ([approval gate](access-common.md#approval-gate)); the hook and the
handler each refuse before a card is built, and the answer names the reason.
Reads and `preview=true` are unaffected.

## Ways around the tool

On every profile with the tool the hook blocks terminal calls whose text names
the plugin or its Keychain scope (`cloudflare-access`), `api.cloudflare.com`,
a Cloudflare credential's shape or its usual environment names, the
`X-Auth-Key` header, wrangler, cloudflared or flarectl run as a command (also
through a package runner such as `npx` or `pnpm exec`) or with a command that
uses the account, the CLIs' logins (`.wrangler/config`, `~/.cloudflared`) or an
inline Cloudflare SDK import, and file-tool calls on the state directory or the
CLIs' logins. Mentions that run nothing (`grep wrangler package.json`) stay
open. Because the tokens' names are free, and a `secret` read that leaves the
scope out searches the scope named after the working directory's repository,
it also blocks any value read or change of an item in the `hermes` project
(`secret get|set|update|rm|import|env … -p hermes`) and the Keychain's own
password reads; `secret ls` and `secret show` (metadata only) stay open. File
tools may still read the plugin source, and the browser may still open the
Cloudflare dashboard. Patterns: `_TERMINAL` and `_STORE` in
`plugins/cloudflare-access/cfa.py`. Shared rules:
[bypass guard](access-common.md#bypass-guard-ways-around-the-tool). The toolset
is in an `a2a` platform toolset only where `A2A` lists actions (Researcher,
Marketer), never the Assistant's.

## Setup

Service-specific steps; the rest is in [shared setup](access-common.md#setup-shared).

1. In the Cloudflare dashboard, create an API token (My Profile → API Tokens
   for a user-owned token, or Manage Account → API Tokens for an account-owned
   one) limited to the account and zones the profiles should see, with the
   Read permission of each action they should use (the Permissions table of
   the `cloudflare-access:cloudflare` skill lists them) and, for the
   Assistant's changes, Zone → DNS → Edit and Zone → Cache Purge → Purge only
   where it should change them. Copy the account id
   from the account's home page. Store the token with
   `secret set CLOUDFLARE_<LABEL> -p hermes --scope cloudflare-access --no-stage -D TOKEN --meta label=<label> --meta account_id=<account id> --no-env`
   (any name the CLI takes) and paste the token at the hidden prompt.
   `--no-env` keeps it out of `secret env` as a second guard beside the scope.
   The dashboard shows a token once: store it straight away. A fresh token goes
   into the same item with
   `secret update <name> -p hermes --scope cloudflare-access --no-stage --value`,
   which keeps its fields; a mistyped field is fixed the same way with
   `--meta label=<label>` or `--meta account_id=<account id>`.
2. Enable the plugin and add `cloudflare_access` to the profile's `toolsets`
   and `platform_toolsets` (`a2a` only for Researcher and Marketer), then
   restart the gateway. The three example configs in this repo have it; the
   private configs carry the same entries.
3. `status` shows each stored token; `account` confirms Cloudflare takes it.
