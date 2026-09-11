# Rendered UI acceptance

Read the accepted direction and [shared design knowledge](../shared/design-catalog.md).
Use actual pixels and behavior, not code-only inspection or a build-agent claim.
Do not mistake a style preference for a measured defect.

1. Confirm the exact URL and worktree/build it serves using supplied startup
   output, project instructions and observed content. No guessed ports or `.env`
   scans for URLs. Browser harnesses can decorate document titles; verify actual
   URL/content/build identity rather than exact title equality alone.
2. Use Engineer's isolated browser_exec session. Keep a unique job/role-specific
   session name if naming one explicitly; never reuse global `main`/`ui-review`
   names or attach to another process's CDP. No real-account profile, copied
   cookies or production-side effects. Prepare test accounts when needed.
3. Observe desktop/mobile (1440x900 and 375x812 by default, project targets win)
   and the changed interaction/empty/loading/error states. Native screenshot
   attachments are inspected directly; use vision_analyze only if native vision
   is unavailable. A recorded screenshot without a look is not a completed check.
4. Check grouping, alignment, readable type/hierarchy, contrast, focus, responsive
   overflow and intended visual direction. Measure when claiming numeric values;
   label estimates and unsupported checks. Collect console/page errors if supported.
5. For substantial changes, request a separate ui-review resident conversation
   through specialist_call(target="ui-review", kind="work"). Supply exact URLs,
   build identity, intended direction, test states, permitted operations and a
   private evidence location. Small fixes may be checked inline.
6. Judge the report, return concrete corrections through [Build](../build/web-ui.md),
   then continue the same reviewer conversation to check the changed build.
   Keep finding IDs stable. Reopen acceptance when accepted outputs change.

Close only sessions you own. Do not share test-state mutations between concurrent
checks; separate test accounts/fixtures or serialize them. Never test actual
payments, production sends or destructive real-data operations merely because
a UI is clickable. Browser tooling and profile isolation are not a sandbox.

Report actual screenshots, viewports, states, findings and unverified criteria.
Visual acceptance is distinct from [persona testing](ux-persona.md), functional
test results and Client approval. An unverified required criterion cannot pass.
