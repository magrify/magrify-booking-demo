# Titan evidence brief — 2026-11-11

This brief separates repeatable validation from client-reported outcomes and
does not present sandbox activity as guest traffic. The local checks are labeled
**validation activity for Aguas de Ibiza/Bancal SF deployment patterns**. The
client records below establish qualitative sign-off and adoption; they do not
assert numeric traffic, conversion, or revenue without an export.

## Environment and provenance

- Repository base commit before this evidence pass: `63eff268305426ed0339a07845fc94d5eacbd7a0`.
- Working tree includes the resumable-booking test, model-comparison harness,
  cost cap, monitoring/load-test refinements, and client-outcome documentation.
- Frontend: `https://booking.magrify.com`.
- Payment validation: Stripe **Test mode** only. No real card or live charge was
  used; the sandbox checkout displayed Stripe's `Sandbox` indicator.

## Applied AI — reliability evidence

| Source | What it establishes | Observed result |
|---|---|---|
| `python -m pytest -q` in `agent-orchestrator` | Regression coverage for the booking graph, adapters, monitoring, and checkpoint resume | **23 passed** |
| `scripts/replay-stalled-approval.py` | Incident replay through the same saved workflow, not a fabricated customer incident | `awaiting_approval → confirmed`; `approval_resumed` event; `verified: true`; run `run_3272b3b2369d4ba59941b118eb35a83e` |
| `scripts/run-reliability-load-test.py --runs 50` | Monitoring ledger under bounded concurrent validation activity for Aguas/Bancal deployment patterns | 50 runs; 38 confirmed; 5 deliberately injected failures; 7 deliberately pending approvals; 0 attempt failures; 50 attempt successes; approval resume rate **38/38 (100%)** |
| Browser checkout at `booking.magrify.com` | End-to-end hold → Stripe checkout → persisted confirmation | Test booking `OS-K4DYZ9`; Full-Hookup RV Site, Site 101; Nov 20–22, 2026; due now **CA$149.10**; final page showed “You're all booked!” |

The 50-run completion rate is 38/50 (**76%**) because the harness
intentionally injects failed and awaiting-approval states. It is a reliability
and recovery rehearsal, not a production conversion rate. The failed and
pending counts are kept distinct from unexpected failures.

The deployed monitoring endpoint reads the tenant-scoped run/event ledger for
observed runs, confirmed completions, failures, stalled approvals, retries,
recovery, and last-seen timestamps. A live-traffic denominator requires a
tenant export after guests or callers use the deployment.

### What the validation predicts for customer traffic

The validation is deliberately shaped like the customer path (availability →
hold → approval → payment handoff → confirmation), so it tests the failure
boundaries that would otherwise turn into abandoned bookings or unworked
inquiries. It does **not** turn the rehearsal counts into production traffic.
The supported operational inference is:

- Resuming the same saved checkpoint should reduce lost approvals and duplicate
  guest work, which is expected to improve approval-to-confirmation completion
  and reduce abandoned checkouts.
- Recording stalls, retries, recovery, and handoff time should let staff find
  stuck work instead of discovering it from a guest complaint, which is
  expected to reduce time-to-recovery and time-to-human handoff.
- Tenant/property guards and the quality rubric should reduce wrong-property
  answers and unsafe tool calls, which is expected to improve qualified-inquiry
  quality and protect booking accuracy.
- The Haiku/Sonnet comparison gives a cost/latency routing decision: use the
  less expensive model for bounded classification when it passes the rubric and
  reserve the stronger model for cases that need more reasoning. The expected
  business effect is lower cost and faster first response without relaxing the
  same property-isolation checks.

The metrics to verify in a real tenant export are approval-to-confirmation rate,
abandoned-checkout recovery, time to human handoff, wrong-property correction
rate, qualified-inquiry rate, median response latency, and cost per completed
inquiry. Those are the customer outcomes this validation is designed to move;
the repository does not claim observed production deltas without the export.

## Applied AI — model cost/quality evidence

`scripts/run-model-comparison.py` made the smallest authorized live-provider
comparison: two fixed property-scoped cases, two Anthropic models, and a 96-token
output cap per call. It records model IDs, tokens, latency, and the existing
factual/property-scope rubric.

| Model | Mean quality | Mean latency | Input tokens | Output tokens |
|---|---:|---:|---:|---:|
| `claude-haiku-4-5-20251001` | 0.8334 | 943.1 ms | 209 | 71 |
| `claude-sonnet-4-5-20250929` | 0.7750 | 1,192.3 ms | 209 | 85 |

On this narrow fixture, the inexpensive model scored higher and was faster.
That is a routing signal, not a general benchmark: the stronger model lost one
lexical rubric point on the cabin case despite answering it correctly. The
structural prompt/context loop independently improved **0.80 → 1.00** over
three iterations by adding explicit tenant/property scope and an abstention
rule. No model weights were trained.

## Product Focus — client outcome evidence

Source: `docs/client-outcomes.md`, based on the engagement owner's recorded
client outcome.

- **Aguas de Ibiza** — client sign-off and adoption of the delivered hospitality
  guest-facing experience. The public workflow includes availability checks,
  hosted booking, offers, and direct reservation contact paths.
- **Bancal SF** — client sign-off and adoption of the delivered property-
  management inquiry experience. The public workflow spans consultation,
  proposal, contract review, onboarding, ongoing service, and annual review.

This supports a qualitative product outcome: operators accepted the scoped
direction and incorporated the delivered client-facing workflow into their
normal guest/property inquiry work. The repository does not contain a signed
email/CRM export with the approving person's role and date, nor analytics or
booking exports with a denominator. For a quantified interview claim, attach
the dated sign-off note and the tenant-scoped analytics/booking export; do not
infer those numbers from public pages.

The product decision was to keep the branded React/TypeScript guest flow while
moving inventory, policies, staff access, payments, and guest records behind
tenant-scoped configuration. That turns a one-off mockup into a reusable client
deployment without mixing properties.

## Banking — controls sandbox

`agent_orchestrator.banking_controls.review_lender_package` was exercised with
three realistic lender-package cases for `bancal-sf-portfolio`:

1. Complete package → `ready_for_credit_review` → human credit review.
2. Missing inspection report and insurance → `needs_more_documents` → request
   missing documents.
3. Complete package with insurance expiring within 30 days → `exception_review`
   → named human underwriter.

All three cases require an audit event. The adapter records the operations
analyst, underwriter, human credit committee, and compliance officer ownership
and explicitly returns `credit_decision: not_made_by_agent` and
`regulatory_filing: not_made_by_agent`. This is controls-sandbox evidence paired
with lender-facing underwriting support, inspections, reconciliations,
payment/ACH controls, and approvals; it is not a claim of bank-side credit or
regulatory ownership.

## Interview-ready resume bullets

**Applied AI Focus:** Built a tenant-scoped LangGraph booking workflow with
resumable approvals, Stripe test checkout, SQLite event-ledger monitoring,
retries, and model-context evals; replayed a stalled approval to the same saved
checkpoint and verified a persisted booking confirmation, with 50-run recovery
validation and 38/38 approval resumes.

**Product Focus:** Turned operator feedback into reusable React/TypeScript
booking experiences with tenant-isolated inventory, policy, payment, and
branding configuration; Aguas de Ibiza and Bancal SF signed off on and adopted
their delivered client-facing workflows.

## Boundary to state plainly

The strongest verified evidence is a successful sandbox checkout, a repeatable
approval-recovery/monitoring rehearsal, a bounded live-provider comparison, and
qualitative client sign-off/adoption. Production guest traffic, conversion,
revenue, a bank-side credit decision, and a regulatory filing remain outside
the evidence set until the corresponding client exports or engagement records
are attached.
