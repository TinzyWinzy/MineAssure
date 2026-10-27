from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field

from app.auth import dev_login_enabled, get_current_user
from app.engine import (
    ContractVersionInput,
    InvoiceLineInput,
    reconcile_line,
)
from app.routers.domain import Money, Quantity, StrictModel

router = APIRouter(prefix="/reconcile", tags=["reconcile"])


Nonnegative = Annotated[
    Decimal,
    Field(ge=0, le=1000000, allow_inf_nan=False, max_digits=18, decimal_places=6),
]


class RateLineIn(StrictModel):
    work_code: str
    unit: str = "hour"
    rate: Money
    cap_hours: Quantity | None = None


class ContractVersionIn(StrictModel):
    id: str
    status: str = "approved"
    effective_from: datetime
    effective_to: datetime | None = None
    currency: str = "USD"
    rate_lines: list[RateLineIn] = Field(default_factory=list)


class InvoiceLineIn(StrictModel):
    line_id: str
    quantity: Nonnegative
    unit: str = "hour"
    unit_price: Money
    work_code: str | None = None
    work_reference: str | None = None


class ReconcileLineRequest(StrictModel):
    invoice_line: InvoiceLineIn
    contract_version: ContractVersionIn | None = None
    verified_qty: Nonnegative = Decimal(0)
    evidence_work_refs: list[str] = Field(default_factory=list)
    duplicate_invoice: bool = False
    duplicate_work_ref: bool = False
    service_out_of_contract: bool = False


class FindingOut(StrictModel):
    rule_code: str
    severity: str
    message: str
    quantified_amount: str | None = None


class ReconcileLineResponse(StrictModel):
    invoice_line_id: str
    invoiced_amount: str
    supported_amount: str
    unverified_amount: str
    quantified_variance: str
    approved_amount: str
    findings: list[FindingOut]
    explanation: str


@router.post("/line", response_model=ReconcileLineResponse)
def reconcile_line_endpoint(body: ReconcileLineRequest, user=Depends(get_current_user)):
    if not dev_login_enabled():
        raise HTTPException(403, "Development calculation preview disabled")
    cv = None
    if body.contract_version is not None:
        cv = ContractVersionInput(
            id=body.contract_version.id,
            status=body.contract_version.status,
            effective_from=body.contract_version.effective_from,
            effective_to=body.contract_version.effective_to,
            currency=body.contract_version.currency,
            rate_lines=[rl.model_dump() for rl in body.contract_version.rate_lines],
        )
    inv = InvoiceLineInput(
        line_id=body.invoice_line.line_id,
        quantity=Decimal(body.invoice_line.quantity),
        unit=body.invoice_line.unit,
        unit_price=Decimal(body.invoice_line.unit_price),
        work_code=body.invoice_line.work_code,
        work_reference=body.invoice_line.work_reference,
    )
    # fix rate_lines rate as str already Decimal-compatible
    if cv is not None:
        for rl in cv.rate_lines:
            rl["rate"] = str(rl["rate"])
    res = reconcile_line(
        inv,
        cv,
        Decimal(body.verified_qty),
        body.evidence_work_refs,
        body.duplicate_invoice,
        body.duplicate_work_ref,
        body.service_out_of_contract,
    )
    return ReconcileLineResponse(
        invoice_line_id=res.invoice_line_id,
        invoiced_amount=str(res.invoiced_amount),
        supported_amount=str(res.supported_amount),
        unverified_amount=str(res.unverified_amount),
        quantified_variance=str(res.quantified_variance),
        approved_amount=str(res.approved_amount),
        findings=[
            FindingOut(
                rule_code=f["rule_code"],
                severity=f["severity"],
                message=f["message"],
                quantified_amount=str(f["quantified_amount"])
                if f.get("quantified_amount") is not None
                else None,
            )
            for f in res.findings
        ],
        explanation=res.explanation,
    )
