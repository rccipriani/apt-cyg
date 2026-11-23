# Fork compatibility inventory

This inventory covers the operations and user-facing options in
[ZenSage apt-cyg2](https://github.com/zensage/apt-cyg2/blob/master/CHANGES-apt-cyg2.txt)
and [kou1okada/apt-cyg](https://github.com/kou1okada/apt-cyg/blob/master/README.md),
including relevant options found in their scripts. It describes functional
coverage, not byte-for-byte command/output compatibility. Existing MIT copyright
notices remain in the installer and LICENSE.

## Operations

| Feature or operation | Implementation or equivalent |
|---|---|
| install, upgrade, reinstall, remove, autoremove | Dependency plans, tracking and protected removal. Installed-version reinstalls require authenticated metadata. |
| localinstall and dependency hints | Repository archive authentication or explicit local trust; version constraints and alternatives require Setup. |
| check, --files, --fix | Database/manifests/dependencies/pending scripts, optional file-presence checks and planned repairs. |
| update, download | Signed metadata and verified binary downloads into the shared mirror cache. |
| show, find, describe | show, listall/find and description searches. Kou's installed-package show is covered by list/list-installed-packages. |
| depends, rdepends | Dependency graphs with cycle handling. |
| packageof | Persistent installed-manifest index with content-based invalidation; optional ag backend. search remains available for exact installed-file ownership. |
| listfiles | Installed manifests, or a verified package archive for an uninstalled package. |
| filelist | Current Cygwin web file listing without fetching the binary archive. |
| filesearch | Cached Cygwin package queries and matching web file paths for repository-current versions. searchall remains the basic online package lookup. |
| list-desired/required/installed/orphaned/lacked-packages | Dedicated reports; desired roots include manual picks, Base and protected packages. |
| list-overages-and-shortages-of-packages | Three-column comm-style comparison, optional header. |
| hypothetical +PKG/-PKG package differences | Accepted by dependency reports, without modifying package state. Use -- before negative differences. |
| mark-auto/manual, mark-showauto/manual | Marking commands plus compatibility aliases for list-auto/manual. |
| key-add/del/list/finger | Dedicated keyring; removal requires full primary fingerprint. Explicit key refresh preserves custom keys. |
| upgrade-self | Alias for self-update; TLS, syntax validation, backup and optional completion refresh. |
| completion-install/uninstall | Bash and native Zsh definitions; optional apt-cyg-scoped zsh-autosuggestions integration, automatic self-update refresh, persistent opt-out and parsed-subcommand helper. |
| mirrors-list/long/online | Recorded URLs/details and online official list. |
| benchmark-mirrors, benchmark-parallel-mirrors, benchmark-parallel-mirrors-list | Sequential or bounded parallel comparisons; no automatic mirror switching. |
| scriptinfo, pathof | Resolved script/environment paths. pathof mirrors identifies setup.rc, which stores recorded mirror values. |
| show-packages-busyness | Observational busy diagnostics; never equates unobserved use with proof that a file is unlocked. |
| setup, update-setup, dist-upgrade | Signed official Setup, fixed active root, --wait and exit-status propagation; no process termination. |
| packages-total-count/size, packages-cached-count/size | Current binary archive totals or selected metadata-section size regex; cache totals include cached source archives. |
| repair-postinstall | Restores perpetual scripts historically renamed .done, with backups; check --fix can then run them. |
| repair-acl | Explicit paths only, ACL backups before any changes, owner access only, no recursion or SID removal. |
| source, mirror-source | Authenticated current source archive downloads to the mirror cache. |
| browse-summary/homepage/homepage-with-mirror-source | Browser shortcuts; source metadata is read as text and never evaluated. Only literal HTTP(S) URLs are opened. |
| get-proxy | Shell-quoted exports of effective proxy variables. This explicitly requested output may contain proxy credentials. |
| ls-categories, ls-pkg-with-category | Category names and category/package pairs. |
| setuprc-get | All values in a requested setup.rc section. |
| set-cache, set-mirror | Configuration aliases; saved alternative mirrors supported, one selected per invocation. |
| Kou's binary mirror operation | Covered by download. Our existing mirror operation continues to configure the mirror. |
| call, time | Public operations run through a child CLI so locking, validation and simulation cannot be bypassed through internal helpers. |
| help | Alias for --help. |

## Options and supporting behavior

| Feature or option | Coverage |
|---|---|
| --simulate/--dry-run/-s, --yes/-y | Supported; package state and scripts remain untouched during simulation. Diagnostic caches may refresh. |
| --force, --force-remove | Explicit dependent-package removal override; never permits live runtime replacement. |
| --name, --files, --fix | Supported for localinstall/check as appropriate. |
| --no-user-picked | Explicit install/localinstall targets become automatic; defaults remain manual. |
| --ag | Optional the_silver_searcher backend for packageof. |
| --force-update-packageof-cache | Rebuild owner index even when its fingerprint is unchanged. |
| --ignore-case/-i | Query matching, including owner-index and local file-search result filtering. |
| --benchmark-timeout, --max-jobs/-j | Request timeout and parallel worker limit. |
| --force-fetch-trustedkeys | Explicitly fetch and import only the fingerprint-pinned Cygwin key, preserving custom trusted keys. |
| --no-verify/-X | Explicit metadata-signature bypass. Official Setup signatures remain mandatory. |
| --no-check-certificate | wget/curl only, explicitly bypasses TLS certificate checks. Metadata signatures/checksums still apply; self-update refuses this option. |
| --no-update-setup | Fail if no cached installer exists instead of automatically downloading one. Cached installers are still signature-checked. |
| --no-header | Suppress dependency-difference table headers. |
| --proxy/-p, APT_CYG_PROXY | inherit, none, or an explicit URL; no automatic discovery. |
| --completion-get-subcommand | Return parsed operation without running it. |
| --completion-disable-autoupdate | Persist opt-out on completion-install, or skip refresh for one self-update. |
| --mirror/-m, --mirror-index/-M, --cache/-c | Per-invocation overrides; mirror index selects a zero-based last-mirror entry. |
| --file/-f | Repeated target files, one target per line, including CRLF and comment lines. |
| --noscripts, --nodeps | Explicit script/dependency bypasses. |
| --noupdate/-u | Verified cached metadata only for implicit reads; web diagnostics require cached pages. An explicit update still requests a refresh. |
| --ipv4/-4 | wget/curl only. |
| --no-progress, --quiet/-q, --verbose/-v | Supported. Errors remain on stderr. |
| --use-setuprc | Accepted obsolete no-op, as in Kou's fork; setup.rc is always used. |
| SHA-1, SHA-224, SHA-384 | Supported alongside MD5, SHA-256 and SHA-512, selected by digest length. |
| Conditional metadata transfers | ETag/Last-Modified with wget/curl. A 304 response is usable only with an already verified cached source, and the detached signature is checked again. |
| Cached metadata index, in-process planning, atomic DB updates, logging, compressed formats, alternate test roots | Retained from the earlier feature work, with the dependency/failure fixes in this fork. |

## Explicit exclusions and adaptations

- No automatic stale-lock takeover. A stale owner must be verified before a lock
  is manually removed.
- No --force replacement of the live Cygwin runtime.
- No automatic process termination, including Kou's internal
  dist-upgrade-no-ask helper. For unattended Setup, pass its native options
  explicitly; closing applications remains the caller's responsibility.
- No WPAD/PAC discovery/execution. The associated proxy-force-refresh and
  proxy-refresh-interval options do not apply and are not accepted.
- No broad recursive ACL reset, inheritance rewrite, or SID removal. repair-acl
  is a targeted owner-access repair, not a recreation of arbitrary Windows ACLs.
- call/time do not expose raw internal helpers, arbitrary shell commands or
  eval. Public operations retain the normal guards.
- Custom version/alternative dependency solving is not supplied by these ports;
  official Setup remains the supported route rather than dropping constraints.

Web file lists, cached website queries and homepage URLs are diagnostics obtained
from cygwin.com. They are not authenticated package manifests and are never used
to authorize archive installation or dependency changes. Source archives used by
the homepage helper follow the normal authenticated source-download path.

Native Windows ACLs, PE execution and full Windows process visibility still need
native Cygwin validation. Fixture and live-web tests do not establish those
platform-specific behaviors.

## Setup/checker and Zsh follow-up

Installed-version matching now accepts Setup's synthetic .tar.bz2 archive suffix
and architecture-tag variations, using the exact version advertised by signed
metadata. Missing records for genuinely different versions remain errors.
Completed one-shot postinstall scripts count as present under their .done names;
perpetual scripts incorrectly marked .done remain repair diagnostics.

Native Zsh completion and optional zsh-autosuggestions integration are additional
features beyond the reviewed Bash-completion forks. Completion candidates are
read-only and offline; Bash completion also handles value-bearing options before
the operation and forwards cache/mirror overrides to that backend.

## Virtual capabilities and PTY-free inline suggestions

The index records provides per package version and uses obsoletes as a fallback
only in the absence of explicit provides, matching official Setup. Installed
providers and explicitly planned providers satisfy aliases in checks/plans;
removal, autoremove and reports follow the real provider packages. The synthetic
_windows capability is recognized on Cygwin hosts. Qualified capability rules and
ambiguous new-provider selection remain delegated to Setup. Version-tied provider
sidecars preserve knowledge when old metadata expires.

Inline autosuggestions use cached candidates directly and no longer delegate to
the upstream completion strategy or zpty. Native Tab completion is unchanged.
Existing global upstream completion strategies still retain their own PTY
requirements; the README shows the compatible history/apt_cyg configuration.
