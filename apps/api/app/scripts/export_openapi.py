"""Write the OpenAPI document that the frontend types are generated from.

Usage: ``python -m app.scripts.export_openapi <output.json>``
"""

import json
import sys
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.main import create_app


def build_openapi() -> dict[str, Any]:
    # Explicit blank settings: the spec must not depend on the developer's .env.
    return create_app(Settings(_env_file=None)).openapi()


def render(spec: dict[str, Any]) -> str:
    return json.dumps(spec, indent=2, sort_keys=True) + "\n"


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: python -m app.scripts.export_openapi <output.json>")
    out = Path(sys.argv[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(build_openapi()), encoding="utf-8", newline="\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
