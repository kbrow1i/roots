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

from roots import find_roots

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

# Return dependency graph of all packages listed in INIFILE, plus a
# fictitious ’base’ package that requires all the packages in the Base
# category.
def parse_setup_ini(inifile):
    g = defaultdict(list)

    with open(inifile) as f:
        for line in f:
            match = re.match(r'^@\s+(\S+)', line)
            if match:
                # New package
                name = match.group(1)
                continue

            if(re.match(r'^category:.*\bBase\b', line)):
                g['base'].append(name)
                continue

            match = re.match(r'^requires:\s*(.*)$', line)
            if match:
                g[name] = match.group(1).split()
    return g

# Return a list of installed packages.
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
    args = parser.parse_args()

    inifile = get_setup_ini(args)
    if not os.path.exists(inifile):
        print("%s doesn't exist" % inifile)
        sys.exit(1)

    all_pkgs_graph = parse_setup_ini(inifile)

    inst = get_installed_pkgs()
    inst.append('base')
    
    roots = sorted(find_roots({p: all_pkgs_graph[p] for p in inst}))
    roots.remove('base')

    print(','.join(roots))

if __name__ == '__main__':
    main()
