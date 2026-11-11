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
