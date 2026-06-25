import math

import networkx as nx


def ensure_strong_connectivity(
    zone: nx.DiGraph,
    G_full: nx.DiGraph,
    priority_only: bool = False,
) -> nx.DiGraph:
    if priority_only:
        return _ensure_sc_priority_only(zone, G_full)

    repaired = zone.copy()

    if nx.is_strongly_connected(repaired):
        return repaired

    # Upper bound on iterations: at most (|V| 1) SCCs can be merged.
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
                "G_full - cul-de-sac reel dans le reseau source.  "
                f"Aucun chemin de {from_nodes} vers {to_nodes} dans G_full."
            )

        _graft_path(repaired, path, G_full)
    else:
        if not nx.is_strongly_connected(repaired):
            raise ValueError(
                "Reparation non convergee apres le nombre maximal d'iterations."
            )

    return repaired


def _pick_sink_source_pair(cond: nx.DiGraph) -> tuple[int, int]:
    sinks   = [n for n in cond.nodes() if cond.out_degree(n) == 0]
    sources = [n for n in cond.nodes() if cond.in_degree(n) == 0]

    from_idx = sinks[0]
    # Prefer a source that differs from the chosen sink.
    to_idx = next((s for s in sources if s != from_idx), None)
    if to_idx is None:
        # All sources happen to be the same SCC pick any other node.
        to_idx = next(n for n in cond.nodes() if n != from_idx)

    return from_idx, to_idx


def _shortest_path_between_sets(
    G: nx.DiGraph,
    from_set: frozenset,
    to_set: frozenset,
) -> list | None:
    best_length = math.inf
    best_path: list | None = None

    # frozenset iteration order is hash-randomized per process (str node IDs) -
    # sort first so tie-breaks (equal-length paths) are reproducible across runs.
    for s in sorted(from_set):
        try:
            lengths, paths = nx.single_source_dijkstra(G, s, weight="weight")
        except nx.NodeNotFound:
            continue
        for t in sorted(to_set):
            d = lengths.get(t, math.inf)
            if d < best_length:
                best_length = d
                best_path = paths[t]

    return best_path


def _graft_path(repaired: nx.DiGraph, path: list, G_full: nx.DiGraph) -> None:
    for u, v in zip(path, path[1:]):
        if u not in repaired:
            repaired.add_node(u, **G_full.nodes[u])
        if v not in repaired:
            repaired.add_node(v, **G_full.nodes[v])
        if not repaired.has_edge(u, v):
            attrs = dict(G_full.edges[u, v])
            attrs["repair"] = True
            repaired.add_edge(u, v, **attrs)


def _graft_path_as_connector(
    result: nx.DiGraph, path: list, G_full: nx.DiGraph
) -> None:
    for u, v in zip(path, path[1:]):
        if u not in result:
            result.add_node(u, **G_full.nodes[u])
        if v not in result:
            result.add_node(v, **G_full.nodes[v])
        if not result.has_edge(u, v):
            attrs = dict(G_full.edges[u, v])
            attrs["connector"] = True
            result.add_edge(u, v, **attrs)


def _ensure_sc_priority_only(zone: nx.DiGraph, G_full: nx.DiGraph) -> nx.DiGraph:
    # Extraire le sous-graphe des arcs reellement a deneiger
    prio_edges = [(u, v, d) for u, v, d in zone.edges(data=True) if d.get("needs_clearing")]
    if not prio_edges:
        raise ValueError(
            "priority_only=True mais aucun arc a deneiger dans la zone "
            "(needs_clearing=True). Verifier les flags 'priority'/'h_neige'."
        )

    result = nx.DiGraph()
    for u, v, d in prio_edges:
        if u not in result:
            result.add_node(u, **zone.nodes[u])
        if v not in result:
            result.add_node(v, **zone.nodes[v])
        result.add_edge(u, v, **d)

    if nx.is_strongly_connected(result):
        return result

    # Meme algorithme que le mode CPP sink->source iteratif mais sur le
    # sous-graphe prioritaire et avec _graft_path_as_connector.
    max_iter = result.number_of_nodes() + G_full.number_of_nodes()

    for _ in range(max_iter):
        if nx.is_strongly_connected(result):
            break

        cond = nx.condensation(result)
        from_idx, to_idx = _pick_sink_source_pair(cond)

        from_nodes = cond.nodes[from_idx]["members"]
        to_nodes   = cond.nodes[to_idx]["members"]

        path = _shortest_path_between_sets(G_full, from_nodes, to_nodes)
        if path is None:
            raise ValueError(
                "Impossible de relier les composantes fortement connexes via "
                "G_full - cul-de-sac reel dans le reseau source.  "
                f"Aucun chemin de {from_nodes} vers {to_nodes} dans G_full."
            )

        _graft_path_as_connector(result, path, G_full)
    else:
        if not nx.is_strongly_connected(result):
            raise ValueError(
                "Reparation RPP non convergee apres le nombre maximal d'iterations."
            )

    return result
