# Quality assurance — image-creator: kit

Read [common quality assurance](../../SKILL.md) first.

For a kit, normal/pressed/hover/disabled state pairs must keep the same
silhouette and alignment — generated drift between two states of the same
item is a FAIL, never dismissed as artistic variation, and a bar's fill
must sit inside its frame with matching registration. Without a stated
pair mapping, that check is GAP, never PASS by guessing which files pair
up. Read coverage (every requested item/category/state present, no extra
defaults or duplicates hidden by the zip archive), style consistency across
props and UI at use size, and alpha/geometry against the item's row in
`items.json`/`manifest.json`. An item still marked `passed: false` in the
manifest stays flagged in your delivery too — do not call a kit
production-ready by dropping its failed status, and route an exact
interchangeable-geometry need to `create-kit` rather than asking
`generate-kit` for a second silhouette-matching attempt. No new measurement
is taken here: `kit-images.py`'s recorded sheets and the hands' `qa.md`
findings are the evidence, never a fresh `measure` pass or a reroll to
double-check a borderline state pair.

The verdict and delivery-to-client shape are common — see
[common quality assurance](../../SKILL.md).
