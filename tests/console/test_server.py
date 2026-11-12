"""The console transport is tested on real loopback sockets over a temporary project."""

from __future__ import annotations

import asyncio
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from harness.console.backend.server import ConsoleServer
from harness.console.kernel.data import DashboardData
from harness.console.pin import CONSOLE_SERVER_REQUIREMENTS


def test_server_dependencies_are_exact_dev_pins_only() -> None:
    config = tomllib.loads((Path(__file__).parents[2] / "pyproject.toml").read_text(encoding="utf-8"))
    assert config["project"]["dependencies"] == []
    assert set(CONSOLE_SERVER_REQUIREMENTS) <= set(config["dependency-groups"]["dev"])






















@pytest.mark.real_process
@pytest.mark.skipif(sys.platform != "win32", reason="requires a real Windows ACL")
def test_windows_discovery_has_protected_current_user_only_dacl(tmp_path: Path) -> None:
    from harness.console.kernel.discovery import discovery_path

    project = tmp_path
    async def scenario() -> None:
        server = ConsoleServer(project)
        await server.start()
        try:
            path = str(discovery_path(project)).replace("'", "''")
            script = (
                "$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value; "
                f"$paths=@('{path}', (Split-Path -Path '{path}')); "
                "foreach($p in $paths) { $a=Get-Acl -LiteralPath $p; "
                "if(!$a.AreAccessRulesProtected -or $a.Access.Count -ne 1) {exit 3}; "
                "if($a.Access[0].IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value -ne $sid) {exit 4}; "
                "if($a.Access[0].AccessControlType -ne 'Allow' -or $a.Access[0].FileSystemRights -ne 'FullControl') {exit 5} }; 'private'"
            )
            result = await asyncio.to_thread(
                subprocess.run,
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True,
                text=True,
                timeout=10,
            )
            assert result.returncode == 0, result.stderr
            assert result.stdout.strip() == "private"
        finally:
            await server.close()

    asyncio.run(scenario())




























DATA = DashboardData(
    ok=1,
    warn=0,
    fail=0,
    skipped=0,
    repo_map_tier="не установлен",
    harness_version="1.0.0",
    drift_state="clean",
    active_batches=None,
)












































