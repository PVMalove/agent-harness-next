"""`install-global.py --cli` installs a `harness` launcher that runs this checkout's CLI."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
