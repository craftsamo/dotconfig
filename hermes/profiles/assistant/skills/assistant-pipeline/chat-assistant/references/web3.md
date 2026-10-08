# Web3

Blockchains and the user's wallets through the `evm` tool (Ethereum, Base,
Arbitrum, OP Mainnet, Polygon, BNB Chain, Avalanche and their testnets) and
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

Sending, and making a new wallet, is only ever the user's own request in
this conversation. Never schedule a job meant to send funds or make a wallet
— schedule a reminder for the user instead.
