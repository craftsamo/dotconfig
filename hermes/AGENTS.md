# hermes/ — maintainer rules

Rules for whoever edits this subtree: OpenCode, or a Hermes profile doing
repository upkeep (Engineer through OpenCode, the Assistant's Admin topic).
`../install.sh` symlinks these files into `~/.hermes/`; Hermes reads
`~/.hermes/`, never `~/.config`, and never loads this file, `README.md` or
`docs/` at runtime. What a profile actually sees at runtime is its
`config.yaml` (`agent.system_prompt`), its `SOUL.md` and its skills.

## Where things live

| Content | Home |
|---|---|
| Maintainer rules: what must not break when editing, with a one-line why | this file |
| Mechanics: install, symlinks, layout, tracking, engines, browser and web-search plumbing, commands | [`README.md`](README.md) |
| Behavior contracts: topology, each profile, broker, hands, models and auth | [`docs/`](docs/) — index: [`PROFILES.md`](PROFILES.md) |
| Knowledge a profile needs while working | that profile's skill `references/` (or `~/Workspaces/AGENTS.md` for rules of the Assistant's working area) |

- **One fact, one place.** Change a contract in its owning doc and point to it
  from elsewhere; do not restate it here. A rule belongs here only if editing
  the repo can silently break it.
- **Current state, not history.** No incident narratives, dated verification
  logs or patch lists in docs — Git history keeps those. Keep the rule and one
  clause of why, so nobody deletes it later as arbitrary.
- **Runtime knowledge goes where the runtime reads it.** If a profile must know
  something while working, it goes into that profile's skill or references,
  not into these docs (Hermes will not see it here).

## Repository and install

- **Edit here, never `~/.hermes/…`** — those are symlinks back to this repo.
  New files need `../install.sh`; `link()` never overwrites a real file (it
  prints `WARN … not overwriting` and skips). Adopt real files with the steps
  in [README "Tracking a profile"](README.md#tracking-a-profile).
- **No secrets, no `.env`.** Keys live in the macOS Keychain and are injected
  by the `bin/hermes` shim (see the `keychain-secrets` skill). Private data —
  reference voices, the Irodori lexicon, manifest paths, Telegram ids — never
  enters tracked config or docs; it lives in the private overlay
  (`~/.config/private`, the `private-dotconfig` repo).
- **`config.yaml` is rewritten by Hermes on load.** Match its output format
  (block style, key order) and keep diffs minimal; never hand-reformat or
  alphabetize. Custom top-level keys survive the rewrite.
- **`cron/` is not in this repo.** Never re-link it and never re-add it with
  `skip-worktree` (that hid new jobs and broke branch switches). A missing
  `jobs.json` reads as zero jobs, silently — back it up before touching the
  directory. See [README "Cron"](README.md#cron).
- **Managed skills never get `skip-worktree`**: their changes must stay visible
  in `git status`. Ownership by directory type and the `learned/` → `technic/`
  promotion step: [README "Tracked vs ignored"](README.md#tracked-vs-ignored).
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
- **Pinned Telegram topics bind no skill.** The Assistant's `dm_topics` must
  keep a topic literally named `Inbox` (`profile-secrets.sh` derives the cron
  thread from that name; renaming it makes every bare `deliver: telegram` job
  fail closed) and no topic may carry `skill:` (validator-enforced). Adding
  one: a `dm_topics` entry without `thread_id` → gateway restart (writes the id
  back into the private repo) → key its `channel_prompts` entry → `/restart`.
  Hermes never deletes a Telegram topic; close retired ones by hand. See
  [docs/profiles/assistant.md](docs/profiles/assistant.md).

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
  browsing for every profile, silently ([README "Browser"](README.md#browser)).
- **Rotating an API key needs a gateway restart** — resident sessions keep the
  environment injected at gateway launch.
- **OAuth logins from `default` only** (`hermes model`, no `-p`). Running it in
  a worker writes that profile's `auth.json` and shadows the inherited creds.
- **Anthropic accounts — do not cross the streams.** The default Keychain entry
  `Claude Code-credentials` always wins Hermes' resolver and must stay logged
  into the **Hermes** account; OpenCode runs on the sub account through a
  suffixed entry (`claude-sub`). A plain `claude /login` therefore changes
  Hermes' account — afterwards verify with
  `security find-generic-password -s "Claude Code-credentials"` plus the OAuth
  profile endpoint. Details: [docs/models-auth.md](docs/models-auth.md).
- **A new Claude model is not covered until checked.** Before adopting one,
  read its breaking changes against the mandatory-thinking and
  no-forced-`tool_choice` substring lists (unknown ids default to "disable
  accepted, forcing accepted"). See
  [docs/models-auth.md "Models and fallback chains"](docs/models-auth.md).

## Gateway and A2A

- **One multiplex gateway process** hosts every bot and A2A endpoint. A new bot
  = a `hermes-<name>` Keychain layer + `platforms` / `a2a_agents` / toolset
  entries + the multiplex allowlist — never a second gateway process (one bot
  token = one live connection).
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
  load them; shared with other harnesses); `video-creator`
  pins four individual technical dirs from it, never the whole store. An
  installer run reseeds dead relative links into `profiles/*/skills/` or the
  shared `hermes/skills/` — the tell is the validator's `local skill root must
  not contain symlinks` while `skills list` still works. **Delete** those
  links, never repoint them; check both roots. The one intentional link is the
  Assistant's private-overlay `assistant-pipeline`. Verify with
  `hermes -p creator skills list` — a bare `hyperframes skills` installs rather
  than reports.
- **Writing worker playbooks:** worker terminal approvals cannot prompt, so a
  flagged command just fails. Build playbooks on scripts and wrapper CLIs,
  never inline interpreters or one-liners, and keep `command_allowlist` empty
  (allowing `bash -c *` reopens what the guard catches). What trips the guard:
  [README "Worker terminal approvals"](README.md#worker-terminal-approvals).
- **Tool handlers take the model's JSON as one positional dict**
  (`handler(args, **kwargs)`); declaring schema fields as parameters registers
  a tool that fails on every call.

## Creator hands and broker

Contract: [docs/hands/overview.md](docs/hands/overview.md) and
[docs/broker.md](docs/broker.md). When editing:

- A hands skill is a `<hands>-pipeline/<verb>/<subject>/SKILL.md` leaf with one
  form — never a technic, a generated index, `menu.yaml`, a preset layer or
  cross-media Styles (earlier shapes with those decided nothing or governed
  everything). A subject must be unique across all hands, because Creator reads
  them through one `external_dirs` list; the validator enforces the shape.
- Creator's broker references mirror subjects, not forms: new subject
  references land with their hands family, never as placeholder stubs.
- An execution-environment trap goes into the Procedure of the leaf that hits
  it, not into a shared rule.
- Legacy capability retirement stays family-by-family, after caller coverage
  and a both-client soak — a new leaf alone does not retire anything.
- Tests that read the design text: `test_ad_routing.py` and
  `test_audio_creator_routing.py` read `docs/`; after media-craft changes also
  run `test_media_craft_routing.py` with the hands/entry tests.

## Media and engines

- **`auxiliary.vision` stays `auto`** — pinning it to a video-capable model
  disables the main model's native image vision; video analysis runs through
  the `video-analyze-mimo` override instead ([README "Plugins"](README.md#plugins)).
- **TTS routes by language through the fallback chain; do not add a router.**
  The explicit character-voice path is the opposite contract: it must never
  read `tts.fallback.chain`, never retry on another engine, and never drop a
  style control silently. Do not weaken the shared TTS text cleaner — the
  character path works around it on purpose. Contract:
  [docs/hands/audio.md "Speech family"](docs/hands/audio.md); plumbing:
  [README "Local TTS engines"](README.md#local-tts-engines).
- Engine pins stay hash-locked in `engines/`; private voice/lexicon paths go
  through the launchers' `register*` commands, never into tracked files.

## Browser and web search

- **Browser:** read [README "Browser"](README.md#browser) before touching
  browser config. Invariants: one dedicated Brave profile per consenting Hermes
  profile, never shared (Google rotates session cookies and signs out every
  other holder); never edit the cloned bundle (it breaks the signature and
  cookie decryption); never copy IndexedDB between profiles.
- **Web search:** paid backends are pinned per profile with
  `web.provider_tier`; editing `search_backend` alone is not enough (a present
  key makes auto bill the paid path), and a backend name that no longer exists
  silently resolves to `firecrawl`. Current split and how to verify:
  [README "Web search backends"](README.md#web-search-backends).

## OpenCode integration

Contract: [docs/profiles/engineer.md "OpenCode runtime"](docs/profiles/engineer.md).
When editing `plugins/opencode` or `~/.config/opencode/agent/hermes-*.md`:

- **The plugin is the only owner of the hidden primaries' permissions.** The
  agent files carry no `permission:` block (a plugin test fails if one
  reappears) — OpenCode deep-merges both, so two owners means neither is the
  truth. On `opencode run`, `ask` is never a question (rejected without
  `--auto`, approved with it); write `allow` or `deny`.
- Role → agent mapping lives only in `OPENCODE_AGENTS`; renaming an installed
  agent touches that map and nothing else.
- Keep caller/worktree/branch binding, JSON error handling (exit zero is not
  success), finite deadlines and no automatic replay after uncertain effects.
- Keep `TURN_TIMEOUT` identical in `profiles/assistant/scripts/resident-session.sh`
  and `plugins/specialist-call`. Engineer's tool deadline
  (`timeouts.tools.sequential_call` / `concurrent_batch`) must stay above
  `opencode_cli.timeout`, or long calls turn into polling loops; verify with
  `HERMES_HOME=~/.hermes/profiles/engineer` +
  `agent.tool_executor._resolve_sequential_tool_timeout()`. Likewise `creator`
  and `marketer` keep theirs (5460) above `TURN_TIMEOUT` + cleanup, or a
  blocking CLI `specialist_call` times out at 420 s and polls.
- The Assistant's Admin-topic calls being planned and reviewed by its own
  model is an accepted exception; do not extend it to Engineer, and move the
  reviewer to another model family before moving Engineer off Fable.

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
   merge refuses to start; `git checkout --` only flips which twin is dirty). A missing patch fails silently at runtime, e.g.
   completion notifications for secondary profiles or browser isolation.
2. `./scripts/validate-profile-skills.py --all`; delete any seeded category
   directory under `profiles/*/skills/` other than `<profile>-pipeline`,
   `technic` or `learned` (upstream seeds past `.no-bundled-skills`). A lone
   seeded `DESCRIPTION.md` is harmless and comes back each launch.
3. `scripts/verify-work-continuity.py` (above) and the test suite.
4. Still unpatched upstream, so re-check behavior rather than a branch: a
   browser attach daemon that outlived its clone keeps a dead port
   ([README "Browser"](README.md#browser)), and shutdown / `/restart`
   notifications for secondary profiles are not routed.

## Maintenance loop

Full reference: [README "Commands"](README.md#commands).

- `./scripts/validate-profile-skills.py --all` (`--strict-git` in a staged or
  clean tree fails on managed files that are still untracked).
- Tests: `PYTHONPATH=$(ghq root)/github.com/NousResearch/hermes-agent
  $(ghq root)/github.com/NousResearch/hermes-agent/venv/bin/python -m pytest
  plugins/ scripts/tests/ -q --import-mode=importlib` — the Hermes venv is
  required and `--import-mode=importlib` is not optional (plugin suites share
  the `tests/test_plugin.py` basename in hyphenated, non-importable dirs).
- `../install.sh` after adding files; `hermes update` to update (not
  `setup.sh`); `hermes doctor` for providers and model tiers.

## Commits

Conventional Commits with the `(hermes)` scope: `feat(hermes): …`,
`chore(hermes): …`, `docs(hermes): …`, `refactor(hermes): …`.
