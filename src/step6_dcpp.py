"""
Step 6 — Directed Chinese Postman Problem (DCPP) per snowplow zone.

Given a strongly connected DiGraph (one zone from step 5), finds the shortest
closed walk that traverses every arc at least once, starting and ending at the
depot node.

Algorithm
---------
1. Reject zones that are not strongly connected (DCPP is undefined there).
2. If the zone is already Eulerian (every node has in_degree == out_degree),
   go directly to nx.eulerian_circuit.
3. Otherwise, compute the imbalance of each node:
       imbalance(v) = out_degree(v) − in_degree(v)
   - imbalance > 0 : node emits more than it absorbs → needs more incoming arcs
                     → flow *sink*  (demand = +imbalance)
   - imbalance < 0 : node absorbs more than it emits → needs more outgoing arcs
                     → flow *source* (demand = imbalance, which is negative)
4. Build a min-cost flow network whose arc costs equal the shortest directed
   path lengths (Dijkstra, weight='weight') between each source–sink pair.
   Solve with nx.min_cost_flow.  Arc costs are scaled to integers (×1 000) for
   compatibility with NetworkX's network_simplex backend.
5. For each unit of flow from source s to sink t, duplicate the arcs along the
   shortest path s → … → t in a MultiDiGraph copy of the zone.
6. Run nx.eulerian_circuit on the balanced MultiDiGraph, starting at depot.
7. Return the ordered arc list and the total km (duplicated arcs counted once
   per traversal — this is the x_ij > 1 of the CPP formulation).
"""

import math

import networkx as nx


def compute_tour(zone: nx.DiGraph, depot) -> tuple[list, float]:
    """
    Solve the DCPP on *zone* starting and ending at *depot*.

    Parameters
    ----------
    zone   : strongly connected DiGraph produced by step 5; edges carry 'weight'.
    depot  : node ID that exists in *zone*; the tour departs from and returns
             to this node.

    Returns
    -------
    circuit : list of (u, v) arcs in traversal order.
    total_km: sum of 'weight' for every traversal (duplicated arcs counted
              once per pass).

    Raises
    ------
    ValueError  if *zone* is not strongly connected.
    ValueError  if *depot* is absent from *zone*.
    """
    if depot not in zone:
        raise ValueError(f"Depot {depot!r} absent from zone nodes.")

    scc_count = nx.number_strongly_connected_components(zone)
    if scc_count != 1:
        raise ValueError(
            f"Zone non fortement connexe — DCPP impossible : "
            f"{scc_count} composantes fortement connexes"
        )

    imbalances = {v: zone.out_degree(v) - zone.in_degree(v) for v in zone.nodes()}

    if all(b == 0 for b in imbalances.values()):
        balanced = nx.MultiDiGraph(zone)
    else:
        balanced = _balance(zone, imbalances)

    circuit = list(nx.eulerian_circuit(balanced, source=depot, keys=True))

    # Total distance: use the MultiDiGraph to respect duplicated arc weights.
    total_km = sum(balanced[u][v][k]["weight"] for u, v, k in circuit)

    # Strip keys from the public return value — callers only need (u, v).
    return [(u, v) for u, v, _ in circuit], total_km


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _balance(zone: nx.DiGraph, imbalances: dict) -> nx.MultiDiGraph:
    """
    Return a MultiDiGraph copy of *zone* with extra arc copies added along
    shortest paths so that every node has in_degree == out_degree.

    Uses min-cost flow (network_simplex backend) to minimise total added km.
    Arc costs are multiplied by 1 000 and rounded to integers to satisfy
    NetworkX's integer-weight requirement.
    """
    # Nodes that need to shed excess incoming arcs (supply flow outward).
    sources = [v for v, b in imbalances.items() if b < 0]
    # Nodes that need to absorb excess outgoing arcs (absorb incoming flow).
    sinks = [v for v, b in imbalances.items() if b > 0]

    total_supply = sum(b for b in imbalances.values() if b > 0)  # upper bound for capacities

    # Build flow network.
    flow_net = nx.DiGraph()
    for v in zone.nodes():
        flow_net.add_node(v, demand=imbalances[v])

    # Pre-compute shortest paths between every source and every sink.
    for s in sources:
        lengths = nx.single_source_dijkstra_path_length(zone, s, weight="weight")
        for t in sinks:
            cost = lengths.get(t, math.inf)
            if cost < math.inf:
                flow_net.add_edge(
                    s, t,
                    capacity=total_supply,
                    weight=round(cost * 1_000),  # integer cost in metres
                )

    flow = nx.min_cost_flow(flow_net)

    # Duplicate arcs along the chosen shortest paths.
    balanced = nx.MultiDiGraph(zone)
    for s in sources:
        for t, fval in flow.get(s, {}).items():
            if fval <= 0:
                continue
            path = nx.shortest_path(zone, s, t, weight="weight")
            for _ in range(int(fval)):
                for i in range(len(path) - 1):
                    u, v = path[i], path[i + 1]
                    balanced.add_edge(u, v, **zone.edges[u, v])

    return balanced
