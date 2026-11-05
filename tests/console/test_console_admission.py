"""The console admission rules are pure functions over raw ASGI-style headers."""

from __future__ import annotations

import pytest

from harness.console.backend.api import admission

PORT = 43210
TOKEN = "ab" * 32
HOST = f"127.0.0.1:{PORT}"
ORIGIN = "http://" + HOST


def _admit(headers: list[tuple[str, str]], target: str = "/ws") -> int | None:
    raw = [(name.lower().encode(), value.encode()) for name, value in headers]
    path, _, query = target.partition("?")
    status = admission.request_status(raw, b"GET", PORT)
    if status is not None:
        return status
    return admission.upgrade_status(raw, b"GET", path, query.encode(), PORT, TOKEN)


def _upgrade() -> list[tuple[str, str]]:
    return [
        ("Host", HOST),
        ("Upgrade", "websocket"),
        ("Connection", "Upgrade"),
        ("Sec-WebSocket-Key", "dGhlIHNhbXBsZSBub25jZQ=="),
        ("Sec-WebSocket-Version", "13"),
        ("Authorization", "Bearer " + TOKEN),
    ]


def test_a_valid_upgrade_is_admitted() -> None:
    assert _admit(_upgrade()) is None


@pytest.mark.parametrize(
    "case,status",
    [
        ("wrong-token", 401),
        ("duplicate-auth", 401),
        ("conflict", 401),
        ("duplicate-cookie", 401),
        ("cookie-no-origin", 401),
        ("ambiguous-cookie", 401),
        ("foreign-origin", 403),
        ("null-origin", 403),
        ("duplicate-origin", 403),
        ("foreign-host", 403),
        ("wrong-port", 403),
        # The HTTP parser answers 400 before admission; the rule itself still fails closed.
        ("duplicate-host", 403),
        ("missing-host", 403),
        ("query-token", 404),
        ("body-upgrade", 400),
        ("chunked-upgrade", 400),
        # Key and version belong to the WebSocket handshake layer, which answers 400.
        ("bad-key", None),
        ("bad-version", None),
    ],
)
def test_websocket_admission_cases(case: str, status: int | None) -> None:
    headers = _upgrade()
    target = "/ws"
    if case == "wrong-token":
        headers[-1] = ("Authorization", "Bearer wrong")
    elif case == "duplicate-auth":
        headers.append(headers[-1])
    elif case == "conflict":
        headers.extend([("Origin", ORIGIN), ("Cookie", "console_token=wrong")])
    elif case in {"duplicate-cookie", "cookie-no-origin", "ambiguous-cookie"}:
        headers.pop()
        headers.append(("Cookie", "console_token=" + TOKEN))
        if case != "cookie-no-origin":
            headers.append(("Origin", ORIGIN))
        if case == "duplicate-cookie":
            headers.append(("Cookie", "console_token=" + TOKEN))
        if case == "ambiguous-cookie":
            headers[-2] = ("Cookie", "console_token=" + TOKEN + "; console_token=wrong")
    elif case in {"foreign-origin", "null-origin", "duplicate-origin"}:
        headers.append(
            (
                "Origin",
                {
                    "foreign-origin": "https://example.invalid",
                    "null-origin": "null",
                    "duplicate-origin": ORIGIN,
                }[case],
            )
        )
        if case == "duplicate-origin":
            headers.append(("Origin", ORIGIN))
    elif case == "foreign-host":
        headers[0] = ("Host", "example.invalid")
    elif case == "wrong-port":
        headers[0] = ("Host", "127.0.0.1:0")
    elif case == "duplicate-host":
        headers.append(("Host", HOST))
    elif case == "missing-host":
        headers.pop(0)
    elif case == "query-token":
        headers.pop()
        target += "?token=" + TOKEN
    elif case == "body-upgrade":
        headers.append(("Content-Length", "1"))
    elif case == "chunked-upgrade":
        headers.append(("Transfer-Encoding", "chunked"))
    elif case == "bad-key":
        headers[3] = ("Sec-WebSocket-Key", "invalid")
    elif case == "bad-version":
        headers[4] = ("Sec-WebSocket-Version", "12")
    assert _admit(headers, target) == status


def test_browser_cookie_with_loopback_origin_is_admitted() -> None:
    headers = _upgrade()
    headers[-1] = ("Cookie", "console_token=" + TOKEN)
    headers.append(("Origin", ORIGIN))
    assert _admit(headers) is None


@pytest.mark.parametrize("method", [b"POST", b"PUT", b"DELETE", b"OPTIONS"])
def test_other_methods_get_405_after_host_check(method: bytes) -> None:
    headers = [(b"host", HOST.encode())]
    assert admission.request_status(headers, method, PORT) == 405
    assert admission.request_status([(b"host", b"x")], method, PORT) == 403
    assert admission.ALLOWED_METHODS == b"GET, HEAD"


def test_a_non_get_upgrade_is_405_and_another_target_is_404() -> None:
    raw = [(b"host", HOST.encode()), (b"authorization", f"Bearer {TOKEN}".encode())]
    assert admission.upgrade_status(raw, b"HEAD", "/ws", b"", PORT, TOKEN) == 405
    assert admission.upgrade_status(raw, b"GET", "/other", b"", PORT, TOKEN) == 404


def test_pages_are_exact_paths_without_a_query() -> None:
    assert admission.page_status("/", b"", ("/",)) == 200
    assert admission.page_status("/", b"x=1", ("/",)) == 404
    assert admission.page_status("/unknown", b"", ("/",)) == 404


def _cookie_upgrade(cookie: str) -> list[tuple[str, str]]:
    headers = _upgrade()
    headers[-1] = ("Cookie", cookie)
    headers.append(("Origin", ORIGIN))
    return headers


@pytest.mark.parametrize(
    "cookie",
    [
        f"console_token_{PORT}={TOKEN}",
        f'console_token_{PORT}="{TOKEN}"',
        f"theme=dark; console_token_{PORT}={TOKEN}; other=1",
        f"console_token_1={'cd' * 32}; console_token_{PORT}={TOKEN}",
        f"console_token={TOKEN}",
    ],
)
def test_the_port_cookie_or_the_legacy_cookie_is_admitted(cookie: str) -> None:
    assert _admit(_cookie_upgrade(cookie)) is None


@pytest.mark.parametrize(
    "cookie",
    [
        f"console_token_{PORT}=wrong",
        f"console_token_1={TOKEN}",
        f"console_token_{PORT}={TOKEN}; console_token_{PORT}={TOKEN}",
        f"console_token_{PORT}={TOKEN};other=1",
        f"console_token_{PORT}={TOKEN}; ",
        f"console_token_{PORT}={TOKEN}; other=a b",
        f"console_token_{PORT}={TOKEN}; bad name=1",
        f"console_token_{PORT}={TOKEN}; novalue",
        "",
    ],
)
def test_a_wrong_foreign_duplicate_or_malformed_cookie_is_rejected(cookie: str) -> None:
    assert _admit(_cookie_upgrade(cookie)) == 401


def test_cookie_parsing_keeps_foreign_cookies_and_rejects_repeats() -> None:
    assert admission.parse_cookies(b'a=1; b="2"; c=') == {
        b"a": b"1",
        b"b": b"2",
        b"c": b"",
    }
    assert admission.parse_cookies(b"a=1; a=2") is None
    assert admission.parse_cookies(b"a=1,2") is None
    assert admission.cookie_name(PORT) == f"console_token_{PORT}".encode()


@pytest.mark.parametrize(
    "method,path,query,extra,status",
    [
        (b"GET", "/", "token=" + TOKEN, [], 303),
        (b"GET", "/", "token=wrong", [], 401),
        (b"GET", "/", "token=", [], 401),
        (b"HEAD", "/", "token=" + TOKEN, [], None),
        (b"GET", "/index.html", "token=" + TOKEN, [], None),
        (b"GET", "/", "token=" + TOKEN + "&lang=en", [], None),
        (b"GET", "/", "token=" + TOKEN + "&token=" + TOKEN, [], None),
        (b"GET", "/", "lang=en", [], None),
        (b"GET", "/", "token", [], None),
        (b"GET", "/", "token=" + TOKEN, [("authorization", "Bearer " + TOKEN)], None),
        (b"GET", "/", "token=" + TOKEN, [("content-length", "1")], None),
    ],
)
def test_bootstrap_redeems_only_one_exact_token_query(
    method: bytes,
    path: str,
    query: str,
    extra: list[tuple[str, str]],
    status: int | None,
) -> None:
    headers = [(b"host", HOST.encode())] + [
        (name.encode(), value.encode()) for name, value in extra
    ]
    assert (
        admission.bootstrap_status(headers, method, path, query.encode(), TOKEN)
        == status
    )
