"""Measure pure rule arithmetic; excludes API, database, imports and allocations."""

import json
import platform
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from time import perf_counter

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "apps" / "api"))

from app.engine import ContractVersionInput, InvoiceLineInput, reconcile_line  # noqa: E402

service_date = datetime(2026, 10, 1, tzinfo=timezone.utc)
contract = ContractVersionInput(
    id="benchmark-contract",
    status="approved",
    effective_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
    effective_to=None,
    currency="USD",
    rate_lines=[{"work_code": "EQ-HIRE", "unit": "hour", "rate": "240"}],
)
started = perf_counter()
results = []
for line_number in range(1000):
    line = InvoiceLineInput(
        line_id=f"benchmark-{line_number}",
        quantity=Decimal("160"),
        unit="hour",
        unit_price=Decimal("250"),
        service_date=service_date,
        work_code="EQ-HIRE",
        work_reference=f"benchmark-work-{line_number}",
    )
    result = reconcile_line(line, contract, Decimal("145"), [line.work_reference])
    assert result.invoiced_amount == Decimal("40000"), result
    assert result.supported_amount == Decimal("34800"), result
    assert result.quantified_variance == Decimal("5200"), result
    results.append(result)
elapsed = perf_counter() - started
print(json.dumps({
    "scope": "pure-engine arithmetic only; no database/API/import/allocation",
    "lines": len(results),
    "seconds": round(elapsed, 6),
    "python": platform.python_version(),
    "platform": platform.platform(),
    "processor": platform.processor(),
    "meets_60_second_arithmetic_target": elapsed <= 60,
}, indent=2))
