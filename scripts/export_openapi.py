"""Export the OpenAPI schema from the FastAPI app to a JSON file."""

import json
import sys
from pathlib import Path

from apps.api.main import app


def main() -> None:
    """Write the OpenAPI JSON schema to apps/ui/openapi.json."""
    schema = app.openapi()
    output_path = Path("apps/ui/openapi.json")
    output_path.write_text(json.dumps(schema, indent=2) + "\n")
    print(f"Wrote OpenAPI schema to {output_path}")


if __name__ == "__main__":
    sys.exit(main() or 0)
