# The motion vocabulary stays rule-free

Status: in force
Owner doc: docs/hands/video.md "Promotion family" (Storyboard vocabulary)

## Decision

The kernel's `references/motion-vocabulary.md` lists names, looks and usual
builds only. Authored leaves name its entries in the storyboard; it adds no
plan field, schema or rule.

## Why

In a blind swap the same storyboard scored the same whether Hermes or OpenCode
built it, so taste is decided in the storyboard, and naming concrete entries
instead of generic "fade" or "card" raised the films' ranking. A rules layer
(numeric defaults, avoid-lists, self-scoring), a static-frame metrics gate and
a cross-family critic were tried in the same study and lowered or did not move
the ratings.

## Do not

- Add numeric defaults, avoid-lists or self-scoring to the vocabulary.
- Add a static-frame metrics gate or a cross-family critic to the authoring
  loop.
