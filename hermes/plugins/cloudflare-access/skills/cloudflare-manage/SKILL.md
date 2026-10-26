---
name: cloudflare-manage
description: "Use before changing anything in the user's Cloudflare: DNS records, cache, zone settings, e-mail rules, tunnel hostnames, R2, KV, D1, or rolling back a Worker or a Pages site."
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [cloudflare, dns, domains, cache]
---

# Changing Cloudflare through the `cloudflare` tool

Reading is in `cloudflare-access:cloudflare`; load it too. This skill owns
how a change is prepared, approved and checked.

## Contract

- **Every change is one card.** Each write action shows Hermes' approval card
  (the account, the zone and what changes, read fresh from Cloudflare) and
  runs only if the user approves it. A change that deletes something asks
  every time, even after "always".
- **Read, agree, then card.** Read what is there first (`dns_records`), settle
  every name, value and setting with the user in chat, then make the call.
  `preview=true` returns the exact card without asking or changing anything;
  use it when the user wants to see it first or when you are unsure.
- **Denied means stop.** Never retry a denied or expired card unchanged.
- **No person, no change.** Where nobody can answer a card (cron, another
  agent's session, a single query) every change is refused. Prepare it with
  `preview=true` and hand the exact call back to whoever can ask the user.
- **Deploying is not this tool's.** Code reaches Workers and Pages through the
  project's own tooling, run in the project's repository (`pnpm run deploy`,
  `pnpm exec wrangler deploy`); never route around that with this tool.

## Outcomes

| Answer | Meaning | Next |
|---|---|---|
| `ok` with `done` and `result` | applied | report `result` |
| `not done: …` | nothing changed | fix the cause or tell the user |
| `stopped part way: …` | the steps listed in `done` applied, the rest did not | read it, tell the user what is there now |
| `UNCERTAIN: …` | sent, outcome unknown | read it first; never repeat the call blindly |
| "what the card showed changed" | Cloudflare or the stored token changed after the card | read again, then ask anew |

## DNS records

`dns_change` takes the `zone` and up to 20 `changes`, applied in one batch:
all of them land or none does, so a set that belongs together (a new mail
setup, a move to another host) is one call and one card. Each change is one
of:

- `{op: add, type, name, content}` with optional `ttl` (1 = automatic, the
  default, or 60 to 86400 seconds), `proxied` (A, AAAA and CNAME only),
  `priority` (required for MX) and `comment`.
- `{op: update, id, …}` with only the fields that change: `name`,
  `content`, `ttl`, `proxied`, `priority`, `comment`. The type stays; to change
  it, delete the record and add one of the new type in the same call.
- `{op: delete, id}`.

`name` is relative to the zone (`www`, `@` for the zone itself). The `id` comes
from `dns_records`. Only A, AAAA, CNAME, MX, TXT and NS records are changed
here; other types are the user's to change in the dashboard.

The card shows each change on one line: `+` adds, `~` changes (old → new),
`-` deletes. Names are relative to the zone on the card as well. Every line
must fit the chat's card, so about five changes fit one call on Telegram and
fewer on Discord; a card that cannot show them all is refused, and the
changes go in smaller calls (each its own batch).

Recipes:

- Point a name at a server: add `A` (and `AAAA` for IPv6) with the address.
  `proxied: true` puts Cloudflare in front (the address stays hidden, HTTPS
  and caching apply); `false` answers with the address as it is.
- Point a name at a service: add `CNAME` to the host name the service gives.
  A name with a CNAME holds no other record, so delete what is there in the
  same call.
- Mail: `MX` records with their priority, plus the provider's TXT records
  (SPF, DKIM, DMARC at `_dmarc`). Changing them can stop mail: say so.
- Domain verification: add the TXT record the service asks for; remove it
  later only if the service says it may.

Resolvers keep the old answer until its TTL runs out, so a change reaches
everyone within the old TTL.

## Cache

`cache_purge` takes the `zone` and exactly one of: `urls` (full URLs, up to
30), `hosts` (every file under each host name), `prefixes` (a host and path
without the scheme, `www.example.com/blog/`, every file under it) or
`everything: true`. Each must lie inside the zone. Purge what changed rather
than everything: a full purge sends every visitor's next request to the
origin at once, so it asks every time. A purge cannot be taken back, but it
only drops copies; the next request fetches them again. Cloudflare limits how
many purges an account sends a minute on smaller plans: a rate limit is a
reason to wait, not to retry.

## Zone settings

`zone_setting` takes the `zone`, a `setting` and its new `value`; read it
first (`zone_settings`). Only these change here, each with its own values:
`ssl` (`off`, `flexible`, `full`, `strict`), `min_tls_version` (`1.0` to
`1.3`), `tls_1_3` (`on`, `off`, `zrt`), `security_level` (`off`,
`essentially_off`, `low`, `medium`, `high`, `under_attack`), `cache_level`
(`basic`, `simplified`, `aggressive`), `browser_cache_ttl` (seconds from
Cloudflare's list, `0` follows the origin) and the switches
`always_use_https`, `automatic_https_rewrites`, `http3`, `development_mode`,
`always_online`, `email_obfuscation`, `ipv6`, `websockets` (`on`, `off`).
Everything else stays with the dashboard.

- `ssl`: `strict` needs a valid certificate on the origin, `full` any
  certificate, `flexible` reaches the origin over plain HTTP. A mode the
  origin cannot serve takes the site down (error 525/526): check before
  raising it, and say what lowering it exposes.
- `development_mode: on` bypasses the cache for three hours, then turns off
  by itself.
- `security_level: under_attack` challenges every visitor; use it during an
  attack only.

Lowering `ssl`, `min_tls_version` or `security_level`, or turning
`always_use_https` off, weakens what protects visitors: its card is marked
and asks every time.

## E-mail rules

`email_rule` takes the `zone` and an `op`; read first (`email_routing`):

- `add` with `to` (an address at the zone, `sales` or `sales@example.com`) and
  one of `forward` (a destination address the account has verified), `drop:
  true` or `worker` (a Worker's name); optional `name`, `enabled`.
- `update` with `id` and only what changes: `to`, the action, `name`,
  `enabled`.
- `delete` with `id`: mail to that address falls to the catch-all.
- `catch_all` with its action and/or `enabled`: where mail no rule matches
  goes.

A destination that is not verified receives nothing: Cloudflare e-mails its
owner first, and adding destinations is the user's to do in the dashboard.
Deleting a rule and changing the catch-all ask every time.

## Tunnel hostnames

`tunnel_route` takes the `tunnel` (its id; `tunnels` lists them), an `op` and
the `hostname`; read the tunnel first (`tunnels` with `tunnel`).

- `add` with `service` (what the connector serves: `http://localhost:8080`,
  `https://…`, `tcp://…`, `ssh://…`) and optional `path`: the hostname is
  published, and its DNS record (a proxied CNAME to the tunnel) made with it.
  A hostname that already has other DNS records is refused; remove them first
  with `dns_change`.
- `update` with a new `service` for a published hostname.
- `remove`: the hostname stops answering, and its DNS record goes when no
  other rule of the tunnel uses it.

Publishing puts a service of the machine behind the tunnel on the internet:
ask who should reach it and whether it has its own login, and suggest
Cloudflare Access in the dashboard when it should not be open to everyone.
Adding, changing and a removal that deletes the DNS record ask every time.
Rules keep their order, so a path rule written before others still applies
first. A tunnel managed in a local config file changes on that machine, not
here.

## Storage containers

`storage_create` with `kind` (`r2`, `kv`, `d1`) and `name` makes an empty
bucket, namespace or database; binding it to a Worker happens in the
project's own configuration. `storage_delete` with `kind` and the `bucket`,
`namespace` (its id) or `database` (its id) deletes one only when it is found
empty, both when the card is made and when it runs: no object, no key, no
table. Emptying one is the user's to do, since contents are never read here.
A delete asks every time; say which Worker loses it.

## Rollbacks

A rollback puts back what ran before; it never deploys new code. Read first
(`workers` with `script`, `pages` with `project`) and say which deployment
goes live.

- `worker_rollback` with `script`: by default the previous deployment exactly
  as it was (a gradual rollout keeps its shares), or with `version` one version
  an earlier deployment served, at 100%. `message` is the new deployment's
  note. The rollback is itself a deployment: the next deploy replaces it.
- `pages_rollback` with `project`: by default the previous successful
  production deployment, or the `deployment` named (its id or short id). A
  preview, a failed build, the live deployment or one newer than it is
  refused.

A deploy that lands between the card and the run stops the rollback: read
again and ask anew.

## Errors

"lacks a permission" means the token may not change this: the user adds it
to the token in the Cloudflare dashboard (DNS records need Zone → DNS →
Edit, a purge Zone → Cache Purge → Purge, a setting Zone → Zone Settings →
Edit, an e-mail rule Zone → Email Routing Rules → Edit, a tunnel hostname
Account → Cloudflare Tunnel → Edit with Zone → DNS → Edit, a bucket Account →
Workers R2 Storage → Edit, a namespace Account → Workers KV Storage → Edit, a
database Account → D1 → Edit, a Worker rollback
Account → Workers Scripts → Edit, a Pages rollback Account → Cloudflare
Pages → Edit). A setup problem
(no token, a refused token) is the user's to fix: relay it, never work around
it.
