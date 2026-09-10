# Quality assurance — image-creator: emoji

Read [common quality assurance](../index.md) first.

For a pack, the size-of-use look is the actual platform: a Slack/Discord
custom emoji renders around 32 px, so read the hands' 32 px sheet
(`sheet32_zoom.png` from a generate delivery, or `pack32.png` from
analyze-emoji) for whether each expression still reads at that size — a
finding that only the 128 px identity sheet can show is a GAP for the
platform size, not a pass. Compare the platform/format/cap and alpha
findings against the client's chosen `platform`; a light/dark background
check belongs here too when the client named one. Round A candidates are
reviewed at native size for identity against `character.md`'s named
features, never by proxy of the round B pack. No new measurement is taken
here: the hands' coverage/alpha/`within_cap` numbers and 32 px/128 px sheets
are the evidence, never a fresh finish or a reroll to double-check a
borderline call.

The verdict and delivery-to-client shape are common — see
[common quality assurance](../index.md).
