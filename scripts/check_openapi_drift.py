"""Check that the committed openapi.json matches the current FastAPI schema."""

import json
import sys
from pathlib import Path

from apps.api.main import app


def main() -> int:
    """Compare the live OpenAPI schema against the committed file.

    Returns:
        0 if they match, 1 if there is drift.
    """
    output_path = Path("apps/ui/openapi.json")
    if not output_path.exists():
        print("ERROR: apps/ui/openapi.json not found. Run: poe generate-api-client")
        return 1

    committed = json.loads(output_path.read_text())
    live = app.openapi()

    if committed == live:
        print("OpenAPI schema is up to date.")
        return 0

    print("ERROR: OpenAPI drift detected!")
    print("The committed apps/ui/openapi.json does not match the current FastAPI schema.")
    print("Run: poe generate-api-client")
    return 1


if __name__ == "__main__":
    sys.exit(main())
