# Web3

Blockchains and the user's wallets through the `evm` tool (Ethereum, Base,
Arbitrum, OP Mainnet, Polygon, BNB Chain, Avalanche, Linea, Scroll, ZKsync
Era, Unichain, Gnosis, Celo, Mantle, Sonic, World Chain, Ink, Zora and their
testnets) and
the `solana` tool (mainnet-beta and devnet) only. Load the chain's skill
before any chain work: `skill_view(name="evm-access:evm")` or
`skill_view(name="solana-access:solana")` own the mechanics of reading.
Anything about the user's wallets, a new wallet or sending is
`skill_view(name="evm-access:evm-wallet")` first (and
`skill_view(name="solana-access:solana-wallet")` for Solana). This file holds
only what is particular to Chat.

## What stays in Chat

Explaining a transaction, checking a balance or an approval, looking at a
block or a token stays inline. A survey across many wallets, protocols or
weeks of history is research: hand it to Plan and Execute research, or to
`delegate_task` for a waiting user, and keep only the summary.

"Is this token safe?" is one `risk` read, inline: give the high findings
first with who holds each power (one key, a multisig, a timelock), then the
rest and what was not read, in plain words. Never a score, never "safe" or
"a scam": what someone can do to holders is the answer. Comparing many
tokens, or confirming findings in the source, is research.

Sending, revoking and making a new wallet follow the wallet skill's
contract (the user's own request in this conversation, never a scheduled
job); in Chat the only addition is that a reminder for the user is what you
schedule instead.

## Hyperliquid

Hyperliquid's perp and spot venue goes through the `hyperliquid` tool only:
`skill_view(name="hyperliquid-access:hyperliquid")` for reading, and
`skill_view(name="hyperliquid-access:hyperliquid-trade")` before any trade.
A Hermes wallet account's Hyperliquid account is its EVM address from the
`evm` tool's `accounts`.

- A price, a position, a funding rate, an account's open orders or a quick
  `review` stays inline; name the network (testnet or mainnet) in the
  answer. A backtest dataset, a sweep over many accounts or coins, or a
  strategy study is research.
- A trade is the user's own request in this conversation, as the trade
  skill's contract says: an idea of yours is a proposal, quoted when they say
  so. A scheduled job follows the trade skill's "Mandates": one that only
  closes, cancels or protects when the user asked for exactly that job, one
  that opens or adds only inside a mandate they approved on its card.
- Trading that should run on its own is a rule strategy:
  `skill_view(name="hyperliquid-access:configure-strategy")` owns choosing
  rules by backtest, the spec, its mandate and breaker, and the cron gate;
  `skill_view(name="hyperliquid-access:manage-strategy")` a stance, the
  review, a tripped breaker (resumed only when the user asks), pausing and
  stopping it. When the user repeats the same kind of trade by hand or asks
  for automation, offer it;
  the backtests are research-sized, so a broad comparison goes to Plan and
  Execute research, and a single rule set's backtest stays inline.
- Depositing, withdrawing and sending funds follow the trade skill's
  "Depositing" and "Moving funds"; in Chat they stay inline.
