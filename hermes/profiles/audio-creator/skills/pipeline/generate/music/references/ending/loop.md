# Loop

Intent: the delivered file is meant to be repeated seamlessly by a
downstream player. `ending: loop` is a request that the prompted material
end on material compatible with looping - it is **not** a promise that
the raw generated take itself loops, and it is not a backend "make it
loop" flag (this engine has no such toggle).

Prompt guidance: describe the loop intent ("written to loop, ending
returns toward the opening feel") in the prompt so the model favors
compatible material, but treat any resulting seam as unverified until
edited.

Actual loop delivery: producing a verified seam is a separate, explicit
`edit-music` step (`loop_seconds`, `crossfade_ms`) on the rendered WAV,
with only a numerical boundary-sample check as evidence - never a
musical "sounds seamless" claim from this leaf alone.

QA cue: the report must name the separate edit-music step as still
required for an actual looping delivery, never claim the raw generated
take already loops seamlessly.
