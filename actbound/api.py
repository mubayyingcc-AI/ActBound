"""Local-only REST facade. Authentication tokens are test fixtures, not production identity."""
from __future__ import annotations

import os
import time
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .core import ActBound, TaskManifest

app = FastAPI(title="ActBound Enforcement Gateway", version="0.2.0",
              description="LOCAL SANDBOX ONLY — simulated payment operations; no production credentials.")
system = ActBound(os.environ.get("ACTBOUND_DB_PATH", ":memory:"))


class ManifestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_id: str = Field(min_length=1, max_length=100)
    purchase_order_id: str
    vendor_id: str
    destination: str
    currency: str = Field(min_length=3, max_length=8)
    max_amount_minor: int = Field(gt=0, le=2**63 - 1)
    allowed_operations: list[str]
    allowed_sequence: list[str]
    expires_at: int
    policy_version: str
    nonce: str


class ActionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    step_id: str
    operation: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    predecessor_receipt_id: str | None = None
    amount_minor: int | None = Field(default=None, gt=0)
    idempotency_key: str | None = None


class RevokeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(default="issuer-requested", max_length=200)


def principal(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Bearer token required")
    token = authorization.removeprefix("Bearer ")
    issuer = os.environ.get("ACTBOUND_TEST_ISSUER_TOKEN", "local-issuer-token")
    agent = os.environ.get("ACTBOUND_TEST_AGENT_TOKEN", "local-agent-token")
    if token == issuer:
        return "issuer"
    if token == agent:
        return "agent"
    raise HTTPException(403, "Unknown local test principal")


def require_issuer(actor: str = Depends(principal)) -> str:
    if actor != "issuer":
        raise HTTPException(403, "Issuer role required")
    return actor


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": "LOCAL_SANDBOX_ONLY"}


@app.post("/v1/tasks")
def create_task(body: ManifestIn, _: str = Depends(require_issuer)) -> dict[str, Any]:
    try:
        manifest = TaskManifest(**{**body.model_dump(), "allowed_operations": tuple(body.allowed_operations),
                                   "allowed_sequence": tuple(body.allowed_sequence)})
        signed = system.create_manifest(manifest)
        return {"task_id": manifest.task_id, "manifest_hash": signed.manifest_hash,
                "issuer_key_id": manifest.issuer_key_id, "state": "ACTIVE"}
    except (ValueError, PermissionError) as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get("/v1/tasks/{task_id}")
def get_task(task_id: str, _: str = Depends(principal)) -> dict[str, Any]:
    row = system.db.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Task not found")
    import json
    manifest = json.loads(row["manifest_json"])
    return {"task_id": task_id, "state": row["state"], "manifest_hash": row["manifest_hash"],
            "allowed_operations": manifest["allowed_operations"], "reserved_minor": row["reserved_minor"],
            "paid_minor": row["paid_minor"], "remaining_minor": manifest["max_amount_minor"] - row["reserved_minor"] - row["paid_minor"]}


@app.post("/v1/tasks/{task_id}/actions")
def submit_action(task_id: str, body: ActionIn, actor: str = Depends(principal)) -> dict[str, Any]:
    if actor != "agent":
        raise HTTPException(403, "Agent role required for action submission")
    if body.step_id != body.operation:
        return {"decision": "DENY", "reason": "STEP_OPERATION_MISMATCH"}
    if body.operation == "po.verify":
        ok = system.verify_po(task_id)
        return {"decision": "ALLOW" if ok else "DENY", "operation": body.operation}
    if body.operation == "delivery.accept":
        try:
            receipt = system.accept_delivery(task_id, body.amount_minor)
            return {"decision": "ALLOW", "receipt_id": receipt.receipt.receipt_id,
                    "receipt": receipt.receipt.payload(), "signature": receipt.signature}
        except (ValueError, PermissionError, RuntimeError) as exc:
            raise HTTPException(403, str(exc)) from exc
    if body.operation == "payment.release_simulated":
        if not body.predecessor_receipt_id or not body.idempotency_key or not body.amount_minor:
            raise HTTPException(422, "Payment requires predecessor_receipt_id, amount_minor and idempotency_key")
        return system.release_payment(task_id, body.predecessor_receipt_id, body.amount_minor,
                                      body.idempotency_key, body.operation, body.parameters)
    row = system.db.execute("SELECT manifest_json FROM tasks WHERE task_id=?", (task_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Task not found")
    import json
    from .core import TaskManifest
    m = json.loads(row["manifest_json"])
    manifest = TaskManifest(**{**m, "allowed_operations": tuple(m["allowed_operations"]),
                               "allowed_sequence": tuple(m["allowed_sequence"])})
    system.behavior.observe(body.operation, manifest)
    return {"decision": "DENY", "reason": "UNKNOWN_OPERATION"}


@app.post("/v1/tasks/{task_id}/revoke")
def revoke_task(task_id: str, body: RevokeIn, _: str = Depends(require_issuer)) -> dict[str, Any]:
    row = system.db.execute("SELECT task_id FROM tasks WHERE task_id=?", (task_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Task not found")
    system.revoke(task_id)
    return {"task_id": task_id, "state": "REVOKED", "reason": body.reason}


@app.get("/v1/receipts/{receipt_id}")
def get_receipt(receipt_id: str, _: str = Depends(principal)) -> dict[str, Any]:
    row = system.db.execute("SELECT * FROM receipts WHERE receipt_id=?", (receipt_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Receipt not found")
    import json
    return {"receipt": json.loads(row["receipt_json"]), "signature": row["signature"],
            "consumed": row["consumed_by"] is not None}


@app.post("/v1/receipts/verify")
def verify_receipt(body: dict[str, Any], _: str = Depends(principal)) -> dict[str, Any]:
    receipt = body.get("receipt")
    signature = body.get("signature")
    if not isinstance(receipt, dict) or not isinstance(signature, str):
        raise HTTPException(422, "receipt object and signature string required")
    return {"signature_valid": system.verifier.verify(receipt, signature),
            "note": "Offline signature verification does not establish current non-revocation or consume the receipt."}


@app.get("/v1/audit")
def get_audit(task_id: str | None = None, _: str = Depends(principal)) -> dict[str, Any]:
    return {"events": system.audit_events(task_id)}
