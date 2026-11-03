# ActBound Prototype Threat Model

## Protected asset

The only consequential asset in this prototype is the mock Payment Sandbox operation ledger and the task's cumulative simulated payment budget.

## Adversary

The agent runtime is untrusted. It may issue malformed, out-of-scope, repeated, concurrent, replayed, or parameter-substituted requests. It may attempt direct calls to the mock payment service.

## Trust assumptions

- The test issuer signing key is trusted for task creation.
- The designated verifier key is trusted for acceptance receipts.
- The local SQLite database and Python process are not compromised.
- Mock service state is the authoritative source for this experiment.
- The Payment Sandbox honors operation-ID idempotency.

## Controls implemented

- Signed manifest and signed transition receipt.
- Task, manifest, PO, vendor, currency, destination and amount binding.
- Receipt expiry, task state and revocation epoch checks.
- Atomic receipt consumption, budget reservation and outbox creation in one SQLite write transaction.
- Idempotent target operation ID and reconciliation method.
- Mock direct-call rejection for agent principal.
- Fail-closed audit and verifier availability checks.
- Behavioral sequence anomaly signal that cannot grant authority.

## Not demonstrated

The prototype does not withstand compromise of the gateway, database, issuer key or verifier key. It does not establish network-level complete mediation, process isolation, HSM-backed custody, external append-only audit, physical delivery truth, or exactly-once effects across independent systems.
