# Operator session evidence

Run `python scripts/run-operator-session.py` against a local or deployed
orchestrator to rehearse the same API path a user/operator uses. The session:

1. submits a business description, ICP, offer, and lead;
2. observes the approval-gated run before any outbound action;
3. approves the prepared draft as an operator;
4. records feedback, demo, configuration, training, and workflow-use events;
5. reads adoption and reliability reports back from the service.

The concrete workflow change demonstrated by the rehearsal is:

> Manual inquiry triage becomes a tenant-scoped approval queue with a visible
> recovery path and recorded staff handoff.

That is a product hypothesis and an operator-rehearsal observation until a
client records `operator_signoff` and `staff_workflow_used` from an actual
deployment. The script labels its output `operator_rehearsal` so the evidence
cannot be mistaken for customer adoption.
