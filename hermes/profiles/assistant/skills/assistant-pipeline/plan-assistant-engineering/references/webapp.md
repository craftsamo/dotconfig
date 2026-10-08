# Stateful Web application - Client guide

Describe the user journeys, who may access which information, existing data,
external integrations and operational constraints. Ask about real user needs,
not database schemas the user would have to inspect code to answer. An OpenCode plan run
investigates and proposes the technical design, dependencies and sequence.

Preserve known hosting/account/budget decisions. Paid services, destructive
data changes, production access and deployment need their own scoped approval;
an implementation approval is not blanket permission for them. Prepare safe
test accounts/data when journeys need authentication. Never share personal
browser cookies or send credentials in a public Issue or PR.

Acceptance: named journeys have actual execution evidence, auth/data boundaries
have relevant tests, migration/recovery claims are supported, and UI evidence
matches the changed build. Missing external-service validation stays explicit.
Repository implementation ends with a PR. Do not automatically register an
epic, Issues or a project board because an application is stateful or large.
