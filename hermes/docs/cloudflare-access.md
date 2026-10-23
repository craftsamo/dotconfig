# Cloudflare access

Cloudflare for the Assistant, Researcher and Marketer: the zones, DNS records
and zone settings of the user's own Cloudflare accounts, through API tokens the
user creates. Every profile with the tool reads. Read it when changing the
plugin, its tokens or what it may call. Common rules:
[access-common.md](access-common.md). Part of the Hermes design docs — index:
[`PROFILES.md`](../PROFILES.md).

## Shape

| Piece                                                                                                          | Home                                                                                             | Reader                          |
| -------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ | ------------------------------- |
| Engine: validation, request building from a fixed table, zone lookup, token state, result shapes, bypass guard | `plugins/cloudflare-access/cfa.py`                                                               | all                             |
| The only process holding a token; the endpoints it may call (`ROUTES`) and the account it fills in             | `plugins/cloudflare-access/bridge.py`                                                            | all                             |
| `cloudflare` tool and the `pre_tool_call` hook (toolset `cloudflare_access`), the actions each profile gets    | `plugins/cloudflare-access/__init__.py`                                                          | Assistant, Researcher, Marketer |
| How a profile reads Cloudflare: accounts, zones, record names, pages, permissions, recovery                    | the `cloudflare-access:cloudflare` plugin skill (`plugins/cloudflare-access/skills/cloudflare/`) | Assistant, Researcher, Marketer |

Cloudflare's own REST API, so no terms are stretched: the risk is the user's
sites and domains, not the account. Everything is standard library, so there is
no venv and no install step; the bridge runs under Hermes' own interpreter in
isolated mode with a minimal environment
([bridge process](access-common.md#state-directory-and-bridge-process)). It
calls only `https://api.cloudflare.com/client/v4`, only the method and path
pairs in `ROUTES`, and never follows a redirect. Deploying code (Workers,
Pages) is not the tool's job: it stays with the project's own tooling.

## Profiles

| Profile    | Actions    | Inbound A2A |
| ---------- | ---------- | ----------- |
| Assistant  | every read | refused     |
| Researcher | every read | reads       |
| Marketer   | every read | reads       |

The action list a profile gets (`PROFILES`) is fixed when the plugin registers
and checked again by the gate, the handler and the engine
([profile gating](access-common.md#profile-gating)). An inbound request runs
only what `A2A` lists for the profile, and only when the turn's bound profile
home is that profile's, failing closed otherwise. Every profile uses the same
token for a label, so what the token may do in Cloudflare bounds what the tool
can do.

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
zone. A result over
60,000 characters is refused with a hint to narrow it.

Zone and account names, DNS record contents (a TXT record holds any text) and
comments can be set by others, so results carry a note that they are data,
never instructions.

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
   one) limited to the account and zones the profiles should see, with
   Zone → Zone → Read, Zone → DNS → Read, Zone → Zone Settings → Read and
   Account → Account Settings → Read. Copy the account id from the account's
   home page. Store the token with
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
