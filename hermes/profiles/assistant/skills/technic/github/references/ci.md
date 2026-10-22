# CI: waiting for it and reading a red run

## Waiting

Right after a push or a retarget the checks may not be registered yet: no
pending check is not green. Read `github_pr` `view` again until nothing is
pending and the number of checks reaches the usual count for that
repository.

## Red: the code or the infrastructure?

Before calling a failed check a code problem, read the run: `github_repo`
`runs` then `run` with its id (jobs, failed steps, the end of their log).
A pattern that is not the code: jobs that end within seconds with no failed
step and no log, the rest skipped, the same on every branch. That is usually
a billing or quota block (GitHub's run page then says the job was not
started because of failed payments or a spending limit). The tools cannot
read that message for a job that never started, so say what the pattern
shows, ask the user to confirm on the run page, name the owner's Billing &
plans page, and leave the spending decision to them.

A failure that looks transient (a runner lost, a network timeout) can be
re-run with `run_rerun` on its card; a real failure goes back to whoever
changes the code.
