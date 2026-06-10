"""
Step 5b — Repair strong connectivity of a zone before DCPP.

The DCPP (step 6) requires every zone to be strongly connected.
When the zone partitioner (step 5) assigns one-way arcs that create dead-ends,
this module borrows the minimum necessary return paths from the full network
and grafts them into the zone.

Why borrow from G_full instead of reversing arcs?
Because every arc in G_full is a real, driveable street segment.  Adding a
real arc means the snowplow CAN physically traverse it; reversing an arc would
violate traffic direction.

Algorithm
---------
1. If already strongly connected, return a copy unchanged.
2. Condense the zone into a DAG of SCCs.
3. Each iteration: pick a sink SCC (no outgoing in condensation) and a source
   SCC (no incoming in condensation) that are different from each other.
   Find the shortest directed path in G_full from any node in the sink SCC to
   any node in the source SCC, then add every arc on that path (not already in
   the zone) with attribute repair=True.
4. Repeat until strongly connected or until no path can be found (→ ValueError).

Termination guarantee: each iteration adds an arc from a condensation-sink to
a condensation-source.  That creates a directed cycle in the condensation,
merging at least two SCCs into one and strictly reducing the SCC count.
"""

import math

import networkx as nx


def ensure_strong_connectivity(
    zone: nx.DiGraph,
    G_full: nx.DiGraph,
) -> nx.DiGraph:
    """
    Return a copy of *zone* augmented with repair arcs from *G_full* so that
    the result is strongly connected.

    Parameters
    ----------
    zone   : DiGraph produced by step 5; must be a subgraph of G_full.
    G_full : the complete filtered network from steps 1-4.

    Returns
    -------
    A new DiGraph (zone never mutated).  Added arcs carry repair=True.
    Original arcs keep their attributes unchanged (repair is absent or False).

    Raises
    ------
    ValueError  if G_full itself does not contain a path that closes some
                strongly connected component pair — genuine dead-end in the
                source data.
    """
    repaired = zone.copy()

    if nx.is_strongly_connected(repaired):
        return repaired

    # Upper bound on iterations: at most (|V| - 1) SCCs can be merged.
    max_iter = repaired.number_of_nodes() + G_full.number_of_nodes()

    for iteration in range(max_iter):
        if nx.is_strongly_connected(repaired):
            break

        cond = nx.condensation(repaired)
        from_idx, to_idx = _pick_sink_source_pair(cond)

        from_nodes = cond.nodes[from_idx]["members"]
        to_nodes   = cond.nodes[to_idx]["members"]

        path = _shortest_path_between_sets(G_full, from_nodes, to_nodes)
        if path is None:
            raise ValueError(
                "Impossible de relier les composantes fortement connexes via "
                "G_full — cul-de-sac réel dans le réseau source.  "
                f"Aucun chemin de {from_nodes} vers {to_nodes} dans G_full."
            )

        _graft_path(repaired, path, G_full)
    else:
        if not nx.is_strongly_connected(repaired):
            raise ValueError(
                "Réparation non convergée après le nombre maximal d'itérations."
            )

    return repaired


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _pick_sink_source_pair(cond: nx.DiGraph) -> tuple[int, int]:
    """
    Return (sink_idx, source_idx) from the condensation DAG.

    A sink has out_degree=0; a source has in_degree=0.  We want two *different*
    SCC indices.  If every node is both source and sink (all SCCs isolated with
    no inter-SCC edges), we simply pick the first two nodes.
    """
    sinks   = [n for n in cond.nodes() if cond.out_degree(n) == 0]
    sources = [n for n in cond.nodes() if cond.in_degree(n) == 0]

    from_idx = sinks[0]
    # Prefer a source that differs from the chosen sink.
    to_idx = next((s for s in sources if s != from_idx), None)
    if to_idx is None:
        # All sources happen to be the same SCC — pick any other node.
        to_idx = next(n for n in cond.nodes() if n != from_idx)

    return from_idx, to_idx


def _shortest_path_between_sets(
    G: nx.DiGraph,
    from_set: frozenset,
    to_set: frozenset,
) -> list | None:
    """
    Return the shortest weighted directed path in *G* from any node in
    *from_set* to any node in *to_set*, or None if no such path exists.

    Runs one Dijkstra per node in *from_set* and keeps the global minimum.
    """
    best_length = math.inf
    best_path: list | None = None

    for s in from_set:
        try:
            lengths, paths = nx.single_source_dijkstra(G, s, weight="weight")
        except nx.NodeNotFound:
            continue
        for t in to_set:
            d = lengths.get(t, math.inf)
            if d < best_length:
                best_length = d
                best_path = paths[t]

    return best_path


def _graft_path(repaired: nx.DiGraph, path: list, G_full: nx.DiGraph) -> None:
    """
    Add every arc on *path* that is not already in *repaired*, copying node
    and edge attributes from *G_full* and stamping repair=True on new edges.

    Mutates *repaired* in place (called only on the working copy).
    """
    for u, v in zip(path, path[1:]):
        if u not in repaired:
            repaired.add_node(u, **G_full.nodes[u])
        if v not in repaired:
            repaired.add_node(v, **G_full.nodes[v])
        if not repaired.has_edge(u, v):
            attrs = dict(G_full.edges[u, v])
            attrs["repair"] = True
            repaired.add_edge(u, v, **attrs)
