# Client outcome records

The following client outcomes are supplied by Magrify's owner and are included
as deployment evidence, not invented case-study metrics.

## Aguas de Ibiza

- Public client surface: [aguasdeibiza.com](https://aguasdeibiza.com)
- Engagement type: hospitality and resort guest-facing web experience.
- Outcome recorded by Magrify: client sign-off and adoption of the delivered
  experience, as reported by the client engagement owner.
- Public workflow context: the site exposes guest-facing availability checks,
  a hosted booking engine, offers, and direct reservation contact paths. This
  is consistent with the guest funnel the Magrify workflow instruments.
- Evidence boundary: no conversion, revenue, or traffic metric is asserted here
  without a report exported from the client's analytics system.
- Traffic and stakeholder metrics to collect: booking CTA clicks, availability
  checks, inquiry-to-booking conversion, abandoned checkout recovery, direct
  versus assisted bookings, and response time from guest inquiry to staff
  handoff. No numeric traffic or revenue value is asserted without an export
  from the client's analytics or booking system.

## Bancal SF

- Public client surface: [bancalsf.com](https://bancalsf.com)
- Engagement type: property-management web experience and inquiry path.
- Outcome recorded by Magrify: client sign-off and adoption of the delivered
  experience, as reported by the client engagement owner.
- Public workflow context: the site exposes consultation, proposal, contract
  review, onboarding, ongoing services, and annual review stages. This is
  consistent with the operator and inquiry lifecycle the Magrify workflow
  supports.
- Evidence boundary: no lead, revenue, or occupancy metric is asserted here
  without a report exported from the client's analytics system.
- Traffic and stakeholder metrics to collect: consultation CTA clicks, inquiry
  submissions, qualified inquiry rate, response time, staff handoff completion,
  listing engagement, portal activity, maintenance-request routing, and repeat
  contact volume. No numeric lead, occupancy, or revenue value is asserted
  without an export from the client's analytics or property-management system.

## How this maps to the operator workflow

These engagements replace the local rehearsal as the client-outcome examples:
the operator reviewed a working client-facing surface, signed off on the scoped
direction, and adopted the deployed experience in day-to-day guest or property
inquiry work. The repository keeps the sign-off and adoption event capture
available so deployments can record the approving role, conditions, first
observed use, and real traffic totals without fabricating metrics.

## Product decision and expected operational change

The approving stakeholders were the client owners/CEO-level leaders for the two
engagements. Their shared tradeoff was speed to a branded experience versus a
workflow staff could safely reuse. Magrify kept the branded React/TypeScript
surface, but moved inventory, policies, payments, records, and staff actions
behind tenant configuration rather than hard-coding one client.

That decision changes the operator's day-to-day path in a concrete way: staff
can work from one shared availability/inquiry flow, preserve the handoff and
approval state, and reuse the same operating pattern as the property or service
changes. For Aguas de Ibiza, the expected metric movement is more direct
availability-to-booking completion, fewer abandoned checkout recoveries, and
faster guest-to-staff handoff. For Bancal SF, the expected movement is a higher
qualified-inquiry rate, faster response and routing, and fewer repeated contacts
to reconstruct a prospect's consultation or onboarding status. These are
expected outcomes tied to the accepted workflow—not observed numeric deltas;
tenant analytics or CRM exports are required to quantify them.
