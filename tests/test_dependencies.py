"""Exercise the installer against local archives in an isolated fake Cygwin root.

Run with Python 3 and Bash available: python3 -m unittest discover -s tests -v
No downloads, elevated privileges, or changes to the host package DB are needed.
"""

import hashlib
import gzip
import io
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import time
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "apt-cyg"


class DependencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.keys = tempfile.TemporaryDirectory(prefix="apt-cyg-test-keys-")
        cls.signer = Path(cls.keys.name) / "gpg"
        cls.signer.mkdir(mode=0o700)
        subprocess.run(["gpg", "--batch", "--homedir", str(cls.signer), "--passphrase", "",
                        "--quick-generate-key", "apt-cyg fixture", "ed25519", "sign", "0"],
                       check=True, capture_output=True)
        cls.keyring = Path(cls.keys.name) / "trustedkeys.gpg"
        cls.keyring.write_bytes(subprocess.check_output(["gpg", "--batch", "--homedir", str(cls.signer), "--export"]))

    @classmethod
    def tearDownClass(cls):
        cls.keys.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="apt-cyg-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.setup = self.root / "etc/setup"
        self.postinstall = self.root / "etc/postinstall"
        self.cache = self.root / "cache with spaces"
        self.mirror = self.root / "mirror"
        self.mirror.mkdir()
        self.mirror_url = self.mirror.as_uri()
        self.mirror_cache = self.cache / self.mirror_url.replace("/", "%2f").replace(":", "%3a")
        self.workspace = self.mirror_cache / "x86_64"
        for directory in (self.setup, self.postinstall, self.workspace, self.root / "bin", self.root / "tmp"):
            directory.mkdir(parents=True, exist_ok=True)
        self.db = self.setup / "installed.db"
        self.db.write_text("INSTALLED.DB 3\n")
        (self.setup / "setup.rc").write_text(
            f"last-cache\n\t{self.cache}\nlast-mirror\n\t{self.mirror_url}\n"
        )
        self.metadata = []
        script = SOURCE.read_text()
        self.executable = self.root / "bin/apt-cyg"
        self.executable.write_text(script)
        self.executable.chmod(0o755)
        self.env = dict(os.environ, PATH=f"{self.root / 'bin'}:{os.environ['PATH']}")
        self.env.update(APT_CYG_ROOT=str(self.root), APT_CYG_ARCH="x86_64", APT_CYG_KEYRING=str(self.keyring))
        self.env.pop("APT_CYG_INSTALLING", None)

    def package(self, name, dependencies="", field="depends2", extra="", version="1.0-1", files=None):
        relative = f"x86_64/release/{name}/{name}-{version}.tar.xz"
        archive = self.mirror_cache / relative
        archive.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive, "w:xz") as tar:
            for filename, content in (files or {f"bin/{name}.fixture": name}).items():
                payload = content.encode()
                info = tarfile.TarInfo(filename)
                info.size = len(payload)
                tar.addfile(info, io.BytesIO(payload))
        digest = hashlib.sha512(archive.read_bytes()).hexdigest()
        self.metadata.append(
            f"@ {name}\nversion: {version}\ninstall: {relative} {archive.stat().st_size} {digest}\n"
            f"{field}: {dependencies}\n{extra}\n"
        )
        return archive

    def flags(self):
        return {row.split()[0]: row.split()[2] for row in self.db.read_text().splitlines()[1:]}

    def assert_ok(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def write_metadata(self):
        (self.workspace / "setup.ini").write_text("\n".join(self.metadata))
        signed = self.workspace / "setup.signed.ini"
        signed.write_bytes((self.workspace / "setup.ini").read_bytes())
        subprocess.run(["gpg", "--batch", "--yes", "--homedir", str(self.signer),
                        "--detach-sign", "--output", str(signed) + ".sig", str(signed)],
                       check=True, capture_output=True)
        (self.workspace / "setup.signed-source").write_text("setup.ini\n")

    def run_cli(self, *arguments, metadata=True, env=None):
        if metadata:
            self.write_metadata()
        return subprocess.run(
            ["bash", str(self.executable), *arguments],
            cwd=self.root, env=env or self.env, text=True, capture_output=True, timeout=20,
        )

    def run_install(self, *packages):
        return self.run_cli("install", *packages)

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
        result = self.run_cli("depends", "app")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(set(result.stdout.splitlines()), {"app", "app > liba", "app > libb"})

    def test_install_records_manual_and_automatic_packages(self):
        self.package("app", "liba")
        self.package("liba")
        self.assert_ok(self.run_install("app"))
        self.assertEqual(self.flags(), {"app": "1", "liba": "0"})
        self.assert_ok(self.run_install("liba"))
        self.assertEqual(self.flags()["liba"], "1")

    def test_existing_packages_are_conservatively_migrated_as_manual(self):
        self.package("app")
        self.db.write_text("INSTALLED.DB 3\napp app-1.0-1.tar.xz 0\n")
        self.assert_ok(self.run_install("app"))
        self.assertEqual(self.flags()["app"], "1")

    def test_dry_run_does_not_extract_or_mark_packages(self):
        self.package("app", "liba")
        self.package("liba")
        before = self.db.read_bytes()
        result = self.run_cli("install", "--dry-run", "app")
        self.assert_ok(result)
        self.assertIn("2 to install", result.stdout)
        self.assertEqual(self.db.read_bytes(), before)
        self.assertFalse((self.root / "bin/app.fixture").exists())
        self.assertFalse((self.setup / "app.lst.gz").exists())
        self.assertFalse((self.setup / ".apt-cyg.lock").exists())

    def test_missing_transitive_dependency_does_not_extract_any_package(self):
        self.package("app", "liba")
        self.package("liba", "missing")
        result = self.run_install("app")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "bin/app.fixture").exists())
        self.assertFalse((self.root / "bin/liba.fixture").exists())

    def test_reinstall_repairs_file_and_preserves_auto_flag(self):
        self.package("app", "liba")
        self.package("liba")
        self.assert_ok(self.run_install("app"))
        (self.root / "bin/liba.fixture").unlink()
        self.assert_ok(self.run_cli("reinstall", "liba"))
        self.assertTrue((self.root / "bin/liba.fixture").exists())
        self.assertEqual(self.flags()["liba"], "0")

    def test_reinstall_selects_authenticated_previous_version(self):
        self.package("app", version="1.0-1")
        self.assert_ok(self.run_install("app"))
        previous = self.metadata.pop().split("\n", 1)[1]
        self.package("app", version="2.0-1")
        self.metadata[0] += "\n[prev]\n" + previous
        (self.root / "bin/app.fixture").unlink()
        self.assert_ok(self.run_cli("reinstall", "app"))
        self.assertIn("app-1.0-1.tar.xz", self.db.read_text())

    def test_upgrade_installs_new_dependencies_and_drops_stale_files(self):
        self.package("app", files={"bin/app.fixture": "old", "bin/stale": "stale"})
        self.assert_ok(self.run_install("app"))
        self.metadata.clear()
        self.package("app", "libb", version="2.0-1", files={"bin/app.fixture": "new"})
        self.package("libb")
        result = self.run_cli("upgrade", "app")
        self.assert_ok(result)
        self.assertEqual((self.root / "bin/app.fixture").read_text(), "new")
        self.assertFalse((self.root / "bin/stale").exists())
        self.assertEqual(self.flags(), {"app": "1", "libb": "0"})

    def test_remove_refuses_to_break_dependent_package(self):
        self.package("app", "liba")
        self.package("liba")
        self.assert_ok(self.run_install("app"))
        before = self.db.read_bytes()
        result = self.run_cli("remove", "liba")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.db.read_bytes(), before)

    def test_remove_dry_run_and_autoremove(self):
        self.package("app", "liba")
        self.package("liba")
        self.assert_ok(self.run_install("app"))
        self.assert_ok(self.run_cli("remove", "--simulate", "app"))
        self.assertTrue((self.root / "bin/app.fixture").exists())
        self.assert_ok(self.run_cli("remove", "app"))
        # Keep an explicit manual root to exercise orphan reachability.
        self.package("keep")
        self.assert_ok(self.run_install("keep"))
        self.assert_ok(self.run_cli("autoremove", "--simulate"))
        self.assertTrue((self.root / "bin/liba.fixture").exists())
        self.assert_ok(self.run_cli("autoremove"))
        self.assertFalse((self.root / "bin/liba.fixture").exists())
        self.assertEqual(self.flags(), {"keep": "1"})

    def test_manual_and_automatic_mark_commands(self):
        self.package("app")
        self.assert_ok(self.run_install("app"))
        self.assert_ok(self.run_cli("mark-auto", "app"))
        self.assertEqual(self.flags()["app"], "0")
        result = self.run_cli("list-auto")
        self.assert_ok(result)
        self.assertEqual(result.stdout.strip(), "app")
        self.assert_ok(self.run_cli("mark-manual", "app"))
        self.assertEqual(self.flags()["app"], "1")

    def test_shared_file_survives_package_removal(self):
        self.package("app", files={"bin/app.fixture": "app", "share/shared": "shared"})
        self.package("other", files={"bin/other.fixture": "other", "share/shared": "shared"})
        self.assert_ok(self.run_install("app", "other"))
        self.assert_ok(self.run_cli("remove", "app"))
        self.assertTrue((self.root / "share/shared").exists())

    def test_lock_prevents_another_writer(self):
        self.package("app")
        lock = self.setup / ".apt-cyg.lock"
        lock.mkdir()
        (lock / "pid").write_text(str(os.getpid()))
        result = self.run_install("app")
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(lock.exists())
        self.assertNotIn("app ", self.db.read_text())

    def test_failed_command_releases_owned_lock(self):
        result = self.run_install("missing")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.setup / ".apt-cyg.lock").exists())

    def test_index_reused_when_metadata_is_unchanged(self):
        self.package("app")
        self.assert_ok(self.run_cli("listall", "app"))
        index = self.workspace / "setup.idx"
        before = index.stat().st_mtime_ns
        self.assert_ok(self.run_cli("listall", "app", metadata=False))
        self.assertEqual(index.stat().st_mtime_ns, before)

    def test_tampered_metadata_is_rejected(self):
        self.package("app")
        self.write_metadata()
        (self.workspace / "setup.signed.ini").write_text("tampered")
        result = self.run_cli("install", "app", metadata=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("app ", self.db.read_text())

    def publish_mirror_metadata(self, extension="xz", signed=True):
        import bz2
        import lzma
        raw = "\n".join(self.metadata).encode()
        content = {"xz": lzma.compress, "bz2": bz2.compress, "gz": gzip.compress, "ini": lambda value: value}[extension](raw)
        destination = self.mirror / "x86_64" / f"setup.{extension}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        if signed:
            subprocess.run(["gpg", "--batch", "--yes", "--homedir", str(self.signer), "--detach-sign",
                            "--output", str(destination) + ".sig", str(destination)], check=True, capture_output=True)
        return destination

    def test_signed_compressed_metadata_update_and_verification(self):
        self.package("app")
        self.publish_mirror_metadata()
        self.assert_ok(self.run_cli("update", metadata=False))
        self.assert_ok(self.run_cli("install", "app", metadata=False))
        self.assert_installed("app")

    def test_unsigned_metadata_update_fails(self):
        self.package("app")
        self.publish_mirror_metadata(signed=False)
        result = self.run_cli("update", metadata=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.workspace / "setup.ini").exists())

    def test_explicit_no_verify_allows_unsigned_mirror(self):
        self.package("app")
        self.publish_mirror_metadata(signed=False)
        self.assert_ok(self.run_cli("update", "--no-verify", metadata=False))

    def test_bzip2_gzip_and_plain_metadata_fallback(self):
        self.package("app")
        for extension in ("bz2", "gz", "ini"):
            with self.subTest(extension=extension):
                path = self.publish_mirror_metadata(extension)
                self.assert_ok(self.run_cli("update", metadata=False))
                path.unlink()
                Path(str(path) + ".sig").unlink()

    def test_completion_output_and_installation(self):
        result = self.run_cli("completion")
        self.assert_ok(result)
        self.assertIn("complete -F _apt_cyg_complete apt-cyg", result.stdout)
        syntax = subprocess.run(["bash", "-n"], input=result.stdout, text=True, capture_output=True)
        self.assertEqual(syntax.returncode, 0, syntax.stderr)
        self.assert_ok(self.run_cli("completion-install"))
        self.assertTrue((self.root / "etc/bash_completion.d/apt-cyg").exists())
        self.assert_ok(self.run_cli("completion-uninstall"))
        self.assertFalse((self.root / "etc/bash_completion.d/apt-cyg").exists())

    def test_benchmark_local_mirror(self):
        self.package("app")
        self.publish_mirror_metadata()
        result = self.run_cli("benchmark-mirrors", self.mirror_url)
        self.assert_ok(result)
        self.assertIn(self.mirror_url, result.stdout)

    def test_self_update_dry_run_preserves_script(self):
        before = self.executable.read_bytes()
        result = self.run_cli("self-update", "--simulate")
        self.assert_ok(result)
        self.assertIn("rccipriani/apt-cyg", result.stdout)
        self.assertEqual(self.executable.read_bytes(), before)

    def test_key_listing_uses_explicit_keyring(self):
        result = self.run_cli("key-list")
        self.assert_ok(result)
        self.assertIn("apt-cyg fixture", result.stdout)

    def mock_downloader(self, name, body):
        executable = self.root / "bin" / name
        executable.write_text("#!/bin/bash\n" + body + "\n")
        executable.chmod(0o755)

    def test_self_update_keeps_backup_and_rejects_invalid_script(self):
        before = self.executable.read_bytes()
        candidate = self.root / "replacement"
        candidate.write_text("#!/bin/bash\necho updated\n")
        self.mock_downloader("wget", 'while (( $# )); do if [[ $1 == -O ]]; then out=$2; shift; fi; shift; done\ncp "$UPDATE_FIXTURE" "$out"')
        env = dict(self.env, APT_CYG_DOWNLOADER="wget", UPDATE_FIXTURE=str(candidate))
        self.assert_ok(self.run_cli("self-update", env=env))
        self.assertEqual(self.executable.read_bytes(), candidate.read_bytes())
        self.assertEqual(Path(str(self.executable) + ".bak").read_bytes(), before)
        self.executable.write_bytes(before)
        candidate.write_text("#!/bin/bash\nif then\n")
        result = self.run_cli("self-update", env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.executable.read_bytes(), before)

    def test_downloader_failure_falls_back_to_curl(self):
        self.package("app")
        self.mock_downloader("wget", "exit 1")
        self.mock_downloader("curl", 'while (( $# )); do if [[ $1 == -o ]]; then out=$2; shift; fi; shift; done\nprintf fixture > "$out"')
        result = self.run_cli("benchmark-mirrors", "https://fixture.invalid")
        self.assert_ok(result)
        self.assertIn("https://fixture.invalid", result.stdout)

    def test_autoremove_can_remove_last_automatic_package(self):
        self.package("orphan")
        self.assert_ok(self.run_install("orphan"))
        self.assert_ok(self.run_cli("mark-auto", "orphan"))
        self.assert_ok(self.run_cli("autoremove", "--yes"))
        self.assertEqual(self.flags(), {})

    def test_read_only_command_does_not_take_writer_lock(self):
        lock = self.setup / ".apt-cyg.lock"
        lock.mkdir()
        (lock / "pid").write_text("999999\n")
        self.assert_ok(self.run_cli("list-manual"))

    def test_metadata_timestamp_rollback_is_rejected(self):
        self.package("app")
        self.metadata.insert(0, "setup-timestamp: 200\n")
        self.write_metadata()
        before = (self.workspace / "setup.ini").read_bytes()
        self.metadata[0] = "setup-timestamp: 100\n"
        self.publish_mirror_metadata()
        result = self.run_cli("update", metadata=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.workspace / "setup.ini").read_bytes(), before)

    def test_removal_checks_existing_setup_packages_without_sidecars(self):
        self.package("app", "liba")
        self.package("liba")
        self.assert_ok(self.run_install("app"))
        for sidecar in self.setup.glob("*.deps"):
            sidecar.unlink()
        result = self.run_cli("remove", "liba", "--yes")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("needed by", result.stderr)

    def test_stale_dependency_sidecar_after_setup_upgrade_is_ignored(self):
        self.package("app")
        self.package("liba")
        self.assert_ok(self.run_install("app", "liba"))
        self.metadata = []
        self.package("app", "liba", version="2.0-1")
        self.package("liba")
        self.db.write_text(self.db.read_text().replace("app-1.0-1.tar.xz", "app-2.0-1.tar.xz"))
        result = self.run_cli("remove", "liba", "--yes")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("needed by", result.stderr)

    def test_invalid_signature_keeps_previous_metadata(self):
        self.package("app")
        self.write_metadata()
        before = (self.workspace / "setup.ini").read_bytes()
        path = self.publish_mirror_metadata()
        Path(str(path) + ".sig").write_bytes(b"invalid signature")
        result = self.run_cli("update", metadata=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.workspace / "setup.ini").read_bytes(), before)

    def test_key_add_writes_dedicated_keyring(self):
        destination = self.setup / "custom.gpg"
        env = dict(self.env, APT_CYG_KEYRING=str(destination))
        self.assert_ok(self.run_cli("key-add", str(self.keyring), env=env))
        result = self.run_cli("key-list", env=env)
        self.assert_ok(result)
        self.assertIn("apt-cyg fixture", result.stdout)

    def test_perpetual_postinstall_order_and_retry(self):
        self.package("app")
        for name in ("zp_last.dash", "normal.sh", "0p_first.dash"):
            (self.postinstall / name).write_text(f'echo {name} >> "$APT_CYG_ROOT/order"\n')
        self.assert_ok(self.run_install("app"))
        self.assertEqual((self.root / "order").read_text().splitlines(),
                         ["0p_first.dash", "normal.sh", "zp_last.dash"])
        self.assertTrue((self.postinstall / "normal.sh.done").exists())
        self.assert_ok(self.run_install("app"))
        self.assertEqual((self.root / "order").read_text().splitlines()[-2:],
                         ["0p_first.dash", "zp_last.dash"])


if __name__ == "__main__":
    unittest.main()
