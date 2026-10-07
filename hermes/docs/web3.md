# Web3

Read access to EVM chains and Solana for the Assistant, Researcher, Searcher
and Marketer — balances, blocks, transactions, addresses and prices — and a
wallet for the Assistant alone that sends native coins and tokens from
accounts derived from one Hermes-only seed phrase. Part of the Hermes design
docs — index: [`PROFILES.md`](../PROFILES.md).

## Shape

| Piece                                                                                                                         | Home                                                      | Reader                                    |
| ----------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- | ----------------------------------------- |
| Shared engine code: chain table, JSON-RPC client, ABI and Solana parsing, price lookup (code, not a plugin: no `plugin.yaml`) | `plugins/web3/_shared/`                                   | both plugins                              |
| `chain` tool (toolset `web3_read`), read-only                                                                                 | `plugins/web3/chain-read/`                                | Assistant, Researcher, Searcher, Marketer |
| `wallet` tool (toolset `web3_wallet`), its `pre_tool_call` approval hook and bypass guard                                     | `plugins/web3/wallet/`                                    | Assistant                                 |
| Signer: derives accounts, builds, simulates, signs and sends transfers; the only reader of key material                       | `plugins/web3/wallet/signer.py`, run by the engine venv   | the wallet plugin                         |
| Engine dependencies, hash-locked                                                                                              | `engines/web3/requirements.{in,lock}` → `local/web3/venv` | both plugins                              |
| Setup and status launcher                                                                                                     | `scripts/web3.sh install\|status\|addresses`              | people                                    |
| When and how the Assistant reads chains and sends funds                                                                       | the Assistant's `web3` technic                            | Assistant                                 |

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
public API (rate-limited, cached for a minute) and are labelled estimates.

## Reads (`chain`)

One tool, one `action` per call, results as compact JSON capped at 60 000
characters (longer lists are cut and counted). Every action takes `chain`.

| Action       | EVM                                                                                                                                                                                                                                                                                              | Solana                                                                                                                                                            |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `block`      | number, hash, `latest`, `safe` or `finalized`: time, proposer / fee recipient, gas used and limit, base fee, burned and priority fees, blob gas, transaction count by type; `detail=true` adds the top transactions by fee and the most-called contracts                                         | slot or `latest`: time, leader, parent, transaction count, fees, rewards, the most-invoked programs                                                               |
| `tx`         | status and revert reason, from / to / value, nonce, type, fee split (base, priority, burned), calldata decoded, event logs decoded, token and native balance changes per address, created contract; internal calls when the RPC offers `debug_traceTransaction` (otherwise reported unavailable) | status and error, fee, compute units, signers, instructions and inner instructions parsed (`jsonParsed`), SOL and token balance changes per account, program logs |
| `address`    | EOA or contract, balance, nonce, code size, EIP-1967 / EIP-1167 proxy target, detected standards (ERC-20/721/1155), ENS name on Ethereum                                                                                                                                                         | owner program, lamports, executable, data size, parsed token account or mint                                                                                      |
| `portfolio`  | native balance and ERC-20 balances (provider token API when a key is stored, else a known-token list) with USD estimates; `chains=[…]` scans several                                                                                                                                             | SOL and SPL balances with USD estimates                                                                                                                           |
| `activity`   | recent transfers of an address (provider API; without a key, a bounded log scan of token `Transfer` events)                                                                                                                                                                                      | recent signatures with status                                                                                                                                     |
| `logs`       | events of a contract over a block range, at most `LOG_RANGE` blocks per call, decoded when the ABI is known                                                                                                                                                                                      | —                                                                                                                                                                 |
| `token`      | name, symbol, decimals, supply, price                                                                                                                                                                                                                                                            | mint, decimals, supply, authorities, price                                                                                                                        |
| `allowances` | ERC-20 approvals an address has granted, flagging unlimited ones                                                                                                                                                                                                                                 | delegated token accounts                                                                                                                                          |
| `decode`     | raw calldata, a raw signed or unsigned transaction, or a log                                                                                                                                                                                                                                     | a base58 / base64 transaction                                                                                                                                     |
| `gas`        | base fee, priority fee percentiles, fee for a plain and a token transfer                                                                                                                                                                                                                         | recent prioritization fees                                                                                                                                        |
| `price`      | symbol or contract → USD price, 24 h change, market cap                                                                                                                                                                                                                                          | the same by mint                                                                                                                                                  |

ABI decoding tries, in order: the contract's verified ABI from Sourcify (a
proxy's implementation included), the built-in set (ERC-20/721/1155,
WETH, Multicall3, Uniswap V2/V3 swaps, Permit2), then 4byte.directory
signatures, marked `guessed` because selectors collide. Text read from the
chain — token names, symbols, revert strings, memo and log text — is data
from strangers: results return it inside a `untrusted` field, and the tool
description tells the model it never carries instructions.

Researcher and Searcher are A2A-only, so `chain` accepts inbound A2A calls
on them; the Assistant refuses them, as for its other accounts.

## Accounts

The wallet derives every account from one BIP39 seed phrase, created by the
user for Hermes alone and stored only in the Keychain:

| Secret                | Keychain item                                           | Content                                    |
| --------------------- | ------------------------------------------------------- | ------------------------------------------ |
| Seed phrase           | `WEB3_MNEMONIC` (project `hermes`, scope `web3-wallet`) | 12 or 24 words, no passphrase              |
| Extra keys (optional) | `WEB3_KEY_<NAME>` (same scope)                          | a raw private key imported for one account |

Accounts are named by role in the Assistant's private config
(`web3_wallet.accounts`), never by index alone:

```yaml
web3_wallet:
  networks: [sepolia, base-sepolia, solana-devnet]
  accounts:
    ops: { index: 0, chains: [sepolia, base-sepolia, solana-devnet] }
    lab: { index: 1, chains: [base-sepolia] }
```

EVM accounts use `m/44'/60'/0'/0/<index>` (MetaMask's path); Solana uses
`m/44'/501'/<index>'/0'` (Phantom's), so the same words open the accounts in
those wallets for recovery. The scope is the arrangement the Google and X
credentials use: no profile's secret layer, the gateway's environment or a
CLI session ever holds it. Only the signer reads it, through the `secret`
CLI with stdin closed, once per call; the seed, derived private keys and the
raw signed transaction stay in that process and are never written to a file,
a result, a log or an error. Its output is addresses, quotes and transaction
hashes.

**Own addresses** are the addresses the signer derives for the configured
accounts plus the extra keys' addresses — computed from the secrets on each
call, never taken from config, the model or a file the model can write.

## Transfers (`wallet`)

| Action     | What it does                                                                                                                                                                                                                                             |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `accounts` | each role's address per chain and balance; never a key                                                                                                                                                                                                   |
| `quote`    | `account`, `chain`, `to`, `amount`, `token` (omit for the native coin): validates, builds the exact transaction, simulates it (`eth_estimateGas` + `eth_call`; `simulateTransaction`), and stores it as a single-use quote that expires after 10 minutes |
| `transfer` | `quote`: sends exactly the stored transaction                                                                                                                                                                                                            |
| `status`   | a sent transfer's confirmations or failure                                                                                                                                                                                                               |

The scope of a transfer is fixed: an EIP-1559 native transfer, an ERC-20
`transfer`, a SOL System Program transfer, or an SPL `transferChecked`
(creating the recipient's associated token account when missing). No
calldata, program or instruction from the caller is ever signed. A token
must be in the account's configured token list for that chain; a token
outside it is refused, since an unknown contract decides what its own
`transfer` does.

The recipient that counts is the one the signer encoded: for a token
transfer that is the decoded recipient in the calldata or instruction, not
the transaction's `to` (the token contract) — a token sent to the contract
itself is refused. Addresses are checksummed (EVM) or base58-validated
(Solana); an ENS name is resolved at quote time and the card shows both.

At `transfer` time the signer re-reads the nonce and fees; the transaction
may change only within the quote's stated maximum fee, otherwise the call
fails and asks for a new quote.

## Approval

The hook decides before `wallet transfer` runs, from the stored quote, not
from the model's arguments beyond the quote id.

- **Own recipient, within limits:** runs without asking.
- **Any other recipient:** an approval card through Hermes' gate
  (`request_tool_approval`). On Telegram that is the inline-button card; the
  card is kept inside Telegram's reason budget (480 escaped UTF-16 units) so
  it never falls back to the text `/approve` prompt. It reads, one fact per
  line:

  ```
  Send 0.05 ETH (≈ $150) on Base Sepolia
  From: ops 0x…full address…
  To: 0x…full address… (external)
  Max fee: 0.00021 ETH
  Quote: q7f3a, expires 14:32
  ```

  Every value comes from the signer's decoded quote. Addresses are shown in
  full, never shortened, because poisoning attacks forge look-alike prefixes
  and suffixes.

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
- **Limits no approval lifts**, from the private config, per account and per
  asset: `per_tx` and `per_day` amounts in the asset's own units (not USD, so a
  missing or manipulated price cannot widen them), a cap on transfers per hour
  and a daily cap on fees spent. They bind own-address transfers too, so a
  loop cannot drain an account into fees. A call over a limit is blocked
  with the limit named; raising one is a config change.
- **Networks:** only the chains in `web3_wallet.networks` sign. Mainnets are
  added there by hand after the testnet run.
- Inbound A2A requests never reach the wallet.

Quotes, the spend ledger and sent transfers live in
`~/.hermes/profiles/assistant/web3-wallet/`, written under a lock file;
a quote moves to `consumed` before its transaction is broadcast, so a crash
mid-send never re-sends it. Every send appends a line (time, role, chain,
recipient, amount, hash, own/external, approval) to `ledger.jsonl` there.

## Ways around the tools

The wallet's hook blocks terminal and file-tool calls whose command, working
directory or path names the signer, the engine venv's interpreter, the state
directory, the `web3-wallet` or `web3-rpc` scopes or their items, a raw
`secret get` / `security find-generic-password` / `dump-keychain` /
`secret export`, or chain CLIs that sign (`cast send`, `cast wallet`,
`solana transfer`, `spl-token transfer`). Like the other access plugins, it
is a pattern match on the call's text, not a sandbox: it stops ordinary use,
not a determined script. The real boundaries are that the key never leaves
the signer and that the limits and own-address list are computed outside
the model's reach.

Prompt injection is the expected attack: a web page, token name, memo or
message that tells the Assistant to send funds. The card shows what the
signer will sign, the limits cap what an approved mistake costs, and the
wallet should only ever hold what the user is ready to lose.

## Setup

1. `~/.config/hermes/scripts/web3.sh install` — builds `local/web3/venv`
   from the lock.
2. Create a new seed phrase for Hermes alone (never one that holds other
   funds), then `secret set WEB3_MNEMONIC -p hermes --scope web3-wallet -D
MNEMONIC` and type it at the hidden prompt. Hermes never generates or
   shows it.
3. Optional: `secret set ALCHEMY_API_KEY -p hermes --scope web3-rpc` and
   `HELIUS_API_KEY` the same way.
4. Set `web3_wallet` (networks, accounts, token lists, limits) in the
   Assistant's private config, enable `chain-read` and `wallet` there and
   `chain-read` on Researcher, Searcher and Marketer, then restart the
   gateway.
5. `web3.sh addresses` prints each account's addresses (never a key) to fund
   from a faucet; `web3.sh status` shows the engine, which secrets are stored
   (never their values) and today's spend.

After bumping a pin, recompile the lock (command in `requirements.in`) and
run `install` again.
