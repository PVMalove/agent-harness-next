"""Every `harness health` check has a rationale in Russian and English, and the web catalog ships
exactly that table."""

from __future__ import annotations

import json

from harness.console.kernel import web_catalog
from harness.console.kernel.check_rationale import RATIONALES
from harness.health.checks.directories import DIRECTORY_PATHS
from harness.health.registry import REGISTRY


def test_every_registered_check_has_a_rationale_in_both_languages() -> None:
    ids = [check_id for check_id, _ in REGISTRY]
    assert set(DIRECTORY_PATHS) <= set(ids)
    assert set(RATIONALES) == set(ids)
    for check_id in ids:
        ru, en = RATIONALES[check_id]
        assert ru.strip() and en.strip(), check_id
        assert ru != en, check_id
        assert any("а" <= char <= "я" for char in ru.lower()), check_id
        assert en.isascii(), check_id


def test_the_web_catalog_carries_the_rationales_by_id() -> None:
    shipped = json.loads(web_catalog.render())["rationales"]
    assert shipped == {
        check_id: {"ru": ru, "en": en} for check_id, (ru, en) in RATIONALES.items()
    }
