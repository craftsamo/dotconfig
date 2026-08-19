# hermes/ — maintainer rules (for OpenCode)

Version-controlled, non-secret **Hermes Agent** config. `../install.sh` symlinks
these into `~/.hermes/`; Hermes reads `~/.hermes/`, never `~/.config`. This file
is guidance for the agent maintaining this subtree — **not** Hermes runtime config.
Authoritative depth: `README.md` (mechanics) and `PROFILES.md` (multi-agent design).

## Critical rules

- **Edit here, never `~/.hermes/…`.** Those are symlinks back to this repo. New
  files need `../install.sh` to link them; `link()` never overwrites a real file
  (prints `WARN … not overwriting` and skips). Adopt existing real files via the
  move-then-`install.sh` steps in `README.md`.
- **No secrets, no `.env`.** Keys live in the macOS Keychain, injected by the
  `bin/hermes` shim. See the `keychain-secrets` skill / `opencode/instructions/secrets.md`.
- **`config.yaml` is rewritten by Hermes on load.** Expect re-serialization churn;
  match Hermes' output format (block style, key order), keep diffs minimal — don't
  hand-reformat or alphabetize.
- **`cron/` is not in this repo at all.** Hermes `mkdir -p`s its own cron dir and owns
  everything in it — `jobs.json`, `output/`, `executions.db`, `.tick.lock`,
  `.jobs.lock`, `ticker_*`, `catch_up_occurrences`, `suggestions.json` — so
  `install.sh` leaves `~/.hermes/**/cron` a real machine-local directory and links
  nothing. Do **not** re-link it, and do **not** re-add it with `skip-worktree`: that
  flag hid new jobs from `git status` and made every branch switch fail on a
  dirty-but-invisible file. A missing `jobs.json` is read as **zero jobs, silently**
  (`cron/jobs.py:1013-1018`) — back it up before touching that directory. Schedules
  for the private `local-*` jobs are recorded as runnable `hermes cron create`
  commands in the private overlay's README (`~/.config/private`,
  the `private-dotconfig` repo).
- **`platform_toolsets.<platform>` is the effective tool allowlist.** Keep it granular;
  `hermes-cli` / `hermes-telegram` expand to a broad surface and strip default-off
  tools such as `video` / `video_gen`. Mirror the role in top-level `toolsets`, but
  remember that top-level `kanban` is also the front-door runtime gate. Dispatcher
  workers receive `kanban` automatically; their dormant Telegram / Discord lists stay
  empty. Use `no_mcp` when a platform needs none; otherwise list each allowed MCP
  server explicitly so future servers are not inherited accidentally.
- **`SOUL.md` = persona only** (voice/posture), per-profile (`HERMES_HOME`). No
  project rules/paths/commands there. Headings aren't parsed (verbatim inject).
- **Keep `default` neutral** — every `--clone` inherits its `config.yaml`.
  Specialized personas, bots, and cron belong in named profiles.
- **OAuth logins from `default` only** (`hermes model`, no `-p`). Codex / Copilot /
  xAI creds are inherited read-only by every profile (Anthropic native resolves
  separately via the global Claude Code credential/token); running `hermes model`
  inside a worker writes that profile's `auth.json` and shadows the inherited creds.
- **Anthropic account mapping — do not cross the streams.** Hermes' resolver
  (`resolve_anthropic_token()`) ALWAYS prefers the default Keychain entry
  `Claude Code-credentials` over the credential pool (pool entries and
  `suppressed_sources` never override it). That default entry must stay logged
  into the **Hermes** account. OpenCode runs on the **sub account** via the
  `opencode-claude-auth` plugin pinned to a suffixed entry
  (`Claude Code-credentials-<suffix>`; the concrete name lives in the untracked
  `claude-account-source.txt`; `CLAUDE_CONFIG_DIR=~/.claude-sub`,
  alias `claude-sub`). A plain `claude /login` re-login therefore changes
  **Hermes'** account, not OpenCode's — after one, verify with
  `security find-generic-password -s "Claude Code-credentials"` + the OAuth
  profile endpoint before assuming the split still holds.
- **Operating policy lives in `agent.system_prompt`** (per-profile, always-on);
  detailed playbooks are per-profile skills. `SOUL.md` stays persona-only. Do **not**
  run `/personality` on a profile — it shares the `agent.system_prompt` slot and
  silently overwrites the operating contract (the messaging assistant is most at risk).
- **Media stack lives in `plugins/`.** Backends are chosen via `*_gen.provider` /
  `plugins.enabled`. Video analysis runs through the `video-analyze-mimo`
  tool-override (config `video_analyze.model`) so `auxiliary.vision` can stay
  `auto` — **pinning `auxiliary.vision` to a video-capable model disables the
  main model's native image vision.** Custom top-level keys (e.g. `video_analyze:`)
  survive Hermes' config rewrites (`_deep_merge` keeps user keys). Voice routes the
  same way: `tts/tts-fallback` + `transcription/stt-fallback` chains, picked via
  `tts.provider` / `stt.provider` + `*.fallback.chain` (custom keys preserved).
- **Web search backends are pinned per profile — there is NO runtime failover.**
  An empty `web.search_backend` / `web.extract_backend` means auto-detect, which
  takes the first backend whose KEY EXISTS (`tavily → exa → parallel → firecrawl
  → searxng → brave-free → ddgs`, `tools/web_tools.py:223-270`): availability is
  key presence, never quota, and a runtime HTTP error is returned to the model
  as-is — it never falls through to the next backend. Left empty, every profile
  piles onto Tavily and dies together the moment its monthly credits run out.
  So each profile owns a provider: assistant `exa`, researcher `firecrawl`,
  searcher `parallel`, engineer / creator / writer / marketer `tavily`;
  `default` stays neutral (auto ⇒ tavily). Exhaustion is per-provider and each
  one self-heals: Tavily `432` (1,000 cr/month, resets the 1st), Exa `402`
  ($10/month Free Tier grant), Firecrawl 4xx (1,000 cr/month, renews ~the 17th;
  balance: `GET https://api.firecrawl.dev/v2/team/credit-usage`). `401` is a
  dead/rotated key, not exhaustion. Parallel's quota model is UNVERIFIED (no
  balance endpoint) — if searcher starts failing while the key is otherwise
  valid, swap searcher and researcher (`parallel` ⇄ `firecrawl`) and note it
  here. Switching = edit the two keys in this repo (the `~/.hermes` configs are
  symlinks, so a new CLI turn picks them up); rotating an API KEY additionally
  needs a gateway restart, because resident sessions inherit the environment
  injected at gateway launch.
- **The browser tool drives a REAL browser, not a bundled one.** With `browser.backend`
  unset and `uvx` present, `is_browser_use_cli_mode()` replaces the built-in
  `browser_navigate` surface with `browser_exec` → `uvx browser-use` →
  `browser_harness`, which attaches over CDP to an installed browser. So the
  `browser:` block in `config.yaml` (`engine`, `camofox`, …) and any
  `AGENT_BROWSER_*` env var describe the DORMANT built-in path and change nothing;
  only `BU_CDP_URL` / `BU_CDP_WS` / `BH_*` reach the live one. Left to discover on
  its own, the harness picks whichever browser's `Local State` has
  `devtools.remote_debugging.user-enabled` (Chrome first in its fixed profile list)
  and then needs a manual **"Allow remote debugging?" click per connection** —
  auto-approval exists but is hardcoded to Google Chrome (`macos.py` matches
  `process "Google Chrome"` and the Chrome support root), so Brave can never be
  auto-approved. We therefore pin it to a dedicated headless instance on an isolated
  profile via the Keychain `hermes` entry `BU_CDP_URL=http://127.0.0.1:9333`
  (`launchd/chrome-agent-launchctl.sh`); an explicit port on a non-default
  user-data-dir is what suppresses the popup. **The resident instance must come from
  a DIFFERENT app bundle than the everyday browser**: macOS treats one bundle as one
  running app, so a resident Brave made Dock/Spotlight launches merely activate it and
  the daily profile could no longer be opened (2026-08-17). The launcher therefore
  prefers agent-browser's "Chrome for Testing" bundle (resolved dynamically — the
  directory is version-pinned) and falls back to `/Applications/Google Chrome.app`,
  which reintroduces that clash only if Chrome is also used interactively.
  Consequences: the everyday browser is never touched, there is **no fallback** if the
  agent is down (30s timeout, then failure), and the port/profile in the launcher must
  stay in sync with the Keychain value.
- **Worker terminal approvals cannot prompt — a flagged command just fails.** The
  dispatcher runs workers with `stdin=DEVNULL` but still sets
  `HERMES_INTERACTIVE=1`, so `approvals.mode: manual` reaches EOF, denies, and the
  tool returns `status: "blocked"`. The guard reads only the OUTER command, never
  inside a script — so `./scripts/x.sh`, `bash x.sh`, `opencode run`, `npx
  hyperframes …`, `ffmpeg`, `git commit`, non-force `git push`, `gh pr create`,
  `xurl` and `python3 script.py` all pass. What trips it: inline interpreters
  (`bash -c`, `python3 -c`, `node -e`), `find -delete`, `chmod +x … && ./…`,
  recursive `rm -rf`, `git reset --hard`, `git clean -f`, force push. Write worker
  playbooks around scripts and wrapper CLIs, never inline one-liners.
  `command_allowlist` is the escape hatch (exact match or fnmatch glob against the
  WHOLE command; skipped when it contains `&&` `|` `>` `;`) and stays empty on
  purpose — allowing `bash -c *` would reopen exactly what the guard exists to
  catch. The hardline floor (`rm -rf /`, `$HOME`, system dirs) blocks regardless.
- **Upstream skill wiring is external_dirs-only.** Official `skills/` libraries
  attach per category directory, `optional-skills/` per individual skill
  directory, pruned via `skills.disabled` (see each profile's `config.yaml`).
  Never run `hermes skills install` — it copies into `~/.hermes/skills`, i.e.
  this repo (that's what the `.no-bundled-skills` opt-out protects against).
  The setup-gated candidate backlog lives in `PROFILES.md`
  ("Upstream wiring pattern").
- **HyperFrames skills live outside the repo, on purpose.** `creator` reaches the
  `hyperframes*` / `media-use` playbooks through `skills.external_dirs`
  (`~/.agents/skills`) — a harness-neutral store owned by `hyperframes skills
  update` and shared with Claude Code / Codex / Gemini, so it stays untracked.
  Never symlink them into `profiles/creator/skills/`: the CLI already relocated
  the store once (`~/.claude/skills` → `~/.agents/skills`) and the relative links
  broke silently. A fresh machine needs `hyperframes skills update` before creator
  can load them. Note that a bare `hyperframes skills` **installs** rather than
  reports — verify with `hermes -p creator skills list` instead.
  An installer run reseeds those links and every one lands DEAD (26 of them on
  2026-08-19): `~/.hermes/profiles/creator/skills` is itself a symlink into this
  repo, so a target of `../../../../.claude/skills/…` — correct counted from
  `~/.hermes/…` — resolves one level short from the real path and hits
  `~/.config/.claude/`. The tell is `validate-profile-skills.py` failing with
  `local skill root must not contain symlinks` while `skills list` still shows
  every skill, because `external_dirs` was serving them the whole time. DELETE
  the links (gitignored by `hermes/profiles/*/skills/*`, so nothing leaves the
  repo); never repoint them.

## Layout

```
config.yaml          # model/providers, toolsets, agent settings (Hermes-rewritten)
SOUL.md              # default persona (prompt slot #1)
mcp.json             # MCP servers ({} = none)
                     # (no cron/ — Hermes owns ~/.hermes/cron, machine-local)
skills/              # shared maintainer-owned skills tracked
  default-pipeline/  # thin CLI adapter for default; points at the assistant's
                     #   assistant-pipeline reference tree and records CLI deltas
                     # (the ~/Workspaces data-skill cluster — people/pp, household-budget/hb,
                     #   reports/rp, projects/pj, business-prospects/bp, message-reply,
                     #   scaffold + _cross.py — moved to the private overlay, read via
                     #   skills.external_dirs as ~/.config/private/hermes/skills; this repo is public)
                     # (creative/ moved to profiles/creator/skills — creator owns media)
  learned/           # runtime-authored adaptive skills; mutable and ignored
plugins/             # backend chains, tool overrides, completion and Worker
                     # mutation guards; source tracked, __pycache__ ignored
launchd/             # LaunchAgents: assistant gateway, local TTS engines,
                     #   dedicated automation browser (browser tool target)
profiles/<name>/     # assistant, engineer, researcher, searcher, creator, writer, marketer
  - config.yaml      # model/fallback + agent.system_prompt (operating contract)
  - profile.yaml     # routing description (kanban/delegation)
  - SOUL.md          # per-profile persona (BASE + role posture)
  - skills/          # per-profile skills. Every worker has exactly ONE
                     #   root pipeline skill `<profile>-pipeline` (lifecycle +
                     #   capability router, auto-loaded by its operating contract)
                     #   + directly selectable LEAF technics under skills/technic/,
                     #   pinned per card via kanban_create skills:[...]. A technic's
                     #   references are modes only when tools, spend class and QA
                     #   stay the same; styles/presets/formats remain references.
                     #   (searcher: no technics — the lookup/sweep/hunt unit
                     #   playbooks are searcher-pipeline references, paired with
                     #   the assistant's plan/search and quality-assurance/search
                     #   leaves (validator-enforced QA mapping);
                     #   creator: canonical creator-* image/video/audio/music/
                     #   browser-motion/diagram/editorial/icon/card/meme/text-art/
                     #   pixel/sourcing/assembly leaves (1:1 with the assistant's
                     #   plan/creative decision leaves; validator-enforced);
                     #   writer: the japanese-writing skill (notation +
                     #   tech-prose / prose-rhythm / business doctypes /
                     #   inspection lint layers) via the curated
                     #   external-skills symlink dir;
                     #   marketer: + upstream social-media/xurl + creative/humanizer;
                     #   managed technics stay exactly one directory below skills/technic/
                     #   because validate-profile-skills.py enforces flat canonical leaves;
                     #   assistant keeps its front-door pipeline in
                     #   profiles/assistant/skills/assistant-pipeline/ (mode-first
                     #   chat/plan/execute/quality-assurance references) plus its
                     #   surface skills — desks/ holds
                     #   topic-bound personal-desk / project-desk / brainstorm
                     #   (Inline-only; specialist work spins into a new topic);
                     #   both assistant dirs are private-overlay symlinks
                     #   (content tracked by private-dotconfig, not here);
                     #   every profile's learned/ holds mutable runtime-authored
                     #   skills and is never a dispatch or Git ownership surface)
                     # (no cron/ here either; scheduled jobs live machine-local)
                     # assistant/scripts/ holds resident-session.sh (the resident
                     # specialist-session wrapper), kanban-scheduled-sweeper.sh,
                     # kanban-resolve-block.sh for guarded resume, and the
                     # local-* cron scripts
setup.sh README.md PROFILES.md
```

## Profiles

default (CLI front door — assistant's CLI counterpart, neutral persona) +
assistant (messaging front door, hosts the gateway/dispatcher) + engineer /
researcher / searcher / creator / writer / marketer (Workflow v5
specialists). Heavy work runs by default in resident chat sessions the
assistant starts through `assistant/scripts/resident-session.sh` and
supervises conversationally; the kanban board is only for fire-and-forget,
cron-originated, mass-parallel, and `scheduled` work with a lean card
contract (no manifests/digests/probes — the v4 machinery is retired, see the
2026-08-06 rebuild). The card catalog is CLOSED and per-assignee: creator
(`anchored-image-batch`, `tts-voice`, `deterministic-render`), searcher
(`survey-enumeration`, `exhaustive-hunt`), researcher (`claim-verification`);
writer, engineer and marketer are resident-only and refuse every card.
The validator cross-checks worker kernels against the catalog's
`assignee` front matter. The assistant itself is the quality gate (contracts under
`profiles/assistant/skills/assistant-pipeline/references/quality-assurance/`)
and owns GitHub bookkeeping.
Planning is one conversational approval. On cards, specialists speak the
`STATE:`/`Q<n>:`/`DECISION(Q<n>):`/`PROGRESS:`/`AUTHORITY+:`/`REVIEW:`
comment protocol; resumes go through `kanban-resolve-block.sh`; scheduled
parking uses `SCHEDULED: until=` comments and the assistant sweeper cron.
Workers batch questions into one `needs_input` block; a second block,
`capability` block, or spec gap pulls the card back to a resident session or
re-plan.
Grants: engineer Authority A1/A2/A3 + B1/B2 (worktree-side bootstrap
only — repo creation/registry stays the assistant's; planning documents
and GitHub bookkeeping are never the engineer's — the assistant plans in
its own OpenCode session and hands over `Base session:` / `Issue: #n`),
creator Budget caps, marketer Publish (absent = draft-only; posting needs
verbatim approval or in-cap P1) — see PROFILES.md "Engineer dialogue
loop". Tracked per
profile: `config.yaml`, `profile.yaml`, `SOUL.md`, `skills/`, `.no-bundled-skills`.
Create with `hermes profile create <name> --description "…"`, then adopt into the
repo (move real files → `../install.sh`); see `README.md` / `PROFILES.md`.

## Tracked vs ignored

Tracked: config / SOUL / `profile.yaml`, `plugins/` source, `launchd/`, docs.
Ignored (see `../.gitignore`): `auth.json`, `.env`, `memories/`, `sessions/`,
`state.db*`, `logs/`, `workspace/`, `.hub/`, `.curator_state`, `.usage*`,
`**/__pycache__/`, `*.pyc`. `cron/` is absent entirely — it is not linked, so
nothing it writes ever reaches the repo. Never commit secrets, state, or
host-rendered plists.

**Skill ownership follows the directory type.** Shared `default-pipeline/` and
every worker's `<profile>-pipeline/` and `technic/` are maintainer-owned and
tracked normally. The assistant's `assistant-pipeline/` and `desks/` are also
maintainer-owned but live in the private overlay — symlinks into
`~/.config/private`, tracked by the private-dotconfig repo (they encode the
personal messaging operation; this repo is public). Edit them through the same
paths; commit in the overlay repo. Runtime creates
are forced into `learned/` by the `skill-topology` plugin; `learned/`, external
skills and Hermes bookkeeping stay ignored. Do not use `skip-worktree` for
managed skills: their changes must remain visible in `git status`. Promotion
from `learned/` to `technic/` is an explicit review step; move the complete
package, normalize its technic metadata and routing, pin it against curator
writes on the current machine, then commit it.

## Commands

- `./setup.sh` — install/refresh the hermes binary (uv venv); idempotent.
- `./scripts/validate-profile-skills.py --all` — validate managed/learned skill
  topology, metadata, routing registries and Git ownership; add `--strict-git`
  in a staged/clean tree to fail on managed files that are still untracked.
- `../install.sh` — create the `~/.hermes/` symlinks (run after adding files).
- `hermes update` — git pull + re-sync (use this to update, not setup.sh).
- `hermes doctor` — validate providers / model tiers.
- `launchd/qwen3-tts-launchctl.sh {install,register,unregister,voices,status,uninstall}`
  — multi-voice Qwen3-TTS LaunchAgent (`qwen3-tts` on `127.0.0.1:10102`). It
  shares one pinned Base model across registered character voices and uses an
  ignored Python 3.12 venv/model cache plus an ignored `catalog.json` under
  `hermes/local/qwen3-tts/`. First install requires
  `install --voice-manifest PATH`; add voices with
  `register --voice-manifest PATH [--default]`. The private manifest paths must
  never enter tracked config or docs. Dependencies come from
  `qwen3-tts/requirements.lock` and must stay hash-locked.
- `launchd/gateway-launchctl.sh {install,status,uninstall}` — gateway LaunchAgent,
  **one host only** (one bot token = one live connection). The same Assistant
  process hosts Telegram + Discord and the embedded dispatcher. Discord requires
  the `AsyncSessionDB` regression guards for resolved upstream #40695.
  `install` re-renders + reloads = **restart** (new process re-reads `config.yaml`);
  to apply config you can also send **`/restart`** in chat (drain → `KeepAlive`
  respawns one). **Stop = `uninstall`** (plist `KeepAlive:true`; a plain `kill` just
  respawns). **Never** run `hermes gateway run`/`restart` in a terminal while it's
  loaded — the 2nd poller causes Telegram `getUpdates` 409 conflicts
  (verify a single instance: `pgrep -fl 'gateway run'` ⇒ exactly 1).
- `launchd/chrome-agent-launchctl.sh {install,uninstall,status,check,login}` — the
  headless automation browser the browser tool drives (see the browser-stack rule
  above). `check` probes the CDP endpoint; `login` reopens the same profile
  headful so you can sign in, then restores the headless agent. **Stop =
  `uninstall`** (plist `KeepAlive:true`).

## Commits

Conventional Commits with the `(hermes)` scope: `feat(hermes): …`,
`chore(hermes): …`, `docs(hermes): …`, `refactor(hermes): …`.
