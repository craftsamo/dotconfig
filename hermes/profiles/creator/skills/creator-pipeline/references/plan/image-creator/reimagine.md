# Plan — image-creator: reimagine

Read [common plan](../index.md) first.

## Budget

A metered leaf takes a `budget:` line; absent, the leaf's default applies —
for reimagine: 2 per style + 1 corrective per style. For another subject,
read that subject's Plan reference and hands leaf for its allowance.

## Reimagine: the photo as the edit input

`generate-reimagine` sends the uploaded photo to the image backend as the
edit input, whatever it shows - a person, a pet, an object, a place. [Common
plan](../index.md) "Reference-upload consent" covers a real person's photo;
here the same-round human consent and explicit assistant relay of the user's
asset-and-upload authorization apply
to any of those subjects, not only a person, because every reimagine photo
is an edit input the model receives, never incidental context. Several
styles on one photo are ONE form (`style: comic-book, 80s-anime`), not one
per style: the hands write the identity lock once and every style is judged
against the same note. `keep` stays at its default unless the client
asked for a new scene ("put me in a 70s New York street" → `keep:
identity`; "make this photo a comic" → the default).
