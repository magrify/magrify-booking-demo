# Operator outcome record

Use the authenticated adoption endpoint to record what happened after the
example demo. Do not mark a milestone until the operator or staff member has
actually confirmed it.

## Decision participants

- Operator or property owner: confirms the guest workflow and property rules.
- Operations lead: confirms staff access, handoffs, and daily workflow fit.
- Finance or payments owner: confirms deposit, refund, and reconciliation
  controls.
- Engineering or implementation owner: confirms configuration, integration,
  and rollout readiness.

## Acceptance record

1. `operator_feedback`: capture the requested branded, property-specific
   example and the original workflow problem.
2. `demo_presented`: record the build version and the screens demonstrated.
3. `operator_signoff`: record the approving role and any conditions.
4. `deployment_configured`: record property settings, inventory, policies,
   staff access, and payment connection.
5. `staff_training_completed`: record who was trained and the handoff date.
6. `staff_workflow_used`: record the first observed operational use and what
   changed in the operator's day-to-day process.

The repository provides the capture path; it does not manufacture sign-off or
adoption. A completed record is therefore stronger evidence than a resume
claim because it includes the decision-maker, conditions, and observed use.
