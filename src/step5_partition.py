"""
Step 5 — Partition the street network into one zone per snowplow depot.

Each arc is assigned to exactly one depot by comparing shortest-path distances
on the directed graph (Dijkstra, weight='weight').

Reference point for an arc (u → v)
------------------------------------
We use  min(dist(depot, u), dist(depot, v))  as the proximity score for a
given depot.  Rationale: a snowplow can *begin* clearing arc u→v as soon as
it reaches *either* endpoint (u to drive along it, or v if it approaches from
a downstream street).  Using the minimum is conservative — it reflects the
best-case arrival distance — and is robust when one endpoint is unreachable.
An alternative (mean of both endpoints) would weight both ends equally but
could misclassify arcs that straddle zone boundaries; the minimum is simpler
and more interpretable.

Unreachable arcs
-----------------
If *all* depots have infinite distance to both endpoints of an arc, the arc
cannot be reached by any plow.  Policy: assign it to the first depot in the
list (index 0) and emit a warning.  This keeps the function total (never
raises) while making orphaned arcs visible in logs.
"""

import math
import warnings

import networkx as nx


def partition_network(G: nx.DiGraph, depots: list) -> dict[int, nx.DiGraph]:
    """
    Assign every arc of *G* to the nearest depot and return K subgraphs.

    Proximity is measured as the shortest weighted path from a depot to the
    closer endpoint of the arc (see module docstring for justification).

    Parameters
    ----------
    G      : directed graph produced by steps 1-4; edges must carry 'weight'.
    depots : list of node IDs (must exist in G); one subgraph is created per
             depot.

    Returns
    -------
    dict mapping depot_index (0-based position in *depots*) to a nx.DiGraph
    containing exactly the arcs assigned to that depot.  Node attributes are
    preserved for every node that appears in the subgraph.  The depot index
    (not the node ID) is the key so callers always iterate 0 … K-1.

    Raises
    ------
    ValueError  if *depots* is empty or a depot node is absent from *G*.
    """
    if not depots:
        raise ValueError("depots must contain at least one node.")
    missing = [d for d in depots if d not in G]
    if missing:
        raise ValueError(f"Depot nodes not found in G: {missing}")

    k = len(depots)

    # Compute shortest-path distances FROM each depot to all reachable nodes.
    # Complexity: O(K * (V + E) log V) — acceptable for city-scale graphs.
    dist_from: list[dict] = [
        nx.single_source_dijkstra_path_length(G, depot, weight="weight")
        for depot in depots
    ]

    # Bucket: depot_index → list of (u, v) arcs
    buckets: dict[int, list[tuple]] = {i: [] for i in range(k)}

    orphan_count = 0
    for u, v in G.edges():
        best_depot = _nearest_depot(u, v, dist_from)
        if best_depot is None:
            # All depots have ∞ distance to both endpoints — fallback to 0.
            best_depot = 0
            orphan_count += 1
        buckets[best_depot].append((u, v))

    if orphan_count:
        warnings.warn(
            f"{orphan_count} arc(s) unreachable from all depots; "
            "assigned to depot index 0 as fallback.",
            UserWarning,
            stacklevel=2,
        )

    # Build subgraphs: preserve node attributes for every involved node.
    subgraphs: dict[int, nx.DiGraph] = {}
    for i, arc_list in buckets.items():
        sg = nx.DiGraph()
        # Collect all nodes touched by this zone's arcs.
        nodes_in_zone = {n for arc in arc_list for n in arc}
        for node in nodes_in_zone:
            sg.add_node(node, **G.nodes[node])
        for u, v in arc_list:
            sg.add_edge(u, v, **G.edges[u, v])
        subgraphs[i] = sg

    return subgraphs


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _nearest_depot(
    u: int,
    v: int,
    dist_from: list[dict],
) -> int | None:
    """
    Return the index of the depot whose distance to arc (u, v) is smallest.

    Distance to arc = min(dist_to_u, dist_to_v).
    Returns None if every depot has infinite distance to both endpoints.
    """
    best_idx: int | None = None
    best_score = math.inf

    for idx, distances in enumerate(dist_from):
        d_u = distances.get(u, math.inf)
        d_v = distances.get(v, math.inf)
        score = min(d_u, d_v)
        if score < best_score:
            best_score = score
            best_idx = idx

    return best_idx  # None only when best_score remains inf
