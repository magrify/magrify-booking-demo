# Magrify + CartelBot agent orchestrator

This service is the provider-neutral agent control plane used by both products.
It combines:

- LangGraph for durable, resumable workflows;
- LangChain for typed tool/context composition;
- Deep Agents for long-running CartelBot research jobs;
- the OpenAI Agents SDK for guarded tools, handoffs, and tracing;
- the Anthropic Claude SDK for direct Claude runs;
- a model gateway with OpenAI, Anthropic, and OpenRouter adapters;
- vectorless, tenant-scoped retrieval backed by SQLite;
- approval gates, audit events, and evaluation records.

Completed runs expose redacted trace events and deterministic safety evaluations
at `GET /v1/runs/<run_id>/observability`; the endpoint is authenticated with
the same service token.

`GET /v1/reports/nightly?tenant_id=...` returns the last-24-hour run,
confirmation, recovery, failure, and attributed-revenue totals for operations
reporting.

`GET /v1/monitoring/reliability?tenant_id=...&window_hours=24` returns the
observed operating view for the selected tenant: completion and failure rates,
stalled approvals, approval-resume rate, retry failures, recovery-due runs, and
the underlying event counts. It reads the durable run/event ledger, so the
report is empty until the deployed workflow receives real traffic. The booking
graph also records a `workflow_state` event for every completed or approval-
resumed run, making the post-launch observation path explicit.

`python scripts/run-reliability-load-test.py --runs 100` exercises the same
tenant-scoped event ledger with bounded concurrent validation traffic. It
intentionally produces confirmed, failed, and awaiting-approval cases so the
monitoring math can be checked under contention before a deployment receives
real traffic. Its output is labeled `synthetic_validation`; it is not a
production reliability claim.

`python scripts/replay-stalled-approval.py` replays one incident through the
same event schema: it detects an `awaiting_approval` run, records the operator
recovery, resumes it, and verifies a persisted `confirmed` state. This is an
incident-response regression artifact; it is not presented as a customer
incident.

`GET /v1/evals/prompt-context?iterations=3` runs the deterministic prompt and
context optimization loop. It compares a baseline prompt with a tenant- and
property-scoped prompt on fixed cancellation and amenity cases, reports the
mean score and improvement, and selects the best variant. This is a repeatable
training-style loop for prompt/context changes; it does not claim model-weight
training or send guest data to a provider.

The search adapters also expose concrete retrieval patterns for interviews:
`GET /v1/knowledge/vector-search` runs a small tenant-filtered local vector
index over structured knowledge rows, while `GET /v1/knowledge/file-search`
searches only bounded, tenant-specific Markdown, text, JSON, and CSV files when
`AGENT_FILE_SEARCH_ROOT` is configured. Both adapters are optional and keep
the existing vectorless path intact.

`GET /v1/evals/model-context` runs the same cases through the configured model
gateway and scores returned text for expected facts, forbidden cross-property
leakage, and explicit scope. The response labels itself `live_provider` when a
provider key is configured and `dry_run` otherwise; dry-run output is wiring
validation, not a claim of model quality. If the provider rejects a request for
quota or billing, the response is labeled `provider_error` with per-case error
types instead of silently falling back to a fabricated score.

The service defaults to a safe dry-run when no provider key is configured. It
never sends outbound messages, publishes content, charges cards, or mutates a
booking without an explicit approval token from the calling product.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m agent_orchestrator.app --port 8788
```

Set `AGENT_ORCHESTRATOR_TOKEN` for service-to-service authentication. Provider
keys stay server-side and are never returned by the API.

Set `OPENAI_AGENTS_TRACING=true` to export OpenAI Agents SDK traces. Guardrails
block approval-bypass/secret-exfiltration instructions and unsafe external-side
effect claims; the redacted run event stream remains available independently.

LangGraph checkpoints are persisted in SQLite by default at
`agent-orchestrator-checkpoints.sqlite3`; set `AGENT_CHECKPOINT_PATH` to place
them on durable storage. Approval retries reuse the run's checkpoint thread.

The service retries a failed workflow up to three times, records each attempt,
and returns a failed run without performing an external side effect. Configure
`AGENT_STORE_PATH` for a durable SQLite location, `MODEL_PROVIDER` as `openai`,
`anthropic`, or `openrouter`, and the corresponding provider key. Magrify and
CartelBot call this service with approval required by default.

## CartelBot enrichment worker

`POST /v1/cartelbot/enrich` runs the separate Python worker for bounded CSV or
JSON lead enrichment. It can fetch public website metadata (with private and
loopback destinations rejected), calculate a transparent ICP fit score, and
return completeness/high-fit evaluation metrics. It never contacts a prospect;
the Cloudflare Worker keeps outreach, publishing, and handoffs behind human
approval.

The CartelBot LangGraph now models `discovery → enrichment → fit_score →
approval → outreach_ready → reply_classification → meeting_booked →
revenue_attributed`. It produces drafts and attribution records only; it does
not send outreach or publish content without the approval path.

Set `ENABLE_DEEPAGENTS=true` with `DEEPAGENTS_MODEL` and a server-side provider
key to run the read-only Deep Agents research memo during enrichment. Without
those credentials the graph remains fully functional and records that the
optional research pass is not configured.

The Deep Agents pass now has two concrete read-only tools: bounded workspace
file search and lead-record inspection. It can plan a research job, inspect
tenant-scoped evidence, and return a memo without sending outreach, publishing
content, or changing CRM state. The tools are isolated in
`agent_orchestrator/deepagents_tools.py` so they can be replaced by a hosted
file-search provider later.

The CartelBot Worker emits privacy-safe PostHog-compatible events for run
starts, enrichment, approval decisions, and CRM stage changes when the
`POSTHOG_API_KEY` secret is present. `POSTHOG_HOST` defaults to the US endpoint;
raw emails, phone numbers, tokens, and secrets are filtered before capture.

Example body:

```json
{
  "tenant_id": "cartelbot:workspace",
  "icp": "independent campground and cabin operators",
  "leads": [{"name": "Example", "company": "Example Parks", "website": "https://example.com"}],
  "fetch_websites": false
}
```

## Magrify booking concierge

The booking workflow supports availability lookup, a temporary hold, payment
handoff, confirmation, and abandoned-payment recovery through the
`BookingAdapter`. Configure `MAGRIFY_CONVEX_HTTP_URL`, `MAGRIFY_API_KEY`, and
`MAGRIFY_SITE_URL` to enable real booking calls. The key must be a scoped
Magrify automation key with read/write booking permissions.

LiveKit Agents can send normalized phone turns to `POST /v1/livekit/booking`:

```json
{
  "tenant_id": "property-slug",
  "input": {
    "property_slug": "property-slug",
    "unit_type_slug": "rv-site",
    "check_in": "2030-07-10",
    "check_out": "2030-07-13",
    "adults": 2,
    "children": 0,
    "message": "Need a three-night stay"
  }
}
```

The response is the same run record used by website and CRM inquiries. A
temporary hold requires `hold_requested=true` and an approved run (or an
explicitly non-approval-gated service policy); payment is always handed off to
the hosted booking checkout. Approving a run resumes the graph with side
effects enabled, so the approval endpoint is the only path that can create a
temporary hold through the adapter.

For property-policy, amenity, and seasonal questions, the worker uses
`POST /v1/livekit/knowledge`. Knowledge is tenant-scoped and vectorless: the
orchestrator searches structured property rows by property slug and keywords.
When the orchestrator is not hosted, the worker falls back to Convex's
token-authenticated `/agent/knowledge` bridge, which also includes the
property's public settings and configured unit amenities.

To run the voice worker locally after installing `requirements-livekit.txt`,
use `lk agent dev livekit_agent.py`. Set `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and
`LIVEKIT_API_SECRET` plus the orchestrator URL/token. When the provider-neutral
orchestrator is not hosted, the worker can call the narrow Convex bridge
directly with `MAGRIFY_CONVEX_HTTP_URL` and `MAGRIFY_LIVEKIT_TOKEN`; the bridge
delegates to the same availability query and hold mutation as the guest UI.
Deploying to LiveKit Cloud still requires linking a LiveKit project and
configuring a SIP trunk/phone number.

## Verified end-to-end booking evidence

The approval-resume smoke test verifies the failure mode that matters most in
the booking path: an approval decision resumes the same LangGraph thread from
its saved SQLite checkpoint instead of only changing a status label. The test
then follows the checkout handoff through the `checkout.session.completed`
webhook acknowledgment and checks that a confirmation is persisted. It is a
test booking, not a claim of customer-scale traffic or a bank-side payment
decision.

After launch, operators can use the reliability endpoint to watch the same
workflow in production. The first signals are observed run volume, confirmed
completion rate, failed runs, stalled approvals, approval-resume rate, retry
failures, recovery-due runs, and the last event timestamp. The service keeps
these measurements tenant-scoped and redacts guest PII before writing events.

## Operator-driven product scope

The initial operator request was an example booking experience for one property
with client branding and property-specific inventory. That request exposed a
product tradeoff: a one-off mockup would demonstrate the screen but would not be
reusable for the next operator, while a shared catalog would risk leaking or
mixing property data. The shipped direction keeps the branded guest pages and
React/TypeScript booking workflow, but moves inventory, policies, payment
settings, staff access, and guest workflows behind tenant-scoped configuration.
The demo is therefore an acceptance artifact for the operator-facing path and
the reusable deployment is the follow-on implementation path; the repository
does not claim operator sign-off or staff adoption until those events are
recorded by the client deployment.

`POST /v1/monitoring/adoption/events` records the next engagement milestones:
`operator_feedback`, `demo_presented`, `operator_signoff`,
`client_signoff`, `deployment_configured`, `staff_training_completed`,
`staff_workflow_used`, and `client_adoption_observed`. `GET
/v1/monitoring/adoption` reports which milestones are actually observed, so the
repo distinguishes a shipped demo from real adoption instead of implying
sign-off.

`python scripts/run-operator-session.py` drives a complete local operator
rehearsal through the same API: it submits an ICP and lead, observes the
approval gate, approves draft preparation, records the engagement milestones,
and reads the resulting adoption and reliability reports. Its output is labeled
`operator_rehearsal`; it is designed to be rerun against a deployed URL when a
real operator is available.

## Banking-controls sandbox

`agent_orchestrator/banking_controls.py` demonstrates a lender-package review
workflow using the same approval-first posture: it checks for a rent roll,
operating statement, inspection report, and insurance; routes missing documents
or exceptions to the appropriate human reviewer; and explicitly records that no
credit decision or regulatory filing was made by the agent. This is a technical
readiness sandbox, not a claim of prior bank-side credit authority.
