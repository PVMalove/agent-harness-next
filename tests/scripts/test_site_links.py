"""Внутренние ссылки публичного сайта: raw HTML и Markdown вне валидации MkDocs."""

from __future__ import annotations

from pathlib import Path

from scripts.verification.site_links import find_broken_links


def _docs(tmp_path: Path) -> Path:
    docs = tmp_path / "site" / "docs"
    docs.mkdir(parents=True)
    return docs


def test_existing_links_of_every_kind_pass(tmp_path: Path) -> None:
    docs = _docs(tmp_path)
    (docs / "assets").mkdir()
    (docs / "assets" / "logo.svg").write_text("<svg/>", encoding="utf-8")
    (docs / "console.html").write_text("<p>demo</p>", encoding="utf-8")
    (docs / "guide").mkdir()
    (docs / "guide" / "index.md").write_text("# Guide\n", encoding="utf-8")
    (docs / "index.md").write_text(
        "\n".join(
            (
                "[guide](guide/index.md)",
                "[page](guide/)",
                '<img src="assets/logo.svg" alt="">',
                '<a href="guide/index.html">guide</a>',
                '<a href="https://example.com">external</a>',
                '<a href="#top">anchor</a>',
            )
        ),
        encoding="utf-8",
    )

    assert find_broken_links(docs) == []


def test_missing_raw_html_asset_is_reported(tmp_path: Path) -> None:
    docs = _docs(tmp_path)
    (docs / "index.md").write_text('<img src="missing.svg">', encoding="utf-8")

    assert find_broken_links(docs) == ["index.md: missing.svg"]


def test_missing_markdown_target_is_reported(tmp_path: Path) -> None:
    docs = _docs(tmp_path)
    (docs / "index.md").write_text("[gone](gone.md)", encoding="utf-8")

    assert find_broken_links(docs) == ["index.md: gone.md"]


def test_html_link_resolves_from_the_built_page_url(tmp_path: Path) -> None:
    docs = _docs(tmp_path)
    (docs / "getting-started").mkdir()
    (docs / "getting-started" / "index.md").write_text("# Start\n", encoding="utf-8")
    (docs / "guides").mkdir()
    (docs / "guides" / "workflow.md").write_text(
        '<a href="../../getting-started/">start</a>\n'
        '<a href="../getting-started/">wrong</a>\n',
        encoding="utf-8",
    )

    assert find_broken_links(docs) == ["guides/workflow.md: ../getting-started/"]


def test_static_html_is_checked_from_its_own_directory(tmp_path: Path) -> None:
    docs = _docs(tmp_path)
    (docs / "demo").mkdir()
    (docs / "demo" / "site.css").write_text("body{}", encoding="utf-8")
    (docs / "demo" / "console.html").write_text(
        '<link rel="stylesheet" href="site.css">\n<img src="missing.svg">\n',
        encoding="utf-8",
    )

    assert find_broken_links(docs) == ["demo/console.html: missing.svg"]


def test_link_escaping_the_docs_directory_is_reported(tmp_path: Path) -> None:
    docs = _docs(tmp_path)
    (docs / "index.md").write_text("[outside](../../README.md)", encoding="utf-8")

    assert find_broken_links(docs) == ["index.md: ../../README.md"]


def test_english_page_resolves_raw_html_from_the_en_url(tmp_path: Path) -> None:
    docs = _docs(tmp_path)
    (docs / "assets").mkdir()
    (docs / "assets" / "mascot.svg").write_text("<svg/>", encoding="utf-8")
    (docs / "index.md").write_text('<img src="assets/mascot.svg">', encoding="utf-8")
    (docs / "index.en.md").write_text(
        '<img src="../assets/mascot.svg">\n<img src="assets/mascot.svg">\n',
        encoding="utf-8",
    )

    assert find_broken_links(docs) == ["index.en.md: assets/mascot.svg"]


def test_english_static_html_needs_a_twin_or_a_root_path(tmp_path: Path) -> None:
    docs = _docs(tmp_path)
    (docs / "demo").mkdir()
    (docs / "demo" / "site.css").write_text("body{}", encoding="utf-8")
    (docs / "demo" / "data.js").write_text("", encoding="utf-8")
    (docs / "demo" / "data.en.js").write_text("", encoding="utf-8")
    (docs / "demo" / "console.html").write_text(
        '<link href="site.css">', encoding="utf-8"
    )
    (docs / "demo" / "console.en.html").write_text(
        '<link href="../../demo/site.css">\n'
        '<script src="data.js"></script>\n'
        '<link href="site.css">\n',
        encoding="utf-8",
    )

    assert find_broken_links(docs) == ["demo/console.en.html: site.css"]


def test_english_page_may_link_to_a_page_served_by_fallback(tmp_path: Path) -> None:
    docs = _docs(tmp_path)
    (docs / "guides").mkdir()
    (docs / "guides" / "workflow.md").write_text("# Workflow\n", encoding="utf-8")
    (docs / "guides" / "index.md").write_text("# Guides\n", encoding="utf-8")
    (docs / "index.en.md").write_text(
        '<a href="guides/">guides</a>\n<a href="guides/workflow/">workflow</a>\n'
        '<a href="guides/gone/">gone</a>\n',
        encoding="utf-8",
    )
    (docs / "index.md").write_text("# Home\n", encoding="utf-8")

    assert find_broken_links(docs) == ["index.en.md: guides/gone/"]
