"""Existing suite installations remain usable after the public capability rename."""

from __future__ import annotations


from harness.bin.harness import capabilities, selected_capabilities


def test_catalog_lists_only_neutral_suite_and_cli_accepts_legacy_name() -> None:
    assert "engineering-suite" in capabilities()
    assert "pvmalove-suite" not in capabilities()
    assert selected_capabilities(["pvmalove-suite", "engineering-suite"]) == [
        "engineering-suite"
    ]
