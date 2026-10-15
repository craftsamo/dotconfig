# Hyperliquid USDC moves through Circle's CCTP, not the legacy bridge

Status: in force
Owner doc: docs/hyperliquid.md "Moving funds" and "Deposits"

## Decision

USDC leaves Hyperliquid only as a CCTP burn (`sendToEvmWithData`) to one of
the network's chains Circle carries USDC on, never as a `withdraw3` through
the legacy Arbitrum bridge, and enters only as a CCTP burn on such a chain
(`approve` of exactly the amount, then `depositForBurnWithHook` to Circle's
forwarder on HyperEVM), never as a transfer to that bridge, which the signer
refuses. Circle's fee is read for every quote: a withdrawal's from its
HyperEVM contract (and again before signing, since the burn binds none), a
deposit's from its fee service, capped in the burn; the cards show what
arrives.

## Why

- The venue calls the legacy bridge deprecated in favour of CCTP, and its
  testnet refused a `withdraw3` outright; one route that works is safer than
  a choice whose older half may fail or not credit.
- CCTP reaches every chain Circle supports, with Circle minting and paying
  the gas on the far side, so a withdrawal needs no ETH there.
- Circle's fees differ by chain and change, so a fixed number in the code
  would misstate what arrives.
- A deposit's mint and its relay are bound to Circle's forwarder, so nobody
  else can complete it; the approval Hermes gives is exact, so a burn leaves
  nothing of it to spend.

## Do not

- Bring back `withdraw3` or bridge transfers as an option, or as a fallback
  after a refusal.
- Take a CCTP domain, a contract address or the token from the caller, or
  confuse a domain with an EVM chain id: they come from `chains` by name.
- Approve more than the deposit's amount, or leave the burn's `destinationCaller`
  empty: either lets someone else act on the user's USDC.
- Fix Circle's fees in the code, or sign a withdrawal without reading its fee
  again.
