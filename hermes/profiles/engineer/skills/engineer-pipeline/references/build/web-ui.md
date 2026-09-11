# Implement the agreed UI

Engineer owns the UI direction and independent acceptance. OpenCode no longer
owns the migrated global UI/UX workflows or evaluation agents. Do not ask it to
load a removed Skill or delegate to a removed UI subagent.

Give OpenCode the accepted direction/tokens, existing design-system references,
approved copy/assets, relevant layouts/states, target devices and behavior.
Reference the concrete design decisions from [Plan](../plan/web-ui.md); do not
paste a generic style catalog or rebuild a second design workflow in the prompt.

Ask it to implement within scope, run project tests and check its own rendered
output when applicable. Browser tooling, functional tests and implementation-
time rendering remain available in OpenCode; their actual use follows the repo
and tool capabilities, not the retired global evaluation procedure.

Request the actual app URL, startup method, worktree/branch/build identity and
observed test/render results. Do not guess localhost ports or accept a screenshot
from another worktree. The CLI runner reaps its own child group at exit: do not
assume an OpenCode-started development server survives. Engineer may start and
supervise the approved local test server through its terminal/process tools,
recording its worktree, URL and process handle and stopping only that server
after QA. This is test execution, not target-code editing or deployment.
Engineer inspects the result through
[visual QA](../quality-assurance/web-ui.md), commissioning independent visual or
persona evaluation when appropriate. Send accepted findings back to this same
implementation conversation as specific corrections. Recheck affected evidence.

Prototype-only style tiles remain disposable and outside target code. They do
not become product components or authorize a broader build without Client approval.
