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
- **The upstream source tree has a macOS case collision — one file must stay
  `skip-worktree`.** `contributors/emails/agent@Agents-Mac-mini.local` and
  `contributors/emails/agent@agents-Mac-mini.local` differ only in case, so on
  case-insensitive APFS they are ONE file on disk; whichever git writes last
  wins and the other is reported modified forever. That permanently dirty file
  makes every `git rebase` / `git merge` refuse to start with `cannot rebase:
  You have unstaged changes`, and `git checkout --` just flips which twin is
  dirty. The lowercase variant carries `git update-index --skip-worktree` in the
  hermes-agent checkout (2026-09-01). Do not clear that bit, and re-apply it
  after a fresh clone — this is an UPSTREAM bug, not local drift, so expect it
  to survive until upstream renames one of the two.
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
  workers receive `kanban` automatically; writer / researcher / default keep their
  Telegram / Discord lists empty (engineer / creator / marketer now carry real
  `telegram` lists — they are bots), and every A2A-serving profile has an `a2a`
  list for its inbound peer sessions. `a2a` is also the OUTBOUND toolset name
  (the five `a2a_*` tools, default-off): Engineer/Marketer retain raw A2A;
  Assistant/Creator expose only `specialist` for outbound requests.
  Use `no_mcp` when a platform needs none; otherwise list each allowed MCP
  server explicitly so future servers are not inherited accidentally.
- **Multiplex gateway + A2A peer graph (2026-09 rebuild).** ONE default-hosted
  gateway process (`gateway.multiplex_profiles: true` + allowlist in the root
  `config.yaml`) runs all four Telegram bots (assistant / engineer / creator /
  marketer) and the A2A peer endpoints (writer / researcher receive-only;
  ports 9902-9906 in each profile's `platforms.a2a.extra.port` — NEVER via an
  `A2A_PORT` env var, which is read raw from the process env and would
  collide across profiles). Peer lists live per profile in `a2a_agents`
  (assistant→engineer/creator/marketer/writer; engineer→marketer/researcher/
  writer; creator and marketer→engineer/each-other/researcher/writer;
  creator additionally→image-creator/video-creator/audio-creator) with
  `timeout: 310` (the 120s caller default undercuts the 300s server reply
  window); enforcement is config + operating contract, and contracts forbid
  `a2a_call` against a direct URL. Under multiplex, scope-aware secret reads
  NEVER fall back to the process env: every profile's keys come from
  `secrets.command` → `scripts/profile-secrets.sh <profile>` (Keychain layers
  `global` + `hermes` minus messaging keys + `hermes-<profile>`); only raw-env
  readers (`BU_CDP_URL`, dashboard auth) still see the launcher-injected env.
  A new bot = a new `hermes-<name>` Keychain layer + `platforms` /
  `a2a_agents` / toolset entries + the multiplex allowlist, never a second
  gateway process. **Upstream (≤ 21b2095d) drops background-process /
  async-delegation completion notifications for every secondary profile
  silently** — two defects, both carried as fix branches merged into
  `local` in the hermes-agent checkout, each with a regression test:
  (1) `fix/watch-notification-multiplex-route` — `_inject_watch_notification`
  resolved adapters from `self.adapters` (default only); it now routes
  through the profile-aware `_adapter_for_source`. (2)
  `fix/authz-adapter-process-profile` — `_authorization_adapter` compared
  the stamped profile with `_active_profile_name()`, which follows the
  task-scoped `HERMES_HOME` override; watcher tasks spawned at the end of
  an assistant turn inherit that scope, so a completion for a RESTORED
  session (pre-restart topic, no transport ref) was taken for the host's
  and dropped as "no live adapter". It now compares with
  `_process_profile_name()` under multiplex. Re-check after `hermes update`
  that both merges survived (`git log --grep 'multiplex-route\|process
  profile'`), or resident sessions stop waking the assistant again — and
  the second one is invisible in a fresh topic: reproduce in a topic that
  existed before the last gateway restart. Sibling paths still unpatched
  upstream: shutdown / `/restart` notifications for secondary profiles.
- **The secret helper has one shot per profile per process.** Hermes runs
  `secrets.command` once per `HERMES_HOME` (no re-pull), kills it at
  `helper_timeout_seconds`, and a Telegram adapter that then finds no token
  fails NON-retryably — that bot is dead until the next gateway restart
  (`✗ telegram failed to connect (profile: …)` right after `[secrets:command]
  helper timed out`). `profile-secrets.sh` therefore fetches each Keychain
  layer exactly once (~2s idle for three layers; a duplicated `hermes` fetch
  for the bot profiles pushed them past 15s under boot load on 2026-09-02),
  and every config sets the timeout to 60. Never add a `secret env` call
  per key, and after touching the helper time it with
  `time sh scripts/profile-secrets.sh creator >/dev/null`.
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
- **TTS routes by LANGUAGE through the fallback chain, not a router.**
  `irodori-tts` is Japanese-only — measured against `qwen3-tts` on English-only
  text it scores 27% word error rate to Qwen's 8%, mangling `finished` into
  "finito" — so it *declines* English-dominant input (< 20% kana/kanji) by
  raising, and the ordinary chain advances to `qwen3-tts`. That is why the chain
  order is `irodori-tts → qwen3-tts → edge`: no routing layer exists, and none
  should be added. The hand-off is per utterance ON PURPOSE — the same reference
  voice renders 309 cents apart on the two engines (against 20-40 cents of
  seed-to-seed variation), so splicing them mid-sentence is audible.
  **A named character asset is the opposite contract and must not touch the
  chain.** AudioCreator's `character_voices` / `character_text_to_speech` live in
  the `character-voice` plugin — engine-agnostic, so they belong to neither
  engine plugin — and resolve a provider out of the TTS registry directly.
  Voice ids are qualified `<engine>:<voice>` **because the engine is half of
  the identity** (see the 309 cents above): a bare id would name a request,
  not a sound.   A refusal there is an error that writes no file, never a
  hand-off, so do not "helpfully" retry it on the other engine, and do not let
  the tool read `tts.fallback.chain` — that would smuggle the language routing
  into an explicit contract. Handlers take the model's JSON as ONE positional
  dict (`handler(args, **kwargs)`); declaring schema fields as parameters
  registers a tool that fails on every call.
  **Style control belongs to that explicit contract only.** Irodori performs an
  emoji as a non-verbal vocalisation instead of reading it, takes a free-text
  `caption` for delivery, and honours a `seed`; measured here, one `U+1F92D`
  adds 1.68 s to a 5.24 s line while the transcript keeps the same words, and a
  pinned seed reproduces the take through post-processing (the predicted
  duration is otherwise seed-invariant, so that duration jump is the proof it is
  added vocalisation and not a re-roll). Verify a reproduced take on decoded
  SAMPLES: the WAV is byte-identical but the delivered Ogg gets a random
  bitstream serial from ffmpeg, so ~80 container bytes differ every time. `character-voice` reads
  `provider.style_features` and REFUSES a control the named engine does not
  advertise — it must never learn an engine name for this, and must never drop
  one silently, which would return a file that is not the take that was asked
  for. The chain passes no style arguments and must not start: emoji reaching
  `qwen3-tts` or `edge` get read aloud as "smiling face", which is exactly why
  Hermes' shared cleaner (`tools/tts_text_normalize.py`) strips them for
  everyone. Do not weaken that cleaner — the character path parks the clusters
  behind ASCII placeholders across it and restores them, so the script still
  gets markdown, unit and newline handling.
  **Voice data never enters this repo.** Reference audio lives in the private
  character tree and is copied into the gitignored `local/<engine>/` by the
  launchers; the Irodori pronunciation lexicon is a private-overlay symlink
  (`private/hermes/local/irodori-tts/lexicon.json`). Do not add a `voice:` key
  under `tts.*` and do not name a lexicon path in `config.yaml` — both are
  tracked. `irodori-tts` repairs its own output (leading dead air, trailing
  hallucinated fragments, and the in-pause codec rustle) using only numpy and
  the stdlib, because the Hermes venv has no soundfile or scipy.
- **Web search: PAID backends are pinned per profile; everyone else rides the
  keyless ring.** Upstream DELETED the Tavily backend in v0.21.0 (`d6773cf26`,
  2026-08-31): `plugins/web/tavily/` is gone, `keenable` replaced it, and a
  leftover `TAVILY_API_KEY` in the Keychain is now dead weight. Auto-detect
  (empty `web.search_backend` / `web.extract_backend`) takes the first backend
  whose KEY EXISTS (`exa → parallel → keenable → firecrawl → searxng →
  brave-free → ddgs`, `tools/web_tools.py:215-308`) and then walks the keyless
  tier; availability is key presence, never quota. A NAME THAT NO LONGER EXISTS
  does not error — it silently resolves to `firecrawl`, which is exactly how
  four profiles would have piled onto researcher's credits after this upgrade.
  Since v0.20.5 there IS runtime failover, but only inside the FREE ring
  (`exa → parallel → firecrawl → keenable`, `plugins/web/keyless_mcp.py`): a
  rate-limited keyless request advances to the next vendor, and a failed KEYED
  call gets ONE stateless keyless rescue (`web.keyless_rescue`, default on;
  rescued results are never cached, so the next call retries your own backend).
  A keyed backend still never falls through to another KEYED backend, so the
  per-profile pinning below is what stops one provider's exhaustion from taking
  the fleet down.
  **`web.provider_tier.<vendor>` picks the lane per profile** — `free` forces the
  keyless endpoint EVEN WHEN the key is present and pins that vendor as the ring
  entry point; `paid` forces the keyed path and drops that vendor from the
  profile's ring; unset = auto (key present ⇒ keyed). Editing `search_backend`
  alone is NOT enough: with a key in the environment, auto silently bills the
  paid path.
  Current split — the three paid keys stay with the high-volume profiles, and
  everyone else sits on the free ring with DISTRIBUTED entry points so they do
  not all start at the same vendor: assistant `exa` (paid), searcher `parallel`
  (paid), researcher `firecrawl` (paid); engineer `exa`, creator `parallel`,
  writer `firecrawl`, marketer `keenable`, each with `provider_tier: <vendor>:
  free`. `default` keeps both backends EMPTY (neutral, so every `--clone`
  inherits nothing opinionated) but pins `provider_tier.exa: free`, because
  otherwise auto-detect resolves to the KEYED Exa path and eats the assistant's
  grant. `KEENABLE_API_KEY` is not set and is not needed — a `free` pin resolves
  without one. Verify a change by resolving the backend per profile
  (`HERMES_HOME=~/.hermes/profiles/<p>` + `tools.web_tools._get_search_backend()`)
  and by running `web_search_tool`; `data.served_by` appears only when the ring
  failed over, so its ABSENCE means your pinned vendor answered.
  Exhaustion is per-provider and each one self-heals: Exa `402` ($10/month Free
  Tier grant), Firecrawl 4xx (1,000 cr/month, renews ~the 17th; balance:
  `GET https://api.firecrawl.dev/v2/team/credit-usage`). `401` is a
  dead/rotated key, not exhaustion. Parallel's quota model is UNVERIFIED (no
  balance endpoint) — if searcher starts failing while the key is otherwise
  valid, swap searcher and researcher (`parallel` ⇄ `firecrawl`) and note it
  here. Switching = edit the keys in this repo (the `~/.hermes` configs are
  symlinks, so a new CLI turn picks them up); rotating an API KEY additionally
  needs a gateway restart, because resident sessions inherit the environment
  injected at gateway launch.
- **Browser stack (2026-09-06 rebuild): real-profile browsing on a CLONED
  Brave bundle; no resident CDP instance, no `BU_CDP_URL`.** With
  `browser.backend` unset and `uvx` present, `browser_exec` → `uvx browser-use`
  → `browser_harness` attaches over CDP to whatever Hermes resolves
  (`tools/browser_use_cli.py:_route_backend`); the built-in `browser_navigate`
  surface and the `browser.engine` / `camofox` keys describe the DORMANT path.
  Precedence there is fixed: a `BU_CDP_URL` / `BU_CDP_WS` in the PROCESS env
  wins over everything, silently — it is copied raw from `os.environ`, so under
  multiplex one value pre-empts real-profile browsing for EVERY profile with no
  warning. That is why the old Keychain `hermes` entries `BU_CDP_URL` /
  `BH_CHROME_PATH` were deleted with the resident `:9333` Chrome for Testing
  (`chrome-agent-launchctl.sh`, removed from `launchd/`; rollback =
  `git show 93bb5bb:hermes/launchd/...` + `secret set BU_CDP_URL`). Never add
  such a key back to a layer the gateway launcher evals.
  Profiles that need the owner's logins — assistant and marketer only — set
  `browser.use_real_profile: true` + `real_profile_pin:` naming a dedicated
  Brave profile DIRECTORY (`Local State → profile.info_cache` key, not the
  display name): assistant → `"Profile 12"` (**Hermes Agent (Assistant)**),
  marketer → `"Profile 13"` (**Hermes Agent (Marketer)**, 2026-09-09). Log
  in to services THERE, in the everyday Brave; cookies / logins are merged
  into `~/.hermes/profiles/<p>/browser-profile/brave/` on every fresh clone
  launch (gitignored) + `real_profile_binary:` pointing at the clone.
  Everyone else gets upstream's on-demand packaged Chromium in a throwaway
  profile. **One Brave profile per consenting Hermes profile, never shared:**
  Google rotates its session cookies (`__Secure-*PSIDTS`, a few times an
  hour) and treats an older value as a stolen session, so every client that
  shares one Google login signs the others out — the 2026-09-09 case, where
  the everyday Brave, the assistant's clone and a dozen marketer job clones
  all rode Profile 12 and the owner was logged out after each relaunch. X
  and Instagram carry static tokens (`auth_token` / `sessionid`, unchanged
  over days of clone use) and do not do this; the separate profile still
  isolates their risk-detection from each other.
  Preconditions that fail closed: the macOS DEFAULT browser must be Brave
  (detection is the LaunchServices `https` handler only —
  `hermes_cli/browser_connect.py:_detect_default_darwin`; with Safari it
  returns `None`), the pinned profile directory must exist (`Local State →
  profile.info_cache`), and the clone binary must be executable.
  **Why a clone:** macOS treats one app bundle as ONE running app, so while a
  headless Brave launched from `/Applications/Brave Browser.app` is alive a
  Dock / Spotlight / `open` launch only activates it and the everyday Brave
  cannot be opened — the 2026-08-17 defect, reproduced on upstream's real-
  profile path 2026-09-06. An APFS clone (`cp -Rc`) at another path has no
  shared identity, and its untouched signature still satisfies the Keychain
  `Brave Safe Storage` ACL (bundle id + team, not path), so cookies decrypt
  with no prompt — verified from the CLI and from the launchd gateway. The
  clone lives in the gitignored `local/brave-agent/Brave Agent.app`;
  `scripts/brave-agent-sync.sh` re-clones on version drift and the gateway
  launcher runs it before every start (Brave auto-updates; a stale clone keeps
  working until then). NEVER edit the clone — any change breaks the signature
  and with it cookie decryption. The `browser.real_profile_binary` key is a
  LOCAL patch (`fix/real-profile-binary-override` merged into `local`, with
  `tests/tools/test_browser_real_profile_binary.py`); re-check after `hermes
  update` like the other fix branches — without it the config key is ignored
  and the real bundle launches, bringing the Dock clash back.
  Runtime facts: the clone is launched with `--remote-debugging-port=0` and
  lives until the gateway process exits (only the atexit hook reaps it; the
  inactivity janitor closes agent-browser sessions, not this process), so one
  headless Brave (~230 MB) is resident whenever a consenting profile has
  browsed. **Owned CDP routing (2026-09-07 local upstream fix:
  `fix/browser-harness-target-scope`):** resolved CDP calls now use a private
  daemon runtime and stable name scoped by profile + logical session/task,
  rather than the global sticky `browser_harness` daemon. The binding and
  browser UUID are verified before executing code; endpoint changes are
  serialized. Do not use the old generic `bu-default` kill workaround.
  Owned-daemon idle cleanup (600 s) is opportunistic on calls and exit, not
  a background timer; it does not refresh a live browser's cookie snapshot.
  Stale cookies still require a fresh browser launch. The read-only isolated
  Instagram baseline succeeded; the user agent was not implicated.
  **A fresh launch means the CLONE process, not the gateway.** Cookies are
  mirrored (`snapshot_real_profile` → `_mirror_profile_auth`) only on the
  cold path of `_real_profile_cdp`; a gateway restart finds the surviving
  clone via `DevToolsActivePort` and RE-ATTACHES (`real-profile: re-attached
  to surviving Chrome`), mirroring nothing — the 2026-09-09 case: the owner
  logged in to Google in Profile 12 at 13:09, the clone from 10:48 kept
  serving the account chooser through two gateway restarts. And the clone
  must go TOGETHER with its agent-browser daemon (`hermes-real-profile-<p>`
  session, pid in `/tmp/agent-browser-hermes-real-profile-<p>/`): upstream
  only closes that session when `get cdp-url` succeeds, so a daemon that
  outlived a killed clone keeps the dead port, ignores the `--cdp <new
  port>` of the next launch ("daemon already running"), and every call
  fails with `All CDP discovery methods failed for 127.0.0.1:<old port>`
  until the gateway restarts — UNPATCHED upstream, so watch it after
  `hermes update`. The relaunch procedure the assistant runs itself is the
  private-overlay skill `hermes-browser-relaunch` (`scripts/relaunch.sh`:
  SIGTERM clone → stop daemon → clear socket dir; never launches; the next
  `browser_exec` does). Note also that `_find_agent_browser` resolves the
  npx cache copy (0.26.0 on 2026-09-09) ahead of the mise shim (0.31.1);
  not implicated, but the version you see on PATH is not the one the daemon
  runs.
  **Two more LOCAL patches carried in `local`, both from the 2026-09-09
  incident; re-check after `hermes update` like the others.**
  (1) `fix/real-profile-session-scope`
  (`tests/tools/test_browser_real_profile_session_scope.py`): upstream names
  the attach daemon `hermes-real-profile` in EVERY hermes process. Resident
  specialist sessions are separate processes (`HERMES_HOME=profiles/
  marketer`), so a marketer job found the assistant's daemon answering for a
  foreign data dir, closed it, re-snapshotted, launched its own clone — a
  dozen times an evening — and left a daemon holding a dead port for the
  assistant's next call to hang on (`took too long to start` after 120 s).
  The name is now per hermes home (`-<profile>` suffix, following the
  context-local override under multiplex), the CDP cache is keyed by it, and
  the reaper exempts every profile's live-owned daemon. The earlier note
  that "every consenting profile shares ONE clone" was true only inside the
  gateway process; across processes it was the bug.
  (2) `fix/real-profile-cookie-merge`
  (`tests/tools/test_browser_real_profile_cookie_merge.py`): the cookie
  store is merged row by row on relaunch, newest `last_update_utc` wins on
  the store's own unique index, source attached read-only; version / column
  drift or a non-SQLite copy falls back to the old overwrite. Without it a
  relaunch replaced the clone's freshly rotated Google token with the
  everyday profile's stale one and signed the clone out — verified live:
  after 25 minutes the clone's `__Secure-1PSIDTS` already differed from
  Profile 12's. Deletions do not propagate (a sign-out in the everyday Brave
  leaves the clone signed in). The worker-facing rule (spawn your own
  browser with port 0, never attach to Hermes' instance) lives in
  `~/Workspaces/AGENTS.md` (private overlay).
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
  **v0.21.0 seeds PAST that opt-out.** Every gateway launch writes
  `autonomous-ai-agents/DESCRIPTION.md` into the RUNNING profile's skill root
  (assistant) even though `.no-bundled-skills` is present and linked, and an
  upgrade that CHANGES a bundled skill copies the whole skill in too:
  `hermes-agent/` landed there on 2026-09-01, byte-identical to upstream with
  mtimes preserved. A lone `DESCRIPTION.md` is harmless — gitignored, no
  `SKILL.md`, so the validator stays green and deleting it only invites it back
  next launch. A seeded SKILL.md is not: it fails
  `validate-profile-skills.py` with `unexpected skill root`. So after every
  `hermes update`, run the validator and delete any category directory under
  `profiles/*/skills/` that is not `<profile>-pipeline`, `technic` or
  `learned`; the skills stay readable in place via `skills.external_dirs`.
- **Creator's hands (v3) are `<hands>-pipeline/<verb>/<subject>/SKILL.md`
  leaves, one form each — never a technic, never a generated index.** The
  contract (client model, five verbs, front-matter `form`, handoff text,
  family-by-family migration) lives in `PROFILES.md` "Creator hands (v3)";
  the validator enforces the shape (`validate_hands`), and a subject must be
  unique across every hands because Creator reads all of them through one
  `skills.external_dirs` list. `image-creator` (A2A `:9907`, receive-only)
  serves the icon, emoji, mascot, reimagine, kit and card families (`emoji-fit.sh`
  is the ONE home of the platform table; `generate-emoji` and
  `generate-mascot` are two rounds — anchor, then pack — and a mascot's
  approved anchor is the `reference:` of its emoji pack; `mascot-fit.sh`
  draws on chroma green, never white, because `key_px` on white counts
  eye whites; `generate-reimagine` sends the photo as `image_url` — the
  edit input — and every style reference opens with a Medium line,
  because an edit model returns the photo with a filter unless told
  what the picture IS; a human client consents to the upload in the
  same clarify round as the style; kit has all five verbs, with a
  style-sheet/list approval gate for generation and deterministic
  `create-kit` for exact UI states/9-slice geometry; `kit-images.py`
  owns finish/palette/atlas/measure, uses alpha bounds rather than colour
  trim for hollow UI frames, and rejects stale nonempty QA/atlas dirs);
  Creator
  (pipeline v8: Plan → Build → Quality assurance,
  `creator-pipeline/references/<phase>/index.md` followed by the selected
  `<hands>/<subject>.md`; plain references, never additional `SKILL.md`s)
  tells its client apart by the message's SHAPE — brief lines = the
  assistant → text `Q<n>:`; conversational = a human → the `clarify` tool
  (native buttons on Telegram) — fills the leaf's form and hands off; the
  technic-era routes for unmoved families sit in `references/legacy/`. Two earlier shapes failed —
  the generic technics decided nothing, `refactor/creator-profile` governed
  everything — so: no menu.yaml, no generated MENU.md, no preset layer, no
  cross-media Styles; an execution-environment trap goes into the leaf's
  Procedure that hits it (Japanese `。` in argv trips the guard → text via
  file; > 420 s → `background: true`; vision holds ~3 images → contact sheet
  then one at a time; `magick montage` aborts without a default font →
  `+append`; a multi-file `rm` trips the guard → leave `/tmp` alone; an
  inline `for` loop over a script variable trips it too → batches go
  through a script file; a 32 px tile is judged point-magnified 4x; a
  look whose finding is not appended to `qa.md` before the next
  `vision_analyze` did not happen — an image leaves the context three
  looks later and an unwritten run cycled 152 looks over three files;
  the write guard reads the WHOLE terminal command, so `cp … && <skill
  script>` is refused → a skill script runs in a command of its own).
- **Creator's v8 broker references mirror subjects, not forms.** Each of
  Plan / Build / Quality assurance owns a common index plus one flat
  `<hands>/<subject>.md` for every subject actually served by the three
  hands; verb differences stay inside that file. `validate_creator_references`
  derives coverage from the hands leaves and checks both missing and orphan
  references, real index links and local link targets. A v8 root requires the
  complete tree and rejects the old phase monoliths; a v7 root with no phase
  directories remains valid for the earlier Stack layer. New subject references
  land with their hands family, never as placeholder stubs. Creator reads QA
  evidence against intent; do not transplant the hands' measurement commands
  into Creator's QA. Actual legacy capability retirement stays family-by-family
  after caller coverage and both-client soak, not merely because a leaf exists.
  Writer's released-unit ownership is unchanged; see PROFILES.md "Broker shape".
- **Assistant is a deliverable-first Client, not a second production broker.**
  Its plain `plan/creative/<deliverable>.md` guides hold Client questions and
  acceptance criteria, with conditional reference research and common Execute
  and QA. No hands-name parity, form/provider/limit catalog or duplicate
  per-deliverable Execute/QA tree: a missing guide never means unavailable.
  The retained production decision/inspection files now live in each mode's
  `creative/legacy/`; only those Plan/QA files retain technic/Covers parity.
  Each parent index must route `legacy/index.md`; nested card declarations
  are forbidden, and the two original creative card units stay in the normal
  Execute index. Relocation is not capability retirement. Assistant's fixed
  house formats, device catalog and blanket past-film recipes are retired in
  both paths, not transplanted into Creator. Real technical constraints stay
  with the current producer; frozen outputs and approvals stay unchanged.
  Research examples are inspiration only, not authorized production assets.
  Creator's common Plan accepts observed/suggested/user-decided/open briefing
  text but requires explicit relayed asset-and-operation upload consent;
  Assistant origin, a path, a public URL or "use this" alone is insufficient.
  Rights, upload, remote analysis, exact proposal approval and Publish remain
  separate. Validate the paired public/private candidate structurally before
  approved cutover, then check real Git ownership and fresh-session discovery;
  never weaken the live symlink/Git boundary to make temporary-copy tests pass.
- **Card is one image subject with create/generate/edit/analyze leaves.**
  `scripts/card.py` consumes canonical `create/card/references/destination/`
  scalar front matter and `styles/*.md` CSS blocks. Generate's own style refs
  are backdrop prompt prose, not duplicated CSS. Local HTML uses isolated
  offline agent-browser with frozen assets/fonts, no inherited login/CDP, and
  exclusive output bundles. Full panoramas render before exact PNG crops;
  text belongs to individual tiles, not global destination crops. X pair 7:8
  is UNVERIFIED; X article 5:2 is user-verified ratio, not official 1500x600.
  Gap previews are configurable local simulations, never platform screenshots.
  Generate proposes 3+1 attempts across resumes but needs explicit current-work
  user budget approval before paid calls. Card routes before creator-text-card;
  retain its files/private-overlay mappings until handoff coverage, paid live
  validation and legacy caller migration prove retirement safe. No new profile,
  toolsets, secrets, test posts, authenticated access or gateway restart.
- **Video hands start with `clip`, not the whole legacy video surface.**
  `video-creator` receives forms on loopback A2A `:9908`; its three clip leaves
  are `generate-clip` (1-15 s, silent single shot), `edit-clip` (a <=60 s
  segment), and `analyze-clip` (findings). It has no TTS; `create-tour`/
  `create-ad`/`create-explainer-video` may optionally consult four curated HyperFrames technical
  references via `skills.external_dirs` (read-only, procedural background
  only — see `PROFILES.md` "Video authoring references"), and clip does not
  use them. `clip-media.py` owns local probe/frames/edit with exclusive
  output publication, measured byte caps and full decode; never treat
  GIF repeat metadata as a seamless-motion guarantee. Frame times are
  seek positions, not exact PTS. Remote video analysis is a separate
  upload-consent field; without it temporal QA remains unverified.
  xAI persistent public storage is disabled in this profile. Old learned
  `video-render-environment` remains on disk but is disabled (it names
  retired menu leaves). A2A identifies loopback callers by IP, NOT a
  cryptographically verified profile; verbal origin confirmation adds no
  security. Keep localhost restrictions, do not widen the transport.
  The MiMo override now calls upstream `_download_media` with explicit
  video options: `_download_video` was removed in `c4a9f2bf49`. Its tests
  invoke the handler with real imports so registration-only tests cannot
  hide another deferred ImportError.
- **Tour is a new video subject, not a global legacy retirement.**
  `create/tour` owns bounded (<=60 s) task-local authored UI walkthroughs,
  with frozen source projects, exclusive preview/final directories and a safe
  approval resume. VideoCreator authors HTML/CSS/GSAP from approved reference
  images/design/text; Creator owns semantic flow/fidelity/choice approvals.
  Intro/outro default ON; three reference examples are not exhaustive,
  free-text directions stay verbatim and only explicit none omits them.
  `authored.py` freezes/checks/renders v2/v3, never generates UI. The unchanged
  `tour.py` entry remains for persisted v1 screenshot projects/direct calls.
  `screen_mode` is recreate (omitted preserves v2), supplied or capture. Explicit
  modes use v3 proposal/hash approval without migrating frozen v1/v2 artifacts.
  `footage.py` prepares actual local video with bounded source ranges and explicit
  keep/mute; `capture.py` owns isolated sanitized Web recording under job/scope
  leases. Reference/source/target are distinct, never consent. Native capture is
  UNAVAILABLE: cua-driver 0.23.2 records the main display, and no cross-profile
  desktop guard covers Assistant's computer_use. Never grant it to VideoCreator
  or use Assistant fallback. Wrapper checks are not a terminal/website sandbox;
  no authenticated/private-region capture or privacy redaction is claimed.
  No edits to frozen source, external runtime workflows/executables, or TTS
  (the optional read-only HyperFrames references, `PROFILES.md` "Video
  authoring references", are advisory background only); use finished
  audio-creator WAV/words.json. Creator always uses specialist
  `kind="work"` for tours. Keep creator-html-motion and its 1:1 mappings intact.
  GSAP is minimally vendored with its own license and hash provenance.
- **Ad is an audience/promise/action deliverable, not a product-category
  skill tree.** VideoCreator serves `analyze-ad` (<=60s, bounded overview,
  two dense windows, three native detail looks; facts/interpretations/unknowns
  separate) and `create-ad` (6..30s, 30fps; aspect 9:16/16:9/1:1/4:5,
  default 9:16; authored HTML/CSS/GSAP from supplied assets). Canonical sizes
  live in ad-render.py; source, preview and output must match. A ratio change
  needs re-layout and new approvals, never crop/scale or old-preview reuse.
  Old aspect-less portrait plans keep their bytes and hashes. Always
  specialist kind="work". Analyze may retain
  report/evidence at explicit deliver, never a new ad; readable local video
  paths use frame extraction, not requests for chat attachments. Remote video
  analysis remains separately consented, at most once; image vision uses the
  normal profile policy, not a promise of offline inference. Create requires
  exact content-plan approval then exact frozen-preview approval in the same
  work conversation. The helper binds bytes, not approver identity; static
  copy checks are neither visual readability nor claim verification. No
  invented metrics, client-live claims, generation, TTS or capture; theme
  defaults never authorize missing asset generation. Generate-ad and PV are
  future leaves, no legacy mappings are retired. PV primarily introduces
  qualities/world; duration and CTA presence alone do not decide the route.
- **Explainer video is a topic/audience/learning_goal deliverable, authored
  locally, not a UI tour, an ad, or a talking-model product.**
  `video-creator` serves `create-explainer-video`: 1..180 seconds, always
  `specialist kind="work"` even though free, rendering through an
  explicitly chosen v1 HyperFrames or v2 Motion Canvas engine at 16:9
  (1280x720) or 9:16 (720x1280), 30fps — the engine is selected in the
  proposal and preserved, never silently switched, including never on
  failure. Motion Canvas is implemented (`engines/motion-canvas/`,
  `create/explainer-video/scripts/motion_canvas.py`) as its own local
  reference (`create/explainer-video/references/motion-canvas.md`) with no
  dependency on the external HyperFrames skills; prefer it for reactive
  diagrams, algorithms and Canvas-based explanation, and prefer HyperFrames
  for HTML/UI or media-oriented compositions. Old version 1 Motion Canvas
  discussion proposals stay non-executable and need a fresh version 2
  proposal and a new approval, never a resume of the old hash.
  `framing` (none/bust/full) is a field separate from `performance`
  (still/puppet/animated) and `lip_sync` (off/cues/baked): bust only
  proposes lip-sync cues by default, never a silent substitute for an
  explicit `off`, and full supports whatever performance the client
  actually approved rather than an automatic upgrade toward it. Neither
  renderer provides automatic phoneme/viseme inference, rig authoring, or
  native talking-model playback, so a naturally talking video is never
  something this leaf generates on its own. Already-supplied authored cue
  JSON plus mouth
  PNGs can drive a deterministic mouth track; a supplied finished muted
  MP4 carrying its own sync evidence can carry a continuous animated
  performance instead. A missing required performance asset is reported
  as pending-inputs, never a silent downgrade of framing/performance/
  lip_sync. Creator, never VideoCreator, resolves the caller-selected
  workspace/asset root: a direct path or an identity it already holds
  first, else a bounded name-only lookup inside the caller's own known
  workspace, with an ambiguous match going back as a question rather than
  a guess — never a broad home-directory scan, and never a new character
  invented merely because a file is missing. Explicit assets are retained
  as unchanged originals; the resolved root and any asset's private name
  stay working detail and never enter a public proposal, form, or report.
  An unspecified character is not "no character" — Creator clarifies none
  vs. an existing character vs. a new one, and an existing character
  missing a needed pose is a missing-only generation request through the
  fitting image-creator mascot leaf that preserves its approved identity.
  New character art goes through image-creator's mascot family, script
  text through Writer's current `write-script` family (never the retired
  writer technic, and never Creator composing the script itself),
  grounding facts through researcher as needed, and narration/audio
  through audio-creator; VideoCreator cannot call those hands/peers
  directly and instead returns a dependency request to Creator, released
  as its own separately budgeted/approved unit. The runtime
  lifecycle mirrors Tour/Ad's proposal-then-approval shape: `propose
  --spec SPEC --out <new proposal-vN dir>` writes `plan.json` +
  `proposal.md` + an assets snapshot and returns `pending-inputs` or
  `awaiting-approval` with the proposal's SHA-256 — missing inputs are
  described in `spec.pending`, never invented files or hashes; the
  approved script and exact on-screen copy are settled inputs, and each
  unit explains its before/change/after and visual expectations. A
  formally ready proposal exists only once the selected modes' required
  inputs and a supported renderer are in hand; silent/no-character modes
  need no audio/character assets. The user approves it via
  Creator. Only then does `freeze --approved-plan <proposal.md>
  --approval-sha256 HASH --source SOURCE --project NEW` run, followed by
  `snapshot --project PROJECT --out NEW`, and only a matching
  `render --project PROJECT --approved-preview PREVIEW --approval-sha256
  previewhash --out NEW` releases the final video. Nothing here
  self-approves; frozen outputs stay unchanged. Client confirmation is
  conversational like every other hands leaf — hashes bind bytes, not
  approver authority. For a HyperFrames plan, the existing curated
  HyperFrames external references and their read-only, discussion-scoped
  policy (`video-creator-pipeline/references/hyperframes.md`, `PROFILES.md`
  "Video authoring references") cover this leaf too, alongside
  create-tour/create-ad; a missing or unreadable reference is reported with
  a local-authoring fallback, never a blocker, while an actual runtime or
  approval error still blocks as always. A Motion Canvas plan instead uses
  only its own local reference and the pinned local runtime that a
  maintainer explicitly provisions with
  `node hermes/engines/motion-canvas/setup.mjs --browser <browser>` — jobs
  never install or upgrade it. Setup APFS-clones a supplied macOS `.app`
  browser into an ignored `runtime/browser/Renderer.app` (signed contents
  preserved, avoiding a Dock/LaunchServices clash with the everyday
  browser) and uses a non-app dedicated Chromium/headless-shell binary
  directly; neither path copies cookies or a profile, so every render gets
  a fresh isolated one. Rerunning setup against the same pinned lock skips
  reinstalling dependencies but never overwrites a different existing
  clone or a changed lock — that drift needs explicit maintainer
  replacement/provisioning and a new preview approval. Every preview
  records the actual runtime/Node/browser identity used; a normal browser
  version change doesn't by itself require reinstalling, but any changed
  identity still needs a fresh preview and approval, and final QA always
  carries the engine's contrast-audit status — Motion Canvas has no
  automated contrast check and reports it as requiring manual visual
  review. This is additive: existing music-video, ad, tour and Mix routes
  are unchanged.
- **Audio hands own `speech`, `sfx`, `music` and `mix`.** `audio-creator` receives forms on A2A
  `:9909`: generate/edit/analyze-speech. The character-voice plugin registers
  only there; Creator retains ordinary conversational TTS, never a speech
  asset bypass. House uses the language chain (including online Edge); a
  qualified local voice never falls back and rejects unsupported style/seed.
  `free` is a media-fee class, not unlimited takes: one plus one corrective
  by default, failures counted. `speech-media.py` owns track/edit/analyze,
  cached local ASR, exclusive bundles and measured normalization. Existing
  WAV timing sidecars are checked before reuse; lossy sibling derivatives
  get fresh ASR. Subtitle timing is estimated, pronunciation/performance
  unverified. Never invent a listening verdict or re-roll for an ASR spelling
  variant. Speech can feed a legacy film as a completed input; vocal-song
  generation and standalone audio visualization are withdrawn, not migrated.
  The old voice card is retired; no hands kanban contract is added.
- **SFX is a separate four-leaf family, not music or mixing.** `create-sfx`
  uses eight deterministic local kernels; `edit-sfx` and `analyze-sfx` never
  generate. `sfx-media.py` preserves mono/stereo, freezes local inputs, bounds
  decode to 22s/16 MiB and publishes new 48 kHz PCM WAV bundles. Short SFX may
  have no integrated LUFS; that is WARN, not a reason to re-roll. Peak/clipping
  and boundary samples are measurements, never hearing or seamless-loop proof.
  `generate-sfx` uses the standalone `sfx-gen` plugin and `sfx_gen` toolset,
  enabled only on audio-creator. **Local `local:stable-audio-3-medium` is
  installed and is the default engine when `engine` is omitted** (installed
  via `stable_audio3.py install --accept-terms`, a maintainer-only, one-time
  step — jobs never install or download anything). It takes a `seed`
  (default 0, 0..2^32-1, returned with the result); attempt N uses
  `(base seed + N - 1) mod 2^32`. It rejects `loop=true` and any
  `prompt_influence`/`paid_approved`/`max_usd` outright rather than dropping
  them silently. Each render is a fresh subprocess under the shared runtime
  lock (inherited by the child, 180s timeout) — no LaunchAgent, no port, no
  GPU-resident process. `resume` never regenerates: it only re-validates the
  saved `take-NN/raw.wav` + `take.json` + `inference.log` against the job's
  frozen receipt; an interrupted attempt with no result and no running
  process is marked failed (still counted), and `next` may use the
  remaining grant. Explicit `fal:elevenlabs-sfx-v2` remains available as an
  alternative: it must be named explicitly, needs explicit current-work
  paid approval (prompt/seconds/loop/cap/`max_usd`), supports `loop` and
  `prompt_influence`, and has NO seed (verified OpenAPI); requests cap at
  21.5s to leave 0.5s padding/drift headroom. Neither engine ever falls
  back to the other, automatically or silently. `max_calls` defaults to 4
  (3 variants + 1 corrective) on local; fal requires an explicitly approved
  cap. Both have hard cap 8, every attempt
  including failures counted. Metadata cost stays `metered` (the leaf can
  still spend on fal), but actual local spend is reported as `$0`. Frozen
  job state counts before a paid submission and retains request IDs; paid
  POSTs never use the SDK's automatic submit retries. Ambiguous fal
  submissions stop. Secrets resolve from profile scope, never process-env
  fallbacks. Old `local:stable-audio` (Stable Audio Open, 401-gated) is
  retired history, not the current Medium engine's status — never describe
  Medium as gated or blocked. `create-ad` accepts up to 16 distinct
  finished WAV cues, one placement per source and distinct positive audio
  track indices when multiple; final multi-audio true peak is checked. No
  gain automation, TTS, music/mix family, tour changes or new peer is added.
  SFX leaf commands use a literal Python path (or unquoted `~/ghq/...`),
  never `$(ghq root)` in the executable: a real generate-sfx packaging run
  was refused as "Nested executable body could not be resolved". Resolve
  a different ghq root separately, then execute the absolute path. Reuse the
  surviving raw WAV/receipt; this packaging repair consumes no generation.
- **Music is instrumental BGM or a short melodic piece, not Song or Mix.**
  Four leaves live at `audio-creator-pipeline/<verb>/music/`: create renders an
  AudioCreator-authored, approved score using five synthetic colors; generate
  uses `music-gen`/`music_gen` only on audio-creator; edit processes one source;
  analyze is also a standalone musical-analysis request, including existing
  vocal music without lyric or singing analysis. `music_plan.py` freezes the
  effective form, exact score/prompt and reference hashes in a proposal. Both
  creation leaves require Creator-relayed approval of that exact proposal;
  hash matching is integrity, never approver authentication. No audio/uploads
  in round A, no automatic reference-audio conditioning. Users need not author
  a score or prompt. `music-media.py` owns 48 kHz PCM bundles and bounded local
  tempo/key/activity estimates; instruments, genre and vocal absence stay
  unverified. Create/generate cap at 60s, edit/analyze at 600s/128 MiB.
  Local Stable Audio 3 Medium shares SFX's weights and runtime lock, never a
  new daemon. `render_music` has its own bounds; SFX `render` remains <=21.5s.
  Explicit `fal:stable-audio-3-medium` supports seed and needs current-work
  approval and a dollar cap; neither direction falls back. Default local
  grant is 2+1 attempts (hard cap 8), failures counted, resume never generates.
  Corrected approved prompts retain the consumed-call ledger and frozen
  engine/duration/seed/budget. Runtime adapter edits invalidate its install
  fingerprint: maintainer `stable_audio3.py refresh --previous-adapter PATH`
  verifies the previous adapter fingerprint and the entire existing install
  offline before updating its marker. Never bypass drift checks or rewrite
  existing job receipts; completed SFX resume remains valid, next detects drift.
  Finished music uses create-ad's existing WAV cues. No new tour/MV finish,
  song, mix, peer, secret, model download or launch service is implied.
  **Keep music front matter inside the runtime's first 4,000 characters.**
  Hermes discovery truncates before parsing YAML; an incomplete fence falls
  back to the parent name, collapsing create/music and generate/music into
  one `music` skill despite the topology validator passing. Compact labels,
  keep full procedures in the body, and test actual `_find_all_skills` names.
  MusicVideo is now `generate-music-video` at `generate/music-video/` and
  its complete form also fits the discovery prefix. Runtime write protection
  checks literal operations/targets, not `mv` inside a job path; the music
  proposal CLI has a real guard-plus-proposal regression for that case.
- **Mix places already-finished sources on a shared timeline, not a new
  synthesis or a music/SFX family.** Three leaves live at
  `audio-creator-pipeline/<verb>/mix/`: `create-mix` takes 1-16 standalone
  local speech/sfx/music files (WAV/FLAC/Ogg/MP3/AIFF, each <=128 MiB,
  <=512 MiB combined, <=600s decoded) and AudioCreator authors cue
  placement (<=32 cues) from `direction`/`must_keep` when no exact
  `arrangement` is supplied, with gain/fade/piecewise-dB-envelope
  automation; `edit-mix` revises one existing bundle from a
  plain-language change request against its frozen previous spec/
  sources; `analyze-mix` returns format/loudness/clipping/true-peak
  findings, plus recorded cue/source placement when a bundle is
  supplied — findings only, no delivery file. `mix-media.py` owns
  propose/render/analyze/verify; `create-mix`/`edit-mix` are TWO rounds
  like music — round A is always a zero-render `proposal-v<N>/
  proposal.md` + SHA-256, and only a matching Creator-relayed
  `approved_plan`+`approval_sha256` releases the render. No loops,
  speed/pitch changes, EQ, reverb, or source separation; every source
  stays the original standalone file, frozen and hash-verified before
  use — this leaf assembles, it never generates. `target_lufs`/
  `true_peak_dbtp` are explicit authored choices with no hidden default
  (`null` is a valid `target_lufs`); a source's own existing defect
  (e.g. prior clipping) is retained and reported, never silently
  corrected, and a mix that retains it still FAILs. Captions, when
  produced, come only from an existing `.words.json` sidecar on a
  speech source, timing-adjusted to that cue's placement — never a
  fresh ASR pass on the mixed master. This is `cost: free` (no
  provider fee) throughout; the leaf is deterministic placement/gain/
  fade/sum on already-decoded PCM, not a model call. No new engine,
  plugin, toolset, secret, peer or daemon is added; Mix shares no
  runtime with SFX/Music's Stable Audio install. Old `no skill fits`
  language for "audio mixing" in Creator's docs is replaced by a
  pointer to these three leaves; the fact that a music/SFX leaf is not
  itself a mixer is unchanged.
  Normalization is measured constant gain only, never loudnorm's implicit
  dynamic-limiter fallback. Infeasible loudness/peak targets FAIL; stereo-to-
  mono cancellation is warned and recorded. Ad/Tour opt in with
  `audio_workflow: mix`: preliminary timing first, Creator-brokered Mix next,
  then ordinary video approval using real master/receipt hashes. No dummy
  audio or placeholders in an approved plan. `mix_audio.py` validates the
  staged subset; Tour binds `mix-caption-N` text/timing to the distinct
  captions.json (never relax speech's words.json hash check). Only the master
  plays; kept footage audio conflicts. Final decoded audio duration and peak
  are measured again. Omitted Mix fields preserve frozen v1/v2/v3 behavior.
- **Multiplex TTS needs the scoped toolset-cache fix in the local Hermes
  checkout.** At upstream `4f0309e9cf`, `toolsets.resolve_toolset` memoized
  by toolset/registry generation but NOT profile scope. After Creator lost
  character-voice, warming its `tts` entry hid the two tools from AudioCreator
  despite correct scoped registration. `toolsets.py` now also keys on
  `registry.current_scope_key()` (static-only resolution uses an empty scope).
  It is carried as `fix/toolset-profile-scope-memo` merged into `local` in the
  hermes-agent checkout, with a regression test; re-check after `hermes update`
  that the merge survived. `test_audio_creator_routing.py` also exercises the
  real resolver across scopes at unchanged generation. Registration-only
  tests and direct CLI synthesis cannot detect this gateway-specific failure.
- **`image_generate` only advertises what the configured provider's
  `capabilities()` declares, fail-closed to text-only.** The
  `image-fallback` chain provider did not declare one until 2026-09-05,
  so every profile on `img-codex-xai-fal` had NO `image_url` /
  `reference_image_urls` in the tool schema while codex and xai both
  supported them. The chain now reports the first available member's
  surface and, for a call that carries images, skips text-only members
  instead of falling through to a redraw. Verify after an upstream
  change with `_build_dynamic_image_schema()` under the profile's
  `HERMES_HOME` (`plugins/image_gen/image-fallback/tests`).
- **MV is a deliverable, not a character/format skill product.** VideoCreator's
  `generate-music-video` uses existing `video_generate`, with local style/theme/direction
  references. Theme defaults are concrete world vocabulary overridden by
  `theme_detail`; never introduce a menu generator or cross-media presets.
  First round returns only a new `proposal-v<N>.md` and its SHA-256, with zero media calls.
  Creator relays client approval; only a matching `approved_plan` and
  `approval_sha256` in the same work conversation releases generation. This is
  an operating contract, not cryptographic caller authorization. Changed inputs
  or creative choices require a new proposal; attempts never reset on resume.
  Supplied music may be pending in a zero-spend proposal via textual
  `music_plan`: mark pending-inputs/can_generate:false, never invent a file
  or hash. Pending image-upload consent does not block local-only planning.
  Before generation, require real music_file/consent and a NEW numbered
  proposal/hash approval; a preliminary approval is not executable. Music
  production is separately released through Creator, never done in this leaf.
  Native audio must be supported by the actual backend; reference videos and
  supplied music are never uploaded by this leaf. Exact words/supplied music
  may require separately approved finishing, and a silent visual master is
  not a completed musical MV. Keep unverified temporal/audio QA explicit.
  Recipes are authored, not yet paid-render validated; broader legacy video
  remains available, and clip/tour are unchanged.
  xAI's reference-image path silently clamps to 10s despite advertising 15s;
  use a conditional 10s default and block explicit longer requests before spend.
  The current xAI-first chain does not advertise native audio: generated sound
  is blocked until a capable route is explicitly configured, never guessed.
  Only the skill name/path is renamed; `mv_<slug>` output filenames and runtime
  job paths stay unchanged. No old-name alias: reissue active legacy jobs with
  a new proposal and client approval; never edit frozen old jobs. Keep the
  closing frontmatter within 3800 characters for upstream's 4000-character scan.
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
  repo); never repoint them. **The SHARED root `hermes/skills/` gets seeded the
  same way** — 26 dead `../../.claude/skills/…` links there on 2026-08-29, found
  by the same validator failure and removed on 2026-09-01. That root is
  gitignored too (`.gitignore: hermes/skills/*`), and only `default-pipeline/`
  and `learned/` belong in it; anything else appearing there is installer
  residue. Check BOTH roots when the validator reports symlinks — the two
  intentional ones are the assistant's private-overlay `assistant-pipeline` and
  `desks`, which resolve and must stay. **`video-creator` pins four individual
  dirs from the same store** (`hyperframes-core`, `hyperframes-animation`,
  `cut-the-curve`, `oversized-cursor`) for its `create-tour`/`create-ad`/
  `create-explainer-video` leaves only — never the whole store, and the same
  never-copy/never-symlink rule applies (see `PROFILES.md` "Video authoring
  references"). A missing or unreadable entry there is a documented
  local-authoring fallback per that leaf's contract, not a runtime failure.

## Writer leaf migration

Writer v7 accepts `<write|edit|analyze>/<subject>/SKILL.md` below
`writer-pipeline`, with category `writing`, a named output and a form.
Each leaf owns Procedure, QA and Report; selected reference options need
local backing files and direct body links. `validate_writer_leaves` checks
this without changing Creator hands' verbs or media cost contract.
All six families now use leaves. Pre-draft advice uses only the root's
`references/consultation.md`; a request to edit/evaluate a target selects its
leaf. Unsupported combinations return to the requester, never a generic
fallback. Keep new families in separate layers rather than bundling them.

Article leaves distinguish source drafts from destination rendering. Keep
platform capability notes local to each leaf; do not promise note/X Article
Markdown import, unknown HTML support or untested embeds. Insertion markers
bind to stable production-note IDs and never imply generated assets. A missing
asset or editor step is not removed to manufacture a publication-ready result.
The shared Japanese core is a single `SKILL.md`, with no inspection resources
or scripts. Writer's leaves own document construction and checks. Historical
source attribution remains in `agents/README.md` and Git history.

Document leaves are `<write|edit|analyze>/document/`, including legacy briefs
named documentation/business-document. Formats are local form options, not
new profiles: README, guide, reference, report, minutes, proposal, slides,
release notes and issue. Keep absent records distinct from explicit decisions;
never infer owners, deadlines, release status or runtime success. Analysis
returns a report, not a replacement document. No additional inspection workflow
is added to a document leaf's checks.

Message leaves are `<write|edit|analyze>/message/` for email, chat, notification,
UI and error wording, not sending or system diagnosis. Preserve the sender's
intent and unknown outcome states; an existing retry control does not establish
safe repetition. Field labels/review notes are not recipient-facing text.
Use supplied context without new personal-record lookups. Source assertions,
actual runtime state and rendered UI fit are separate evidence questions.

Copy leaves are `<write|edit|analyze>/copy/` for landing pages, promotional mail
and announcements, including legacy marketing-copy briefs. Destination options
have operation-specific local references. Keep approved claims, offer terms and
disclosures; evidence conflicts are not solved by inventing proof or silently
weakening a protected promise. CTA requirements depend on the released purpose.
Marketer consumes accepted text unchanged, returns edits to Writer and keeps its
own inspection/Publish gate. Analysis is not new copy or a performance/legal
verdict. Script and unmigrated platform-post workflows remain separate.

Script leaves are `<write|edit|analyze>/script/`, with local narration/comic/
storyboard/screenplay/slide-script references. The actual producer contract
decides units, fields and limits; never impose genre-wide counts or timing.
Plain spoken files contain only intended words, not labels, fences or notes.
Keep `.production.md` and required raw exports consistent with the master.
Existing unit IDs remain stable; retired IDs are not recycled and any remapping
needs requester/consumer agreement. Changed words invalidate dependent evidence
until rechecked. Script analysis is a report, not a new production input. Each
leaf owns QA. Consultation may propose bounds but cannot present them as actual
producer requirements or measured evidence, nor execute a writing workflow.

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
launchd/              # LaunchAgents: multiplex gateway (all bots, one process),
                     #   local TTS engines
engines/             # tracked pin/lock definitions for local engines
                     #   (irodori-tts, qwen3-tts, stable-audio-3) — grouped
                     #   here; local/ still owns their untracked
                     #   weights/venvs and plugins/ still owns adapters
scripts/             # profile-secrets.sh (secrets.command helper),
                     #   brave-agent-sync.sh (real-profile browser clone),
                     #   validate-profile-skills.py
local/               # gitignored machine-local installs: TTS engines, the
                     #   brave-agent clone bundle
profiles/<name>/     # assistant, engineer, researcher, searcher, creator, writer, marketer,
                     #   image-creator (Creator's hands; leaves under
                     #   image-creator-pipeline/<verb>/<subject>/)
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
                     #   plan/creative/legacy decision leaves; validator-enforced);
                     #   writer: the japanese-writing language core (one
                     #   SKILL.md, five notation defaults) via the curated
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

default (CLI front door, neutral persona; hosts the multiplex gateway) +
four PRIMARIES with their own Telegram bots — assistant (messaging front
door + dispatcher home board), engineer, creator, marketer — + researcher /
searcher / writer (Workflow v5
specialists; writer and researcher also serve inbound A2A peer requests,
searcher has no A2A endpoint). The A2A peer graph and the multiplex rules
live in the critical rule above and PROFILES.md. Heavy work runs by default in resident chat sessions the
assistant starts through `specialist_call(kind="work")` (backed by
`assistant/scripts/resident-session.sh`) and
supervises conversationally; the kanban board is only for fire-and-forget,
cron-originated, mass-parallel, and `scheduled` work with a lean card
contract (no manifests/digests/probes — the v4 machinery is retired, see the
2026-08-06 rebuild). The card catalog is CLOSED and per-assignee: creator
(`anchored-image-batch`, `deterministic-render`), searcher
(`survey-enumeration`, `exhaustive-hunt`);
writer, engineer, marketer and researcher are card-free and refuse every card
(researcher's `claim-verification` unit was retired in the 2026-09 peer
rebuild — fact-checks travel through researcher's A2A peers).
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
land in `learned/` because every `config.yaml` sets `skills.create_dir:
skills/learned` (validator-enforced; a `category` nests as
`learned/<category>/<name>`) — NOT because of the `skill-topology` plugin, whose
`category: learned` rewrite only saw the flat `action: create` shape and missed
every `operations[]` create after upstream `72874b0675`. `learned/`, external
skills and Hermes bookkeeping stay ignored. Do not use `skip-worktree` for
managed skills: their changes must remain visible in `git status`. Promotion
from `learned/` to `technic/` is an explicit review step; move the complete
package, normalize its technic metadata and routing, pin it against curator
writes on the current machine, then commit it.

## Commands

- `./setup.sh` — install/refresh the hermes binary (uv venv); idempotent.
- `./scripts/validate-profile-skills.py --all` — validate managed/learned skill
  topology, metadata, routing registries, hands leaves, Creator's phase/subject
  references and Git ownership; add
  `--strict-git` in a staged/clean tree to fail on managed files that are
  still untracked.
- Tests: `PYTHONPATH=$(ghq root)/github.com/NousResearch/hermes-agent \
  $(ghq root)/github.com/NousResearch/hermes-agent/venv/bin/python -m pytest \
  plugins/ scripts/tests/ -q --import-mode=importlib`. The Hermes venv is
  required (plugins import `agent.*` / `tools.*`), and `--import-mode=importlib`
  is NOT optional: every plugin keeps its suite at `tests/test_plugin.py`, those
  basenames collide under the default import mode, and `__init__.py` cannot fix
  it because the plugin directories are hyphenated and so are not importable
  package names.
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
  `engines/qwen3-tts/requirements.lock` and must stay hash-locked.
- `launchd/irodori-tts-launchctl.sh {install,register,register-lexicon,voices,status,uninstall,purge}`
  — Irodori-TTS LaunchAgent (`irodori-tts` on `127.0.0.1:10103`), coexisting with
  qwen3-tts on `:10102`. Pins live in `engines/irodori-tts/pinned.conf` — named `.conf`
  because `**/*.env` is ignored and the pins must be tracked. It installs a git
  checkout of the upstream server plus a uv venv under the ignored
  `local/irodori-tts/`; `--python` is mandatory there, since uv otherwise picks
  3.12 and the pinned `sentencepiece` has no wheel for it. `register --voice PATH
  --id NAME` and `register-lexicon --file PATH` copy private data in, so those
  paths must never reach tracked config. `register-lexicon` refuses to write
  through a symlink, which is what the private overlay installs.
- `launchd/gateway-launchctl.sh {install,status,uninstall}` — the MULTIPLEX
  gateway LaunchAgent (`local.hermes.gateway.multiplex`), **one host only**
  (one bot token = one live connection, four bots in this one process). The
  default-hosted process serves assistant Telegram + Discord, the
  engineer / creator / marketer bots, the A2A endpoints (127.0.0.1:9902-9906),
  and the embedded dispatcher; `install` also unloads the legacy
  `local.hermes.gateway.assistant` agent. Discord requires
  the `AsyncSessionDB` regression guards for resolved upstream #40695.
  `install` re-renders + reloads = **restart** (new process re-reads `config.yaml`);
  to apply config you can also send **`/restart`** in chat (drain → `KeepAlive`
  respawns one). **Stop = `uninstall`** (plist `KeepAlive:true`; a plain `kill` just
  respawns). **Never** run `hermes gateway run`/`restart` in a terminal while it's
  loaded — the 2nd poller causes Telegram `getUpdates` 409 conflicts
  (verify a single instance: `pgrep -fl 'gateway run'` ⇒ exactly 1).
- `scripts/brave-agent-sync.sh {sync,check,path,remove}` — the cloned Brave
  bundle real-profile browsing launches (see the browser-stack rule above).
  `sync` re-clones when `/Applications/Brave Browser.app` changed version
  (the gateway launcher runs it before every start; run it by hand after a
  Brave update if you do not want to wait for a restart), `check` reports
  drift, `path` prints the `real_profile_binary` value. Signing in for the
  agent = log in to the **Hermes Agent** profile in the everyday Brave; there
  is no separate headful login step any more.

## Commits

Conventional Commits with the `(hermes)` scope: `feat(hermes): …`,
`chore(hermes): …`, `docs(hermes): …`, `refactor(hermes): …`.
