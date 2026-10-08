# hermes/ — maintainer rules

Rules for whoever edits this subtree: OpenCode, or a Hermes profile doing
repository upkeep (the Assistant through OpenCode).
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
  reference voices, the Irodori lexicon, manifest paths, Telegram ids, and the
  names of the user's businesses, clients, messaging accounts, spreadsheets
  and tabs — never enters tracked config, docs, tests, examples or commit and
  PR text; it lives in the private overlay (`~/.config/private`, the
  `private-dotconfig` repo). Use neutral examples (`work`, `personal`,
  `Leads`). The overlay installs local commit and push hooks that refuse
  known names; a refusal is fixed by rewording, never by `--no-verify`. The
  Assistant pipeline is tracked here too: what it must know about a private
  account, business or person goes on the private technic shelf, and the
  entry names that technic only.
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
- **Hermes gets shared secret layers only.** `profile-secrets.sh` and the
  tool-mode `bin/secret-shim` pin `--scope <project>`; without it `secret env`
  adds the scope named after the working directory's repository. The Discord
  user token, the Telegram session, the Substack cookies, the YouTube
  refresh tokens and the Google token sit in the `hermes` keychain under the
  scopes `discord-user`, `telegram-access`, `substack-session`,
  `youtube-access` and `google-access` and rely on that pin to stay out of
  every profile ([docs/discord-access.md](docs/discord-access.md),
  [docs/telegram-access.md](docs/telegram-access.md),
  [docs/substack-access.md](docs/substack-access.md),
  [docs/youtube-access.md](docs/youtube-access.md),
  [docs/google-access.md](docs/google-access.md)).
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
- **Anthropic accounts — do not cross the streams.** The default Keychain entry
  `Claude Code-credentials` always wins Hermes' resolver and must stay logged
  into the **Hermes** account; OpenCode runs on the sub account through its
  own OAuth login, outside the Keychain. A plain `claude /login` therefore changes
  Hermes' account — afterwards verify with
  `security find-generic-password -s "Claude Code-credentials"` plus the OAuth
  profile endpoint. Details: [docs/models-auth.md](docs/models-auth.md).
- **A new Claude model is not covered until checked.** Before adopting one,
  read its breaking changes against the mandatory-thinking and
  no-forced-`tool_choice` substring lists (unknown ids default to "disable
  accepted, forcing accepted"). See
  [docs/models-auth.md "Models and fallback chains"](docs/models-auth.md).

## Gateway and A2A

- **One multiplex gateway process** (LaunchAgent `ai.hermes.multiplex`)
  hosts every bot and A2A endpoint and serves every profile directory under
  `profiles/` — there is no allowlist. A new bot = a `hermes-<name>` Keychain
  layer + `platforms` / `a2a_agents` / toolset entries — never a second gateway
  process (one bot token = one live connection). Never run
  `hermes -p <role> gateway stop` on a specialist that must stay reachable: it
  parks that profile in the shared gateway.
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
  links, never repoint them; check both roots. No skill root is a link: the
  Assistant's private technics are read through one `external_dirs` entry (see
  [README "Layout"](README.md#layout)). Verify with
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
  profile config; `test_plugin_config_keys.py` checks it.
- **`plugins/messaging/_shared/` is code, not a plugin.** The four chat
  plugins load `archive_check.py` from it by path, so moving or renaming it
  breaks all four at import. Never give it a
  `plugin.yaml` (Hermes would try to load it), and keep each sender's own
  file rules passed in rather than copied there
  ([docs/signal-access.md](docs/signal-access.md)). Its terminal guard
  (`unpacked_guard`) keys on the `.unpacked` folder name that `extract` gives
  an unpacked archive, and the skills the messaging plugins ship name it too:
  rename it everywhere or the guard stops matching without a failure.
- **`plugins/web3/_shared/` is code, not a plugin, and holds the web3 tools'
  logic.** evm-access and solana-access are thin entry points that load
  `access.py` from it by path and share its one in-memory record of approval
  decisions, so both break at import if it moves, and it never gets a
  `plugin.yaml`. The signer and reader run from there too, with paths that
  `scripts/web3.sh` names ([docs/web3.md](docs/web3.md)).
- **Moving a plugin directory moves its LaunchAgent's script path.** The
  installed plists of the `messaging/` sync agents embed the absolute path of
  `sync.py` / `engine.py`, so after such a move each agent needs its
  launcher's `install` (or `restart`) again, or launchd keeps restarting a
  file that is gone.

## Hands, commissioning and Creator

Contract: [docs/hands/overview.md](docs/hands/overview.md),
[docs/broker.md](docs/broker.md) and
[docs/profiles/creator.md](docs/profiles/creator.md). When editing:

- A hands skill is a `<hands>-pipeline/<verb>/<subject>/SKILL.md` leaf with one
  form — never a technic, a generated index, `menu.yaml`, a preset layer or
  cross-media Styles (earlier shapes with those decided nothing or governed
  everything). A subject must be unique across all hands, because the Assistant
  and Creator read them through one `external_dirs` list; the validator enforces
  the shape.
- Each served subject has one Assistant commissioning reference and one Creator
  capability reference; both mirror subjects, not forms, and land with their
  hands family, never as placeholder stubs.
- Creator stays an advisor: never give it a generation toolset, a hands target,
  or a bot (the studies behind that split are in its doc). New
  creative capability is a hands leaf, never a Creator technic.
- An execution-environment trap goes into the Procedure of the leaf that hits
  it, not into a shared rule.
- Tests that read the design text: `test_ad_routing.py` and
  `test_audio_creator_routing.py` read `docs/`; after media-craft changes also
  run `test_media_craft_routing.py` with the hands/entry tests.

## Media and engines

- **`auxiliary.vision` stays `auto`** — pinning it to a video-capable model
  disables the main model's native image vision; video analysis runs through
  the `video-analyze-mimo` override instead ([README "Plugins"](README.md#plugins)).
- **Native vision shows the model only the newest 3 tool images per request.**
  Past that, a `vision_analyze` result still says "Image loaded" while carrying
  no image the model can see, and models re-request in a loop (500-970 looks
  per video job). The `vision-window` plugin, enabled on the Creator family,
  fixes this through `transform_tool_result` without touching Hermes core; see
  [docs/hands/overview.md "Vision window"](docs/hands/overview.md). Do not
  solve it with a hermes-agent patch.
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

Contract: [docs/opencode.md](docs/opencode.md).
When editing `plugins/orchestration/opencode`:

- **The plugin keeps no run record.** The owner binding lives in the session's
  `metadata.hermes`; a run's state is read from the service (the `idle` message
  carries a turn's outcome). Do not add a state file, a watcher or a stored PID:
  they would become a second source of truth that disagrees with the service. The
  per-worktree lock file only serializes starts. Nothing enforces a deadline on
  purpose (a run outlives Hermes); do not reintroduce one without deciding that.
- **Roles are configuration, not code.** Role names, agents, policies and models
  come from `opencode.roles`; `DEFAULT_ROLES` is only the fallback. Code keys
  on the policy (`read-only` / `write`), never on a role or agent name.
- **The session ruleset owns each run's constraints.** Subagent sessions copy it
  and OpenCode applies it after their own posture, so it holds denies, asks and
  narrow allows, and the caller can approve a request only `once` — a
  session-wide allow would reopen what an explore or reviewer subagent denies
  itself. The one deliberate exception is a `write` run's `edit *` in its
  worktree, ordered before every edit deny so the config, skill and secret denies
  still win (a test enforces both). An `ask` reaches the caller as a decision;
  anything the caller must never approve is a `deny`.
- **Reach OpenCode only through `api.py`** (`opencode api`, output to files,
  minimal environment). A piped reply is cut off at a buffer boundary with exit
  status zero, `--param` silently drops query parameters (queries go in the
  path), and a service the command starts keeps its environment for every
  session — never widen `ENV_NAMES` to a secret. Prefer stable routes over
  `/api/experimental/*`: instructions entries are the one experimental route
  used, with a prompt fallback when the service refuses it.
- Keep caller/worktree/branch binding, completion from the turn's own idle
  marker (not a session-level outcome or an exit code), and no automatic replay
  after `unknown`.
- Keep `TURN_TIMEOUT` identical in `profiles/assistant/scripts/resident-session.sh`
  and `plugins/orchestration/specialist-call`. `creator`
  and `marketer` keep their tool deadline (5460) above `TURN_TIMEOUT` + cleanup, or a
  blocking CLI `specialist_call` times out at 420 s and polls; the Assistant
  keeps its (960) above `specialist_call.wait_timeout` (900) + 30.
- **Live callers bind to their conversation route, not the session id.**
  `_topic_owner` hashes profile home, platform, chat, thread, sender and session
  key; dropping a field merges topics or senders, adding the session id loses
  runs on `/new`.
- **`cancelled` is the only early stop a specialist conversation resumes
  from**, and only because the owning runner confirmed its group gone; never
  make `unknown`/`interrupted` resumable or let anything but that runner signal
  the group ([docs/profiles/specialist-calls.md](docs/profiles/specialist-calls.md)).
- **A caller never gets its own model.** The plugin refuses the caller's
  configured `model.default` and the model it last answered with (the
  `post_api_request` hook) for every role. Keep that hook registered and keep
  `models.model_key` folding speed tiers and snapshots, or a fallback or `-fast`
  alias slips through. When a profile's main model equals a role's default
  model, give that role its own `model` in `opencode.roles`.

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
   browser isolation.
2. `./scripts/validate-profile-skills.py --all`; delete any seeded category
   directory under `profiles/*/skills/` other than `<profile>-pipeline`,
   `technic` or `learned` (upstream seeds past `.no-bundled-skills`). A lone
   seeded `DESCRIPTION.md` is harmless and comes back each launch.
3. `scripts/verify-work-continuity.py` (above) and the test suite.
4. Re-check behavior rather than a branch: a browser attach daemon that
   outlived its clone keeps a dead port (unpatched upstream;
   [README "Browser"](README.md#browser)), and whether shutdown / `/restart`
   notifications reach secondary profiles.

## Maintenance loop

Full reference: [README "Commands"](README.md#commands).

- `./scripts/validate-profile-skills.py --all` (`--strict-git` in a staged or
  clean tree fails on managed files that are still untracked).
- Tests: `cd ~/.config/hermes && PYTHONPATH=$(ghq root)/github.com/NousResearch/hermes-agent
  hermes-python --test -m pytest plugins/ scripts/tests/ -q
  --import-mode=importlib` — the Hermes test interpreter is required (PM owns
  it; there is no venv path) and `--import-mode=importlib` is not optional
  (plugin suites share the `tests/test_plugin.py` basename in hyphenated,
  non-importable dirs). Private overlay tests likewise run with
  `hermes-python --test -m unittest …`.
- `../install.sh` after adding files; `hermes update` to update (not
  `setup.sh`); `hermes doctor` for providers and model tiers.

## Commits

Conventional Commits with the `(hermes)` scope: `feat(hermes): …`,
`chore(hermes): …`, `docs(hermes): …`, `refactor(hermes): …`.
