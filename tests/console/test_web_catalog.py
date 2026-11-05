"""The web console reads the committed catalog; it must equal the console's translation tables."""

from __future__ import annotations

import json

from harness.console.kernel import web_catalog
from harness.console.kernel.i18n import section_label
from harness.console.kernel.i18n_strings import EN


def test_committed_catalog_equals_the_rendered_tables() -> None:
    committed = web_catalog.CATALOG_PATH.read_text(encoding="utf-8")
    assert committed == web_catalog.render(), (
        f"{web_catalog.CATALOG_PATH.name} is out of date: run "
        f"`{web_catalog.REGENERATE}` and commit the result."
    )


def test_the_catalog_carries_strings_facts_and_sections() -> None:
    catalog = json.loads(web_catalog.render())
    assert set(catalog) == {"en", "facts", "sections"}
    assert catalog["en"] == EN
    assert catalog["facts"]["Ветка"] == "Branch"
    assert catalog["sections"]["Home"] == {
        "ru": section_label("ru", "Home"),
        "en": section_label("en", "Home"),
    }
    assert catalog["en"]["Нет сервера"] == "No server"
