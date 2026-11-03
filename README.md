# ActBound — High-Consequence Action Enforcement

**Prototype status:** research prototype; sandbox only.  
**Working branch:** `prototype/high-consequence-enforcement`

ActBound is a high-consequence AI-agent action enforcement prototype. Its primary demonstration is a simulated procurement/payment workflow:

1. Verify delivery acceptance independently of the agent's own report.
2. Issue a task-bound, signed, expiring acceptance receipt.
3. Authorize a simulated payment only when the action matches the signed task scope, recipient, and remaining budget.
4. Consume the receipt and reserve budget atomically to prevent replay and concurrent double-spend.
5. Record decisions and state transitions for later review.

## Safety boundary

This repository is a local research prototype. It uses simulated payment units, mock services, and test credentials only. It must not be connected to real payment rails, production procurement systems, or real customer data.

## Supporting detection

The ActBound Behavioral Guard compares observed tool/service actions with the approved manifest and can flag or request intervention for unexpected sequences, destinations, and access. It is a supporting detection layer, **not** the security boundary: it cannot grant permissions or override a hard policy denial.

## Prototype components

- Ed25519-signed task manifests and receipts
- Mock purchase-order and delivery verification
- Gateway checks for identity, scope, recipient, receipt validity, and budget
- Atomic SQLite receipt consumption and budget reservation
- Idempotent simulated payment operation
- Outbox/reconciliation path for uncertain outcomes
- FastAPI sandbox API
- Adversarial tests and comparative harness
- Threat model and experiment results

## Run locally

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
pytest -q
python run_harness.py
```

Run the API with:

```bash
uvicorn actbound.api:app --host 127.0.0.1 --port 8000
```

## Evidence and limitations

The included comparative harness evaluates this prototype against a deliberately non-atomic local check-then-act approximation. That comparison is not an AWS AgentCore benchmark and does not establish production security or superiority over any commercial platform. Results must be interpreted within the tested local scenarios.

A compromised trusted-verifier signing key remains a critical trust-boundary failure requiring stronger key isolation and custody before any production consideration.

## Repository layout

- `actbound/` — core enforcement logic, API, and scenarios
- `tests/` — API and core tests
- `docs/` — technical specification and threat model
- `results/` — recorded harness output and comparative metrics
- `.github/workflows/` — automated test workflow
