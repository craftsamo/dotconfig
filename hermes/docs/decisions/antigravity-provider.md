# Antigravity as a direct-OAuth provider plugin

Status: in force
Owner doc: docs/models-auth.md "Google Antigravity"

## Decision

Google Antigravity reaches Hermes as `plugins/model-providers/antigravity`, a
model-provider plugin in this repo that holds its own Google OAuth login in
the credential pool and calls Antigravity's Cloud Code endpoint directly, the
same way OpenCode's `opencode-antigravity-auth` plugin does. It is picked by
hand and named in no fallback chain.

## Why

- One mechanism for both harnesses: OpenCode already uses the direct OAuth
  route, and the person wanted Hermes to match it rather than run a second,
  differently shaped integration.
- The catalog's Antigravity plugins all drive Google's `agy` CLI as a
  subprocess. That route passes the gateway's whole environment, Keychain
  keys included, to the child, writes the system prompt into a workspace
  file, re-maps the CLI's own tools onto Hermes tools, and gives no account
  pool. Google's terms do not exempt a wrapped `agy` either, so it lowers the
  risk of a ban less than it seems.
- Not a runtime patch: upstream removed its own native Antigravity provider
  (and Gemini CLI OAuth), and the files that integration touched have changed
  across hundreds of commits since. The runtime's provider-plugin seams
  (`auth_handler`, `refresh_credential`, `create_client`) carry a provider
  with no core edit, and the runtime's native Gemini client already holds the
  request and response translation, so the plugin adds only what differs.
- The OAuth client secret lives in the Keychain, not in the repository: it is
  a public value of the Antigravity client, but a tracked copy trips secret
  scanning, and splitting the string to slip past a scanner is not something
  to keep in this repo.

## Scope

The rule covers Hermes' own model selection. A run the Assistant drives in
the person's OpenCode uses OpenCode's specialist routes, which lead the
explore, worker and searcher subagents with Gemini Flash on Antigravity and
pass a refused or spent step to the next one. That use is accepted: the
person chose those routes for OpenCode as a whole, and a Hermes-driven run
inherits them rather than adding a chain of its own.

## Do not

- Put `antigravity` in a `fallback_providers` chain or a profile's `model:`
  without deciding again: every request is a third-party use that Google's
  terms forbid, and a chain would send it unattended.
- Add `google` to the Assistant's `opencode.allowed_providers` without
  deciding again: the caller's own-model check folds speed tiers and
  snapshots, not Antigravity's spelling of a Claude model.
- Copy the client secret into the repository, in one piece or several.
- Replace the plugin with a runtime patch to recover the removed upstream
  provider: its code assumed a single stored login and core files that no
  longer exist in that form.
