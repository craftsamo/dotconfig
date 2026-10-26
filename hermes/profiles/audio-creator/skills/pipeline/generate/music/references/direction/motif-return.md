# Motif return

Intent: state a short, recognizable musical idea early, depart from it,
then bring a recognizable version of it back near the end - a bookend
structure. Suits a piece that needs to feel "complete" rather than
open-ended.

Prompt guidance: name the motif in words and ask for its return
explicitly ("opens with a short rising three-note phrase on piano,
develops through the middle, the same rising phrase returns near the
end"). A prompted model has no guaranteed exact-motif recall; a literal,
verifiable melodic return is not promised the way an authored `create`
score can guarantee it.

QA cue: without note-level ground truth, treat motif return as
requested-but-perceptually-unverified unless a chroma/beat estimate from
analyze-music gives supporting (still uncertain) evidence; never claim a
verified motif return from sampled listening alone.
