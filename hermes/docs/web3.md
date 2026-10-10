# Web3

EVM chains and Solana as two access plugins, one tool per chain family: reading
(balances, blocks, transactions, addresses, prices) for the Assistant,
Researcher, Searcher and Marketer, and for the Assistant alone the user's
wallets, sending native coins and tokens from Hermes-only seed phrases and keys
in the Keychain. Read it when changing the read engine, the signer or the
approval path. The approval and bypass-guard rules follow
[access-common.md](access-common.md). Part of the Hermes design docs — index:
[`PROFILES.md`](../PROFILES.md).

## Shape

| Piece                                                                                           | Home                                                                                                             |
| ----------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `evm` / `solana` tools (toolsets `evm_access`, `solana_access`)                                 | `plugins/web3/evm-access/`, `plugins/web3/solana-access/`: thin entry points                                     |
| Tool schemas, per-profile actions, `pre_tool_call` approval hook, bypass guard                  | `plugins/web3/_shared/access.py`, `guard.py` (code, not a plugin: no `plugin.yaml`)                              |
| Read engine: chain table, JSON-RPC, ABI and Solana parsing, prices                              | `_shared/reader.py` with `chains.py`, `rpc.py`, `abi.py`, `evm.py`, `sol.py`, `prices.py`                        |
| Signer: derives accounts, builds, simulates, signs and sends; the only reader of wallet secrets | `_shared/signer.py` with `keychain.py`, `ledger.py`, `seeds.py`                                                  |
| Engine dependencies, hash-locked                                                                | `engines/web3/requirements.{in,lock}` → `local/web3/venv`                                                        |
| Setup and status launcher                                                                       | `scripts/web3.sh`                                                                                                |
| How a profile reads a chain; how the Assistant lists wallets, makes new ones and sends          | plugin skills `evm-access:evm`, `solana-access:solana`, and for the Assistant only `evm-access:evm-wallet`, `solana-access:solana-wallet` |
| What the Assistant does inline in Chat; how Researcher and Searcher use chain evidence          | the Assistant's Chat reference `web3.md`; each pipeline's `references/platforms/evm.md`, `solana.md`             |

Every profile in the plugins' list gets the read actions; the Assistant's tools
also carry the wallet actions. Both tools run their engine as a child process
with the venv's interpreter
([bridge process](access-common.md#state-directory-and-bridge-process)), so the
gateway's own Python never imports a chain library or holds a key. The upstream
`blockchain/evm` and `blockchain/solana` skills are not wired: they run through
the terminal, which Researcher and Searcher do not have.

## Chains and RPC

Chains come from a fixed table in `_shared/chains.py` and are named by its key
(`base`, `sepolia`, `solana-devnet`), never by a free-form URL. Each EVM chain
has a fee model for what it charges beyond gas (`fee` in the table); a
transfer's stated maximum fee must cover it. Celo's native coin also answers as
an ERC-20 at a fixed address; that address is kept out of the token lists so
the balance is never counted twice.

`address`, `contract`, `call` and `storage` resolve their block once and read
everything at it, so one result never mixes blocks; Solana's account reads
return the `slot` they saw.

Each chain uses its public RPC unless a provider key is stored: Alchemy (EVM)
and Helius (Solana) keys sit in the Keychain under project `hermes`, scope
`web3-rpc`, read by the engine on first use. Provider URLs embed the key, so the
engine never returns, logs or raises an error with an RPC URL; errors name the
chain and provider only. An Etherscan key in the same scope widens contract
reads. Prices are CoinGecko estimates; testnets have none.

## Reads

Each tool takes one `action` per call and every action takes `chain`; the tool
schema lists the actions. Rules that hold across them:

- `call` runs one function as `eth_call` and never changes state (a write
  function runs too: the answer is whether it would succeed for that caller).
- What a read did not cover is named, never silently dropped (`unread_ranges`
  for `logs`, `state_unread` for `contract`, `l1_fee_unread` for `gas`).
- `activity` and `portfolio` say whether they used a provider index or a
  bounded scan.
- `gas` on an L1-fee chain uses the same oracles as a quote (`_shared/fees.py`).
- Text read from the chain is data from strangers (see "ABI decoding" below).

### Token risk

`risk` (both tools, every reading profile; `_shared/risk.py`) answers "what can
this token's controllers do to its holders". It never scores. Rules:

- Each finding carries a `severity`, an `area`, the `evidence` read and a
  `confidence`; `controllers` names who holds each power and what that holder
  is; `unknowns` names what was not read. A read that fails becomes an
  `unknown`, never a failure of the whole result.
- Role names stay in `evidence`, never in the finding's sentence. Unverified
  EVM code makes the code itself `high` and the named powers `low` confidence.
- Holder concentration is read only on Solana, from the largest token accounts
  (pools, exchanges and locks hold for many owners), so it is a lead and never
  above `medium`.
- A name-based finding is a lead to confirm in the source or with `call`.

### ABI decoding and untrusted text

ABI decoding prefers a verified ABI (Sourcify, else Etherscan) over the
built-in standards, and falls back to 4byte.directory signatures marked
`guessed` because selectors collide. A `powers` entry is a lead from a
function's name, not proof of what its code does. Text read from the chain —
names, symbols, NatSpec, IDL descriptions, revert strings, memos, log text — is
data from strangers: results return it as `{"untrusted": …}`, and the tool
description tells the model it never carries instructions.

Researcher and Marketer answer inbound A2A reads (their work arrives that way;
Searcher has no A2A endpoint); the Assistant refuses them, and no inbound
request ever reaches a wallet action. A call naming a chain of another family,
or an action its profile lacks, is refused before the engine starts, and only
the action's own fields reach the engine.

## Accounts

The wallet has no settings file and changes nothing about `secret`. Its accounts
are the seed phrases and private keys in the Keychain, in any `secret` project,
recognized by their kind as `secret` records it; the name, which the user
chooses anyway, says whether Hermes may sign:

```sh
secret set HERMES_MAIN -p <project> -D MNEMONIC --no-env         # a seed phrase Hermes may sign with
secret set PROJECTX_HERMES -p <project> -D PRIVATE_KEY --no-env  # a private key Hermes may sign with
secret set PROD_MNEMONIC -p <project> -D MNEMONIC                # watch-only: addresses read, never signed
```

- **Naming rule:** a name with `HERMES` as one of its `_` / `-` / `.` separated
  words, in any case, marks a Hermes wallet (`HERMES_MAIN`, `projectx-hermes`;
  not `THERMES_KEY`). Any other seed or key is watch-only, so a project's own
  wallets never sign and never count as own by accident; a transfer to one asks
  like any external one. Renaming an item to carry `HERMES` is the user's
  consent to signing with it.
- **`--no-env`** keeps an item out of `secret env`, which every injected
  environment is built from, so only `get` reads it
  ([secret.md](../../zsh/functions/secret.md)). A Hermes wallet stored without
  it is reported (`warnings` in `accounts`, `web3.sh status`) and still signs.
- **Kind-based reads:** each call lists every project's items with
  `secret projects` and `secret ls --long` (names, scopes and kinds, no values)
  and reads with `secret get` only items whose kind is a seed phrase or a
  private key. No other secret's value is read, so an API key that happens to
  look like a private key never becomes a wallet. Items that fail validation
  and duplicate copies are listed as skipped, never used; a secret stored under
  both a Hermes name and another keeps its Hermes copy. Without the `secret`
  CLI the wallet is unavailable.
- **Paths:** a source is `<project>[/<scope>]/<name>`; an account is
  `<source>#<index>` for a seed and the source itself for a key. EVM uses
  `m/44'/60'/0'/0/<index>` (MetaMask), Solana `m/44'/501'/<index>'/0'`
  (Phantom), so the same words open the accounts in those wallets for recovery.
  A key signs on its own family only.
- **Secrets stay in the signer:** seeds, derived keys and raw signed
  transactions are never written to a file, a result, a log or an error; the
  output is addresses, quotes and hashes. This deliberately reads seeds and
  keys across `secret` projects, which the rest of Hermes never does.

**Own addresses** are what the Hermes wallets control: each Hermes seed's
accounts 0–100 on both families and every Hermes key's address — computed from
the secrets on each call, never taken from the model or a file the model can
write. Funds moved to a spare account, between Hermes seeds or to a Hermes key
stay the user's. Watch-only wallets are not own, and an item renamed without
`HERMES` becomes watch-only on the next call.

## Transfers (the Assistant's wallet actions)

`quote` validates, builds the exact transaction, simulates it and stores it as a
single-use quote that outlives the approval wait; `transfer` sends exactly the
stored quote and reports `confirmed`, `failed` (landed but reverted: only the
fee was spent) or `pending`. `quote` takes `kind` `revoke` ([Revokes](#revokes))
or `nft` ([NFTs](#nfts)) beside the default `transfer`.

- **Fixed scope:** a native transfer, an ERC-20 `transfer`, a System Program
  transfer or an SPL `transferChecked` (creating the recipient's associated token
  account when missing), plus the fixed calls of Revokes and NFTs (ERC-721/1155
  `safeTransferFrom`, an SPL `transferChecked` of 1). No calldata, program or instruction from the caller is ever signed.
- **Any token may be sent** (its contract decides what its `transfer` does), so
  it must have code, answer `decimals` and pass simulation, and the card names
  it by address with its self-declared symbol quoted. Refused outright are the
  cases the signer's quote validation names (zero address, self, a token's own
  contract, a program or token account as recipient, a new Solana account below
  the rent-exempt minimum, over-precise amounts).
- **The recipient that counts** is the one the signer encoded: for a token
  transfer, the recipient in the calldata or instruction, not the transaction's
  `to`. An ENS name is resolved at quote time and the card shows both.
- **The stated maximum fee** is gas times the maximum fee per gas plus the
  chain's fee model ([Chains and RPC](#chains-and-rpc)); `_shared/fees.py` is
  the formula.
- **The quote is tamper-evident:** it carries an HMAC keyed from its sending
  secret over everything it says (id, transaction, recipient, own/external
  verdict, both cards, kind). At `transfer` the signer re-checks the MAC, the
  expiry, that it was never sent, that the MAC is the one the approval was
  given for and the hourly cap; re-derives whether the recipient is own;
  re-reads nonce and fees (the transaction may change only within the quote's
  maximum fee, else a new quote is asked for); and only then signs.

### Revokes

`kind: revoke` takes back an approval a Hermes wallet gave. The signer reads
the approval as it is now and builds one fixed call (ERC-20 `approve(spender,
0)`, NFT `setApprovalForAll(operator, false)`, SPL `Revoke`), or refuses when
there is nothing to revoke. A revoke is simulated and fee-bounded like a
transfer, sends nothing to anyone, and is never own: whoever the spender is,
the hook shows its card, and it is blocked where no human can answer. It counts
against the hourly cap. Only Hermes wallets
revoke; a watch-only wallet's approvals are listed by `allowances` for the user
to revoke elsewhere. ERC-721 single-token approvals are not covered.

### NFTs

`kind: nft` sends an NFT the Hermes wallet holds (ERC-721, ERC-1155, a plain
Solana NFT) with one fixed call per standard, after checking the wallet holds
it. Gas estimation runs the transfer, so a recipient contract that cannot take
the NFT refuses it at quote time; programmable and compressed Solana NFTs are
refused. An NFT is treated like a coin: to an own wallet it runs, to anyone else
it asks, and it counts against the hourly cap.

## Approval

The hook decides before a `transfer` runs, from the quote as the signer verifies
it (`verify`) — never from the quote file as read, nor from the model's
arguments beyond the quote id — so a card is only ever the authentic one.

- **Own recipient:** runs without asking, mainnets included (the funds stay the
  user's; only the fee is spent). The signer refuses a send approved this way
  unless it re-derives the recipient as own.
- **Any other recipient**, watch-only wallets included: an approval card through
  Hermes' gate (`request_tool_approval`). The signer writes a detailed and a
  compact card into the quote under its MAC; every value comes from the quote,
  a card is never cut (it sheds memos, then falls back to the compact card), and
  addresses are shown in full because poisoning attacks forge look-alike
  prefixes and suffixes.
- **Session and always do nothing.** Hermes' card always offers them and a
  plugin cannot hide them, so every card has a fresh rule key (quote id plus a
  random suffix): a grant can never answer another card.
- **Fail closed where no human answers.** External transfers are blocked
  wherever no person can answer ([approval gate](access-common.md#approval-gate));
  the hook checks this itself (`_no_human` in `access.py`), since the gate would
  otherwise auto-approve, and assumes nobody is present when it cannot read
  Hermes' approval context. Silence, denial, timeout and gate errors block.
- **The decision travels in memory:** the hook records `own` or `card` and the
  verified quote's MAC in the gateway process; the tool takes them once and
  passes them to the signer, which sends only the quote with that MAC. A
  transfer without a decision (or a stale one) never reaches the signer.
- **At most 10 transfers an hour**, every account and recipient together, so a
  loop cannot drain an account into fees. There are no amount limits: an
  approved external transfer can move everything the account holds, so accounts
  should only hold what the user is ready to lose.
- Inbound A2A requests never reach the wallet.

Quotes and the send ledger live in `<profile home>/web3-wallet/`, written under a
lock held from the checks through the broadcast, so two sends never race the
cap. The order is the contract: a quote is marked consumed and a ledger line
with outcome `unknown` is written before broadcast, so a crash mid-send never
re-sends; later lines record `sent` with the hash or `rejected`, then the
`confirmation`. A quote the ledger has seen is never sent again, even if its
consumed mark is cleared. The cap counts `sent` and `unknown` (no answer after
broadcasting may still mean it happened) and a reverted transaction (its fee was
spent); `rejected` moved nothing. Nothing after the broadcast turns the reply
into an error: a failed read while waiting reports `pending`.

## New wallets

`create_wallet` (either tool; the Assistant only) and `web3.sh new-wallet` make
a Hermes seed phrase in the signer and store it in the Keychain, so a wallet can
exist without anyone typing or seeing its words. The Assistant supplies `name`
(`HERMES` as one of its words; refused when the project has any item of that
name), `project`, `scope`, phrase length and a one-line `purpose`; the kind and
`--no-env` are fixed.

- The hook asks the signer to normalize the spec against the Keychain listing
  (`wallet_check`: names and metadata only) and always shows its card, under the
  transfers' presence rule and a fresh rule key per card. The decision carries
  the spec's digest in memory; `wallet_create` normalizes again under the wallet
  lock and refuses a differing digest (nothing is made).
- The phrase comes from the OS's randomness and is stored with
  `secret set --new --stdin`: create-only, so an existing item is refused rather
  than overwritten (`--new` turns any complaint from `security`, in any
  language, into a refusal), and the phrase never appears in argv, a file, a
  result or a log. The signer then reads the Keychain back as the wallet does:
  a Hermes seed, `ENV no`, the same account #0.
- A cut-off write, an unreadable listing or an item that reads back differently
  is reported as possibly made, not to be funded, and counts against the cap.
- The phrase is never shown, so the Keychain holds its only copy until the user
  reads it with `secret get` for a written one; the result says so.
- At most three new wallets an hour (counting any that may exist), in
  `<state>/wallets.jsonl` (names and addresses only), apart from the transfer
  ledger. `web3.sh new-wallet` shows the same card and asks on the terminal.

## Ways around the tools

The wallet's secrets have any name in any project, so on the Assistant the hooks
keep the Keychain itself out of the terminal: terminal, code-execution and
file-tool calls are blocked when their text runs `secret get` / `env` / `set` /
`update` / `rm` / `import` / `export` or `security …-generic-password` (a deleted
or overwritten seed is lost funds), runs `dump-keychain` or a chain CLI that
signs or sends (`cast send`, `solana transfer`, `spl-token transfer`: a keypair
on disk is not in the Keychain), or names the signer, `web3.sh`, the engine
venv, the wallet's state directory or the `web3-rpc` scope. Researcher, Searcher
and Marketer, which have no wallet, block only the read engine's paths and the
RPC keys. Patterns: `plugins/web3/_shared/guard.py`. Like the other access
plugins this is a pattern match on the call's text, not a sandbox
([bypass guard](access-common.md#bypass-guard-ways-around-the-tool)), and the
Assistant has a terminal. The real boundaries are that the secrets never leave
the signer, that whether a recipient is own is computed from the secrets, and
that every external transfer shows its card.

Prompt injection is the expected attack: a web page, token name, memo or message
that tells the Assistant to send funds. The card shows what the signer will
sign; the user's answer is the only thing between an external recipient and the
funds.

## Setup

1. `scripts/web3.sh install` builds `local/web3/venv` from the lock.
2. Per wallet Hermes may send from, a seed phrase or key for Hermes alone, never
   one that holds other funds: ask the Assistant for a new wallet, run
   `web3.sh new-wallet` ([New wallets](#new-wallets)), or store your own as in
   [Accounts](#accounts). Wallets already stored under other names show up
   watch-only without any step.
3. Optional provider keys (`ALCHEMY_API_KEY`, `HELIUS_API_KEY`,
   `ETHERSCAN_API_KEY`) go in project `hermes`, scope `web3-rpc`.
4. Enable `evm-access` and `solana-access` in the Assistant's config (the other
   profiles already have them), then restart the gateway.
5. `web3.sh addresses` and `web3.sh status` list accounts and stored items
   (never values); usage is in the script's header.
