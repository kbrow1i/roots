#!/usr/bin/env python3

# See the thread starting at
# https://www.cygwin.com/ml/cygwin/2016-07/msg00025.html.

from collections import defaultdict
from subprocess import check_output
from urllib.parse import quote
import argparse
import os
import re
import sys

try:
    import tarjan
except ImportError:
    print("This program requires the tarjan package.")
    print("Please install it and try again.")
    sys.exit(1)

# We need to know for each package (a) which strongly connected
# component it’s in (identified by index); (b) whether it’s a base
# package; (c) what it requires; (d) whether it’s a root (i.e., not
# yet known to be a nonroot).  (d) is only relevant for the first
# package in each component, which is used as representative of that
# component.
class PackageInfo:
    def __init__(self):
        self.requires = []
        self.scc_ind = -1
        self.is_root = True
        self.is_base = False

def get_setup_ini(args):
    if args.inifile:
        return args.inifile
    
    # /etc/setup/setup.rc has encoding errors near the end.
    with open("/etc/setup/setup.rc", errors='ignore') as f:
        for line in f:
            if re.match(r'^last-cache', line):
                cache_dir_w = '/'.join(next(f).strip().split('\\'))
                cache_dir = check_output(['cygpath', '-u', cache_dir_w]).strip().decode()
                break
        else:
            print("Can't get last cache")
            sys.exit(1)

        for line in f:
            if re.match(r'^last-mirror', line):
                mirror = next(f).strip()
                mirror_dir = quote(mirror, safe='').lower()
                break
        else:
            print("Can't get last mirror")
            sys.exit(1)
    
    arch = os.uname().machine
    if arch == 'i686':
        arch = 'x86'
    return os.path.join(cache_dir, mirror_dir, arch, 'setup.ini')

# Return dictionary of all packages listed in setup.ini, indexed by name.
def parse_setup_ini(inifile):
    pkgs = defaultdict(PackageInfo)
    with open(inifile) as f:
        for line in f:
            match = re.match(r'^@\s+(\S+)', line)
            if match:
                # New package
                name = match.group(1)
                pkgs[name] = PackageInfo()
                continue

            if(re.match(r'^category:.*\bBase\b', line)):
                pkgs[name].is_base = True
                continue

            match = re.match(r'^requires:\s*(.*)$', line)
            if match:
                pkgs[name].requires = match.group(1).split()
    return pkgs

# Given a dictionary PKGS as above and a list INST of installed
# packages, return the strongly connected components of the dependency
# graph of installed packages.  This is a list of lists.
def components(pkgs, inst):
     return tarjan.tarjan({p: pkgs[p].requires for p in inst})

def get_installed_pkgs():
    with open("/var/log/setup.log.full") as f:
        c = f.read()
        match = re.search(r'^Dependency order of packages: (.*)$', c,
                          re.MULTILINE)
        if not match:
            print("Can't get list of installed packages from /var/log/setup.log.full.")
            sys.exit(1)
        return match.group(1).split()

def main():
    parser = argparse.ArgumentParser(description='Find roots of Cygwin installation')
    parser.add_argument('--inifile', '-i', action='store', help='path to setup.ini', required=False, metavar='FILE')
    (args) = parser.parse_args()
    inifile = get_setup_ini(args)
    if not os.path.exists(inifile):
        print("%s doesn't exist" % inifile)
        sys.exit(1)

    all_pkgs = parse_setup_ini(inifile)

    inst = get_installed_pkgs()

    sccs = components(all_pkgs, inst)

    # For each installed package, record the index of its scc.
    for i, c in enumerate(sccs):
        for p in c:
            all_pkgs[p].scc_ind = i

    # For each component C, mark as nonroot any earlier component
    # required by something in C.  And mark C as nonroot if it
    # contains a base package.
    for i, c in enumerate(sccs):
        for p in c:
            if all_pkgs[p].is_base:
                all_pkgs[c[0]].is_root = False
            for q in all_pkgs[p].requires:
                j = all_pkgs[q].scc_ind
                if j < i:
                    all_pkgs[sccs[j][0]].is_root = False

    roots = sorted([c[0] for c in sccs if all_pkgs[c[0]].is_root])
    print(','.join(roots))

main()
