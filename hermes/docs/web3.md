# Web3

EVM chains and Solana as two access plugins, one tool per chain family like
the other access plugins' one tool per platform: reading — balances, blocks,
transactions, addresses and prices — for the Assistant, Researcher, Searcher
and Marketer, and for the Assistant alone the user's wallets, sending native
coins and tokens from the Hermes-only seed phrases and private keys in the
Keychain. Read it when changing the read engine, the signer or the approval
path. The approval and bypass-guard rules follow
[access-common.md](access-common.md). Part of the Hermes design docs — index:
[`PROFILES.md`](../PROFILES.md).

## Shape

| Piece                                                                                                                               | Home                                                                                                                             | Reader                                    |
| ----------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------- |
| `evm` tool (toolset `evm_access`)                                                                                                   | `plugins/web3/evm-access/`                                                                                                       | Assistant, Researcher, Searcher, Marketer |
| `solana` tool (toolset `solana_access`)                                                                                             | `plugins/web3/solana-access/`                                                                                                    | Assistant, Researcher, Searcher, Marketer |
| Both tools' schemas, per-profile actions, the `pre_tool_call` approval hook and bypass guard (code, not a plugin: no `plugin.yaml`) | `plugins/web3/_shared/access.py`, `guard.py`                                                                                     | both plugins                              |
| Read engine: chain table, JSON-RPC client, ABI and Solana parsing, price lookup                                                     | `plugins/web3/_shared/reader.py` with `chains.py`, `rpc.py`, `abi.py`, `evm.py`, `sol.py`, `prices.py`, run by the engine venv   | both plugins                              |
| Signer: finds the wallet secrets, derives accounts, builds, simulates, signs and sends transfers; the only reader of wallet secrets | `plugins/web3/_shared/signer.py` with `keychain.py`, `ledger.py` and `seeds.py` (new wallets), run by the engine venv            | both plugins, for the Assistant           |
| Engine dependencies, hash-locked                                                                                                    | `engines/web3/requirements.{in,lock}` → `local/web3/venv`                                                                        | both plugins                              |
| Setup and status launcher                                                                                                           | `scripts/web3.sh install\|status\|addresses\|new-wallet`                                                                         | people                                    |
| How a profile reads a chain (actions, one-block reads, limits)                                                                      | the `evm-access:evm` and `solana-access:solana` plugin skills (`plugins/web3/<plugin>/skills/`), for every profile with the tool | Assistant, Researcher, Searcher, Marketer |
| How the Assistant lists wallets, makes new ones and sends funds                                                                     | the `evm-access:evm-wallet` and `solana-access:solana-wallet` plugin skills; registered for the Assistant only                   | Assistant                                 |
| What the Assistant does inline in Chat                                                                                              | the Assistant's Chat reference `web3.md`                                                                                         | Assistant                                 |
| How Researcher weighs and gathers chain evidence, and what Searcher records from chains                                             | each pipeline's `references/platforms/evm.md` and `solana.md`                                                                    | Researcher, Searcher                      |

Every profile in the plugins' list gets the read actions; the Assistant's tools
also carry the wallet actions (`accounts`, `create_wallet`, `quote`, `transfer`,
`status`). Both tools run their engine as a child process with the venv's
interpreter ([bridge process](access-common.md#state-directory-and-bridge-process)),
so the gateway's own Python never imports a chain library or holds a key. The
upstream `blockchain/evm` and `blockchain/solana` skills are not wired: they run
through the terminal, which Researcher and Searcher do not have.

## Chains and RPC

Chains come from a fixed table in `_shared/chains.py` (id, native symbol and
decimals, explorer, public RPC, fee model). Solana: mainnet-beta and devnet. A
chain is named by its table key (`base`, `sepolia`, `solana-devnet`), never by a
free-form URL. Each EVM chain has a fee model for what it charges beyond gas,
which a transfer's maximum fee must cover: `none` (gas covers it, the L1 cost
included where there is one), `op` (the OP Stack L1 data fee and operator fee),
`op-token` (as `op`, the L1 fee converted into the native token) or `scroll`
(Scroll's own L1 fee oracle). Celo's native coin also answers as an ERC-20 at a
fixed address; it is the native balance, so that address is kept out of the
token lists to never count it twice.

`address`, `contract`, `call` and `storage` resolve their block once (the
current one unless `block` names another) and read everything at it, so one
result never mixes blocks and its `block` names the one read; Solana's account
reads return the `slot` they saw. Public endpoints cap a JSON-RPC batch and
refuse the rest as rate-limited, so the engine sends small batches and retries
refused items in smaller rounds. Without a provider key a chain is only as
reachable as its public RPC.

Each chain uses its public RPC unless a provider key is stored: Alchemy (EVM)
and Helius (Solana) keys sit in the Keychain under project `hermes`, scope
`web3-rpc`, read by the engine on first use. Provider URLs embed the key, so the
engine never returns, logs or raises an error with an RPC URL; errors name the
chain and provider only. An Etherscan key in the same scope lets the decoder and
`contract` read contracts Sourcify has not verified and, where Etherscan's plan
covers the chain, name an unverified contract's deployer. Prices come from
CoinGecko's public API and are labelled estimates; testnets have none.

## Reads

Each tool takes one `action` per call and every action takes `chain`; the tool
schema lists the actions. Results are compact JSON, one block per result, capped
in size (longer lists are cut and counted). Rules that hold across them:

- `contract` reports verification, proxies, powers and the current values of
  argument-free getters; `call` runs one function as `eth_call` (a write
  function runs too and changes nothing: the answer is whether and how it would
  succeed for that caller at that block). `call` never changes state;
  `contract` names the getters still unanswered in `state_unread`.
- `logs` is bounded per call; what was not read is named in `unread_ranges`
  with the reason, never silently dropped.
- `activity` and `portfolio` use a provider index when a key is stored and a
  bounded scan otherwise, and say which.
- `gas` on a chain with an L1 fee model includes it, from the same oracles as a
  quote (`_shared/fees.py`), or says `l1_fee_unread` when the oracle does not
  answer.
- Text read from the chain is data from strangers (see "ABI decoding" below).

### Token risk

`risk` (both tools, every profile that reads; `_shared/risk.py`) answers "what can this token's controllers do to its
holders". It never scores: each finding has a `severity` — `high` when someone
can change the code, create more, stop, freeze or seize holders' tokens;
`medium` for fees, limits, the funds the contract holds, a single key (or a
1-of-n multisig) on a role and holder concentration; `low` / `info` for metadata
and facts — an `area`, the `evidence` read and a `confidence`. `controllers`
names who holds each power and what that holder is (nobody, a single key, a
multisig, a timelock, a program, another contract), and
`unknowns` what was not read (a holder the RPC would not describe,
AccessControl roles, a beacon's controller); a read that fails there never
fails the whole result. An EIP-1167
clone is reported as fixed code, not upgradeable. Role names stay in `evidence`,
never in the finding's sentence. Unverified EVM code makes the code itself
`high` and the named powers `low` confidence.

Holder concentration is read only on Solana, from the largest token accounts,
which are not owners (pools, exchanges and locks hold for many), so it is a lead
and never above `medium`; public RPCs refuse that list for large tokens, and EVM
has none without an indexer: both are `unknowns`. A name-based finding is a lead
to confirm in the source or with `call`, as everywhere in these tools.

### ABI decoding and untrusted text

ABI decoding tries, in order: the contract's verified ABI from Sourcify, else
from Etherscan when a key is stored (either with a proxy's implementation), the
built-in set of common standards, then 4byte.directory signatures, marked
`guessed` because selectors collide. A `powers` entry is a lead from a
function's name, not proof of what its code does. Text read from the chain —
token and contract names, symbols, NatSpec notices, IDL descriptions, revert
strings, memo and log text — is data from strangers: results return it as
`{"untrusted": …}`, and the tool description tells the model it never carries
instructions.

Both tools answer inbound A2A reads on Researcher and Marketer, whose work
arrives that way (Searcher works only in resident sessions and has no A2A
endpoint); the Assistant refuses them, as for its other accounts, and no inbound
request ever reaches a wallet action. A call names a chain of its tool's family
and an action its profile has; anything else is refused before the engine
starts, and only the action's own fields reach the engine.

## Accounts

The wallet has no settings file and changes nothing about `secret`. Its accounts
are the seed phrases and private keys in the Keychain, in any `secret` project,
recognized by their kind as `secret` already records it; the name, which the
user chooses anyway, says whether Hermes may sign:

```sh
secret set HERMES_MAIN -p <project> -D MNEMONIC --no-env         # a seed phrase Hermes may sign with
secret set PROJECTX_HERMES -p <project> -D PRIVATE_KEY --no-env  # a private key Hermes may sign with
secret set PROD_MNEMONIC -p <project> -D MNEMONIC                # watch-only: addresses read, never signed
```

`--no-env` keeps an item out of `secret env`, which every injected environment
is built from (the Hermes secret helper, the launcher shims, an agent's shell),
so only `get` reads it ([secret.md](../../zsh/functions/secret.md)). A Hermes
wallet stored without it sits in whatever environment injects its layer; the
wallet cannot undo that, so it reports it (`warnings` in `accounts`,
`web3.sh status`) and still signs.

A name with `HERMES` as one of its `_` / `-` / `.` separated words, in any case,
marks a Hermes wallet (`HERMES_MAIN`, `projectx-hermes`; not `THERMES_KEY`). Any
other seed phrase or key is watch-only, so a project's own wallets never sign
and never count as own by accident: Hermes reads their addresses and balances,
and a transfer to them asks like any external one, its card naming the
watch-only account. Renaming an item to carry `HERMES` is the user's consent to
signing with it.

On each call the signer lists every project's items with `secret projects` and
`secret ls --long` — names, scopes and kinds, no values — and reads with
`secret get` only the items whose kind is a seed phrase or a private key
(`MNEMONIC`, `PRIVATE_KEY`, in any spelling). No other secret's value is read, so
an API key that happens to look like a private key never becomes a wallet. A
seed must be a valid English BIP39 phrase; a key a 32-byte hex EVM key, or a
Solana keypair in base58 or as the CLI's JSON byte array. Items that fail, and a
second copy of the same secret, are listed as skipped, never used; a secret
stored both under a Hermes name and another name keeps its Hermes copy. Without
the `secret` CLI the wallet is unavailable.

A source is `<project>[/<scope>]/<name>`; an account is `<source>#<index>` for a
seed (`hermes/HERMES_MAIN#0`) and the source itself for a key. EVM accounts use
`m/44'/60'/0'/0/<index>` (MetaMask's path); Solana uses `m/44'/501'/<index>'/0'`
(Phantom's), so the same words open the accounts in those wallets for recovery.
A key signs on its own family only.

Seeds, derived keys and raw signed transactions stay in the signer process and
are never written to a file, a result, a log or an error; its output is
addresses, quotes and transaction hashes. Every account comes with its Keychain
metadata — project, scope, name, kind and use (`sign` / `watch`) — so the
Assistant can tell the user which wallet is which. This deliberately reads seed
phrases and keys across `secret` projects, which the rest of Hermes never does.

**Own addresses** are what the Hermes wallets control: each Hermes seed's
accounts 0–100 on both families and every Hermes key's address — computed from
the secrets on each call, never taken from the model or a file the model can
write. Funds moved to a spare account, between Hermes seeds or to a Hermes key
stay the user's. Watch-only wallets are not own, and an item renamed without
`HERMES` becomes watch-only on the next call.

## Transfers (the Assistant's wallet actions)

`quote` validates, builds the exact transaction, simulates it and stores it as a
single-use quote that outlives the approval wait before it expires; `transfer`
sends exactly the stored quote and reports `confirmed`, `failed` (landed but
reverted: only the fee was spent) or `pending`. `quote` takes `kind` `revoke`
([Revokes](#revokes)) or `nft` ([NFTs](#nfts)) beside the default `transfer`.
The tool schema lists the other wallet actions.

The scope of a transfer is fixed: an EIP-1559 native transfer, an ERC-20
`transfer`, a SOL System Program transfer, or an SPL `transferChecked` (creating
the recipient's associated token account when missing), plus the fixed calls of
[Revokes](#revokes) and [NFTs](#nfts). No calldata, program or instruction from
the caller is ever signed. Any token may be sent; its contract decides what its
own `transfer` does, so it must have code, answer `decimals`, and pass
simulation, and the card names it by address with its self-declared symbol
quoted. Refused outright: the zero address, the sending account itself, a
token's own contract, a Solana program or token account as recipient (the
owner's wallet address is asked for), a new Solana account below the rent-exempt
minimum, and an amount with more decimals than the asset has.

The recipient that counts is the one the signer encoded: for a token transfer
that is the recipient in the calldata or instruction, not the transaction's `to`
(the token contract). Addresses are checksummed (EVM) or base58-validated
(Solana); an ENS name is resolved on Ethereum's registry at quote time and the
card shows both.

The stated maximum fee is gas times the maximum fee per gas, plus what the
chain's fee model adds ([Chains and RPC](#chains-and-rpc)): twice the L1 data
fee its oracle quotes for the transaction's own bytes (signed to size it, never
broadcast) and, on the OP Stack chains, the operator fee; `_shared/fees.py` is
the formula.

A quote carries an HMAC keyed from its sending secret over everything it says —
its id, the transaction, the recipient, the own/external verdict and both cards
— so an edited quote file, another quote's file under this id, or a quote whose
secret is gone is refused. At `transfer` time the signer re-checks that, the
expiry, that the quote was never sent before, that the MAC is the one the
approval was given for, and the hourly cap; re-derives whether the recipient is
own; re-reads the nonce and fees (the transaction may change only within the
quote's stated maximum fee, otherwise the call fails and asks for a new quote);
and only then signs.

### Revokes

A quote's `kind` is `transfer` (the default), `revoke`, which takes back an
approval a Hermes wallet gave, or `nft` ([NFTs](#nfts)); its MAC covers the kind
like everything else. The signer reads the approval as it is now and builds one
fixed call, or refuses when there is nothing to revoke:

| Approval found                                                    | Call signed                                            |
| ----------------------------------------------------------------- | ------------------------------------------------------ |
| ERC-20 `allowance(owner, spender)` above 0                        | `approve(spender, 0)` on the token                     |
| NFT `isApprovedForAll(owner, operator)` true                      | `setApprovalForAll(operator, false)` on the collection |
| SPL delegate on the owner's associated token account for the mint | SPL Token `Revoke` (instruction 5)                     |

A revoke is simulated and its fee bounded like a transfer, sends nothing to
anyone, and is never own: whoever the spender is, the hook shows its card and
blocks it where no human can answer. It counts against the hourly cap and is
ledgered with its kind. Only Hermes wallets revoke; a watch-only wallet's
approvals are listed by `allowances` for the user to revoke in their own wallet.
ERC-721 single-token approvals are not covered.

### NFTs

`kind: nft` sends an NFT the Hermes wallet holds, with one fixed call per
standard, after checking it is there to send:

| NFT                                                                     | Checked first                           | Call signed                                                   |
| ----------------------------------------------------------------------- | --------------------------------------- | ------------------------------------------------------------- |
| ERC-721 (`supportsInterface(0x80ac58cd)`), `token_id`                   | `ownerOf(token_id)` is the account      | `safeTransferFrom(account, to, token_id)`                     |
| ERC-1155 (`supportsInterface(0xd9b67a26)`), `token_id`, `amount` copies | `balanceOf(account, token_id)` ≥ copies | `safeTransferFrom(account, to, token_id, copies, "")`         |
| Solana plain NFT: a mint of 0 decimals and supply 1                     | its token account is not frozen         | SPL `transferChecked` of 1 (creating the recipient's account) |

Gas estimation runs the transfer, so a recipient contract that cannot take the
NFT (no receiver hook) refuses it at quote time. A programmable NFT (frozen,
moves only through Metaplex) and a compressed NFT (no mint account) are refused.
An NFT is treated like a coin: to an own Hermes wallet it runs, to anyone else
it asks. It counts against the hourly cap and is ledgered with its standard and
token id.

## Approval

The hook decides before a `transfer` runs, from the quote as the signer verifies
it (`verify`: its MAC under its own id, unused, unexpired) — never from the
quote file as read, nor from the model's arguments beyond the quote id — so a
card is only ever the authentic one.

- **Own recipient:** runs without asking, mainnets included (the funds stay the
  user's; only the fee is spent). The signer refuses a send approved this way
  unless it re-derives the recipient as own.
- **Any other recipient**, watch-only wallets included: an approval card through
  Hermes' gate (`request_tool_approval`), the inline-button card on Telegram.
  The signer writes two cards into the quote, both under its MAC: a detailed
  one (transfer first, then `From` and `To` blocks with the Keychain's
  metadata; `To` opens with whose it is) and a compact one for Discord's smaller
  budget. Every value comes from the signer's quote, and a card is never cut: it
  sheds the memos, then falls back to the compact card. Addresses are shown in
  full, never shortened, because poisoning attacks forge look-alike prefixes and
  suffixes.
- **Session and always do nothing.** Hermes' card always offers them and a
  plugin cannot hide them, so every card has a fresh rule key (the quote id and
  a random suffix): a grant can never answer another card, the same quote's
  included. "Always" leaves a dead `plugin_rule:` entry in `command_allowlist`;
  the reference tells the user to answer _once_.
- **Fail closed where no human answers.** External transfers are blocked,
  without asking, wherever no person can answer
  ([approval gate](access-common.md#approval-gate)); the hook checks this itself
  (`_no_human` in `access.py`), since the gate would otherwise auto-approve, and
  assumes nobody is present when it cannot read Hermes' approval context.
  Silence, denial, timeout and a gate error block as everywhere else.
- **The hook's decision travels in memory.** The hook records `own` or `card` and
  the verified quote's MAC in the gateway process; the tool takes them once and
  passes them to the signer, which sends only the quote with that MAC. A
  transfer without a decision (or with a stale one) never reaches the signer.
- **At most 10 transfers an hour**, every account and recipient together, so a
  loop cannot drain an account into fees. There are no amount limits: an
  approved external transfer can move everything the account holds, so the
  accounts should only ever hold what the user is ready to lose.
- Inbound A2A requests never reach the wallet.

Quotes and the send ledger live in `<profile home>/web3-wallet/`, written under
a lock file held from the checks through the broadcast, so two sends never race
the cap. The order is the contract: a quote is marked consumed and a ledger line
is written with outcome `unknown` before broadcast, so a crash mid-send never
re-sends it; a second line for the same attempt records `sent` with the hash, or
`rejected` when the node answered with an error or the signer stopped before
broadcasting. A quote the ledger has seen is never sent again, even if its
consumed mark is cleared. After the broadcast the lock is released and the send
waits briefly for the transaction to land; a third line adds its `confirmation`.
Its outcome stays `sent`, so a transaction that landed and reverted still counts
against the cap, as its fee was spent. Nothing after the broadcast turns the
reply into an error: a read that fails while waiting reports `pending`. The cap
counts every attempt that is `sent` or `unknown` (no answer after broadcasting
may still mean the transfer happened); `rejected` moved nothing and does not
count.

## New wallets

`create_wallet` (either tool; the Assistant only) and `web3.sh new-wallet` make
a Hermes seed phrase in the signer and store it in the Keychain, so a wallet can
exist without anyone typing or seeing its words. The Assistant supplies the
`name` (`HERMES` as one of its words; refused when the project has any item of
that name), the `project`, the `scope`, the phrase length and a one-line
`purpose`; the kind and `--no-env` are fixed. The item's comment ends in the #0
addresses of both families.

The hook asks the signer to normalize the spec against the Keychain listing
(`wallet_check`: names and metadata only, no value read) and always shows its
card, under the transfers' presence rule and a fresh rule key per card. The
decision carries the spec's digest in memory; at `wallet_create` the signer
normalizes the spec again under the wallet lock, refuses one whose digest
differs (nothing is made), makes the phrase from the OS's randomness, derives
account #0 on both families, and stores it with `secret set --new --stdin` —
create-only, so `secret` and `security` refuse an existing item instead of
overwriting it, and the phrase on stdin, never in argv, a file, a result or a
log. It then reads the Keychain back as the wallet does: the item must list as a
Hermes seed phrase, `ENV no`, with the same account #0. An item that has
meanwhile taken the name is someone else's and is left untouched (`--new` makes
any complaint from `security`, in any language, a refusal). A cut-off write, a listing that cannot be read, or an item that reads
back differently is reported as possibly made, not to be funded, and counts
against the cap. The phrase is never shown, so
the Keychain holds its only copy until the user reads it with `secret get` for a
written one; the result says so. At most three new wallets an hour (counting any
that may exist), in `<state>/wallets.jsonl` — names and addresses only — apart
from the transfer ledger; `web3.sh new-wallet` shows the same card and asks on
the terminal.

## Ways around the tools

The wallet's secrets have any name in any project, so on the Assistant the hooks
keep the Keychain itself out of the terminal: terminal, code-execution and
file-tool calls are blocked when their text runs `secret get` / `env` / `set` /
`update` / `rm` / `import` / `export` or `security …-generic-password` (a deleted
or overwritten seed is lost funds), `dump-keychain`, names the signer or its
modules, `web3.sh`, the engine venv, the wallet's state directory or the
`web3-rpc` scope and its items, or runs a chain CLI that signs. Researcher,
Searcher and Marketer, which have no wallet, block only the read engine's paths
and the RPC keys. Patterns: `plugins/web3/_shared/guard.py`. Like the other
access plugins this is a pattern match on the call's text, not a sandbox
([bypass guard](access-common.md#bypass-guard-ways-around-the-tool)), and the
Assistant has a terminal. The real boundaries are that the secrets never leave
the signer, that whether a recipient is own is computed from the secrets, and
that every external transfer shows its card.

Prompt injection is the expected attack: a web page, token name, memo or message
that tells the Assistant to send funds. The card shows what the signer will
sign; the user's answer is the only thing between an external recipient and the
funds.

## Setup

1. `~/.config/hermes/scripts/web3.sh install` — builds `local/web3/venv` from the
   lock.
2. For each wallet Hermes may send from, a seed phrase (or key) for Hermes alone,
   never one that holds other funds: ask the Assistant for a new wallet, or run
   `web3.sh new-wallet HERMES_<NAME> -j <purpose> -p <project>`
   ([New wallets](#new-wallets)) — the phrase is never shown, so read it once
   with `secret get` for a written copy before it holds anything you would mind
   losing — or store your own as in [Accounts](#accounts). Wallets already stored
   under other names show up watch-only without any step.
3. Optional: `secret set ALCHEMY_API_KEY -p hermes --scope web3-rpc`, and
   `HELIUS_API_KEY` and `ETHERSCAN_API_KEY` the same way.
4. Enable `evm-access` and `solana-access` in the Assistant's config (the other
   three profiles already have them), then restart the gateway.
5. `web3.sh addresses [N] [CHAIN]` prints the accounts and balances to fund from
   a faucet; `web3.sh status` names the wallet items with sign or watch-only and
   their ENV setting, and the stored API keys (never their values).
