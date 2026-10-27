"""Deterministic financial reconciliation engine.

Pure functions operating on Decimal. No DB, no IO. Repeatable for same inputs.
"""

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

ZERO = Decimal(0)


@dataclass
class InvoiceLineInput:
    line_id: str
    quantity: Decimal
    unit: str
    unit_price: Decimal  # invoiced rate
    service_date: object | None = None
    work_code: str | None = None
    work_reference: str | None = None


@dataclass
class ContractVersionInput:
    id: str
    status: str
    effective_from: object
    effective_to: object | None
    currency: str
    rate_lines: list[dict] = field(default_factory=list)
    # rate_lines: list of {work_code, unit, rate, cap_hours, minimum_hours, standby_rate, standby_explicit, minimum_explicit}


@dataclass
class WorkEvidence:
    work_record_id: str
    work_code: str
    quantity: Decimal
    unit: str
    service_date: object
    verified: bool = True


@dataclass
class LineReconciliation:
    invoice_line_id: str
    invoiced_amount: Decimal
    supported_amount: Decimal
    unverified_amount: Decimal
    quantified_variance: Decimal
    approved_amount: Decimal
    findings: list[dict] = field(default_factory=list)
    explanation: str = ""


def select_contract_version(
    versions: list[ContractVersionInput], service_date
) -> ContractVersionInput | None:
    """Select approved version effective on service_date."""
    candidates = [
        v
        for v in versions
        if v.status == "approved"
        and v.effective_from <= service_date
        and (v.effective_to is None or service_date <= v.effective_to)
    ]
    if not candidates:
        return None
    # latest effective_from
    best = candidates[0]
    for c in candidates[1:]:
        if c.effective_from > best.effective_from:  # type: ignore[operator]
            best = c
    return best


def find_rate_line(
    version: ContractVersionInput | None, work_code: str | None
) -> dict | None:
    if version is None:
        return None
    for rl in version.rate_lines:
        if work_code is None or rl.get("work_code") == work_code:
            return rl
    return None


def reconcile_line(
    inv_line: InvoiceLineInput,
    contract_version: ContractVersionInput | None,
    verified_qty: Decimal,
    evidence_work_refs: list[str],
    duplicate_invoice: bool = False,
    duplicate_work_ref: bool = False,
    service_out_of_contract: bool = False,
) -> LineReconciliation:
    if any(
        not x.is_finite() or x < ZERO
        for x in (inv_line.quantity, inv_line.unit_price, verified_qty)
    ):
        raise ValueError("Amounts and quantities must be finite and nonnegative")
    invoiced_qty = inv_line.quantity
    invoiced_rate = inv_line.unit_price
    invoiced_amount = (invoiced_qty * invoiced_rate).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    findings: list[dict] = []

    # Contract date check
    if service_out_of_contract:
        findings.append(
            {
                "rule_code": "R004",
                "severity": "high",
                "message": "Service date outside approved contract window.",
            }
        )

    # Rate line
    approved_contract = (
        contract_version is not None
        and contract_version.status == "approved"
        and contract_version.currency == "USD"
    )
    rate_line = (
        find_rate_line(contract_version, inv_line.work_code)
        if approved_contract
        else None
    )
    if rate_line and rate_line.get("unit") != inv_line.unit:
        rate_line = None
    contract_rate = Decimal(str(rate_line["rate"])) if rate_line else Decimal(0)

    # R001 rate
    if contract_rate > 0 and invoiced_rate != contract_rate:
        findings.append(
            {
                "rule_code": "R001",
                "severity": "medium",
                "message": f"Invoiced rate {invoiced_rate} differs from contract rate {contract_rate}.",
                "quantified_amount": (
                    invoiced_qty * (invoiced_rate - contract_rate)
                ).quantize(Decimal("0.000001")),
            }
        )

    # R002 quantity
    if verified_qty < invoiced_qty:
        findings.append(
            {
                "rule_code": "R002",
                "severity": "medium",
                "message": f"Invoiced quantity {invoiced_qty} exceeds verified quantity {verified_qty}.",
                "quantified_amount": (
                    (invoiced_qty - verified_qty) * contract_rate
                ).quantize(Decimal("0.000001"))
                if contract_rate > 0
                else None,
            }
        )

    # R003 duplicates
    if duplicate_invoice:
        findings.append(
            {
                "rule_code": "R003",
                "severity": "high",
                "message": "Duplicate invoice reference detected.",
            }
        )
    if duplicate_work_ref:
        findings.append(
            {
                "rule_code": "R003",
                "severity": "high",
                "message": "Same work reference billed by another invoice.",
            }
        )

    # R007 document gaps
    if not evidence_work_refs:
        findings.append(
            {
                "rule_code": "R007",
                "severity": "medium",
                "message": "Missing supporting evidence documents.",
            }
        )

    # Determine supported/unverified/quantified
    supported_qty = min(invoiced_qty, verified_qty)
    supported_qty = max(supported_qty, ZERO)
    # cap at verified available
    supported_qty = min(supported_qty, verified_qty)
    supported_qty = min(supported_qty, invoiced_qty)

    eligible = (
        approved_contract
        and rate_line is not None
        and not service_out_of_contract
        and not duplicate_invoice
        and not duplicate_work_ref
        and bool(evidence_work_refs)
    )
    if rate_line and rate_line.get("cap_hours") is not None:
        supported_qty = min(supported_qty, Decimal(str(rate_line["cap_hours"])))
    if verified_qty <= ZERO or not eligible:
        # no evidence -> unverified, quantified variance undetermined (0)
        supported_amount = ZERO
        unverified_amount = invoiced_amount
        quantified_variance = ZERO
    else:
        supported_amount = min(
            invoiced_amount,
            (supported_qty * contract_rate).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            ),
        )
        unverified_amount = ZERO
        # quantified variance = invoiced - supported, nonnegative, single non-double-counted
        diff = invoiced_amount - supported_amount
        quantified_variance = max(ZERO, diff)

    # caps (R008) - if cap_hours present and invoiced_qty exceeds
    if rate_line and rate_line.get("cap_hours") is not None:
        cap = Decimal(str(rate_line["cap_hours"]))
        if invoiced_qty > cap:
            findings.append(
                {
                    "rule_code": "R008",
                    "severity": "medium",
                    "message": f"Invoiced quantity exceeds cap {cap}.",
                }
            )

    # variations (R006) placeholder: if contract version approved variations not in rate, note
    # (handled by caller)

    approved_amount = ZERO  # human approval required

    if not approved_contract or rate_line is None:
        findings.append(
            {
                "rule_code": "R006",
                "severity": "high",
                "message": "No approved matching USD hourly contract rate. Amount is unverified.",
            }
        )

    explanation = (
        f"invoiced={invoiced_amount}; supported={supported_amount}; "
        f"unverified={unverified_amount}; quantified_variance={quantified_variance}; "
        f"contract_rate={contract_rate}; verified_qty={verified_qty}"
    )

    return LineReconciliation(
        invoice_line_id=inv_line.line_id,
        invoiced_amount=invoiced_amount,
        supported_amount=supported_amount,
        unverified_amount=unverified_amount,
        quantified_variance=quantified_variance,
        approved_amount=approved_amount,
        findings=findings,
        explanation=explanation,
    )
