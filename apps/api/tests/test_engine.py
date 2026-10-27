"""Deterministic engine properties and rate/date boundary golden scenarios."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.engine import (
    ContractVersionInput,
    InvoiceLineInput,
    reconcile_line,
    select_contract_version,
)


def contract(rate="240", status="approved", **changes):
    return ContractVersionInput(
        id="cv-1",
        status=status,
        effective_from=changes.get("effective_from", datetime(2026, 1, 1, tzinfo=UTC)),
        effective_to=changes.get("effective_to"),
        currency="USD",
        rate_lines=[{"work_code": "EQ-HIRE", "unit": "hour", "rate": rate}],
    )


def invoice(quantity="160", rate="250", **changes):
    return InvoiceLineInput(
        line_id="L1",
        quantity=Decimal(quantity),
        unit="hour",
        unit_price=Decimal(rate),
        work_code=changes.get("work_code", "EQ-HIRE"),
        service_date=datetime(2026, 10, 10, tzinfo=UTC),
    )


def test_scenario_a():
    result = reconcile_line(invoice(), contract(), Decimal(145), ["wr-1"])
    assert result.invoiced_amount == Decimal(40000)
    assert result.supported_amount == Decimal(34800)
    assert result.quantified_variance == Decimal(5200)
    assert result.unverified_amount == 0
    assert {"R001", "R002"} <= {finding["rule_code"] for finding in result.findings}


def test_scenario_b():
    result = reconcile_line(invoice("10", "240"), contract(), Decimal(0), [])
    assert result.invoiced_amount == Decimal(2400)
    assert result.unverified_amount == Decimal(2400)
    assert result.quantified_variance == 0
    assert result.supported_amount == 0


def test_effective_date_boundary_and_draft_variation():
    boundary = datetime(2026, 10, 15, tzinfo=UTC)
    old = contract()
    new = contract("255", effective_from=boundary)
    draft = contract("999", status="draft", effective_from=boundary)
    assert (
        select_contract_version(
            [old, new, draft], datetime(2026, 10, 14, tzinfo=UTC)
        ).rate_lines[0]["rate"]
        == "240"
    )
    assert (
        select_contract_version([old, new, draft], boundary).rate_lines[0]["rate"]
        == "255"
    )


@pytest.mark.parametrize("version", [None, contract(status="draft"), contract()])
def test_missing_unapproved_or_mismatched_terms_are_unverified(version):
    inv = invoice(
        work_code="OTHER" if version and version.status == "approved" else "EQ-HIRE"
    )
    result = reconcile_line(inv, version, Decimal(145), ["wr-1"])
    assert result.supported_amount == 0
    assert result.unverified_amount == result.invoiced_amount
    assert result.quantified_variance == 0


def test_out_of_contract_is_unverified():
    result = reconcile_line(
        invoice(), contract(), Decimal(145), ["wr-1"], service_out_of_contract=True
    )
    assert result.supported_amount == 0
    assert result.unverified_amount == result.invoiced_amount
    assert any(f["rule_code"] == "R004" for f in result.findings)


@pytest.mark.parametrize("quantity", ["0", "0.01", "1", "145", "160", "200"])
@pytest.mark.parametrize("rate", ["1", "239.99", "240", "250", "999.99"])
def test_amount_conservation_and_deterministic_replay(quantity, rate):
    inv = invoice(quantity, rate)
    result = reconcile_line(inv, contract(), Decimal(145), ["wr-1"])
    assert result.supported_amount >= 0
    assert result.supported_amount <= result.invoiced_amount
    assert result.quantified_variance >= 0
    assert (
        result.invoiced_amount
        == result.supported_amount
        + result.unverified_amount
        + result.quantified_variance
    )
    assert result.approved_amount == 0
    assert result == reconcile_line(inv, contract(), Decimal(145), ["wr-1"])
