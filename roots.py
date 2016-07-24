#!/usr/bin/env python3

# Find the roots (sources) of a directed graph, i.e., a minimal set of
# vertices from which all others can be reached.  The conventions for
# graphs are as in the tarjan module: A graph is represented as a
# dictionary { vertex : list of successors }.

import sys

try:
    import tarjan
except ImportError:
    print("This program requires the tarjan package.")
    print("Please install it and try again.")
    sys.exit(1)

def find_roots(g):
    sccs = tarjan.tarjan(g)
    # For each vertex, record the index of its scc.  Also declare the
    # scc a root until we discover otherwise.
    scc_ind = {}
    is_root = []                # Index is index of scc.
    for i, c in enumerate(sccs):
        is_root.append(True)
        for v in c:
            scc_ind[v] = i

    # For each component C, mark as nonroot any earlier component
    # that receives an edge from something in C.
    for i, c in enumerate(sccs):
        for v in c:
            for w in g[v]:
                j = scc_ind[w]
                if j < i:
                    is_root[j] = False

    return [sccs[i][0] for i in range(len(sccs)) if is_root[i]]

def test_roots():
    # See doc/example.png in tarjan package.
    g = {1:[2],2:[1,5],3:[4],4:[3,5], 5:[6],6:[7],7:[8],8:[6,9],9:[]}
    print(find_roots(g))

if __name__ == '__main__':
    test_roots()
