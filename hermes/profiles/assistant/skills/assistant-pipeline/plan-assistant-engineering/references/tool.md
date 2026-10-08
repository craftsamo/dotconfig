# Script, CLI and automation - Client guide

Describe input, expected output, failures that matter, where the tool runs and
what data/services it touches. OpenCode proposes the runtime and implementation
from the existing environment. A small tool does not need a framework, fixed
phase count or a compulsory Issue.

Distinguish implementation from installing a scheduled job, starting a service
or enabling recurring side effects. Those operations need explicit scope and
safe verification. Credentials remain in Keychain-backed environments, not code
or public logs. Preserve the workspace's private-data boundaries.

Durable repository work normally ends in a PR. If a throwaway/local-only output
was explicitly requested, state that boundary rather than inventing a remote
repository or PR. For a new durable repository, use bootstrap.md with the user.

Acceptance: a representative permitted invocation has observed output/exit
behavior, failure cases are covered, and any claimed installation/scheduled run
has its own evidence. A manual run alone is not proof a schedule worked.
