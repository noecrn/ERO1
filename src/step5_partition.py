import math
import warnings

import networkx as nx


def partition_network(G: nx.DiGraph, depots: list) -> dict[int, nx.DiGraph]:
    if not depots:
        raise ValueError("depots must contain at least one node.")
    missing = [d for d in depots if d not in G]
    if missing:
        raise ValueError(f"Depot nodes not found in G: {missing}")

    k = len(depots)

    # Compute shortest-path distances FROM each depot to all reachable nodes.
    # Complexity: O(K * (V + E) log V) acceptable for city-scale graphs.
    dist_from: list[dict] = [
        nx.single_source_dijkstra_path_length(G, depot, weight="weight")
        for depot in depots
    ]

    # Bucket: depot_index list of (u, v) arcs
    buckets: dict[int, list[tuple]] = {i: [] for i in range(k)}

    orphan_count = 0
    for u, v in G.edges():
        best_depot = _nearest_depot(u, v, dist_from)
        if best_depot is None:
            # All depots have inf distance to both endpoints fallback to 0.
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
        # Collect all nodes touched by this zone's arcs.  Sorted (not raw set
        # iteration) so node insertion order and everything derived from it
        # downstream (SCC condensation numbering in step5b) is reproducible
        # across runs/processes regardless of str hash randomization.
        nodes_in_zone = sorted({n for arc in arc_list for n in arc})
        for node in nodes_in_zone:
            sg.add_node(node, **G.nodes[node])
        for u, v in arc_list:
            sg.add_edge(u, v, **G.edges[u, v])
        subgraphs[i] = sg

    return subgraphs


def _nearest_depot(
    u: int,
    v: int,
    dist_from: list[dict],
) -> int | None:
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
