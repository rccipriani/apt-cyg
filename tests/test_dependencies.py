"""Exercise the installer against local archives in an isolated fake Cygwin root.

Run with Python 3 and Bash available: python3 -m unittest discover -s tests -v
No downloads, elevated privileges, or changes to the host package DB are needed.
"""

import hashlib
import io
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "apt-cyg"


class DependencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="apt-cyg-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.setup = self.root / "etc/setup"
        self.postinstall = self.root / "etc/postinstall"
        self.cache = self.root / "cache with spaces"
        self.workspace = self.cache / "https%3a%2f%2fexample.invalid" / "x86_64"
        for directory in (self.setup, self.postinstall, self.workspace, self.root / "bin", self.root / "tmp"):
            directory.mkdir(parents=True, exist_ok=True)
        self.db = self.setup / "installed.db"
        self.db.write_text("INSTALLED.DB 3\n")
        (self.setup / "setup.rc").write_text(
            f"last-cache\n\t{self.cache}\nlast-mirror\n\thttps://example.invalid\n"
        )
        self.metadata = []
        script = SOURCE.read_text()
        script = script.replace("/tmp/", str(self.root / "tmp") + "/")
        script = script.replace("/etc/setup", str(self.setup))
        script = script.replace("/etc/postinstall", str(self.postinstall))
        script = script.replace("tar -x -C / -f", f'tar -x -C "{self.root}" -f')
        self.executable = self.root / "bin/apt-cyg"
        self.executable.write_text(script)
        self.executable.chmod(0o755)
        self.env = dict(os.environ, PATH=f"{self.root / 'bin'}:{os.environ['PATH']}")
        self.env.pop("APT_CYG_INSTALLING", None)

    def package(self, name, dependencies="", field="depends2", extra=""):
        relative = f"x86_64/release/{name}/{name}-1.0-1.tar.xz"
        archive = self.cache / "https%3a%2f%2fexample.invalid" / relative
        archive.parent.mkdir(parents=True, exist_ok=True)
        payload = name.encode()
        with tarfile.open(archive, "w:xz") as tar:
            info = tarfile.TarInfo(f"bin/{name}.fixture")
            info.size = len(payload)
            tar.addfile(info, io.BytesIO(payload))
        digest = hashlib.sha512(archive.read_bytes()).hexdigest()
        self.metadata.append(
            f"@ {name}\nversion: 1.0-1\ninstall: {relative} {archive.stat().st_size} {digest}\n"
            f"{field}: {dependencies}\n{extra}\n"
        )
        return archive

    def run_install(self, *packages):
        (self.workspace / "setup.ini").write_text("\n".join(self.metadata))
        return subprocess.run(
            ["bash", str(self.executable), "install", *packages],
            cwd=self.root, env=self.env, text=True, capture_output=True, timeout=15,
        )

    def assert_installed(self, *packages):
        names = {line.split()[0] for line in self.db.read_text().splitlines()[1:]}
        for package in packages:
            self.assertIn(package, names)
            self.assertTrue((self.root / f"bin/{package}.fixture").is_file())

    def test_jq_modern_dependencies_and_transitive_dependency(self):
        self.package("jq", "libjq1, libonig5")
        self.package("libjq1", "libonig5")
        self.package("libonig5")
        result = self.run_install("jq")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_installed("jq", "libjq1", "libonig5")

    def test_legacy_dependencies(self):
        self.package("app", "liba libb", field="requires")
        self.package("liba")
        self.package("libb")
        result = self.run_install("app")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_installed("app", "liba", "libb")

    def test_depends_alias_and_modern_precedence(self):
        self.package("app", "liba", field="depends", extra="requires: obsolete")
        self.package("liba")
        result = self.run_install("app")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_installed("app", "liba")

    def test_empty_modern_list_overrides_legacy(self):
        self.package("app", extra="requires: obsolete")
        result = self.run_install("app")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_installed("app")

    def test_previous_and_test_dependencies_are_excluded(self):
        self.package("app", "liba", extra="[prev]\nversion: 0.9-1\ndepends2: missing-old\n[test]\nversion: 2.0-1\ndepends2: missing-test")
        self.package("liba")
        result = self.run_install("app")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_installed("app", "liba")

    def test_explicit_current_after_test(self):
        self.package("app", "liba")
        self.metadata[0] = self.metadata[0].replace(
            "version: 1.0-1", "[test]\nversion: 2.0-1\ndepends2: missing-test\n[curr]\nversion: 1.0-1"
        )
        self.package("liba")
        result = self.run_install("app")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_installed_parent_repairs_missing_dependency(self):
        self.package("jq", "libjq1")
        self.package("libjq1")
        self.db.write_text("INSTALLED.DB 3\njq jq-1.0-1.tar.xz 0\n")
        (self.root / "bin/jq.fixture").write_text("jq")
        result = self.run_install("jq")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_installed("jq", "libjq1")

    def test_cycle_terminates(self):
        self.package("app", "liba")
        self.package("liba", "app")
        result = self.run_install("app")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_installed("app", "liba")

    def test_missing_dependency_returns_failure_and_can_retry(self):
        self.package("app", "missing")
        result = self.run_install("app")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Package app installed", result.stdout)
        self.package("missing")
        result = self.run_install("app")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_installed("app", "missing")

    def test_version_constraint_fails_before_extracting_parent(self):
        self.package("app", "liba (>= 2.0-1)")
        result = self.run_install("app")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Cygwin Setup", result.stderr)
        self.assertFalse((self.root / "bin/app.fixture").exists())

    def test_failed_postinstall_remains_retryable(self):
        self.package("app")
        script = self.postinstall / "app.sh"
        script.write_text("#!/bin/bash\nexit 1\n")
        script.chmod(0o755)
        result = self.run_install("app")
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(script.exists())
        self.assertFalse(script.with_suffix(".sh.done").exists())
        script.write_text("#!/bin/bash\nexit 0\n")
        result = self.run_install("app")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(script.with_suffix(".sh.done").exists())

    def test_bad_archive_is_not_registered(self):
        archive = self.package("app")
        old_digest = hashlib.sha512(archive.read_bytes()).hexdigest()
        old_size = archive.stat().st_size
        archive.write_bytes(b"invalid archive")
        self.metadata[0] = self.metadata[0].replace(
            f"{old_size} {old_digest}",
            f"{archive.stat().st_size} {hashlib.sha512(archive.read_bytes()).hexdigest()}",
        )
        result = self.run_install("app")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("app ", self.db.read_text())

    def test_dependency_graph_uses_current_modern_metadata(self):
        self.package("app", "liba (>= 1.0), libb", extra="[prev]\nversion: 0.9\ndepends2: obsolete")
        (self.workspace / "setup.ini").write_text("\n".join(self.metadata))
        # Load definitions without invoking the command-line dispatcher.
        definitions = self.executable.read_text().split("if [ -p /dev/stdin ]", 1)[0]
        result = subprocess.run(
            ["bash", "-c", definitions + "\ndependency-edges\n"],
            cwd=self.workspace, env=self.env, text=True, capture_output=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ["app liba", "app libb"])


if __name__ == "__main__":
    unittest.main()
