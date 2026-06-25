import math

import networkx as nx


def compute_tour(zone: nx.DiGraph, depot) -> tuple[list, float]:
    if depot not in zone:
        raise ValueError(f"Depot {depot!r} absent from zone nodes.")

    scc_count = nx.number_strongly_connected_components(zone)
    if scc_count != 1:
        raise ValueError(
            f"Zone non fortement connexe - DCPP impossible : "
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

    # Strip keys from the public return value callers only need (u, v).
    return [(u, v) for u, v, _ in circuit], total_km


def _balance(zone: nx.DiGraph, imbalances: dict) -> nx.MultiDiGraph:
    sources = [v for v, b in imbalances.items() if b < 0]
    sinks = [v for v, b in imbalances.items() if b > 0]

    total_supply = sum(b for b in imbalances.values() if b > 0)  # upper bound for capacities

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

    # strip 'key' from attrs MultiDiGraph interprets it as multi-edge key and
    # would update the existing edge instead of adding a duplicate arc
    balanced = nx.MultiDiGraph(zone)
    for s in sources:
        for t, fval in flow.get(s, {}).items():
            if fval <= 0:
                continue
            path = nx.shortest_path(zone, s, t, weight="weight")
            for _ in range(int(fval)):
                for i in range(len(path) - 1):
                    u, v = path[i], path[i + 1]
                    attrs = {k: val for k, val in zone.edges[u, v].items() if k != "key"}
                    balanced.add_edge(u, v, **attrs)

    return balanced
