# Sensitive files go to Drive encrypted with an age key pair

Status: in force
Owner doc: docs/google-access.md "Sensitive files"

## Decision

`google_drive` `upload` encrypts a file in a sensitive area of the Workspaces
layout with age, to every public key in a recipients file, before anything
reaches Google. The secret key is one Keychain item for every profile, with a
copy the person keeps outside the Mac. Whether a file is sensitive comes from
the layout's `sensitive` flag, never from area names in the plugin or from a
per-call option.

## Why

- **What it protects.** The threat is the file being read outside the Mac:
  on Google's side, through a taken-over account, or through a sharing
  mistake. A Mac that is taken over already holds the clear files, so a
  secret key in its Keychain weakens nothing that encryption could protect.
- **A key pair, not a passphrase.** An upload needs only the public keys, so
  the secret key is read only to decrypt. A passphrase would be read on every
  upload, and the gateway can never prompt for one.
- **age.** It is already in the Brewfile, its files open with the plain `age`
  command anywhere, and it encrypts to several keys at once, so a backup key
  kept elsewhere opens every file without the Mac. A format of the plugin's
  own would need the plugin to read its own files.
- **The Keychain, not the Secure Enclave.** An enclave key (`age-plugin-se`)
  cannot be copied out, so the copy outside the Mac would have to be a second
  key, and it adds a dependency. The Keychain item is the same kind of store
  the OAuth token already uses.
- **Its kind and `--no-env`.** The web3 wallet reads every Keychain item of
  kind `MNEMONIC` or `PRIVATE KEY` as a wallet, and `secret env` injects every
  item not marked `--no-env`; a kind of its own and that flag keep the key out
  of both.
- **No switch.** A per-call option would let a model send a sensitive file in
  the clear; refusing when no key is set up is the only way around encryption.
- **The `.age` name.** Drive search keeps working, at the cost of the name
  hinting at the content; a random name would need a local index to find
  anything again.
