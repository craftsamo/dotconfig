# Cloudflare zone changes without a card only inside a zone mandate

Status: in force
Owner doc: docs/cloudflare-access.md "Zone mandates"

## Decision

A Cloudflare write runs without its approval card only when it fits one zone
mandate the user approved on a card of its own. A mandate belongs to one
account and names:

- the account (its token's label and the Cloudflare account id) and one to
  three of its zones, each by id with the name the card showed;
- the classes it covers, from `dns` (a `dns_change` of which every item adds
  or updates a proxied A, AAAA or CNAME record), `settings` (a `zone_setting`
  in which no item weakens protection or turns a protective setting off) and
  `purge` (a `cache_purge` of URLs, hosts or prefixes);
- how many covered changes an hour it allows (1 to 20, counted per mandate:
  each DNS item, each setting, each URL, host or prefix of a call counts one),
  a purpose in one line, and an end at most 7 days out.

A write fits only when its class is covered, its account and zone are the
mandate's, its card is below 🚨, and the hour has room for all its changes (a
call with more changes than the mandate allows an hour is never covered).
Whatever the terms say, these always ask on their card: any delete; in a DNS
call, any other record type (MX, TXT, NS, CAA, SRV …), any record that is not
proxied after the change (an add without `proxied: true`, an update that
turns the proxy off or leaves an unproxied record unproxied), any name whose
first label starts with `_` (`_acme-challenge`, `_dmarc`, `_domainkey`), and
any record that is or would become a tunnel's CNAME (`*.cfargotunnel.com`),
one such item making the whole call ask; a setting that weakens protection or
turns off one that protects visitors or addresses (`ssl` off, Always Use
HTTPS, Automatic HTTPS Rewrites, TLS 1.3, security level off, e-mail address
obfuscation); a purge of everything; tunnel routes, e-mail rules, Worker and
Pages rollbacks, storage; and any other zone or account. A mandate is never
made by another mandate, and revoking one needs no card and ends it at once.

The hook decides a write is covered and records which mandate; the handler
plans the write again, requires the same digest the hook saw, checks again at
the write that the mandate is still in force and that the plan still fits, and
counts its changes before anything is sent (one ledger row each, written
together under the store's lock). A write that no longer fits is refused with
nothing sent. Inside a mandate a write also runs where nobody can
answer a card, such as a cron job. A read, a preview, a write outside a
mandate and a write that does not fit keep the rules of the access doc.

Mandates are stored by the shared mandate store
(`plugins/_shared/mandate_store.py`) under the plugin's own state directory,
and the writes they cover are counted in the shared MAC'd ledger beside them
(`plugins/_shared/mandate_ledger.py`). The Keychain is skipped only while no
`head.json` exists, that is until the first mandate has been made; revoking
every mandate leaves the head file, so from then on each write reads the key.

## Why

- Repeated setup work, such as pointing several records at a new host or
  warming caches after a deploy, needs a card per call otherwise, which trains
  the user to approve without reading. A card's "session" or "always" covers
  only an identical request (or, for three ✅ cards, one kind per target), so it
  cannot say "these records of these zones, for a few days".
- The bounds keep an injected agent from the harm that cannot be taken back or
  that exposes something: it cannot delete a record, weaken a setting, empty
  the cache of a whole zone, publish a service through a tunnel, redirect mail,
  roll code back, or touch a zone the user did not name. What is left can be
  undone by the next change, within a few zones and a few changes an hour.
- DNS is narrowed to what points a visible host through Cloudflare: a proxied
  A, AAAA or CNAME record under an ordinary name. MX and TXT records route or
  authenticate mail (SPF, DKIM, DMARC) and prove domain control, NS records
  delegate, `_`-prefixed names are challenge and key records, and an unproxied
  record publishes an origin address: none of those can be taken back once
  resolvers or a verifier have seen them, so they ask.
- A mandate bounds changes, not calls: one call may carry up to 20 items, so
  the count is per item, or twenty an hour would be four hundred.
- The card's own level judges a setting only by moving down a scale (SSL mode,
  TLS floor, security level) or Always Use HTTPS off; a setting that switches
  a protection off from a value that is not on a scale (Automatic HTTPS
  Rewrites, TLS 1.3, e-mail obfuscation) is ⚠️ on its own card. A mandate is
  stricter than the card there: it refuses those, so the card's levels did not
  change.
- Development mode on and purges of hosts or prefixes stay covered on purpose:
  they only bypass the cache for three hours or make the next requests fetch
  fresh copies from the origin, and the next change or the passing of time
  undoes them; the bound is the hourly count.
- The class is judged from the requests the write would send, read from
  Cloudflare when the hook plans it and again at the write, not from the call's
  arguments: a record that became a tunnel's CNAME in between stops the write.
- Counting before the send, and also when it fails or is uncertain, keeps the
  hourly bound whatever happens to the request.
- A deleted, emptied or replaced ledger reads as used up, never as unused.
- The 7-day ceiling is lower than the 30 of the GitHub and send mandates
  because a zone change reaches every visitor at once; a forgotten mandate
  should lapse on its own.

## Do not

- Cover a delete, an MX, TXT, NS or other non-A/AAAA/CNAME record, an
  unproxied record, a `_` name, a tunnel record, a weaker setting or one that
  turns a protection off, a purge of everything, a tunnel route, an e-mail
  rule, a rollback, storage, or a zone or account the card did not name,
  whatever the terms say. Count calls instead of changes.
- Let a mandate be made without its own card, from a cron job, a single query
  or an inbound request, or let one raise its own bounds.
- Decide what is in force from the history file: only the MAC'd head does.
- Count a write after it was sent, or only when it succeeded; read a missing,
  unreadable or linked ledger as zero uses.
- Skip the digest comparison at the write because a mandate covers it.
- Keep the MAC key anywhere a profile receives, or open the state directory or
  the key's name to file or terminal calls.
- Lengthen the 7-day ceiling or raise the 20 an hour without a decision of its
  own.
