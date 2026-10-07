# Hands commissioning

How the Assistant commissions the media hands, when it consults Creator, and
which references each side owns. Part of the Hermes design docs — index:
[`PROFILES.md`](../PROFILES.md).

## Who does what

- **Assistant** — the only client of the hands. It owns the user's goal,
  context and decisions, the durable location, grants and consent, filling and
  sending each hands form, relaying proposals and approvals, sequencing
  dependent units, running independent ones in parallel, and delivery. It adds
  no aesthetic gate and repeats no producer QA.
- **Creator** — the creative advisor: directions and located revisions, never
  production or commissioning ([profiles/creator.md](./profiles/creator.md)).
- **Hands** — image-creator, video-creator and audio-creator: one form per leaf,
  its procedure, storyboards and proposals, self-checks and the spend tally
  ([hands/overview.md](./hands/overview.md)).

A request the user's words already settle goes straight from the Assistant to
the hands. Creator is consulted when a required field is open, a look or a
reference needs interpreting, or the user's feedback on a storyboard, draft or
delivery is too vague to map onto a form. A look is settled only when named
concretely (a leaf style or option, a reference, colours, typefaces or motifs);
a mood given as an adjective or two is open, because in the advisor study the
run that commissioned straight from 「あたたかみのある感じで」 lost its case. The
user picks among Creator's directions or changes; the Assistant records that
human decision separately from Creator's suggestion and sends the picked draft
handoff.

A hands `Q<n>:` that the user can answer literally is filled by the Assistant
from the user's words. One that needs interpretation (which field "brighter"
changes, for example) goes to Creator first, so the user chooses between
concrete options instead of answering a field name.

## References each side owns

Every served hands subject has exactly one reference on each side, plain
references rather than skills, landing together with their hands family and
never as placeholder stubs:

| Owner     | Path                                                         | Says                                                                                                                                                                                             |
| --------- | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Assistant | `execute-assistant-creative/references/<subject>.md` | transport (`inquiry` or `work`), the subject's round-trip (for example storyboard, approval, render), how each approval is relayed, the units it depends on, subject-specific budget and consent |
| Creator   | `creator-pipeline/references/<hands>/<subject>.md`           | what the leaf can express: range, options, boundary with neighbouring leaves, where its examples live                                                                                            |

The hands leaf's front matter remains the only form; neither side copies forms,
option lists, provider defaults, size tables or approval hashes. The Assistant
reads leaves through its `skills.external_dirs` entries for the three hands
pipelines and reads a leaf's form with `skill_view`, never running its
`<Procedure>`. The Plan entry's outcome Client guides
(`plan-assistant-creative/references/<deliverable>.md`) stay deliverable-first:
a new hands subject does not oblige a guide, and a missing guide never
establishes an unavailable capability.

`validate_creator_references` collects subjects from the actual hands leaves and
requires exact per-hands coverage on both sides. It rejects missing, orphaned or
nested references, broken or escaping local links, and missing kernel or
recovery dependencies.

## Approvals, budget and consent

- A Budget line is not proposal approval, and proposal approval is not an
  expanded spend. Grants only expand on request with a cost estimate.
- Approvals are relayed in the same `target` and `conversation_id`, quoting the
  user's words and the exact proposal or preview path and SHA-256 the hands
  returned. The Assistant never computes, refreshes or invents a hash.
- Approvals and choices are the user's only. An unreachable user leaves the
  gate open: the Assistant stops and reports, and the hands treat an approval
  the Assistant or Creator gave on its own judgement as none (the advisor study
  caught both arms approving storyboards for a client they could not reach).
- Asset and operation upload consent is relayed explicitly. A local path, a
  public URL, a direction choice or "use this" is not consent; reuse rights,
  model upload, remote analysis and publication are separate permissions.
  Research material stays inspiration, never a production input.
- Failure and unknown flags survive every handoff. A viewable preview may be
  shown early with failures disclosed; delivery is not acceptance.

## Legacy routes

There is no legacy production route. Of Creator's 19 former technics, five
become hands leaves before the advisor cutover: the SVG diagram, grid-exact
pixel art, official brand-asset sourcing (as an extension of `source-icon`) and
text-free generated illustration on image-creator, and pixel animation on
video-creator. The other fourteen are archived under
`hermes/archive/creator-technic/`, which no profile reads; a request only they
covered returns `no leaf fits` until a leaf exists. The Assistant's legacy Plan
and QA references retire with them. Existing frozen outputs, proposal hashes
and approvals are never rewritten.

## Other producers

Writer's form-based leaves do not by themselves transfer editorial authority;
its released-unit ownership is unchanged. Apply the same ownership-first gate
to later profile migrations: a shared directory shape is not permission to
change who plans, approves, publishes or verifies a result.
