# Creative — plan

Collect the MediaBrief from chat, memory, and the user before any
session or card — creator should never burn credits guessing style:

- **Purpose & audience** — what the asset is for, where it will be seen.
- **Destination & specs** — platform/placement constraints (dimensions,
  aspect ratio, duration, format, file-size cap) when known.
- **Style direction** — tone, palette, brand assets, reference
  images/links; pass references via `--image` or paths in Inputs.
- **Quantity & variants** — how many, which sizes/crops.
- **Budget** — a `Budget:` line with generation-spend caps; omitted =
  creator defaults (4 image variants / 2 video renders per asset, 1
  corrective pass, batch = the brief's count). Widen it up front for
  sanctioned exploratory work; expand mid-session in a later turn.
- **Deadline / priority.**

Ask at most one compact `clarify` round for missing essentials; fill
sensible defaults yourself and say so.

**Feasibility and cost questions go to the session first**: for a novel
technique, an expensive asset, or an uncertain chain, open the session in
advisory ("この方針は現実的? 概算コストは?") before promising the user
anything. The reply grounds your plan.

**Style anchor before batch spend** — for a consistent multi-asset set or
a high-cost asset (a long video), the first production turn asks for one
cheap sample/anchor. Check it (quality-assurance), show the user when
taste is theirs to judge, then approve the batch in the next turn. Never
let a batch run before its anchor passed. This gate is also what makes a
batch card-eligible: the `anchored-image-batch` unit requires an
**approved** anchor as input, so anchor exploration itself can never ride
a card.

**Composite media is a DAG, not a card** — a video with scenes, voice,
and edit is planned as separate stages (each resident or a matching unit)
with your QA between them; "作って" requests that imply a composite are
decomposed here, at plan time, with the user seeing the stages.
