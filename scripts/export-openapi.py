"""Write the implemented FastAPI schema without connecting to the database."""

import json
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "apps" / "api"))

from app.main import app  # noqa: E402

destination = project_root / "docs" / "openapi.json"
destination.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"Wrote {destination}")
