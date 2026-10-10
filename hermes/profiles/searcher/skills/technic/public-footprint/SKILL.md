---
name: public-footprint
description: >-
  Use to map one person's, brand's or organization's public footprint from a
  starting account or URL: the accounts tied to it across X, note, YouTube,
  Substack and the web, its public activity over time, its self-made claims
  beside what first-party sources state, and on-chain facts for the addresses
  it publishes. A hunt technic; never de-anonymizes or collects private life.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: technic
    mode: hunt
    tags: [search, footprint, account, osint, x, note, youtube, substack, web3]
---

<ReadBeforeWork>

This technic adds to `hunt-searcher` and never replaces it. Require the
full-body kernel (`skill_view(name="searcher-pipeline")`), the hunt entry
(`skill_view(name="hunt-searcher")`), the current stage reference
(`skill_view(name="searcher-pipeline", file_path="references/<stage>.md")`)
and this body in current context, not a past load or summary. If unchanged is
returned while the earlier body is unavailable, use read_file on
`${HERMES_SKILL_DIR}/SKILL.md` and the kernel's canonical
`${HERMES_SKILL_DIR}/../../searcher-pipeline/SKILL.md`; stop the affected action
if they stay unavailable. Selecting this technic is not the caller's release
and never widens the agreed scope or cap.

</ReadBeforeWork>

# Public footprint

The question is "what does this subject show of itself in public, and what
ties those pieces together" — not "who is behind it" and not "can they be
trusted". The deliverable is a source map of accounts, activity, claims and
chain facts, each with the evidence that ties it to the subject.

## Brief

Plan settles, or a settled brief carries:

- **Start** — one handle, profile URL, site or published address, and the
  service it is on. A bare name with no account is a spec gap: ask which
  account is meant.
- **Purpose and consumer** — what decision this serves (a collaboration, an
  invitation or DM to check, a speaker or creator to choose, a project's team)
  and who reads it next. The purpose sizes the hunt; it never widens the floors.
- **Subject kind** — a public figure, a business or brand, or a private
  individual. For a private individual the map covers only accounts the subject
  links themselves and the activity on them: Route step 3 is skipped and no
  leads are sought.
- **Services** — default all of X, note, YouTube, Substack, the open web and
  the chains; the brief may narrow them.
- **Window**, **exclusions** and a finite **cap** (hops or tool calls).

## Ties

Every account or site in the map carries one tie grade and the URL that shows
it:

- **confirmed** — the two link to each other (A's profile lists B and B's lists
  A), or a first-party page (the subject's own site, its employer's or
  publisher's page, a conference programme) names both.
- **self-declared** — only the subject's own account points to it.
- **unconfirmed lead** — anything weaker that is visible on the accounts
  themselves: the same name or handle elsewhere, the same or a visibly similar
  avatar, a named third party saying so. Leads are recorded in their own
  section with the observation that raised them, never in the map. A lead is chased only toward a self-declaration or a
  first-party page: found, it is promoted with that URL; not found, it stays a
  lead.

## Route

Run as the hunt's hop loop, the anchor first:

1. **Anchor.** Read the start's own profile: `x(action="user")` for an X
   handle, `note(action="creator")`, `youtube(action="channels")`,
   `substack(action="archive")` or the page itself. Record the handle, URL,
   display name, join or creation date, counts and every link it lists.
2. **Follow its own links.** Open each listed account or site and check
   whether it links back: that settles confirmed or self-declared. Push the
   new account's own links onto the frontier.
3. **Same subject per service** (not for a private individual). On each
   service in scope not reached yet, look for the subject's handle and name: `x_search` (`from:<handle>` for
   representative posts and the accounts they mention), `note` `search` /
   `creator`, `youtube` `search`, `substack` `archive`, and `web_search` for
   a personal site, GitHub, Zenn, talks, interviews and press. What turns up
   here is a lead until a link or first-party page ties it.
4. **Claims.** List what the subject says about itself — role, employer,
   founding, clients, numbers, awards — quoted with where it says so. For
   each, look for a first-party source (the employer's team page, the event's
   programme, the publisher's page, a registry) and record what it shows: a
   first-party page that states it, none found (with the attempts), or a
   first-party page that states otherwise, quoted side by side. Whether the
   claim holds is not decided here.
5. **Chains.** Only addresses or names the subject publishes (a bio, its site,
   a post): `evm` `address` (an ENS name is accepted) and `portfolio` /
   `activity`, `solana` `address` / `activity`, recorded as the chain
   references say. An address attributed by someone else is a lead.
6. **Timeline.** Per tied account: created or first seen, latest activity,
   and dated events the sources show (launches, role changes, renames).

The service references (`skill_view(name="searcher-pipeline",
file_path="references/platforms/<service>.md")`) own what to record per item
and each service's budget.

## Never

The kernel's "People are not unmasked" floor, in detail. Whatever the tie
grade and whatever the brief asks:

- No tying a pseudonymous account to a legal name, face, home or work
  address, family, phone number or private email the subject has not
  published on that account. A lead that would do so is dropped and noted as
  "excluded by the floor", without its content.
- No breach or leak data, people-search or data-broker sites, paste dumps, or
  pages behind a login.
- No writing-style, posting-time or network-overlap comparison to tie
  accounts, and no reverse image search of a face.
- No contact with the subject or anyone else, and no follow, like, reply or
  message.
- Health, religion, politics, sexuality and similar sensitive traits are not
  collected; a public statement the purpose needs is quoted only as the
  subject published it.

## Output additions

Add to the hunt's output:

```text
## Account map
- <service> <handle / URL> — tie: confirmed | self-declared — <evidence URL> (created <date>, last active <date>, <counts @ read time>)
## Leads (unconfirmed)
- <service> <handle / URL> — <observation> — would confirm: <what was sought, where>
## Timeline
- <date> — <event> — <URL>
## Claims
- "<claim as quoted>" — claimed at <URL> — first-party states it <URL> | none found (<attempts>) | first-party states otherwise: "<quote>" <URL>
## On-chain (published addresses only)
- <chain> <address> — attributed at <URL> — <facts with block / slot>
```

`Open for researcher` holds whether the subject is trustworthy, whether its
claims hold, what it intends, and whether two accounts are the same person
beyond what the ties show.

## Verification additions

- Every map entry has its tie grade and an evidence URL retrieved this run; a
  self-declared entry records that the reverse link was checked.
- No lead appears in the map; every lead names its observation.
- Every claim is quoted with what the first-party search found, never with a
  verdict; for a private individual no leads were sought.
- Every address came from the subject's own publication.
- Nothing listed under Never was collected, and each service in scope was
  read or named as unsearched ground.
