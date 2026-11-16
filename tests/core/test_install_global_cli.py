"""`install-global.py --cli` installs a `harness` launcher that runs this checkout's CLI."""

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_GLOBAL = [sys.executable, str(REPO_ROOT / "bin" / "install-global.py")]


@unittest.skipIf(sys.platform == "win32", "the POSIX launcher is checked on POSIX only")
class InstallGlobalCliTests(unittest.TestCase):
    """The launcher follows the installer's conflict policy for files it does not own."""

    def setUp(self) -> None:
        """Пустой домашний каталог для установки."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.launcher = self.home / ".local" / "bin" / "harness"

    def install(self, *extra: str) -> subprocess.CompletedProcess[str]:
        """Запустить install-global.py с --cli для временного домашнего каталога."""
        return subprocess.run(
            INSTALL_GLOBAL + ["--target-home", str(self.home), "--cli", *extra],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_launcher_runs_this_checkout_cli_and_is_idempotent(self) -> None:
        """Лаунчер исполняемый, `harness --help` через него успешен, повтор и --check проходят."""
        self.assertEqual(self.install().returncode, 0)

        self.assertTrue(os.access(self.launcher, os.X_OK))
        self.assertIn(
            str(REPO_ROOT / "harness" / "bin" / "harness.py"),
            self.launcher.read_text(encoding="utf-8"),
        )
        run = subprocess.run(
            [str(self.launcher), "--help"], capture_output=True, text=True, check=False
        )
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("usage: harness", run.stdout)
        self.assertEqual(self.install().returncode, 0)
        self.assertEqual(self.install("--check").returncode, 0)

    def test_foreign_file_is_a_conflict_until_replace_backs_it_up(self) -> None:
        """Чужой файл на месте лаунчера: без --replace-conflicts отказ, с ним бэкап и замена."""
        self.launcher.parent.mkdir(parents=True)
        self.launcher.write_text("#!/bin/sh\necho foreign\n", encoding="utf-8")

        refused = self.install()

        self.assertEqual(refused.returncode, 1)
        self.assertIn("CONFLICT", refused.stderr)
        self.assertEqual(
            self.launcher.read_text(encoding="utf-8"), "#!/bin/sh\necho foreign\n"
        )
        self.assertEqual(self.install("--replace-conflicts").returncode, 0)
        backups = list((self.home / ".agent-harness-backups").rglob("harness"))
        self.assertEqual(len(backups), 1)
        self.assertIn("echo foreign", backups[0].read_text(encoding="utf-8"))
        self.assertIn("harness.py", self.launcher.read_text(encoding="utf-8"))

    def test_check_fails_on_missing_launcher_without_writing(self) -> None:
        """--check без установленного лаунчера завершается ошибкой и ничего не пишет."""
        result = self.install("--check")

        self.assertEqual(result.returncode, 1)
        self.assertFalse(self.launcher.exists())

    def test_runtime_or_cli_is_required(self) -> None:
        """Без --runtime и без --cli установщик отказывает с ошибкой аргументов."""
        result = subprocess.run(
            INSTALL_GLOBAL + ["--target-home", str(self.home)],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("--runtime", result.stderr)


def load_installer() -> ModuleType:
    """Импортировать bin/install-global.py как модуль (имя файла содержит дефис)."""
    spec = importlib.util.spec_from_file_location(
        "install_global", REPO_ROOT / "bin" / "install-global.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WindowsLauncherTests(unittest.TestCase):
    """The CRLF `harness.cmd` launcher is current on a repeated install and under --check."""

    def test_windows_launcher_is_idempotent(self) -> None:
        """Повторная установка и --check принимают свой harness.cmd с CRLF."""
        installer = load_installer()
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)

            self.assertTrue(
                installer.install_launcher(REPO_ROOT, False, False, home, "win32")
            )
            launcher = home / ".local" / "bin" / "harness.cmd"
            self.assertIn(b"\r\n", launcher.read_bytes())
            self.assertIn(b"harness.py", launcher.read_bytes())
            self.assertTrue(
                installer.install_launcher(REPO_ROOT, False, False, home, "win32")
            )
            self.assertTrue(
                installer.install_launcher(REPO_ROOT, True, False, home, "win32")
            )


if __name__ == "__main__":
    unittest.main()
