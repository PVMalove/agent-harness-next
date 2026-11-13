#!/usr/bin/env python3
"""The container executor guide is a shipped payload of backend-orchestration only (#710).

It installs as ``.harness/docs/container-executor.md``, comes from ``harness/docs/`` and never from
the source repository's root ``docs/``, and its example adapter keeps the agent's native approval.
"""

from __future__ import annotations

import unittest

from harness.bin import harness as harness_cli

INSTALLED = ".harness/docs/container-executor.md"
SOURCE = harness_cli.PACKAGE / "docs" / "container-executor.md"
# Options that would approve actions on the human's behalf or skip the agent's permission checks.
BYPASS_TOKENS = ("dangerously", "bypassPermissions", "acceptEdits", "skip-permissions")


class ContainerGuideTests(unittest.TestCase):
    def test_backend_orchestration_installs_the_guide_byte_for_byte(self) -> None:
        payload = harness_cli.package_files(["backend-orchestration"])

        self.assertEqual(payload[INSTALLED], SOURCE.read_bytes())

    def test_a_project_without_orchestration_does_not_receive_the_guide(self) -> None:
        payload = harness_cli.package_files(["engineering-suite"])

        self.assertNotIn(INSTALLED, payload)

    def test_the_guide_comes_from_the_package_and_not_from_root_docs(self) -> None:
        root_docs = (harness_cli.ROOT / "docs").resolve()
        sources = harness_cli.selected_resources(["backend-orchestration"])

        self.assertIn(SOURCE, sources)
        self.assertFalse(SOURCE.resolve().is_relative_to(root_docs))

    def test_the_guide_gives_the_build_commands_of_both_engines(self) -> None:
        text = SOURCE.read_text(encoding="utf-8")

        for engine in ("docker", "podman"):
            for dockerfile in ("Dockerfile.sandbox", "Dockerfile.proxy", "Dockerfile.qa"):
                with self.subTest(engine=engine, dockerfile=dockerfile):
                    self.assertIn(
                        f"{engine} build -f .harness/container/{dockerfile}", text
                    )

    def test_the_qa_image_ships_a_rust_toolchain_and_the_guide_names_the_chosen_behavior(
        self,
    ) -> None:
        dockerfile = (SOURCE.parent.parent / "container/Dockerfile.qa").read_text(
            encoding="utf-8"
        )
        text = SOURCE.read_text(encoding="utf-8")

        self.assertIn("FROM harness-sandbox:local", dockerfile)
        self.assertIn("--default-toolchain", dockerfile)
        self.assertIn("build-essential", dockerfile)
        self.assertIn("there is no stage filter by executor", text)
        self.assertIn("qa-environment-failure", text)

    def test_the_guide_marks_rootless_podman_on_selinux_as_verified_and_the_rest_as_unverified(
        self,
    ) -> None:
        text = SOURCE.read_text(encoding="utf-8")
        section = text.split("## Verified and unverified environments", 1)[1]
        verified, after = section.split("not verified by a real smoke", 1)
        unverified = after.split("\n\n")[1]

        self.assertIn("rootless Podman", verified)
        self.assertIn("SELinux enforcing", verified)
        self.assertIn("Rootful Podman", unverified)
        self.assertIn("Rootless Docker", unverified)
        self.assertNotIn("Podman, rootful and rootless", unverified)

    def test_the_container_adapter_keeps_native_approval(self) -> None:
        text = SOURCE.read_text(encoding="utf-8")
        section = _section(text, "Agent adapter in a container")

        self.assertIn("claude_worker.py", section)
        self.assertIn("HARNESS_EXECUTOR=docker", section)
        self.assertIn("allowed_tools", section)
        self.assertIn("dontAsk", section)
        for token in BYPASS_TOKENS:
            with self.subTest(token=token):
                self.assertNotIn(token, text)

    def test_the_container_adapter_streams_the_events_the_host_attests_from(self) -> None:
        """#1014: the host reads the model from the stream-json init event of the worker."""
        section = _section(
            SOURCE.read_text(encoding="utf-8"), "Agent adapter in a container"
        )

        self.assertIn("--output-format stream-json --verbose", section)
        self.assertIn("never to run", section)

    def test_reports_from_a_container_name_the_host_side_self_report(self) -> None:
        section = _section(
            SOURCE.read_text(encoding="utf-8"), "Reports from a container"
        )

        for expected in (
            "container-host",
            "init",
            "report submit --file",
            "model_mismatch",
            "heartbeat",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, section)

    def test_the_guide_names_the_subscription_token_and_distrobox(self) -> None:
        text = SOURCE.read_text(encoding="utf-8")

        self.assertIn("CLAUDE_CODE_OAUTH_TOKEN", text)
        self.assertIn("claude setup-token", text)
        distrobox = _section(text, "Running inside distrobox")
        self.assertIn("You must run distrobox-host-exec inside a container", distrobox)
        self.assertIn("/sys/fs/selinux/enforce", distrobox)

    def test_the_guide_shows_container_qa_with_in_process_roles(self) -> None:
        section = _section(
            SOURCE.read_text(encoding="utf-8"), "Container QA with in-process roles"
        )

        self.assertIn('"operations"', section)
        self.assertNotIn('"defaults"', section)
        self.assertIn("in-process", section)


def _section(text: str, title: str) -> str:
    """The body of the ``##`` section ``title``, up to the next ``##`` heading."""
    return text.split(f"## {title}\n", 1)[1].split("\n## ", 1)[0]


if __name__ == "__main__":
    unittest.main()
