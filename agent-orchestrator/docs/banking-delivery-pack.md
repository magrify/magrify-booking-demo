# Banking delivery pack

This sandbox is designed to make a bank-facing engagement concrete without
claiming that the agent approved credit.

## Workflow

`package_received → completeness_review → exception_review → human_credit_review → compliance_review → decision_recorded`

The implementation currently automates the first three steps:

- checks the rent roll, operating statement, inspection report, and insurance;
- records missing documents and exceptions;
- routes exceptions to a named human underwriter;
- preserves an explicit `not_made_by_agent` boundary for credit decisions and
  regulatory filings.

## Delivery controls

- Operations analysts can request missing documents but cannot approve credit.
- Underwriters resolve package exceptions and record rationale.
- Compliance reviewers own regulatory checks and filing decisions.
- Every transition is designed to produce an audit event with tenant, case,
  actor role, and timestamp.

## What a live engagement would add

The next bank-side implementation step is a client-approved adapter for the
bank's system of record, identity model, document store, and regulatory review
queue. Until those integrations and stakeholder approvals exist, this pack is
technical readiness evidence rather than a claim of bank production delivery.
