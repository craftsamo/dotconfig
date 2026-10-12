# New product - Client guide

For a new product, and for a feature of an existing one that adds screens or
stored data. The user must be able to say what people will do with it before
anyone fixes how it is built, so the stages run in this order and each ends
with the user's choice. A stage the user already settled (they handed over a
mock, a spec, a schema) is recorded in the decision log and skipped.

| Stage | OpenCode | The user |
| --- | --- | --- |
| 1. Purpose and use | nothing yet, or a short `plan` turn on an existing repository | Who uses it, for what, a first real use; in their words |
| 2. Capabilities, screens, data | `opencode_run_design` writes HTML mocks and diagrams into the job directory | Opens the HTML, corrects it, answers what only they can decide |
| 3. Roadmap | `opencode_run_plan`: stack, hosting and the Phases (each one PR or stack layer) | Approves the order and content of the Phases |
| 4. Each Phase | a fork of the plan trunk plans that Phase's steps, then builds it | Approves the Phase, then tries what it delivers |

## 1. Purpose and use

Ask what the user wants to stop doing or start doing, who else touches it
(clients, other people, other agents) and the first real occasion they will use
it for. Write their words into the decision log. Your own opinions about the
product (what to leave out, what matters) go in as your proposals and are put
to the user as such; never as their decision because they did not object.

## 2. Capabilities, screens and data

Run `opencode_run_design` on the repository (or a starter the user already
chose) with the user's words, the decision log and a `design/` subdirectory of
the job directory as `output_dir`; without a `design` tool, a `build` run on a
task worktree with the same `output_dir` and an approval for mocks only does
the same. It writes:

- `index.html`: who uses the product, what each of them can do, the screen map
  and the main flows.
- one page per screen, in its main states.
- `data.html`: what is stored, who can see or change it, and the choices that
  are hard to undo later (ownership, versions, what a shared link points to).

Send the user `index.html` (and the screen pages it links to) as files; they
open in the chat. Say in a few lines what the mock proposes and which parts are
proposals, then ask in one round what only they can decide: missing or unwanted
capabilities, the look, the hard-to-undo data choices. Revise on the same design
session until the user says it describes what they want; record what they
chose. Technical structure is not shown or asked here.

## 3. Roadmap

On a plan session (a new one, pointed at the design directory and the log),
ask OpenCode for the technical plan and the Phases: each Phase one PR or stack
layer, with what people can do when it lands and how the user will try it, the
first one letting the user try the main flow end to end. Show the Phases whole
and get the user's approval of the roadmap; hosting, paid services and the
first deployment are separate approvals.

## 4. Each Phase

Follow the Phases section of the entry: a fork of the trunk per Phase, its
steps shown and approved before its build, progress reported per step, and
its PR delivered with how to try it, together with the next Phase's plan for
approval.

Acceptance: each Phase's PR delivers what its plan said people can do, shown
the way the user will try it, and its screens match the approved mock or the
difference is explained by a later decision.
