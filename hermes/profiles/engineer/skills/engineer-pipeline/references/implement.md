# Implement mode — deliver a code change by driving OpenCode

Loaded when the brief's deliverable is a **code change** (or the repo that
will hold one — see <BootstrapBranch>). This file is the flow skeleton; the
mechanics live in three engines, loaded at the stage that needs them:

- `references/opencode.md` — driving OpenCode: model routing, the unit
  cycle, permission/question bridges, course correction. Load before the
  first run.
- `references/verify.md` — the V-checks + per-intent profiles. Load before
  accepting any unit/result.
- `references/delivery.md` — GitHub flow, PR upkeep, the evidence-backed
  report. Load when work leaves the worktree.

Implement consumes **released units**, one per turn (core <Runtimes>
pacing): a purpose (`Issue: #n` — the Issue text is the spec), a Wave
(`Base session: <id>` + the Wave to implement), or a whole small job
released as one unit. The assistant owns the decomposition; never
double-plan. Two finding kinds go back instead of being absorbed:
work bigger than its released unit is a **granularity finding**, and a
spec that fails to determine the unit — missing done criteria, an
undecided material choice the Issue/outline should have fixed — is a
**spec-gap finding**. Checkpoint, report, let the assistant re-plan or
re-spec; deciding it locally is the assistant's job outsourced, never
initiative. Session context is
NOT the durable layer — the Issue/outline text, git history, and your
session reports are.

## IntentDispatch

The core file's <IntentTriage> classified the job (`feature` / `bugfix` /
`refactor` / `rebuild` / `perf` / `deps`). The intent shapes three things:

1. **The first move** (from the triage table) — e.g. bugfix reproduces
   BEFORE any OpenCode build run; perf measures the baseline; refactor
   confirms the test safety net is green; rebuild confirms the evacuation.
   Do it, record the evidence in your report — it is the before-side of
   the intent gate in `references/verify.md`.
2. **What OpenCode loads** — this machine's OpenCode owns a matching
   approach skill for most intents; the catalog lives in `opencode-env`
   <IntentCatalog>. Name it in the dispatch prompt ("load and follow
   `approach-refactor`") so OpenCode's own discipline kicks in — prompt
   intent, don't paste procedure.
3. **The verification profile** — `references/verify.md` intent rows are the
   acceptance floor for every unit close and the final handback.

The brief may carry `Intent:` explicitly; absent → infer per the core
table and note the inferred token in your first report.

## RiskDiscipline

Risk shapes rigor **inside** the cycle — never planning ownership (the
assistant decomposes; you consume released units at every risk level):

| Risk | Examples | Discipline |
| --- | --- | --- |
| Low | mechanical fix, docs, small test, cleanup within scope | the cycle in one session; confirm gate still mandatory |
| Medium | standard feature/refactor inside granted scope | full cycle + a review primary (<InspectionPrimaries>) before handback |
| High | architecture change, public API/schema change, dependency change, anything near the grant's edge | full cycle; confirmed phases that touch the grant's edge go through checkpoint-then-block BEFORE the build fork; review primary mandatory |

## Steps

0. **Know the executor.** If the goal leans on a capability you have not
   confirmed here (a technique OpenCode should own as a skill, a subagent, a
   tool, a model), load `opencode-env` and check — including <IntentCatalog>
   for the intent's approach skill and <InjectedLayer> for what every
   session already knows. Knowing that layer is a **precondition for
   writing dispatch prompts** (opencode.md <PromptContract>): you cannot
   write the delta without knowing the baseline. Environment symptoms
   during the build (missing keys, a launcher that "loses" its env,
   credential errors) are `machine-env`'s subject, not the model's.
1. **First move** per <IntentDispatch>; record its evidence.
2. **Model + cycle setup** — load `references/opencode.md`; route
   provider/model (<ModelRouting>).
3. **Run the unit cycle** for the released unit per opencode.md
   <UnitCycle>: ground (base fork / Issue plan run / the brief) →
   decompose → confirm (**the GO gate** — a `<unit ref> phases confirmed`
   line must be reported before the build fork; a detailed approved plan
   or Issue goes through the derive variant, <DetailedPlanRule>, never
   straight to build) → implement (build fork under <PermissionBridge>) →
   verify → commit → report, then stop at the unit boundary (batch only
   under an explicit grant). Read every run's output per <QuestionBridge>;
   interpose <InspectionPrimaries> per <RiskDiscipline>; recover per
   <CourseCorrect>.
4. **Verify per unit** — load `references/verify.md`; run the intent
   profile's REQ checks + the intent gate. Findings loop back into the
   unit's build fork; failures never hand back silently.
5. **Deliver** — load `references/delivery.md`: commits/PR flow via
   OpenCode under the Authority grant, audit the results (verify.md V6),
   assemble the evidence-backed report, complete.

Any material decision outside the grant at any step →
<CheckpointThenBlock>. `Review: required` in the body → core <ReviewGate>
before completion.

## BootstrapBranch — no repo yet

When the brief says to establish a repo that does not exist (the assistant
decided the path after an assess bootstrap signal), this is the one **write
path that does not use OpenCode** — there is no codebase for it to operate
on. Work with `git` / `gh` / the scaffolder directly. Establish the
skeleton + initial commit; never decompose units or build features in the
same job.

**Authority — B1/B2, not A1-3** (there is no worktree yet):

| Preset | Grants |
| --- | --- |
| `B1` (default) | create the repo **locally only** — clone / scaffold / `git init` at the target ghq path (the chosen starter's own dependency install included), initial commit. No remote. |
| `B2` | B1 + `gh repo create` (the named repo + visibility from the body) + push the initial commit. |

Inputs the brief must supply (ask if missing): **target** (`owner`/`repo`
+ absolute ghq path — the durable home; always operate on the absolute
path: `git -C <path>`, `<scaffolder> <path>`), **path**
(`clone <url|owner/repo>` / `starter <scaffolder + source>` /
`greenfield`), **visibility** (B2 only).

Procedure:

1. **Guard.** The target must not already contain a repo (`git -C <path>
   rev-parse` fails / dir absent or empty). Non-empty target → ask, never
   overwrite.
2. **Establish** per the chosen path: `gh repo clone` / the named scaffolder
   (`npx degit`, `create-next-app`, `cargo new`, `uv init`, …; `git init` if
   it didn't) / `git init <path>` + the minimal asked-for skeleton. `gh repo
   create --template` is a **B2** action. When the path names a starter
   from the local family, load the `starter-catalog` technic skill and
   follow its <IntroductionPaths>: clone the named source, point `origin`
   at the new repo (B2), wire the `upstream` remote to the parent —
   rebranding the identity surface is NOT bootstrap (it is the follow-up
   implement task's first unit).
3. **Initial commit** (`git -C <path> add -A && git -C <path> commit -m
   "chore: initial commit"`) unless clone history exists.
4. **Remote (B2 only)** — `gh repo create <owner>/<repo> --<visibility>
   --source <path> --remote origin --push`.
5. **Report** the handoff facts: ghq path, path taken + initial sha, remote
   url (or "none — B1"), stack, and the suggested `pj repo-set` /
   `pj link-repo` line. **Never run pj yourself** — registration is the
   assistant's post-bootstrap step.

Bootstrap pitfalls: opening OpenCode (no codebase yet); remote/push at B1;
overwriting a non-empty target; speculative scaffolding beyond the asked
skeleton; shopping for a starter (the orchestrator chose the path —
execute it or ask).

## Pitfalls

- Skipping the intent's first move (building before reproducing / measuring
  / confirming the safety net) — the after-side gate in verify.md then has
  no before-side to compare against.
- Treating the intent label as decoration — it decides the OpenCode approach
  skill and the verification floor; an inferred intent that feels wrong
  mid-job is a finding to report (and a `Q<n>` if it changes scope).
- Working from this skeleton without loading the engine the stage needs —
  the bridges, V-checks, and GitHub flow live there, not here.
- Building a unit whose decompose surfaced an out-of-grant need (dependency,
  push, architecture change) without a block round-trip.
- Writing a unit decomposition yourself — for work that already has an
  Issue (the Issue is the spec; double-planning drifts it) or for a job
  that turned out multi-unit (a granularity finding, not your outline).
- Filling a spec gap with a plausible local default — an undecided
  material choice returns as a spec-gap finding, whatever the schedule
  pressure.
- Running past the released unit — the next Wave/Issue needs a release or
  an explicit batch grant.
- Insurance-prose prompts written without knowing the injected layer —
  restating agent permissions, skill content, or the repo's own check
  commands (opencode.md <PromptContract>) instead of prompting the delta.
- Trusting a completion message without the verify.md pass — the classic.

## Verification

- The intent was named (body or inferred + noted); its first move ran with
  recorded evidence; the verify.md intent profile passed at every unit
  close and at handback.
- Every unit's build fork was preceded by its reported `<unit ref> phases
  confirmed` gate artifact (opencode.md <UnitCycle> confirm step).
- Work consumed released units only — no self-generated decomposition;
  granularity findings were reported, never silently absorbed; work
  stopped at each unit boundary absent a batch grant.
- Engines were loaded at their stages (opencode.md before the first run,
  verify.md before acceptance, delivery.md before remote actions).
- Bootstrap branch: the guard ran; remote/push only under B2; pj untouched;
  no OpenCode invocation.
- Every remote/destructive action maps to a grant or a block round-trip.
