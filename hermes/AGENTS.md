# hermes/ — maintainer rules

Rules for whoever edits this subtree: OpenCode, usually started by the person.
The Assistant may drive it here too (hands-reference upkeep does), but only in a
task worktree (`opencode_session workspace`): the plugin refuses a write run in
the live checkout `~/.config`. Hermes reads `~/.hermes/` (symlinks into this
repo), never `~/.config`, and never loads this file, `README.md` or `docs/`;
a profile sees only its `config.yaml` (`agent.system_prompt`), `SOUL.md` and
skills.

## Where things live

| Content | Home |
|---|---|
| Maintainer rules: what must not break when editing, with a one-line why | this file |
| Entry point, symlinks, layout, commands | [`README.md`](README.md) |
| Mechanics: install, tracking, skills, plugins, services, engines, browser, web search | [`docs/ops/`](docs/ops/) |
| Behavior contracts: topology, each profile, broker, hands, models and auth | [`docs/`](docs/) — index: [`PROFILES.md`](PROFILES.md) |
| Why a design was fixed | [`docs/decisions/`](docs/decisions/) |
| Knowledge a profile needs while working | that profile's skill `references/` (or `~/Workspaces/AGENTS.md` for rules of the Assistant's working area) |

- **One fact, one place.** Change a contract in its owning doc and point to it
  from elsewhere; do not restate it here. A rule belongs here only if editing
  the repo can silently break it.
- **Current state, not history.** No incident narratives, dated verification
  logs, version labels or patch lists in docs — Git history keeps those. Keep
  the rule and one clause of why, so nobody deletes it later as arbitrary. A
  rationale worth keeping becomes a short file in `docs/decisions/`.
- **Runtime knowledge goes where the runtime reads it.** If a profile must know
  something while working, it goes into that profile's skill or references,
  not into these docs (Hermes will not see it here).

## Repository and install

- **Edit here, never `~/.hermes/…`** — those are symlinks back to this repo.
  New files need `../install.sh`; `link()` never overwrites a real file (it
  prints `WARN … not overwriting` and skips). Adopt real files with the steps
  in [docs/ops/tracking.md "Tracking a profile"](docs/ops/tracking.md).
- **No secrets, no `.env`.** Keys live in the macOS Keychain and are injected
  by the `bin/hermes` shim (see the `keychain-secrets` skill). Private data —
  reference voices, the Irodori lexicon, manifest paths, Telegram ids, and the
  names of the user's businesses, clients, messaging accounts, spreadsheets
  and tabs — never enters tracked config, docs, tests, examples or commit and
  PR text; it lives in the private overlay (`~/.config/private`, the
  `private-dotconfig` repo). Use neutral examples (`work`, `personal`,
  `Leads`). The overlay installs local commit and push hooks that refuse
  known names; a refusal is fixed by rewording, never by `--no-verify`. The
  Assistant pipeline is tracked here too: what it must know about a private
  account, business or person goes on the private technic shelf, and the entry
  names that technic only.
- **`config.yaml` is rewritten by Hermes on load.** Match its output format
  (block style, key order) and keep diffs minimal; never hand-reformat or
  alphabetize. Custom top-level keys survive the rewrite.
- **`cron/` is not in this repo.** Never re-link it and never re-add it with
  `skip-worktree` (that hid new jobs and broke branch switches). A missing
  `jobs.json` reads as zero jobs, silently — back it up before touching the
  directory. See [docs/ops/tracking.md "Cron"](docs/ops/tracking.md).
- **Managed skills never get `skip-worktree`**: their changes must stay visible
  in `git status`. Ownership by directory type and the `learned/` → `technic/`
  promotion step: [docs/ops/tracking.md "Tracked vs ignored"](docs/ops/tracking.md).
- **The live checkout is not an isolated test bed.** `~/.hermes` points into
  it, so a branch here is live for anything Hermes reads. Test behavior changes
  in a task worktree with its own overlay links and isolated `HOME`; never
  repoint live links, run candidate install scripts against the live
  configuration, or weaken the live symlink/Git ownership checks to make a
  temporary copy pass.

## Profiles and config

- **`SOUL.md` = persona only** (voice/posture; injected verbatim, headings are
  not parsed). Operating policy lives in `agent.system_prompt`; detailed
  playbooks live in skills. **Never run `/personality`** on a profile — it
  shares the `agent.system_prompt` slot and overwrites the operating contract.
- **Keep `default` neutral** — every `--clone` inherits its `config.yaml`.
  Personas, bots and cron belong in named profiles.
- **`platform_toolsets.<platform>` is the effective tool allowlist.** Keep it
  granular (composite toolsets such as `hermes-cli` / `hermes-telegram` expand
  broadly and strip default-off tools), mirror the role in top-level
  `toolsets`, and list each allowed MCP server explicitly or use `no_mcp`, so
  future servers are not inherited by accident. Design:
  [docs/topology.md "Toolsets"](docs/topology.md).
- **`agent.*` does not inherit from the root profile** — set it per profile
  ([docs/models-auth.md](docs/models-auth.md)).
- **Pinned Telegram topics bind no skill.** `dm_topics` must keep a topic
  literally named `Inbox` (`profile-secrets.sh` derives the cron thread from
  that name; a rename makes every bare `deliver: telegram` job fail closed), and
  no topic may carry `skill:` (validator-enforced). Adding and retiring topics:
  [docs/profiles/assistant.md "Pinned Telegram topics"](docs/profiles/assistant.md).

## Secrets, auth and accounts

- **The secret helper has one shot per profile per process.** Hermes runs
  `secrets.command` once per `HERMES_HOME` and kills it at
  `helper_timeout_seconds`; a Telegram adapter that then finds no token is dead
  until the next gateway restart. So `profile-secrets.sh` fetches each Keychain
  layer exactly once, every config keeps the timeout at 60, and you never add
  a `secret env` call per key. After touching the helper, time it:
  `time sh scripts/profile-secrets.sh creator >/dev/null`.
- **Never put `BU_CDP_URL` / `BU_CDP_WS` in a layer the gateway launcher
  evals** — under multiplex one process-env value pre-empts real-profile
  browsing for every profile, silently ([docs/ops/browser.md](docs/ops/browser.md)).
- **Hermes gets shared secret layers only.** `profile-secrets.sh` and the
  tool-mode `bin/secret-shim` pin `--scope <project>`; without it `secret env`
  adds the scope named after the working directory's repository, and the
  account credentials of the access plugins (kept in the `hermes` keychain
  under their own scopes) would reach every profile. Each scope is named in its
  doc; the shared rules: [docs/access-common.md](docs/access-common.md) "Secret
  scoping".
- **The web3 wallet is the one reader across `secret` projects.** Its signer
  lists every project's names and kinds and reads only items of kind
  `MNEMONIC` / `PRIVATE_KEY`; only names with the word `HERMES` sign or count as
  own, every other wallet is watch-only. Never widen the kinds it reads,
  loosen that name rule, or pass a wallet secret through a process
  environment — a project's own deployer key would start signing. Hermes
  wallets are stored `--no-env` so `secret env` (the helper and the shims)
  never injects them; keep `secret env` honouring that flag. On the
  Assistant the web3 tools' hook blocks terminal `secret get/env/set/rm` and
  `security …-generic-password` for the same reason
  ([docs/web3.md](docs/web3.md)).
- **Rotating an API key needs a gateway restart** — resident sessions keep the
  environment injected at gateway launch.
- **OAuth logins from `default` only** (`hermes model`, no `-p`). Running it in
  a worker writes that profile's `auth.json` and shadows the inherited creds.
- **Anthropic accounts — do not cross the streams.** The Keychain entry
  `Claude Code-credentials` always wins Hermes' resolver and must stay the
  **Hermes** account; OpenCode uses its own login outside the Keychain. A plain
  `claude /login` therefore silently switches Hermes' account. Verification:
  [docs/models-auth.md "Authentication inheritance"](docs/models-auth.md).
- **`provider: anthropic` is the Console API key lane, not the subscription.**
  The subscription is `anthropic-oauth`; a Claude tier on the wrong lane is
  silent (it bills credits, or with no key is skipped). The credit keys' env
  names (`ANTHROPIC_CREDIT_*`) are what the `anthropic` pool reads: renaming one
  empties that entry, in the root `auth.json` and in any per-profile copy.
  Details: [docs/models-auth.md "Console credit lanes"](docs/models-auth.md).
- **A new Claude model is not covered until checked.** Before adopting one,
  read its breaking changes against the mandatory-thinking and
  no-forced-`tool_choice` substring lists (unknown ids default to "disable
  accepted, forcing accepted"). See
  [docs/models-auth.md "Models and fallback chains"](docs/models-auth.md).

## Gateway and A2A

- **One multiplex gateway process** (LaunchAgent `ai.hermes.multiplex`) serves
  every profile directory under `profiles/` — there is no allowlist. A new bot
  = a `hermes-<name>` Keychain layer + `platforms` / `a2a_agents` / toolset
  entries — never a second gateway process (one bot token = one live
  connection). Never run `hermes -p <role> gateway stop` on a specialist that
  must stay reachable: it parks that profile in the shared gateway.
- **A2A ports go in `platforms.a2a.extra.port`, never an `A2A_PORT` env var** —
  it is read raw from the shared process env and would collide across
  profiles. Peer `a2a_agents` entries keep `timeout: 310` (the 120 s caller
  default undercuts the 300 s reply window). Design:
  [docs/topology.md](docs/topology.md).
- **Never run `hermes gateway run` / `restart` in a terminal while the
  LaunchAgent is loaded** — a second poller causes Telegram 409 conflicts.
  Restart with `launchd/gateway-launchctl.sh install` or `/restart`; stop with
  `uninstall`.
- Changes to code that runs inside the gateway (e.g. the Assistant-side
  `specialist_call` kind validation) need a gateway restart; runner, handoff
  and OpenCode-plugin changes apply on the next resident turn.

## Skills

- **Upstream skills attach through `skills.external_dirs` only.** Never run
  `hermes skills install` (it copies into `~/.hermes/skills`, i.e. this repo).
  Wiring pattern and backlog:
  [docs/topology.md "Upstream wiring pattern"](docs/topology.md).
- **External skill stores are never copied or symlinked into a profile.** The
  HyperFrames / `media-use` playbooks live in `~/.agents/skills` (owned by
  `hyperframes skills update`, which a fresh machine needs before creator can
  load them; shared with other harnesses); `video-creator` pins four individual
  technical dirs from it, never the whole store. An installer run reseeds dead
  relative links into `profiles/*/skills/` or the shared `hermes/skills/` — the
  tell is the validator's `local skill root must not contain symlinks` while
  `skills list` still works. **Delete** those links, never repoint them; check
  both roots. No skill root is a link: the Assistant's private technics are read
  through one `external_dirs` entry
  ([docs/ops/skills.md "Skill placement"](docs/ops/skills.md)). Verify with
  `hermes -p creator skills list` — a bare `hyperframes skills` installs rather
  than reports.
- **Writing worker playbooks:** worker terminal approvals cannot prompt, so a
  flagged command just fails. Build playbooks on scripts and wrapper CLIs,
  never inline interpreters or one-liners, and keep `command_allowlist` empty
  (allowing `bash -c *` reopens what the guard catches). What trips the guard:
  [docs/ops/skills.md "Worker terminal approvals"](docs/ops/skills.md).
- **Tool handlers take the model's JSON as one positional dict**
  (`handler(args, **kwargs)`); declaring schema fields as parameters registers
  a tool that fails on every call.
- **A plugin's mechanics skill ships inside the plugin, in a directory named
  `skills/`.** `plugins/<group>/<name>/skills/<skill>/SKILL.md` is registered
  by the plugin's `register_skills` from its `SKILLS` table (skill → profiles)
  as `<plugin>:<skill>`; a bare name does not resolve. It is read-only to
  Hermes (`skill_manage` cannot find it) and the `skill-topology` guard
  protects the path only because a path element is literally `skills` — never
  rename the directory. A profile gets a skill only if its tool can do what the
  skill describes, so a read-only profile never sees write procedures: split a
  skill by capability (`x-twitter` / `x-twitter-drafts`), never by
  `references/` (a loaded skill's references are readable by anyone who loads
  it). Plugin skills are absent from the available-skills index, so the tool
  description or the pipeline must name `skill_view(name="<plugin>:<skill>")`.
  `test_plugin_skills.py` is the audience table; a new skill or a wider
  audience is added there on purpose.
- **Moving a plugin between groups changes its depth, and the code that counts
  it fails silently.** Engines and tests locate `hermes/` (the `local/` venvs,
  `profiles/`, `scripts/`) with `parents[N]`, and tests mock the calls that would
  notice. After a move, re-count every `parents[N]` in the plugin and its tests;
  for a plugin that takes a private overlay symlink, also move the overlay's
  twin in the same paired change and name the link in `.gitignore` (the
  `hermes/plugins/*/` re-include no longer reaches a link one level down). Never
  nest deeper than `<group>/<name>`: Hermes stops reading there. Per-plugin
  settings under `plugins.entries` are keyed `group/name` too (only
  `plugins.enabled` takes the bare name), so a move renames those keys in every
  profile config; `test_plugin_config_keys.py` checks it. A move also changes
  the absolute script path embedded in the installed plists of the `messaging/`
  sync agents: run the launcher's `install` (or `restart`) again, or launchd
  keeps restarting a file that is gone.
- **`plugins/_shared/`, `plugins/messaging/_shared/` and
  `plugins/web3/_shared/` are code, not plugins.** Sibling plugins load their
  modules by path (`human_gate.py`; `archive_check.py`; web3's `access.py`,
  reader and signer, with paths that `scripts/web3.sh` names), so moving or
  renaming one breaks them at import, and a `plugin.yaml` there would make
  Hermes load it as a plugin — never add one. web3's evm-access and
  solana-access are thin entry points over `access.py` and share its one
  in-memory record of approval decisions. Messaging's `unpacked_guard` keys on
  the `.unpacked` folder name that `extract` gives an unpacked archive, and the
  skills the messaging plugins ship name it too: rename it everywhere or the
  guard stops matching without a failure. Keep each sender's own file rules
  passed in rather than copied there ([docs/signal-access.md](docs/signal-access.md),
  [docs/web3.md](docs/web3.md)).

## Hands, commissioning and Creator

Contract: [docs/hands/overview.md](docs/hands/overview.md),
[docs/broker.md](docs/broker.md) and
[docs/profiles/creator.md](docs/profiles/creator.md). When editing:

- A hands skill is a `<hands>-pipeline/<verb>/<subject>/SKILL.md` leaf with one
  form — never a technic, a generated index, `menu.yaml`, a preset layer or
  cross-media Styles (those earlier shapes decided nothing or governed
  everything). A subject must be unique across all hands, because the Assistant
  and Creator read them through one `external_dirs` list; the validator enforces
  the shape.
- Each served subject has one Assistant commissioning reference and one Creator
  capability reference; both mirror subjects, not forms, and land with their
  hands family, never as placeholder stubs.
- Creator stays an advisor: never give it a generation toolset, a hands target,
  or a bot. New creative capability is a hands leaf, never a Creator technic.
- An execution-environment trap goes into the Procedure of the leaf that hits
  it, not into a shared rule.
- Tests that read the design text: `test_ad_routing.py` and
  `test_audio_creator_routing.py` read `docs/`; after media-craft changes also
  run `test_media_craft_routing.py` with the hands/entry tests.

## Media and engines

- **`auxiliary.vision` stays `auto`** — pinning it to a video-capable model
  disables the main model's native image vision; video analysis runs through
  the `video-analyze-mimo` override instead
  ([docs/ops/plugins.md](docs/ops/plugins.md)).
- **Native vision shows the model only the newest 3 tool images per request;**
  older ones read "Image loaded" with nothing visible, and models re-request in
  a loop. The `vision-window` plugin (Creator family) fixes this through
  `transform_tool_result` — do not solve it with a hermes-agent patch
  ([docs/hands/overview.md "Vision window"](docs/hands/overview.md)).
- **TTS routes by language through the fallback chain; do not add a router.**
  The explicit character-voice path is the opposite contract: it must never
  read `tts.fallback.chain`, never retry on another engine, and never drop a
  style control silently. Do not weaken the shared TTS text cleaner — the
  character path works around it on purpose. Contract:
  [docs/hands/audio.md "Speech family"](docs/hands/audio.md); plumbing:
  [docs/ops/tts-engines.md "Local TTS engines"](docs/ops/tts-engines.md).
- Engine pins stay hash-locked in `engines/`; private voice/lexicon paths go
  through the launchers' `register*` commands, never into tracked files.

## Browser and web search

- **Browser:** read [docs/ops/browser.md](docs/ops/browser.md) before touching
  browser config. Invariants: one dedicated Brave profile per consenting Hermes
  profile, never shared (Google rotates session cookies and signs out every
  other holder); never edit the cloned bundle (it breaks the signature and
  cookie decryption); never copy IndexedDB between profiles.
- **Web search:** paid backends are pinned per profile with
  `web.provider_tier`; editing `search_backend` alone is not enough (a present
  key makes auto bill the paid path), and an unknown backend name silently
  resolves to `firecrawl`. How to verify:
  [docs/ops/web-search.md](docs/ops/web-search.md).

## OpenCode integration

Contract: [docs/opencode.md](docs/opencode.md). When editing
`plugins/orchestration/opencode`, keep these (each fails silently otherwise):

- **No run record.** The owner binding lives in the session's `metadata.hermes`;
  a run's state is read from the service (the turn's `idle` message carries its
  outcome). A state file, watcher or stored PID would become a second source of
  truth that disagrees with the service. The per-worktree lock only serializes
  starts. No deadline is enforced on purpose (a run outlives Hermes).
- **Roles are configuration, not code.** Names, agents, policies and models come
  from `opencode.roles` (`DEFAULT_ROLES` is only the fallback); code keys on the
  policy (`read-only` / `write`), never on a role or agent name.
- **The session ruleset owns each run's constraints.** Subagent sessions copy it,
  and the caller can approve a request only `once` — a session-wide allow would
  reopen what an explore or reviewer subagent denies itself. The one exception
  is a `write` run's `edit *` in its worktree, ordered before every edit deny so
  the config, skill and secret denies still win (a test enforces both). Anything
  the caller must never approve is a `deny`, not an `ask`.
- **Reach OpenCode only through `api.py`** (`opencode api`, output to files,
  minimal environment): a piped reply is cut off at a buffer boundary with exit
  status zero, `--param` silently drops query parameters (queries go in the
  path), and a service the command starts keeps its environment for every
  session — never widen `ENV_NAMES` to a secret. Prefer stable routes over
  `/api/experimental/*` (instructions entries are the one exception, with a
  prompt fallback).
- Keep caller/worktree/branch binding, completion from the turn's own idle
  marker (not a session-level outcome or an exit code), and no automatic replay
  after `unknown`.
- **Deadlines nest; keep them ordered.** `TURN_TIMEOUT` is identical in
  `profiles/assistant/scripts/resident-session.sh` and
  `plugins/orchestration/specialist-call`; every caller's tool deadline stays
  above it plus cleanup (or, for the Assistant, above `specialist_call.wait_timeout`
  plus 30 s) — otherwise a blocking `specialist_call` silently degrades to
  polling — and plugin send deadlines stay under the Assistant's, or the generic
  deadline cuts them off before their own error. Values and why:
  [docs/profiles/specialist-calls.md "Completion and deadlines"](docs/profiles/specialist-calls.md).
- **Live callers bind to their conversation route, not the session id.**
  `_topic_owner` hashes profile home, platform, chat, thread, sender and session
  key; dropping a field merges topics or senders, adding the session id loses
  runs on `/new`.
- **`cancelled` is the only early stop a specialist conversation resumes
  from**, and only because the owning runner confirmed its group gone; never
  make `unknown`/`interrupted` resumable or let anything but that runner signal
  the group ([docs/profiles/specialist-calls.md](docs/profiles/specialist-calls.md)).
- **The caller's own model is refused unless the role allows it
  (`caller_model: allow`).** The `post_api_request` hook records the model the
  caller last answered with, and `models.model_key` folds speed tiers and
  snapshots: keep both, or a fallback or `-fast` alias slips past a role that
  refuses ([docs/opencode.md "Models"](docs/opencode.md)).
- **A write run never edits the live checkout.** `policy.branch` refuses it in
  `~/.config` (`policy.live_checkout`), because `~/.hermes` links into it; the
  Assistant plans there read-only and builds in the worktree `workspace`
  creates. Cutover stays a person's decision ("Candidates and cutover").
- **A session may only work in the repository it was bound to.** An agent can
  move any session with `session_move` (no permission asked), so
  `metadata.hermes.repo` and the per-turn check in `_prepare` detect a stray
  session at its next turn; the only sanctioned move is
  `opencode_session workspace`. Never ask an OpenCode run to move itself, keep
  the service's own worktree route unused (it can only make a detached HEAD), and
  keep `workspace.py`'s git calls hook-free with the minimal environment: a
  tracked `core.hooksPath` is repository-controlled code and this process holds
  the gateway's secrets.

## Candidates and cutover

Rollout contract: [docs/topology.md "Candidate rollout and cutover"](docs/topology.md).

- Pair public and private changes for rollout and rollback; validate the
  paired candidate structurally, then check real Git ownership and
  fresh-session discovery before an approved cutover.
- Run `scripts/verify-work-continuity.py --runtime <hermes-agent-checkout>
  --private <paired-private-checkout>` before a cutover and after every
  upstream update. It installs, restarts and migrates nothing.
- Task artifacts, grants and approvals are never migrated or rewritten on
  rollout. Commits, pushes and gateway restarts need explicit approval.

## After `hermes update`

1. `./scripts/check-local-patches.sh` — every local `fix/*` branch in the
   hermes-agent checkout must still be merged into `local`, and the
   case-collision twin must keep `skip-worktree` (without it every rebase and
   merge refuses to start; `git checkout --` only flips which twin is dirty). A
   missing patch fails silently at runtime, e.g. browser isolation.
2. `./scripts/validate-profile-skills.py --all`; delete any seeded category
   directory under `profiles/*/skills/` other than `<profile>-pipeline`,
   `technic` or `learned` (upstream seeds past `.no-bundled-skills`). A lone
   seeded `DESCRIPTION.md` is harmless and comes back each launch.
3. `scripts/verify-work-continuity.py` (above) and the test suite.
4. Re-check behavior rather than a branch: a browser attach daemon that
   outlived its clone keeps a dead port (unpatched upstream;
   [docs/ops/browser.md](docs/ops/browser.md)), and whether shutdown /
   `/restart` notifications reach secondary profiles.

## Maintenance loop

Commands: [README "Commands"](README.md#commands).

- Validator and tests as in the README. The Hermes test interpreter is required
  (PM owns it; there is no venv path) and `--import-mode=importlib` is not
  optional (plugin suites share the `tests/test_plugin.py` basename in
  hyphenated, non-importable dirs). Private overlay tests likewise run with
  `hermes-python --test -m unittest …`.
- `../install.sh` after adding files; `hermes update` to update (not
  `setup.sh`); `hermes doctor` for providers and model tiers.
- **`hermes -z` is YOLO.** It sets `HERMES_YOLO_MODE=1` before the agent
  runs, so Hermes approves every plugin approval card unasked; `--yolo` and
  `approvals.mode: off` do the same. Use it to check reads. A write is tried
  only in a gateway chat, where a person answers its card. A plugin that
  escalates writes to a card must itself refuse where no person can answer:
  through `plugins/_shared/human_gate.py` (or web3's `_no_human`), or, for
  substack- and youtube-access, their own `_unattended()` and
  `is_approval_bypass_active()` checks. A new plugin that returns an `approve`
  directive needs one of these.

## Commits

Conventional Commits with the `(hermes)` scope: `feat(hermes): …`,
`chore(hermes): …`, `docs(hermes): …`, `refactor(hermes): …`.
