# Solana

Solana mainnet-beta and devnet, read through the `solana` tool. It reads
only: nothing is signed or sent. An explorer page shows the same chain data
plus the explorer's own labels; cite the chain read; the explorer link the tool returns is its locator. The
tool's actions and mechanics are `skill_view(name="solana-access:solana")`;
this file holds how the evidence is weighed.

## What the chain proves

The kernel's source evaluation and on-chain rules apply. In addition:

- **Programs** — the deployed program's bytes are not readable as source.
  `program` gives its loader, whether it can still be upgraded and by which
  authority, and its last deployment slot. An Anchor IDL is the IDL
  authority's description of the interface, kept in its own account: useful,
  but it can lag or differ from the deployed code. A verified build (matching
  the deployed program to public source) comes from outside the chain; score
  it as that source.

## Patterns

1. **Who controls a program.** `program`: an upgrade authority that is set can
   replace the code; none (or a finalized loader-v4 program) means immutable.
   Read the authority with `address` — a wallet, or a program-owned account
   such as a multisig — and say which.
2. **Who controls a token, and is it safe to hold.** `risk` reads it at once:
   a mint authority still set can create more; a freeze authority can freeze
   holders' accounts; Token-2022 extensions (a transfer fee, a permanent
   delegate that can move anyone's tokens, a transfer hook that can refuse
   transfers, accounts frozen by default) change what holders can expect; a
   mutable Metaplex metadata lets its update authority rename the token. Each
   holder is a wallet (one key), an SPL multisig (m-of-n) or a program-owned
   account: say which, as Observation at the cited slot. The largest token
   accounts' share is a lead, not ownership — pools, exchanges and locks hold
   for many. Give the findings by severity, not a score or a verdict.
3. **Following funds.** Start from `tx` balance changes, then the
   counterparts' `activity`, one hop at a time, within the hop cap and call
   budget agreed in Plan.
4. **Exposure.** `allowances` lists token delegations an owner granted;
   `portfolio` its holdings.

## Limits

- `program`, `address` and `token` return the slot they read as `slot`; `program`
  also gives `program_data_slot` and the IDL's `slot`, read separately: cite
  the slot of the read that shows the fact.
- `activity` returns at most the latest 50 signatures of an address, with no
  paging: anything older is uncovered ground unless a signature already in
  hand leads there through `tx`. Record what was not read.
- The IDL is optional and may be missing; its absence says nothing about the
  program's safety.
