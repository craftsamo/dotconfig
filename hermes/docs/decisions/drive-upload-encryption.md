# Sensitive files go to Drive encrypted with an age key pair

Status: in force; decryption by Hermes superseded by
[google-tools-plugin.md](google-tools-plugin.md)
Owner doc: [Google tools](../google-tools.md#sensitive-files-and-encryption)

## Decision

A file in a sensitive area of the Workspaces layout goes to Drive only
encrypted with age, to the public keys the profile's google-tools
`age_recipients` names, before anything reaches Google: google-tools encrypts
every upload under its `encrypt_dirs`, and google-tools-guard refuses an upload
from a sensitive area those settings do not cover, and any mail attachment from
one. Whether a file is sensitive comes from the layout's `sensitive` flag, never
from area names in the guard or from a per-call option. The secret key is the
person's, with a copy kept outside the Mac; Hermes never reads it and never
decrypts.

## Why

- **What it protects.** The threat is the file being read outside the Mac:
  on Google's side, through a taken-over account, or through a sharing
  mistake. A Mac that is taken over already holds the clear files, so a
  secret key in its Keychain weakens nothing that encryption could protect.
- **A key pair, not a passphrase.** An upload needs only the public keys, so
  no secret is ever handed to the agent. A passphrase would be read on every
  upload, and the gateway can never prompt for one.
- **Hermes never decrypts.** Decrypting would put the secret key within the
  agent's reach; the person opens a file with `age -d` when they need it.
- **age.** It is already in the Brewfile, its files open with the plain `age`
  command anywhere, and it encrypts to several keys at once, so a backup key
  kept elsewhere opens every file without the Mac. A format of the plugin's
  own would need the plugin to read its own files.
- **Not the Secure Enclave.** An enclave key (`age-plugin-se`) cannot be
  copied out, so the copy outside the Mac would have to be a second key, and
  it adds a dependency.
- **If the secret key sits in the Keychain, its kind and `--no-env`.** The
  web3 wallet reads every Keychain item of kind `MNEMONIC` or `PRIVATE KEY` as
  a wallet, and `secret env` injects every item not marked `--no-env`; a kind
  of its own and that flag keep the key out of both.
- **No switch.** A per-call option would let a model send a sensitive file in
  the clear; refusing when the settings do not cover the area is the only way
  around encryption.
- **The `.age` name.** Drive search keeps working, at the cost of the name
  hinting at the content; a random name would need a local index to find
  anything again.
