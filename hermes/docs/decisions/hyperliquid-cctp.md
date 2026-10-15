# Hyperliquid USDC moves through Circle's CCTP, not the legacy bridge

Status: in force
Owner doc: docs/hyperliquid.md "Moving funds"

## Decision

USDC leaves Hyperliquid only as a CCTP burn (`sendToEvmWithData`) to one of
the network's chains Circle carries USDC on, never as a `withdraw3` through
the legacy Arbitrum bridge. Circle's fee is read from its HyperEVM contract
for every quote, and both cards show what arrives.

## Why

- The venue calls the legacy bridge deprecated in favour of CCTP, and its
  testnet refused a `withdraw3` outright; one route that works is safer than
  a choice whose older half may fail.
- CCTP reaches every chain Circle supports, with Circle minting and paying
  the gas there, so a withdrawal needs no ETH on the destination.
- Circle's fee differs by chain and is set on its contract, so a fixed
  number in the code would misstate what arrives.

## Do not

- Bring back `withdraw3` as an option, or as a fallback after a refusal.
- Take a CCTP domain from the caller or confuse it with an EVM chain id: the
  domain comes from `chains.CCTP_DOMAINS` by chain name.
- Fix Circle's fee in the code, or send without the quote's reading of it.
