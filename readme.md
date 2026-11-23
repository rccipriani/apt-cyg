# apt-cyg

Command-line package management for Cygwin, using Cygwin's repositories,
package cache, manifests, and `installed.db`.

This fork combines the modern dependency repairs in
[rccipriani/apt-cyg](https://github.com/rccipriani/apt-cyg) with the indexed
planner and package tracking foundation from
[ZenSage apt-cyg2](https://github.com/zensage/apt-cyg2), adapted from commit
`7a3eaf4788bc63e814d3dc52815e1749122d49ed`. Original MIT copyright notices
are retained in the script and license.

## Installation and requirements

Use the official [Cygwin Setup](https://cygwin.com/install.html) to install
Bash 4.2+, gawk, tar, gzip, bzip2, xz, coreutils, grep, sed, and gnupg, plus
at least one of wget, curl, or lynx. Install zstd for Zstandard metadata and
archives. GNU tar must support the compression used by a package archive.
Cygwin normally supplies most of these tools already.

Save this repository's `apt-cyg` script with Unix line endings and install it:

```bash
install -m 755 apt-cyg /usr/local/bin/apt-cyg
apt-cyg update
apt-cyg install jq
```

The root directory is the Cygwin installation running the script. Confirm
`cygpath -w /` before installing packages if you have both MobaXterm's bundled
environment and a separate Cygwin installation.

## Package operations

```bash
apt-cyg install jq vim          # requested packages become manual picks
apt-cyg install jq --simulate   # show installation/dependency plan
apt-cyg update                  # refresh signed repository metadata
apt-cyg upgrade --simulate      # preview changes to all installed packages
apt-cyg upgrade vim             # select only vim for upgrade
apt-cyg reinstall jq            # restore files from its installed version
apt-cyg remove vim              # check dependents before removal
apt-cyg autoremove --simulate   # preview unused automatic dependencies
apt-cyg autoremove
apt-cyg download jq             # download and verify without extracting
```

Install, upgrade, reinstall, remove, and autoremove display a plan. Interactive
sessions ask for confirmation; `--yes` skips the question. Noninteractive
invocations do not prompt. `--simulate`, `--dry-run`, and `-s` never extract
packages, run package scripts, or modify the installed package database.
Metadata and its cache index may still be refreshed while preparing a plan.

All required archives are downloaded and checked before extraction starts.
Missing dependencies, checksum failures, failed extraction, and failed package
scripts return a nonzero status. An installed parent package is still traversed
to repair missing dependencies. Failed one-shot postinstall scripts stay pending
and can be retried by running `install` for an installed package.

Reinstall selects the installed archive version from authenticated metadata,
including a retained previous version. If that version is no longer advertised,
it fails with instructions to use Setup. Upgrade selects the repository's current
version when its archive differs from the installed archive; this can select an
older version if the repository's current version is older.

Dependencies prefer `depends2`, then `depends`, then legacy `requires`.
Explicit current sections are honored; test/previous sections are excluded from
the current index. Version constraints and alternative dependencies are rejected
before extraction: use official Setup for those packages. `--nodeps` explicitly
bypasses dependency handling; `--noscripts` explicitly skips package scripts.

## Tracking and removal

```bash
apt-cyg list-manual
apt-cyg list-auto
apt-cyg mark-manual jq
apt-cyg mark-auto libjq1
```

Explicit installs are manual; newly installed dependencies are automatic.
Upgrade and reinstall preserve these marks. On first use, existing installed
packages are conservatively treated as manual, so migration cannot immediately
make your old packages eligible for autoremove. Adjust marks explicitly as needed.

Autoremove follows dependencies from manual packages, Base packages, and
protected essentials. Removal refuses to break other installed packages unless
`--force` is explicitly supplied. Shared files are preserved while another
installed package owns them. Missing installed-version dependency information
causes removal/autoremove to fail rather than guessing. Per-package dependency
sidecars are tied to the archive version, so changes made by Setup invalidate
stale dependency records.

## Verification and downloads

Repository metadata is verified with GPG by default, including cached metadata.
The initial Cygwin key is fetched over HTTPS and checked against the pinned
primary fingerprint:

```
5640 5CF6 FCC8 1574 682A 5D56 1A69 8DE9 E2E5 6300
```

The dedicated keyring is `/etc/setup/apt-cyg-trustedkeys.gpg`; your personal GPG
keyring is untouched. For a private repository, explicitly trust its key:

```bash
apt-cyg key-add /path/to/repository-public-key.asc
apt-cyg key-list
```

A missing/invalid signature fails closed. Metadata timestamps are checked against
the previous cache to reject rollback when a prior timestamp is available.
`--no-verify` is an explicit signature-verification bypass. Package archives are
checked using the MD5, SHA-256, or SHA-512 digest recorded in metadata; Cygwin
repository signatures authenticate the metadata containing those hashes. This
does not claim separate detached signatures exist for every package archive.

Metadata formats are tried in this order: Zstandard, xz, bzip2, gzip, plain text,
subject to installed decompressors. A signed source is retained for cache checks.
Downloads use temporary files and fall back through available wget, curl, and
lynx clients. `APT_CYG_DOWNLOADER=wget|curl|lynx` explicitly selects one client.
`APT_CYG_TIMEOUT` controls request timeouts (default 30 seconds).

## Mirrors, completion, and self-updates

```bash
apt-cyg mirror
apt-cyg mirror https://mirrors.kernel.org/sourceware/cygwin
apt-cyg mirrors-list
apt-cyg benchmark-mirrors https://mirror-one/cygwin https://mirror-two/cygwin
apt-cyg cache /path/to/cache
apt-cyg completion-install
apt-cyg self-update --simulate
apt-cyg self-update
```

Benchmarking measures a full `setup.xz` download from each supplied mirror,
sorted by elapsed seconds; it does not automatically change your mirror.
Without URLs, it benchmarks the configured mirror. Per-mirror timeout defaults
to 10 seconds (`APT_CYG_BENCHMARK_TIMEOUT`).

`completion` prints a Bash completion definition; `completion-install` writes
`/etc/bash_completion.d/apt-cyg`. Load that file in Bash or restart a shell
configured to use bash-completion. `completion-uninstall` removes it.

Self-updates are pinned to this fork's `master` script over HTTPS. The replacement
must have the expected Bash shebang and pass `bash -n`; the current script is
saved as `apt-cyg.bak` and the replacement preserves its mode. Self-updates trust
this GitHub repository and TLS; they do not have a detached release signature.
`upgrade-self` is an alias.

## Queries

`show`, `depends`, `rdepends`, `list`, `listall`, `category`, `listfiles`, `search`,
and `searchall` remain available. For example:

```bash
apt-cyg listall 'vim|jq'
apt-cyg depends jq
apt-cyg listfiles jq
apt-cyg search cygjq-1.dll
```

A single-pass parsed metadata index is cached until metadata changes. See
`apt-cyg --help` for command options and environment overrides.

## Integrity checks and repair

```bash
apt-cyg check
apt-cyg check --files
apt-cyg check --files --fix --simulate
apt-cyg check --files --fix --yes
```

`check` validates database structure and duplicate entries, readable manifests,
installed-version dependencies, and pending one-shot postinstall scripts.
`--files` additionally checks that manifest-listed files exist; it does not
compare individual file contents or treat local configuration edits as damage.
Optional package names restrict package checks; pending scripts are still checked
globally. A clean check returns zero; problems return nonzero.

`--fix` prepares a normal dependency/reinstall plan for missing dependencies and
broken packages, then retries pending scripts and rechecks. Reinstalled versions
must still be in authenticated metadata. Malformed databases and unavailable
installed-version dependency records require manual repair or official Setup.
Repairs use the same writer lock, verification, and simulation rules as installs.

## Local packages

```bash
apt-cyg localinstall ./example-1.0-1.tar.xz --simulate
apt-cyg localinstall ./example-1.0-1.tar.xz
apt-cyg localinstall ./private-1.0-1.tar.xz --allow-untrusted
```

A local archive whose name/version exists in repository metadata must match that
metadata's digest. For a private archive absent from metadata, explicitly supply
`--allow-untrusted` and an adjacent `private-1.0-1.hint` file containing
`depends2:`, `depends:`, or `requires:` (an empty list must be declared explicitly).
This trusts the archive, its package scripts, and its dependency hint. The option
does not bypass a checksum mismatch for an archive advertised by the repository.
Repository metadata is still needed to resolve dependencies.

`--name NAME` overrides name inference for one archive. Multiple local archives
can be installed together; dependencies are planned before extraction. Absolute
and parent-traversal archive member paths are rejected. Requested local packages
become manual picks. Their dependency records are retained for removal checks.
Version constraints and alternatives continue to require official Setup.

## Official Setup and files in use

```bash
apt-cyg busy jq vim
apt-cyg update-setup
apt-cyg setup --simulate -- --no-admin
apt-cyg setup -- --no-admin --packages jq
apt-cyg dist-upgrade --simulate -- --no-admin
apt-cyg dist-upgrade -- --no-admin
```

`show-packages-busyness` is an alias for `busy`. These commands observe package
files mapped by processes and report matching PIDs. `no-observed-use` does not
prove a file is unlocked: Windows processes and inaccessible process maps may
be invisible. Diagnostics never open package files for writing or kill processes.

`update-setup` downloads official `setup-ARCH.exe` and its detached signature
into `/etc/setup/setup-bin`. Signature verification is mandatory even when
`--no-verify` was supplied for metadata. `setup` verifies the cached installer
again before launching it, downloading it first if absent. Launching requires
native Cygwin and `cygpath`; downloading and simulation can run in fixture roots.
Native options must follow `--` so apt-cyg does not interpret them.

The wrapper fixes `--root` to the active Cygwin installation, rejects root
overrides, passes `--wait`, and propagates the installer's exit status.
`dist-upgrade` adds `--upgrade-also`. These launch the installer without forcing
unattended mode or terminating Cygwin processes. Close Cygwin applications for
runtime/DLL updates and follow Setup's prompts; a reboot may be required. Setup
uses its own downloader/proxy options, independently of apt-cyg's HTTP clients.

## Additional mirror, trust, and source tools

```bash
apt-cyg mirrors-list-online
apt-cyg mirrors-list-online --long
apt-cyg mirrors-list-long
apt-cyg benchmark-parallel-mirrors URL1 URL2 --max-jobs 4
apt-cyg benchmark-parallel-mirrors-list --max-jobs 4
apt-cyg key-finger
apt-cyg key-del FULL_PRIMARY_KEY_FINGERPRINT
apt-cyg source jq
```

Parallel benchmarking uses bounded batches (1 to 64 workers, default 4), sorts
successful measurements, reports failures, and returns nonzero if any mirror
fails. The `-list` variant uses recorded mirrors. Online discovery fetches the
official HTTPS mirror list; `--long` preserves full semicolon-delimited records.
No mirror is selected automatically.

`key-del` requires a full fingerprint and changes only the dedicated trusted
keyring. Deleting the last key leaves an explicitly empty keyring; verification
fails until a trusted key is explicitly added, rather than silently restoring it.
`key-finger` aliases `key-list`.

`source` and its alias `mirror-source` download current source archives into the
configured mirror cache, verify their metadata digests, and print their paths.
They do not install or build sources. The metadata index now includes source
records and archive sizes; old indexes rebuild automatically.

## Search, configuration, and diagnostics

```bash
apt-cyg describe 'editor|JSON'
apt-cyg describe 'TEXT EDITOR' --ignore-case
apt-cyg find 'VIM' -i
apt-cyg ls-categories
apt-cyg install --file packages.txt
apt-cyg update --mirror URL --cache /path/to/temporary-cache
apt-cyg update --proxy http://proxy.example:8080
apt-cyg update --proxy none
apt-cyg listall vim --quiet
apt-cyg listall vim --verbose
apt-cyg stats
apt-cyg pathof root database cache setup.ini
apt-cyg scriptinfo
```

`describe` searches names plus short/long descriptions using regular expressions;
`find` aliases `listall`. `--ignore-case` applies to list/find/describe matching.
`--file` appends one target per line, accepts CRLF, and skips empty lines and
lines starting with `#`. It can be repeated.

`--mirror` and `--cache` override configuration only for the current invocation.
`--proxy` accepts `inherit` (default), `none`, or an HTTP/HTTPS/SOCKS5 proxy URL
(the downloader must support the selected protocol). Proxy selection applies
to apt-cyg downloads, with no automatic WPAD lookup or PAC-script execution.
`--quiet` suppresses stdout and progress; errors remain on stderr. `--verbose`
prints the operation, root, database, and selected downloader. `--no-progress`
disables progress bars while retaining normal output.

`stats` reports available and installed package counts plus archive counts/sizes
for the selected mirror cache. Sizes are compressed archive bytes, not installed
disk usage. Individual queries are `packages-total-count`, `packages-total-size`,
`packages-cached-count`, and `packages-cached-size`. `pathof` accepts `root`,
`database`, `cache`, `mirror`, `mirrordir`, `setup.ini`, `keyring`, and `setup`.
`scriptinfo` includes the resolved executable path and downloader.

These additional operations are adapted to our trust and tracking model from
features documented by [apt-cyg2](https://github.com/zensage/apt-cyg2) and
[kou1okada/apt-cyg](https://github.com/kou1okada/apt-cyg). The latter's destructive
process termination, write-open lock probes, and simplistic WPAD discovery are
not used.

## Operational limits

Mutating commands take an atomic directory lock at `/etc/setup/.apt-cyg.lock`;
another writer fails immediately. A leftover lock is never automatically stolen.
Verify its recorded process has exited before manually removing a stale lock.
The installed database is replaced by rename, with the previous copy retained.
Official Setup does not participate in this lock: do not run it concurrently.

Package installation is not a filesystem transaction. An extraction failure can
leave partial files, and a later package failure does not roll back packages
already installed. A failed extraction retains its old database entry and
manifest; repair it with reinstall or Setup. Locked Windows DLLs and changes to
the running Cygwin runtime require official Setup with Cygwin processes stopped.
The script refuses to upgrade/reinstall the live `cygwin` package.

## Tests

```bash
bash -n apt-cyg
shellcheck -S error apt-cyg
python3 -m unittest discover -s tests -v
```

Tests require Python 3, Bash, GPG, and the listed GNU tools. They generate a
fixture signing key and operate on isolated alternate roots with local package
archives. They cover dependency repair, plans, tracking, upgrade/reinstall,
removal, locking, signature checks, compression fallback, cached indexing,
download fallback, completion, self-update backup/validation, local archive trust,
integrity repair, Setup verification/argument forwarding, source downloads, proxy
selection, parallel mirrors, diagnostics, and richer queries. They do not
exercise Windows DLL locking, rebasing, or native Cygwin package scripts.
