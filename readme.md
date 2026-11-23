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
version when its package version differs from the installed version; this can select an
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
checked using the MD5, SHA-1, SHA-224, SHA-256, SHA-384, or SHA-512 digest recorded in metadata; Cygwin
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

## Remaining fork tools and compatibility

The full [fork compatibility inventory](docs/fork-compatibility.md) lists every
operation group, option, adaptation, and deliberate exclusion from the two
feature-rich forks reviewed for this project.

### Historical script and targeted permission repair

```bash
apt-cyg repair-postinstall --simulate
apt-cyg repair-postinstall --yes
apt-cyg check --fix --simulate
apt-cyg repair-acl /usr/local/bin/apt-cyg --simulate
```

`repair-postinstall` restores `0p_`/`zp_` scripts historically renamed `.done` by
older installers. If both copies exist, the newer copy is retained; the completed
copy and any overwritten active copy are backed up under
`/etc/setup/postinstall-backups`. Restoration alone does not execute scripts.
`check --fix` also performs the restoration and runs restored perpetual scripts
unless `--noscripts` is set. A read-only check detects these historical mistakes.

`repair-acl` requires explicit file/directory paths and `getfacl`. It saves every
target's ACL and path under `/etc/setup/acl-backups` before changing any target,
then grants only owner read/write access and owner directory traversal. It does
not recurse, follow a final symbolic link, reset inheritance, remove SIDs, or
replace group/other permissions. Complex Windows ACL damage still needs native
permission tools; use the saved ACL records if restoration is needed.

### File caches and dependency reports

```bash
apt-cyg packageof 'bin/.*vim' -i
apt-cyg packageof 'jq' --force-update-packageof-cache
apt-cyg filelist jq
apt-cyg filesearch 'cygjq.*dll'
apt-cyg filesearch 'cygjq.*dll' --refresh
apt-cyg list-desired-packages
apt-cyg list-required-packages
apt-cyg list-orphaned-packages
apt-cyg list-lacked-packages
apt-cyg list-overages-and-shortages-of-packages --no-header
apt-cyg list-required-packages -- +vim -nano
```

`packageof` stores an installed-file index in `/etc/setup/apt-cyg-owners.idx`.
SHA-256 fingerprints of the database and compressed manifests invalidate it on
additions, removals, or manifest content changes. `--ag` selects an optional
`the_silver_searcher` backend. Our existing `search` remains an exact ownership
lookup; `packageof` searches patterns across package/path rows.

`filelist` obtains the repository-current package's file listing from cygwin.com
without downloading its binary archive. `filesearch` caches the online package
query and returns matching current-version file paths. These website responses
are diagnostics, not authenticated installation manifests. The cache lives at
`CACHE/apt-cyg-web/ARCH`; its default lifetime is 86400 seconds, controlled by
`APT_CYG_WEB_CACHE_TTL`. `--refresh` bypasses that cache; `--noupdate` requires
cached metadata/pages and permits expired web pages for offline diagnostics.
TTL age starts at fetch time, independently of server Last-Modified timestamps.

Dependency reports do not change installed packages or marks. Desired roots are
manual picks, Base packages, protected essentials, and installed packages absent
from the repository. Required packages include those roots and their dependency
closure. `+PKG`/`-PKG` change hypothetical roots only. Missing installed-version
records or unresolved alternatives make dependency reports fail instead of
printing a guessed closure. Reports check package presence, not version-constraint
satisfaction. `list-installed-packages` aliases `list`.

### Browsing, configuration, and compatibility options

```bash
apt-cyg browse-summary jq
apt-cyg browse-homepage jq --simulate
apt-cyg browse-homepage-with-mirror-source jq --simulate
apt-cyg setuprc-get last-mirror
apt-cyg set-mirror URL1 URL2
apt-cyg update --mirror-index 1
apt-cyg get-proxy
apt-cyg ls-pkg-with-category
apt-cyg call list
apt-cyg time check
```

Browser commands require `cygstart` from `cygutils`; simulation prints the URL.
Homepage lookup can use the source-package summary or a verified source archive.
Cygport/patch files are read as text, never sourced or evaluated. Only literal
HTTP(S) URLs are opened. `set-cache`, `mark-showauto`, `mark-showmanual`, and `help`
are additional compatibility aliases. `get-proxy` prints shell-quoted effective
proxy exports and may expose credentials only when explicitly requested.
`APT_CYG_PROXY` supplies the default explicit proxy policy.

`--no-user-picked` makes explicit install/localinstall targets automatic instead
of manual. `--force-fetch-trustedkeys` explicitly refreshes the fingerprint-pinned
Cygwin key while retaining custom keys. `--use-setuprc` is an accepted obsolete
no-op; setup.rc is always consulted. `--no-verify` also accepts `-X`.

`call` and `time` accept public operation names, including `apt-cyg-OPERATION`
compatibility names. They invoke a child CLI with normal validation, locking,
simulation and trust options. Arbitrary internal helpers and shell evaluation
are not exposed.

### Download and completion improvements

Metadata requests use ETag/Last-Modified validators with wget/curl. HTTP 304 is
accepted only with a previously signature-verified source, and the detached
signature is verified again before use. Changed or corrupt metadata still fails
closed. `--ipv4` (`-4`) selects IPv4; `--benchmark-timeout` controls benchmark
request timeouts. SHA-1, SHA-224 and SHA-384 archive digests are now supported in
addition to MD5, SHA-256 and SHA-512. Signature policy is unchanged.

`--no-check-certificate` explicitly disables wget/curl TLS certificate checking;
signatures/checksums still apply. Self-update refuses this option because its
trust depends on HTTPS. IPv4 and TLS-bypass flags require wget or curl, not lynx.
`--no-update-setup` requires an existing cached installer and still verifies it.
`packages-total-size REGEXP` selects metadata version sections for size totals;
without a pattern, it retains the current-version total.

Self-update now regenerates installed Bash completion using the new script,
syntax-checks it, and saves the previous completion as `.bak`. To persist an
opt-out, run `completion-install --completion-disable-autoupdate`; reinstalling
completion without the flag reenables refresh. The flag can also skip refresh
for one self-update. `--completion-get-subcommand` supports completion tooling.

## Cygwin Setup records and completed scripts

Cygwin Setup can record `NAME-VERSION.tar.bz2` in installed.db even when the
repository archive for the same version uses xz or Zstandard compression. Archive
names can also include architecture tags. Installed metadata lookup, reinstall,
and upgrade detection compare the exact package version from signed metadata,
allowing these representation differences. A same-version compression or tag
change does not cause a spurious upgrade. A genuinely unavailable installed
version still produces an error; the checker does not substitute another version.

`check --files` recognizes a completed script at
`etc/postinstall/SCRIPT.sh.done` (also .dash/.bat/.cmd) when its original name is
listed in the package manifest. Ordinary files cannot use a .done suffix to
satisfy a missing-file check. Perpetual `0p_`/`zp_` scripts marked .done are still
reported for historical repair.

GPG's `Good signature` indicates successful signature verification. The temporary
verification home has no personal web-of-trust certifications, so `[unknown]` and
the accompanying trust warning can appear even with the fingerprint-pinned Cygwin
key. Those messages do not indicate missing package dependency metadata.

## Native Zsh completion and inline suggestions

After updating apt-cyg, install native completion:

```zsh
apt-cyg completion-install --shell zsh --autosuggestions
```

This installs `_apt-cyg` in `/usr/local/share/zsh/site-functions` and the optional
inline-suggestion configuration in
`/usr/local/share/apt-cyg/zsh-autosuggestions.zsh`. `--shell bash` remains the
default for compatibility; `--shell all` installs both. `completion --shell zsh`
prints the native definition, and `completion-uninstall --shell zsh` removes the
Zsh files while preserving Bash completion. `autosuggestions` prints the optional
integration script separately.

Native completion covers operations, options, option values, directories/files,
categories, available packages and installed packages. Options with values can
precede the operation. Candidate queries read existing metadata or indexes only:
no downloads, key setup, package scripts, or package-state changes occur while
completing. If metadata is missing, run `apt-cyg update` explicitly first.
`completion-candidates available|installed|categories|commands|options` exposes this
read-only diagnostic backend.

Inline suggestions use the separately installed
[zsh-users/zsh-autosuggestions](https://github.com/zsh-users/zsh-autosuggestions)
plugin. If it is not already installed in Oh My Zsh:

```zsh
git clone https://github.com/zsh-users/zsh-autosuggestions \
  "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/zsh-autosuggestions"
```

In .zshrc, after your existing plugins assignment and before the existing
`source "$ZSH/oh-my-zsh.sh"` line, add:

```zsh
fpath=(/usr/local/share/zsh/site-functions $fpath)
plugins+=(zsh-autosuggestions)
```

After the Oh My Zsh source line, add:

```zsh
source /usr/local/share/apt-cyg/zsh-autosuggestions.zsh
```

Restart Zsh. Tab invokes native completion; zsh-autosuggestions displays an inline
suggestion that can be accepted with Right Arrow. The integration retains existing
history/custom strategies and adds an apt-cyg-specific cached-candidate strategy. It is
safe to source repeatedly. Unrelated commands keep their existing suggestion
behavior. Without Oh My Zsh, initialize `compinit` after adding the completion
directory to fpath, load zsh-autosuggestions, then source the integration file.

Self-update refreshes any installed Bash definition, Zsh definition and inline
integration from the new script, syntax-checking each and retaining .bak copies.
The existing persistent/per-update completion opt-out applies to all managed
shell integration files.

## Virtual dependencies and MobaXterm inline suggestions

Cygwin dependencies can name capabilities rather than separate packages. The
metadata index includes version-scoped `provides:` declarations. Matching the
official Setup implementation, `obsoletes:` supplies those capabilities only when
an explicit `provides:` declaration is absent. For example, installed gcc-core
can satisfy gcc14, perl_base can satisfy perl5_044, gnupg2 can replace gnupg, and
libssl1.0 can replace libopenssl100. `_windows` is a synthetic OS capability on a
native Cygwin host; it is not added to installed.db or downloaded as a package.

The checker, explicit install plans, dependency reports, removal guards and
autoremove follow actual providers. A provider already installed or explicitly
included in the same plan can satisfy a virtual requirement. New providers are
not selected arbitrarily from the repository. Installed-version provider records
are retained in `.provides` sidecars so metadata expiry does not automatically
lose that information. Missing provider records, unsupported qualified capability
relationships, and unsafe provider changes require official Setup. Upgrades cannot
drop a capability still required by an unchanged installed consumer.

The checker still reports genuinely missing packages, such as an absent libdb18.1.
Install a genuine missing package through Setup if the normal installer encounters
versioned dependencies:

```zsh
apt-cyg setup -- --packages libdb18.1
```

The inline strategy now reads cached candidates directly. It does not call the
upstream completion-capture strategy, ZLE completion capture, or zpty. This avoids
Moba/Cygwin errors such as `can't open pseudo terminal: bad file descriptor`.
Native Tab completion continues to use the normal Zsh completion system.

To quiet an older installed inline strategy immediately:

```zsh
ZSH_AUTOSUGGEST_STRATEGY=(history)
```

After updating, regenerate and reload the integration in the current shell:

```zsh
apt-cyg self-update
apt-cyg completion-install --shell zsh --autosuggestions
source /usr/local/share/apt-cyg/zsh-autosuggestions.zsh
```

The custom apt_cyg strategy suggests command/option names, package names and simple
option values using the existing offline backend. It preserves the typed prefix
and never evaluates shell input. History strategies handle quoted/escaped/complex
input. If your own configuration also enables the upstream global `completion`
strategy, that strategy still uses zpty; remove that entry on affected terminals
and keep `history` plus `apt_cyg` (and any other compatible strategies).

`APT_CYG_WINDOWS_VERSION` is available only with a nonempty alternate root to model
Windows in isolated fixtures; it does not override native live-root OS detection.
Provider-aware checks concern capability/package presence. Full version-constraint,
conflict and provider-choice solving remains the role of official Setup.

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

Tests require Python 3 with pexpect, Bash, Zsh, GPG, and the listed GNU tools. They generate a
fixture signing key and operate on isolated alternate roots with local package
archives. They cover dependency repair, plans, tracking, upgrade/reinstall,
removal, locking, signature checks, compression fallback, cached indexing,
download fallback, completion, self-update backup/validation, local archive trust,
integrity repair, Setup verification/argument forwarding, source downloads, proxy
selection, parallel mirrors, diagnostics, and richer queries. They do not
exercise Windows DLL locking, rebasing, or native Cygwin package scripts.
