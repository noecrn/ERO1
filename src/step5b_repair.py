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
    priority_only: bool = False,
) -> nx.DiGraph:
    """
    Return a strongly connected DiGraph ready for DCPP (step 6).

    Mode CPP classique (priority_only=False, défaut)
    -------------------------------------------------
    Augmente *zone* avec des arcs de réparation depuis *G_full* jusqu'à
    obtenir la connexité forte.  Arcs ajoutés : repair=True.

    Mode RPP (priority_only=True)
    ------------------------------
    Extrait le sous-graphe des arcs priority=True de *zone*, puis le rend
    fortement connexe en greffant des connecteurs depuis *G_full*.
    Arcs greffés : connector=True.  Les arcs priority originaux conservent
    leurs attributs inchangés.  Les arcs non-prioritaires de *zone* sont
    exclus du résultat sauf s'ils apparaissent comme connecteurs.

    Parameters
    ----------
    zone          : DiGraph produit par step 5 ; doit être un sous-graphe de G_full.
    G_full        : réseau complet issu des étapes 1-4 (garanti SC par graph_adapter).
    priority_only : si True, active le mode RPP décrit ci-dessus.

    Returns
    -------
    Nouveau DiGraph (zone jamais muté).

    Raises
    ------
    ValueError  si G_full ne contient pas de chemin pour relier deux SCCs
                (cul-de-sac réel dans les données source).
    ValueError  si priority_only=True et qu'aucun arc prioritaire n'est présent.
    """
    if priority_only:
        return _ensure_sc_priority_only(zone, G_full)

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

    # frozenset iteration order is hash-randomized per process (str node IDs) —
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


def _graft_path_as_connector(
    result: nx.DiGraph, path: list, G_full: nx.DiGraph
) -> None:
    """
    Greffe les arcs de *path* dans *result* avec connector=True.
    Arcs déjà présents (prioritaires) conservent leurs attributs.
    Mutates *result* in place.
    """
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
    """
    Mode RPP : extrait les arcs priority=True de *zone*, les rend fortement
    connexes en greffant des connecteurs depuis *G_full*.

    Raises ValueError si aucun arc prioritaire ou si G_full ne peut pas relier
    deux SCCs (cul-de-sac réel dans le réseau source).
    """
    # Extraire le sous-graphe prioritaire
    prio_edges = [(u, v, d) for u, v, d in zone.edges(data=True) if d.get("priority")]
    if not prio_edges:
        raise ValueError(
            "priority_only=True mais aucun arc prioritaire dans la zone. "
            "Vérifier le flag 'priority' sur les arcs de la zone."
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

    # Même algorithme que le mode CPP — sink→source itératif — mais sur le
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
                "G_full — cul-de-sac réel dans le réseau source.  "
                f"Aucun chemin de {from_nodes} vers {to_nodes} dans G_full."
            )

        _graft_path_as_connector(result, path, G_full)
    else:
        if not nx.is_strongly_connected(result):
            raise ValueError(
                "Réparation RPP non convergée après le nombre maximal d'itérations."
            )

    return result
