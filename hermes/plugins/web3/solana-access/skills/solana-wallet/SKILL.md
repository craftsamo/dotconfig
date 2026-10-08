---
name: solana-wallet
description: "Use with evm-access:evm-wallet when the user's wallet action is on Solana: what is particular to quoting and sending SOL and SPL tokens."
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [wallet, transfer, solana, spl, solana_access, approval]
---

# Sending on Solana

The procedure is the one in `evm-access:evm-wallet` (accounts, `quote`,
`transfer`, `status`, approval cards and recovery); load it first and use it
with the `solana` tool. Reading the chain is `solana-access:solana`. What is
particular to Solana:

- A transfer is a SOL System Program transfer or an SPL `transferChecked`;
  the tool creates the recipient's associated token account when it is
  missing. Nothing else is ever signed.
- `to` is the recipient's wallet address. A program or a token account as
  recipient is refused, and so is a new account that would hold less than the
  rent-exempt minimum.
- `token` is the mint; omit it for SOL. `amount` takes at most the asset's
  decimals.
- A transaction is identified by its signature: `status` takes it as `hash`.
- One seed's account has an address on both tools, so the same `accounts`
  entry serves EVM and Solana; `chain` picks the cluster for native balances.
