# Web3

Read access to EVM chains and Solana for the Assistant, Researcher, Searcher
and Marketer — balances, blocks, transactions, addresses and prices — and a
wallet for the Assistant alone that sends native coins and tokens from the
Hermes-only seed phrases and private keys the user labels in the Keychain.
Part of the Hermes design docs — index: [`PROFILES.md`](../PROFILES.md).

## Shape

| Piece                                                                                                                                       | Home                                                                                       | Reader                                    |
| ------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ | ----------------------------------------- |
| Shared engine code: chain table, JSON-RPC client, ABI and Solana parsing, price lookup, bypass guard (code, not a plugin: no `plugin.yaml`) | `plugins/web3/_shared/`                                                                    | both plugins                              |
| `chain` tool (toolset `web3_read`), read-only                                                                                               | `plugins/web3/chain-read/`                                                                 | Assistant, Researcher, Searcher, Marketer |
| `wallet` tool (toolset `web3_wallet`), its `pre_tool_call` approval hook and bypass guard                                                   | `plugins/web3/wallet/`                                                                     | Assistant                                 |
| Signer: finds the labelled secrets, derives accounts, builds, simulates, signs and sends transfers; the only reader of wallet secrets       | `plugins/web3/wallet/signer.py` with `keychain.py` and `ledger.py`, run by the engine venv | the wallet plugin                         |
| Engine dependencies, hash-locked                                                                                                            | `engines/web3/requirements.{in,lock}` → `local/web3/venv`                                  | both plugins                              |
| Setup and status launcher                                                                                                                   | `scripts/web3.sh install\|status\|addresses`                                               | people                                    |
| When and how the Assistant reads chains and sends funds                                                                                     | the Assistant's `web3` technic                                                             | Assistant                                 |

Both tools run their engine as a child process with the venv's interpreter
(the `x-access` arrangement), so the gateway's own Python never imports a
chain library or holds a key. The upstream `blockchain/evm` and
`blockchain/solana` skills are not wired: they run through the terminal,
which Researcher and Searcher do not have, and they stop at a transaction's
header where this tool decodes calls, events and balance changes.

## Chains and RPC

Chains come from a fixed table in `_shared/chains.py` (id, native symbol and
decimals, explorer, public RPC). EVM: Ethereum, Base, Arbitrum One, Optimism,
Polygon PoS, BNB Chain, Avalanche C-Chain, and their testnets (Sepolia, Base
Sepolia, Arbitrum Sepolia, Optimism Sepolia, Polygon Amoy). Solana:
mainnet-beta and devnet. A chain is named by its table key (`base`,
`sepolia`, `solana-devnet`), never by a free-form URL.

Each chain uses its public RPC unless a provider key is stored: Alchemy
(EVM) and Helius (Solana) keys sit in the Keychain under project `hermes`,
scope `web3-rpc`, read by the engine on first use. Provider URLs embed the
key, so the engine never returns, logs or raises an error with an RPC URL;
errors name the chain and provider only. Prices come from CoinGecko's
public API (rate-limited) and are labelled estimates; testnets have none.

## Reads (`chain`)

One tool, one `action` per call, results as compact JSON capped at 60 000
characters (longer lists are cut and counted). Every action takes `chain`.

| Action       | EVM                                                                                                                                                                                                                                                                                                                                                                     | Solana                                                                                                                                                                      |
| ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `block`      | number, hash, `latest`, `safe` or `finalized`: time, fee recipient, gas used and limit, base fee and burn, blob gas, transactions by type, the most-called contracts; `detail=true` adds total and priority fees, failures and the top transactions by fee                                                                                                              | slot or `latest`: time, leader, parent, transaction count, the leader's fee reward; `detail=true` adds vote / non-vote counts, failures, fees and the most-invoked programs |
| `tx`         | status and revert reason, from / to / value, nonce, type, fee split (base, priority, burned, L1 data fee), calldata decoded, event logs decoded, token and native balance changes per address, NFT transfers, created contract, EIP-7702 authorizations; `trace=true` adds internal calls when the RPC offers `debug_traceTransaction` (otherwise reported unavailable) | status and error, fee, compute units, signers, instructions and inner instructions parsed (`jsonParsed`), SOL and token balance changes per account, program logs           |
| `address`    | EOA, EIP-7702-delegated EOA or contract, balance, nonce, code size, EIP-1967 / beacon / EIP-1167 proxy target, detected standards (ERC-20/721/1155), verified name, ENS name on Ethereum                                                                                                                                                                                | owner program, lamports, executable, data size, parsed token account or mint                                                                                                |
| `portfolio`  | native and ERC-20 balances (provider token index when an Alchemy key is stored, else a known-token list) with USD estimates; `chains=[…]` scans up to six                                                                                                                                                                                                               | SOL and SPL balances with USD estimates                                                                                                                                     |
| `activity`   | recent transfers of an address (provider index; without a key, a bounded scan of token `Transfer` events, native transfers unseen)                                                                                                                                                                                                                                      | recent signatures with status and memo                                                                                                                                      |
| `logs`       | events of a contract over at most 5000 blocks, decoded when the ABI is known                                                                                                                                                                                                                                                                                            | —                                                                                                                                                                           |
| `token`      | name, symbol, decimals, supply, standards, price                                                                                                                                                                                                                                                                                                                        | decimals, supply, mint and freeze authorities, extensions, price                                                                                                            |
| `allowances` | ERC-20 approvals and NFT operators an address granted in the scanned blocks, still current, flagging unlimited ones                                                                                                                                                                                                                                                     | delegated token accounts                                                                                                                                                    |
| `decode`     | raw calldata, a raw signed or unsigned transaction (sender recovered, EIP-7702 delegations flagged), or a log                                                                                                                                                                                                                                                           | a base58 / base64 transaction                                                                                                                                               |
| `gas`        | next base fee, priority fee percentiles, cost of a plain and a token transfer                                                                                                                                                                                                                                                                                           | base fee and recent prioritization fees                                                                                                                                     |
| `price`      | symbol or contract → USD price, 24 h change, market cap                                                                                                                                                                                                                                                                                                                 | the same by mint                                                                                                                                                            |

ABI decoding tries, in order: the contract's verified ABI from Sourcify (a
proxy's implementation included), the built-in set (ERC-20/721/1155, WETH,
Multicall3, Uniswap V2/V3 swaps, permit, upgrades), then 4byte.directory
signatures, marked `guessed` because selectors collide. Text read from the
chain — token names, symbols, revert strings, memo and log text — is data
from strangers: results return it as `{"untrusted": …}`, and the tool
description tells the model it never carries instructions.

`chain` answers inbound A2A requests on Researcher, Searcher and Marketer,
whose work arrives that way; the Assistant refuses them, as for its other
accounts. A call names its chain from the table and its action from that
chain's family; anything else is refused before the engine starts, and only
the schema's fields reach the engine.

## Accounts

The wallet has no settings file and changes nothing about `secret`. Its
accounts are the seed phrases and private keys in the Keychain, in any
`secret` project, recognized by their kind as `secret` already records it;
the name, which the user chooses anyway, says whether Hermes may sign:

```sh
secret set HERMES_MAIN -p <project> -D MNEMONIC        # a seed phrase Hermes may sign with
secret set PROJECTX_HERMES -p <project> -D PRIVATE_KEY # a private key Hermes may sign with
secret set PROD_MNEMONIC -p <project> -D MNEMONIC      # watch-only: addresses read, never signed
```

A name with `HERMES` as one of its `_` / `-` / `.` separated words, in any
case, marks a Hermes wallet (`HERMES_MAIN`, `projectx-hermes`; not
`THERMES_KEY`). Any other seed phrase or key is watch-only, so a project's
own wallets never sign and never count as own by accident: Hermes reads
their addresses and balances, and a transfer to them asks like any external
one, its card naming the watch-only account. Renaming an item to carry
`HERMES` is the user's consent to signing with it.

On each call the signer lists every project's items with `secret projects`
and `secret ls --long` — names, scopes and kinds, no values — and reads with
`secret get` only the items whose kind is a seed phrase or a private key
(`MNEMONIC`, `PRIVATE_KEY`, in any spelling such as `seed phrase` or
`private-key`). No other secret's value is read, so an API key that happens
to look like a private key never becomes a wallet. A seed must be a valid
English BIP39 phrase; a key a 32-byte hex EVM key, or a Solana keypair in
base58 or as the CLI's JSON byte array. Items that fail, and a second copy
of the same secret, are listed as skipped, never used; a secret stored both
under a Hermes name and another name keeps its Hermes copy. Without the
`secret` CLI the wallet is unavailable.

A source is `<project>[/<scope>]/<name>`; an account is `<source>#<index>`
for a seed (`hermes/HERMES_MAIN#0`) and the source itself for a key. EVM accounts
use `m/44'/60'/0'/0/<index>` (MetaMask's path); Solana uses
`m/44'/501'/<index>'/0'` (Phantom's), so the same words open the accounts in
those wallets for recovery. A key signs on its own family only.

Seeds, derived keys and raw signed transactions stay in the signer process
and are never written to a file, a result, a log or an error; its output is
addresses, quotes and transaction hashes. Every account comes with its
Keychain metadata — project, scope, name, kind label as `secret` lists it,
kind (`seed` / `key`) and use (`sign` / `watch`) — so the Assistant can tell
the user which wallet is which. This deliberately reads seed phrases and
keys across `secret` projects, which the rest of Hermes never does.

**Own addresses** are what the Hermes wallets control: each Hermes seed's
accounts 0–100 on both families and every Hermes key's address — computed
from the secrets on each call, never taken from the model or a file the
model can write. Funds moved to a spare account, between Hermes seeds or to
a Hermes key stay the user's. Watch-only wallets are not own, and an item
renamed without `HERMES` becomes watch-only on the next call.

## Transfers (`wallet`)

| Action     | What it does                                                                                                                                                                                                                                                                                                    |
| ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `accounts` | every labelled seed's first accounts (5 by default, up to 101) and every key, Hermes and watch-only, with their metadata and EVM and Solana addresses; with `chain`, native balances there; skipped items with the reason. Never a key                                                                          |
| `quote`    | `account`, `chain`, `to`, `amount`, `token` (a contract or mint; omit for the native coin): validates, builds the exact transaction, simulates it (`eth_estimateGas` + `eth_call`; `simulateTransaction`), and stores it as a single-use quote that expires after 15 minutes (past the 10-minute approval wait) |
| `transfer` | `quote`: sends exactly the stored transaction                                                                                                                                                                                                                                                                   |
| `status`   | a sent transfer's confirmations or failure                                                                                                                                                                                                                                                                      |

The scope of a transfer is fixed: an EIP-1559 native transfer, an ERC-20
`transfer`, a SOL System Program transfer, or an SPL `transferChecked`
(creating the recipient's associated token account when missing). No
calldata, program or instruction from the caller is ever signed. Any token
may be sent; its contract decides what its own `transfer` does, so it must
have code, answer `decimals`, and pass simulation, and the card names it by
address with its self-declared symbol quoted (`"?"` when the symbol holds
anything but letters, digits and `.$_-`). Refused outright: the zero
address, the sending account itself, a token's own contract, a Solana
program or token account as recipient (the owner's wallet address is asked
for), a new Solana account below the rent-exempt minimum, and an amount
with more decimals than the asset has.

The recipient that counts is the one the signer encoded: for a token
transfer that is the recipient in the calldata or instruction, not the
transaction's `to` (the token contract). Addresses are checksummed (EVM) or
base58-validated (Solana); an ENS name is resolved on Ethereum's registry at
quote time and the card shows both.

A quote carries an HMAC keyed from its sending secret over everything it
says — the transaction, the recipient, the own/external verdict and the card
— so an edited quote file is refused at send, as is a quote whose secret is
no longer labelled. At `transfer` time the signer re-checks the MAC, the
expiry and the hourly cap, re-derives whether the recipient is own, re-reads
the nonce and fees (the transaction may change only within the quote's
stated maximum fee, otherwise the call fails and asks for a new quote) and
only then signs.

## Approval

The hook decides before `wallet transfer` runs, from the stored quote, not
from the model's arguments beyond the quote id.

- **Own recipient:** runs without asking, mainnets included (the funds stay
  the user's; only the fee is spent). The signer refuses a send approved
  this way unless it re-derives the recipient as own.
- **Any other recipient:** an approval card through Hermes' gate
  (`request_tool_approval`). On Telegram that is the inline-button card; the
  card is kept inside Telegram's reason budget (480 escaped UTF-16 units) so
  it never falls back to the text `/approve` prompt. It reads, one fact per
  line:

  ```
  MAINNET (real funds): Send 10 of token "USDC" on Base
  Token: 0x…full address…
  From: hermes/MAIN#0 0x…full address…
  To: 0x…full address… (external)
  Max fee: 0.00018 ETH
  Quote: q1a2b3c4d, expires 14:32 UTC+0800
  ```

  The `MAINNET (real funds)` prefix appears on every mainnet; testnet cards
  start with `Send`. Every value comes from the signer's quote. Addresses
  are shown in full, never shortened, because poisoning attacks forge
  look-alike prefixes and suffixes.

- **Session and always do nothing.** Hermes' card always offers them and a
  plugin cannot hide them, so the rule key is the quote id and a quote is
  consumed by its first send: a grant can never cover another transfer.
  "Always" leaves a dead `plugin_rule:` entry in `command_allowlist`; the
  technic tells the user to answer _once_.
- **Fail closed where no human answers.** External transfers are blocked,
  without asking, in cron, single-query runs, contexts without a human, under
  `/yolo` and with `approvals.mode: off` — the hook checks these itself, since
  the gate would otherwise auto-approve them. Silence, denial, timeout and a
  gate error block as everywhere else.
- **At most 10 transfers an hour**, every account and recipient together, so
  a loop cannot drain an account into fees. There are no amount limits: an
  approved external transfer can move everything the account holds, so the
  accounts should only ever hold what the user is ready to lose.
- Inbound A2A requests never reach the wallet.

Quotes and the send ledger live in `<profile home>/web3-wallet/`, written
under a lock file held for the whole send, so two sends never race the cap.
A quote is marked consumed and a ledger line (time, account, chain,
recipient, asset, amount, maximum fee, own/external, approval) is written
with outcome `unknown` before broadcast, so a crash mid-send never re-sends
it; a second line records `sent` with the hash, or `rejected` when the node
answered with an error or the signer stopped before broadcasting. The cap
counts `sent` and `unknown` (no answer after broadcasting may still mean the
transfer happened); `rejected` moved nothing and does not count.

## Ways around the tools

The wallet's secrets have any name in any project, so on the Assistant the
hooks keep the Keychain itself out of the terminal: terminal, code-execution
and file-tool calls are blocked when their text runs `secret get` / `set` /
`update` / `rm` / `import` / `export` or `security …-generic-password` (a
deleted or overwritten seed is lost funds), `dump-keychain`, names the
signer, `web3.sh`, the engine venv, the wallet's state directory or the
`web3-rpc` scope and its items, or runs a chain CLI that signs (`cast send`,
`cast wallet`, `solana transfer`, `spl-token transfer`). Researcher, Searcher
and Marketer, which have no wallet, block only the read engine's paths and
the RPC keys. Like the other access plugins this is a pattern match on the
call's text, not a sandbox: it stops ordinary use, not a determined script,
and the Assistant has a terminal. The real boundaries are that the secrets
never leave the signer, that whether a recipient is own is computed from the
secrets, and that every external transfer shows its card.

Prompt injection is the expected attack: a web page, token name, memo or
message that tells the Assistant to send funds. The card shows what the
signer will sign; the user's answer is the only thing between an external
recipient and the funds.

## Setup

1. `~/.config/hermes/scripts/web3.sh install` — builds `local/web3/venv`
   from the lock.
2. For each wallet Hermes may send from: create a new seed phrase (or key)
   for Hermes alone, never one that holds other funds, and keep a written
   copy — the Keychain is the only other place it exists. Store it under a
   name with `HERMES` in it, `secret set HERMES_<NAME> -p <project> -D
MNEMONIC` (or `-D PRIVATE_KEY`), typed at the hidden prompt. Hermes never
   generates or shows one. Seed phrases and keys already stored under other
   names show up watch-only without any step.
3. Optional: `secret set ALCHEMY_API_KEY -p hermes --scope web3-rpc` and
   `HELIUS_API_KEY` the same way.
4. Enable `chain-read` and `wallet` in the Assistant's config (the other
   three profiles already have `chain-read`), then restart the gateway.
5. `web3.sh addresses [N] [CHAIN]` prints every labelled seed's first N
   accounts and every key (never a secret), with balances on `CHAIN`, to fund
   from a faucet; `web3.sh status` names the labelled items with sign or
   watch-only, and the stored RPC keys (never their values).

After bumping a pin, recompile the lock (command in `requirements.in`) and
run `install` again.
