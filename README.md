# Magrify Booking Platform

Magrify builds the booking and property operations platform for independent short term rental owners, campgrounds, cabins, glamping operators, and small hospitality teams. It covers direct reservations, availability, rates, guest records, staff operations, payments, refunds, email, calendar feeds, and channel synchronization in one deployment.

Each client deployment is configured for the operator's own property, policies, inventory, payment account, email domain, and branding. The application does not ship with a shared property catalog or fixed client data.

## Magrify resources

Magrify is the product and engineering team behind this platform. Learn more about [booking-ready websites](https://magrify.com/booking-ready-websites/), [hospitality automation](https://magrify.com/hospitality-automation/), and [campground website design](https://magrify.com/campground-website-design/), or [contact Magrify](https://magrify.com/contact/) about a client deployment.

## Client branding

Set `VITE_CLIENT_NAME` to the property or operating company name. Set `VITE_CLIENT_LOGO` to an image path under `public/` when the client has a logo. Without those variables, the interface uses Magrify as the platform brand.

## Production setup

1. Run `npm ci`.
2. Create an isolated Convex deployment and set `VITE_CONVEX_URL`.
3. Set `VITE_MAGRIFY_PROFILE=production`.
4. Configure the client's property, units, rates, policies, staff identities, email provider, and Stripe account in Convex.
5. Set `SITE_URL` and deploy the frontend to Cloudflare Pages or another static host.
6. Run `npm run build` and `npm run typecheck` before publishing.

## Public engineering map

This repository includes the working agent control plane in
[`agent-orchestrator/`](./agent-orchestrator/). The following implementation
map is intentionally concrete so a reviewer can trace each capability to
source rather than relying on a technology list.

| Capability | Where to verify it |
| --- | --- |
| OpenAI Agents SDK | [`agent_orchestrator/agents.py`](./agent-orchestrator/agent_orchestrator/agents.py) — guarded agents and external-side-effect guardrails |
| LiveKit Agents | [`livekit_agent.py`](./agent-orchestrator/livekit_agent.py) — phone concierge tools and secure payment handoff |
| LangGraph | [`agent_orchestrator/workflows.py`](./agent-orchestrator/agent_orchestrator/workflows.py) — booking and prospector state graphs |
| LangChain | [`agent_orchestrator/workflows.py`](./agent-orchestrator/agent_orchestrator/workflows.py) — typed runnable context chain |
| Deep Agents | [`agent_orchestrator/agents.py`](./agent-orchestrator/agent_orchestrator/agents.py) — read-only research adapter |
| Claude SDK | [`agent_orchestrator/gateway.py`](./agent-orchestrator/agent_orchestrator/gateway.py) — provider-neutral Anthropic adapter |
| Backend Python | [`agent_orchestrator/app.py`](./agent-orchestrator/agent_orchestrator/app.py) and [`enrichment_worker.py`](./agent-orchestrator/agent_orchestrator/enrichment_worker.py) |
| Vectorless RAG | [`convex/voiceKnowledge.ts`](./convex/voiceKnowledge.ts) and [`agent_orchestrator/store.py`](./agent-orchestrator/agent_orchestrator/store.py) — tenant/property-scoped structured retrieval |
| Agent evals and observability | [`agent_orchestrator/evaluations.py`](./agent-orchestrator/agent_orchestrator/evaluations.py), run event storage, tracing, and redacted observability endpoints |
| Model gateway | [`agent_orchestrator/gateway.py`](./agent-orchestrator/agent_orchestrator/gateway.py) — OpenRouter routing with OpenAI fallback and task-based model selection |
| Data controls | [`agent_orchestrator/data_controls.py`](./agent-orchestrator/agent_orchestrator/data_controls.py), [`phone_policy.py`](./agent-orchestrator/agent_orchestrator/phone_policy.py), and Convex tenant scoping |

The public copy excludes API keys, local databases, customer records, and
deployment-only environment files. Provider credentials are supplied at
runtime through secret managers.

Magrify created and maintains this platform. The MIT license in `LICENSE` preserves the original copyright and permission notice required for redistributed source.
