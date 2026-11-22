apt-cyg
=======

apt-cyg is a Cygwin package manager. It includes a command-line installer for
Cygwin which cooperates with Cygwin Setup and uses the same repository.

[github.com/rccipriani/apt-cyg][1]

[1]:https://github.com/rccipriani/apt-cyg

Operations
----------

~~~
install
  Install package(s).

remove
  Remove package(s) from the system.

update
  Download a fresh copy of the master package list (setup.ini) from the
  server defined in setup.rc.

download
  Retrieve package(s) from the server, but do not install/upgrade anything.

show
  Display information on given package(s).

depends
  Produce a dependency tree for a package.

rdepends
  Produce a tree of packages that depend on the named package.

list
  Search each locally-installed package for names that match regexp. If no
  package names are provided in the command line, all installed packages will
  be queried.

listall
  This will search each package in the master package list (setup.ini) for
  names that match regexp.

category
  Display all packages that are members of a named category.

listfiles
  List all files owned by a given package. Multiple packages can be specified
  on the command line.

search
  Search for downloaded packages that own the specified file(s). The path can
  be relative or absolute, and one or more files can be specified.

searchall
  Search cygwin.com to retrieve file information about packages. The provided
  target is considered to be a filename and searchall will return the
  package(s) which contain this file.
~~~

Quick start
-----------

apt-cyg is a simple script. To install:

    wget -O apt-cyg https://raw.githubusercontent.com/rccipriani/apt-cyg/master/apt-cyg
    install -m 755 apt-cyg /bin/apt-cyg

Example use of apt-cyg:

    apt-cyg install nano

Dependency handling in this fork
-------------------------------

Installations read `depends2:` and `depends:` from the current stable version,
with support for legacy `requires:` metadata. Modern metadata takes precedence,
including an explicitly empty dependency list. Dependencies from previous or test
versions are excluded. The `depends` and `rdepends` commands use the same stable
package selection and display dependency names.

Running `install` on an installed package checks its dependencies again. This
allows a retry to install missing dependency packages after a partial installation.
Existing package files are not reinstalled or upgraded. Missing files belonging
to a package already registered as installed require repair with Cygwin Setup.

Dependency and post-install failures return a nonzero exit status. Failed
post-install scripts remain pending for a retry. A package can already have been
extracted and registered when a dependency fails; rerun the same install command
after correcting the failure.

Version constraints and alternative dependency expressions require the official
Cygwin Setup dependency solver. This fork stops with an explanatory error when
it encounters them instead of silently installing an unchecked version. Virtual
package providers are not resolved. `--nodeps` explicitly bypasses dependency
handling, as in upstream apt-cyg.

Regression tests use local fixture archives and a temporary installation root.
Run them with Python 3 and Bash available:

    python3 -m unittest discover -s tests -v
