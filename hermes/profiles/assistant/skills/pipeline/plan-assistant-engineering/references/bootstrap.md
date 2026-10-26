# Bootstrap - Client decisions

Repository creation and workspace registration are separate from OpenCode's
work inside a repository. Get the user's approval of owner/name, visibility,
workspace Group and any starter/history choice before establishing them through
[GitHub operations](../../execute-assistant-engineering/references/github-ops.md).

## Choosing a starter

The choice runs as its own OpenCode plan session (read-only, in a job directory
under `.agent/`); it does not have to be the session that later builds. Assistant
need not choose a framework or design the skeleton first. Candidates are
discovered, never recalled from a memorized catalog. An unsuitable starter can be
worse than starting from scratch. Narrow from the cheapest evidence to the
dearest:

1. **Requirements.** Sort them into must, nice and unwanted. Ask the user only
   when a must-have is unclear: every later step is judged against this list.
2. **Candidates, in this order.** The user's own starters first (root
   `<name>-starter`, platform derivative `<root>-with-<platform>`, then
   variant), then the framework's official starter, then the community.
3. **Desk check to two or three.** From metadata alone: last commit, release
   cadence, how old open issues and PRs are, licence, CI and tests, template
   status, deprecated dependencies. Each dropped candidate gets one line saying
   why; do not score or weight them, a number would claim more than the
   evidence holds.
4. **Trial the leader** (two only when the desk check splits). In the plan
   session, in a scratch directory under the job directory, clone it, install,
   build and test. Own and official starters run as they are. A community
   starter is installed with lifecycle scripts disabled (for example
   `--ignore-scripts`) and the trial stops there if the build needs them: report
   that instead of running unknown scripts, since the run's environment is the
   person's.
5. **Decide.** Start from scratch when a must-have is unmet or most of the
   starter would be deleted; there is no fixed percentage. The user's explicit
   instruction outranks OpenCode's recommendation.
6. **Record** the choice in the plan as one row of its decisions: the starter
   chosen (or none), the reasons, and the one-line reasons for the rest, marked
   as OpenCode's proposal until the user approves.

Keeping history vs template instantiation is an explicit choice for the user;
preserve the intended upstream relationship. Concrete account/repository names
remain runtime context, not this guide.

## Establishing it

Confirm the Group with the `workspace_registry` `project` action (id = `<Group>`) and
optional organization with the `projects` action (kind = org); never infer an organization
from the GitHub owner. Default
repository visibility is private unless the user explicitly chooses public.
Deploy-target discussion does not authorize deployment or paid provisioning.

Once an established clone exists, plan its skeleton with an OpenCode plan run
on that clone; implementation follows the same implementation approval
contract. An empty remote/default branch bootstrap that cannot safely
produce a PR is an explicit blocker to resolve, never permission to push default.
