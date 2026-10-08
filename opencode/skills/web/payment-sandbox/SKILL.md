---
name: web-payment-sandbox
description: >-
  Use for bounded API/browser feasibility probes of hosted payment sandbox flows:
  registering a test payment method and reusing it for a later charge
  (決済サンドボックス検証, 決済登録, トークン再利用, 継続課金の可否調査, "payment sandbox
  probe", "hosted checkout test", "tokenized payment reuse"). Sandbox approval is
  never production, implementation or refund approval.
license: MIT
---

# Hosted payment sandbox probes

Use for bounded API/browser feasibility checks of payment registration and subsequent reuse. Do not treat sandbox approval as production, implementation, or refund approval.

## Procedure

1. Record the grant, allowed stores/endpoints, test instrument source, maximum artifact/charge attempts, and cleanup boundaries in private job scratch. Never put job handles, account IDs, approvals, or raw logs in this skill.
2. Resolve the existing scoped secret injection mechanism without printing secrets. Fail closed on a provider-specific DEVELOPMENT credential discriminator before every request. Do not store key fingerprints. Keep raw execution IDs and hosted URLs in mode-0600 scratch state; keep report IDs masked with correlation hashes.
3. Create a small probe harness with explicit endpoint and ownership allowlists, request timeouts, and exclusive durable intent files before each external POST. Separate commands for create, inspect, charge-once, and cleanup. Preserve consumed intents after errors; do not auto-retry unknown outcomes.
4. Preserve sanitized error messages, field paths, methods, masked endpoint paths, status codes, and non-JSON markers. Over-redacting every message destroys the evidence needed to understand a provider validation cascade. Test redaction offline with reflected credential, URL, email, and token fixtures.
5. Use a fresh browser/context, not an owner's account profile. A named browser daemon alone does not prove cookie isolation on every backend. Prefer a newly launched Playwright browser plus newContext for sensitive probes; never load storageState from another session.
6. Wait for actual rendered text or a terminal state, not just DOMContentLoaded. Payment logos can expand accessible button names; inspect the DOM before choosing exact-role-name selectors. Dropdowns may expose a dialog rather than ARIA options. Record visible text and screenshots even when a locator fails.
7. Use only the provider's public test instruments. For masked inputs, verify the final DOM value equals the complete test fixture before submission. Native value setters with normal input events can recover a broken automation fill, but they do not establish success until the actual form accepts the values. Never repeat a submitted registration blindly.
8. Inspect all nested authentication frames, including out-of-process iframes. An empty redirect page is not necessarily a failed challenge. Follow only the test challenge belonging to the probe, and persist a one-time authentication-submit intent when recovery is uncertain.
9. After hosted completion, GET the exact session, reusable credential, and customer. Distinguish session completion, token status, payment success, and application consent. Preserve resource type prefixes: a payment token is not interchangeable with a payment-method object.
10. Perform at most the explicitly authorized subsequent charge. Confirm the returned object by exact-ID GET and cross-check session/token/customer correlations. A failed reference-filter list GET does not prove the charge failed; never use it as a reason to blindly re-POST. Verify reference search capability before designing lost-response recovery around it.
11. Treat rendered channels as display evidence, not proof that every wallet can save or perform merchant-initiated charges. Separate generic future-payment consent from the app's amount, frequency, start date, and cancellation terms.
12. Probe expiry only within the agreed budget. Providers can enforce a minimum future interval beyond schema descriptions. Record a rejected short expiry as a negative boundary test, not a completed expiry/reissue test. Local replay guards are not provider idempotency proof.
13. Clean up only explicitly allowed owned artifacts. Distinguish token deactivation from financial cancellation, and resolve genuine scope conflicts rather than inferring authority from endpoint names. Read back token status and unchanged successful payment after cleanup. Retain audit/webhook evidence and list residual objects.

## Verification

Aggregate sanitized journals programmatically: deduplicate intent/response pairs; count all endpoint families including cleanup; correlate IDs by hashes; assert charge POST count and exact forbidden-mutation absence. Separate historical ACTIVE credential evidence from final CANCELED state. Inspect canonical screenshots directly; label loading captures and locator failures as automation diagnostics. Byte-scanning images is not visual secret verification. Report webhook delivery, positive reissue, provider idempotency, individual channel completion, and production entitlement as unproven unless each was actually exercised.
