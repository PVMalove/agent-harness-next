"""Synthetic Repo Map data for unit tests; no Git or cache setup."""

from harness.repo_map.contract import validation_error

HUB = "pkg/core.py"


def map_payload(commit: str, *, tier: str = "full") -> dict[str, object]:
    """Сформировать полезную нагрузку схемы v1: все виды рёбер, достоверность, хаб и диагностика."""
    if tier == "minimal":
        payload: dict[str, object] = {
            "schema_version": 1,
            "commit": commit,
            "tier": "minimal",
            "parser": "path-only",
            "degradation_reason": "offline parser bundle unavailable",
            "token_estimator_version": "1",
            "parser_provenance": {
                "policy_mode": "portable",
                "policy_sha256": None,
                "max_file_bytes": 1000,
                "max_files": 100,
                "timeout_seconds": 30,
                "max_tokens": 4000,
                "bundle_mode": "degraded",
                "bundle_source": "none",
            },
            "files": [{"path": HUB}, {"path": "pkg/cli.py"}, {"path": "README.md"}],
            "edges": [],
            "diagnostics": [],
            "estimated_tokens": 120,
        }
    else:
        payload = {
            "schema_version": 1,
            "commit": commit,
            "tier": "full",
            "parser": "bundle",
            "degradation_reason": "parser bundle applied",
            "token_estimator_version": "1",
            "parser_provenance": {
                "policy_mode": "enforced",
                "policy_sha256": "ab" * 32,
                "policy_tier": "full",
                "max_file_bytes": 1000,
                "max_files": 100,
                "timeout_seconds": 30,
                "max_tokens": 4000,
                "bundle_mode": "applied",
                "bundle_source": "local-cache",
                "python_tag": "cp314",
                "platform_tag": "linux_x86_64",
                "lock_sha256": "cd" * 32,
                "script_hash": "ef" * 32,
                "core_version": "0.25.0",
                "core_abi_range": "13-15",
                "grammars": [
                    {
                        "name": "python",
                        "version": "0.23.6",
                        "abi": 14,
                        "sha256": "12" * 32,
                    }
                ],
            },
            "files": [
                {
                    "path": HUB,
                    "signatures": ["def load_config(path)", "class Settings"],
                    "parser_status": "ok",
                },
                {
                    "path": "pkg/cli.py",
                    "signatures": ["def main(argv)"],
                    "parser_status": "ok",
                },
                {
                    "path": "pkg/broken.py",
                    "signatures": [],
                    "parser_status": "syntax_error",
                },
                {"path": "README.md", "signatures": [], "parser_status": "ok"},
            ],
            "edges": [
                {
                    "source": "pkg/cli.py",
                    "target": HUB,
                    "kind": "import",
                    "confidence": "high",
                },
                {
                    "source": "pkg/cli.py",
                    "target": HUB,
                    "kind": "unique-name-ref",
                    "confidence": "medium",
                },
                {
                    "source": "pkg/broken.py",
                    "target": HUB,
                    "kind": "ambiguous-name-ref",
                    "confidence": "low",
                },
                {
                    "source": HUB,
                    "target": "pkg/cli.py",
                    "kind": "unique-name-ref",
                    "confidence": "medium",
                },
            ],
            "diagnostics": [{"code": "syntax_error", "path": "pkg/broken.py"}],
            "estimated_tokens": 512,
        }
    assert validation_error(payload) is None
    return payload
