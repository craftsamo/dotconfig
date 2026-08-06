# Produce — the production loop (entry)

Loaded for Produce work: the brief describes assets to deliver. The
kernel's contracts (Budget caps, dialogue contract) apply throughout; this file owns the chain routing and the per-asset loop.

Intent shapes the entry (kernel <IntentTriage>):

- `new` — this file, top to bottom. A consistent batch or a high-cost
  asset without a pinned reference belongs to the execute Direction route first
  (`references/plan.md`) — check before spending.
- `revise` — load `references/iterate.md` FIRST; it owns inheritance and
  feedback triage, then re-enters this loop for the actual re-rendering.
- `salvage` — load `references/resume.md` <Salvage> FIRST; it owns the
  inventory; this loop then covers only what genuinely must be produced.

## CapabilityRouting

Load `references/capabilities.md`, select the canonical leaf by final
deliverable and production method, then `skill_view` it before work. The leaf
owns craft and medium-specific QA; this pipeline continues to own Budget,
questions, review, verification floor, and delivery.

A dispatch may preload a canonical technic, but preload is not proof that it
resolved. Perform the capability handshake from that reference before spend.
The body remains authoritative enough to recover from a skipped optional pin;
a missing canonical leaf is a block, not permission to improvise.

The table is intentionally extensible. Before declaring a niche asset
unsupported, scan the opt-in catalog and check prerequisites. External catalog
skills do not become stable dispatch names automatically, and their inline
`clarify` flows never override the kernel's `Q<n>:` block protocol.

## ProductionLoop

Per asset (or batch chunk):

1. **Spec first.** Destination constraints (platform, dimensions, format,
   caps) and brand/style inputs come before the first generation — the
   depth skills open with exactly this discovery. An anchored batch reuses
   the locked anchor verbatim (`references/plan.md` <AnchorByType>).
2. **Generate deliberately** within the Budget caps: variants are for
   real alternatives, not retries of an unread failure. Post-process with
   terminal tools (ffmpeg, the bundled scripts) in the task workspace;
   keep intermediates out of the delivery.
3. **Verify before moving on** — `references/verify.md`, the intent's
   profile. A clear miss gets the corrective pass (default: one per
   asset); if it still misses, deliver the best attempt and state the gap
   plainly — exceeding the Budget instead is a `Q<n>` block, never a
   judgment call.
4. `PROGRESS:` with the running spend tally, then the next asset.

Ambiguity discovered mid-loop (a spec the brief doesn't pin, a taste fork
the anchor doesn't settle) → the kernel's block protocol: batch the
questions, checkpoint, block once.

## Handoff

All assets verified → `references/delivery.md`: attachment discipline
(including the anchor/reuse contract), the Review gate when the body
carries `Review:`, and the evidence-backed report + metadata.

## Pitfalls

- Generating before reading the whole brief (count, specs, platform,
  Budget) or before the spec/anchor is pinned.
- Skipping the Direction gate on a batch because production "can start now" —
  anchor first, batch after sign-off.
- Declaring an asset type unsupported without scanning the opt-in catalog,
  or using an opt-in chain whose prerequisite isn't running.
- Treating an external catalog name as a canonical dispatch identity, or
  silently falling back when a requested canonical leaf fails its handshake.
- Letting a technique skill's inline `clarify` override the block
  protocol.
- Retrying a failed generation without reading WHY it failed — variants
  cost the same as successes.
- Verifying at the end of the whole task instead of per asset — a drifted
  spec discovered late costs the batch.

## Verification

- Every produced asset went through its `references/verify.md` intent
  profile before delivery; corrective passes stayed within caps.
- Chain/depth-skill choice matched the asset type (or the catalog scan is
  documented); prerequisites were checked before use.
- Handoff ran through `references/delivery.md` — nothing stranded, report
  evidence itemized.
