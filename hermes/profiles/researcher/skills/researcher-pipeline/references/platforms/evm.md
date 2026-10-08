# EVM chains

Ethereum, Base, Arbitrum, OP Mainnet, Polygon, BNB Chain, Avalanche and their
testnets, read through the `evm` tool. It reads only: nothing is signed or
sent, and a write function run with `call` is an `eth_call` simulation. A
block explorer page shows the same chain data plus the explorer's own labels;
cite the chain read; the explorer link the tool returns is its locator.

## What the chain proves

The kernel's source evaluation and on-chain rules apply. In addition:

- **Verified source** — an ABI and source verified by Sourcify (`exact`, or
  `partial` when only metadata differs) or Etherscan is primary for what the
  code is. Unverified code yields function selectors with `guessed` names,
  which the kernel treats as Inference until the source or a decisive `call`
  settles them.
- **`powers`** — write functions grouped by what their names suggest (mint,
  pause, blocklist, fees, limits, trading, upgrade, control, funds) are
  Inference, a lead to check in the verified source or with `call`, never a
  finding by themselves.

## Patterns

1. **Who controls a contract.** `contract` gives the proxy and its admin, the
   deployer and, in `state`, the current values of getters such as `owner`,
   `pauser` or `admin`: use those values rather than calling the same getters
   again; `call` what `state` lacks (those in `state_unread`, getters with
   arguments or list results, anything past its first 25). A role set to the zero address
   is unset. Read each other holder with `address`: an EOA is one key; a
   contract may be a multisig (for a Safe, `call` `getThreshold()` and
   `getOwners()`) or a timelock (`call` `getMinDelay()`). `logs` for
   `OwnershipTransferred`, `RoleGranted` or `Upgraded` shows when control
   changed.
2. **Whether something can happen.** Run the function with `call` from the
   address that would do it, with `amount` when it pays: a revert and its
   decoded reason, or success. A simulation shows the outcome for that caller
   at that block, not that it will always hold — say which block.
3. **Following funds.** Start from `tx` balance changes, then the counterparts'
   `activity` or `logs`, one hop at a time. Agree the hop cap, call budget and
   stop points (an exchange deposit address, a bridge, a mixer) in Plan; a
   trail past the cap is a stated gap, not a guess.
4. **Exposure.** `allowances` lists current ERC-20 approvals and NFT operators
   an address granted, flagging unlimited ones; `portfolio` its holdings.
5. **History.** `call` and `storage` take a past `block` only on an RPC that
   keeps history (an Alchemy key); a refusal leaves that point unknown. A proxy
   is read with the implementation it had then.

## Limits

- Without a provider key, `activity` scans recent blocks for token transfers
  only and misses native transfers; `trace` is usually refused. `logs` reads
  one contract over at most 5000 blocks a call and returns at most 100 events,
  counting the rest as `omitted`. `allowances` scans a recent window (50000
  blocks by default, `blocks` up to 200000) and misses older approvals; carry
  its `coverage` into the evidence. Record what was not readable as uncovered
  ground; an empty result over a window is not "none ever".
- Without an `ETHERSCAN_API_KEY`, contracts verified only on Etherscan read as
  unverified.
- A decoded call or event says where its ABI came from (`verified`, `known`,
  `guessed`); carry that label into the evidence.
- `contract`, `call`, `storage` and `address` read one block and return its
  number as `block`; cite that number. Proxies are found through EIP-1167,
  EIP-1967 and OpenZeppelin's older (zos) slots; another pattern shows no
  `proxy`, so a contract whose behaviour suggests one stays an open question.
