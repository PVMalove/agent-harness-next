"""The translation catalog of the web console, generated from the console's own tables.

The SPA in `harness/console/frontend` reads the same Russian-to-English strings as the TUI:
`render()` turns `EN`, `FACT_LABELS_EN` and the section labels into one JSON document, and the
committed `catalog.json` must equal it. Regenerate with `python -m harness.console.kernel.web_catalog`."""

from __future__ import annotations

import json
from pathlib import Path

from .i18n import sections
from .i18n_strings import EN, FACT_LABELS_EN

CATALOG_PATH = (
    Path(__file__).resolve().parents[1] / "frontend" / "src" / "i18n" / "catalog.json"
)
REGENERATE = "python -m harness.console.kernel.web_catalog"


def render() -> str:
    """The catalog JSON text: sorted keys, UTF-8 text, a trailing newline."""
    catalog = {"en": EN, "facts": FACT_LABELS_EN, "sections": sections()}
    return json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> None:
    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CATALOG_PATH.write_text(render(), encoding="utf-8")


if __name__ == "__main__":
    main()
