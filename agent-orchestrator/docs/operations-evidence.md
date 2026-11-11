# Agent operations evidence

## Booking test and production monitoring

The booking smoke test exercises the failure mode that matters in a human-
approval workflow:

1. A booking run is persisted in SQLite with a LangGraph thread ID.
2. Approval changes the run and resumes the same graph from its saved
   checkpoint.
3. The booking adapter hands the guest to hosted checkout; the test webhook
   returns `200 OK`.
4. The run reaches a persisted confirmation state and records an evaluation,
   workflow-state event, and completion event.

The test proves state continuity and confirmation persistence. It does not
claim production traffic, a card charge, or bank-side credit approval.

`python scripts/replay-stalled-approval.py` exercises the incident-response
path and verifies `awaiting_approval -> confirmed` with an `approval_resumed`
event. It is a repeatable incident replay, not a fabricated customer incident.

After deployment, `GET /v1/monitoring/reliability` reads the tenant-scoped run
and event ledger and reports:

- observed runs and confirmed completions;
- failure, stalled-approval, and recovery-due rates;
- approval decisions and approval-resume rate;
- retry successes and failures;
- event counts and the last observed event/run timestamp.

These metrics are intentionally based on real requests to the orchestrator.
They remain empty until a deployment receives traffic, which keeps the resume
honest about what is tested versus what is observed after launch.

`python scripts/run-operator-session.py` drives the HTTP API as an operator: it
submits an ICP and lead, observes the approval gate, approves draft preparation,
records deployment milestones, and reads adoption and reliability back. The
session labels itself `operator_rehearsal`; actual sign-off still requires a
client event.

## Prompt and context optimization

`GET /v1/evals/prompt-context` runs a deterministic optimization loop over two
prompt variants. The baseline uses the supplied property context; the selected
variant adds explicit tenant/property scope and a rule to abstain when context
does not answer the question. The fixture set covers cancellation and amenity
questions across two properties and scores both factual-term coverage and
scope-boundary enforcement.

This is a repeatable training-style loop for prompt/context changes. It records
the baseline score, selected score, improvement, and per-case results without
claiming model-weight training or sending guest data to a model provider.

## Operator decision record

The operator asked for an example booking experience for a property with its
own branding, inventory, policies, and checkout path. A one-off mockup would
demonstrate the screen but would not be reusable; a shared catalog would risk
mixing property data. The implemented tradeoff keeps the branded React/
TypeScript guest workflow while moving inventory, policies, payments, staff
access, and guest workflows behind tenant-scoped configuration.

The demo is the acceptance artifact for the operator-facing path. The next
engagement step is deployment configuration, staff access, payment connection,
and observed workflow usage. The repository does not claim operator sign-off
or staff adoption until the client deployment records those events.

## Banking boundary

The accompanying work history supports lender-facing commercial real estate
operations: underwriting support, property inspections, reconciliations,
vendor/payment controls, ACH onboarding, and approval workflows. Those are
transferable controls for a banking engagement. This project does not claim
ownership of a bank's credit decision, underwriting approval, or regulatory
filing; those are the domain areas to learn and validate with Titan's platform
and client stakeholders.
