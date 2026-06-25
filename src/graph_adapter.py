import json
import warnings
from pathlib import Path

import networkx as nx

SEUIL_NEIGE_MIN_CM = 2.5
SEUIL_NEIGE_MAX_CM = 15.0


def extract_main_scc(G: nx.DiGraph) -> nx.DiGraph:
    if nx.is_strongly_connected(G):
        return G.copy()

    largest_scc = max(nx.strongly_connected_components(G), key=len)
    result = G.subgraph(largest_scc).copy()

    discarded_total = G.number_of_edges() - result.number_of_edges()
    discarded_prio = sum(
        1 for u, v, d in G.edges(data=True)
        if d.get("priority") and not (u in largest_scc and v in largest_scc)
    )
    discarded_nonprio = discarded_total - discarded_prio

    warnings.warn(
        f"extract_main_scc : {discarded_total} arc(s) ecartes hors de la grande SCC "
        f"({discarded_prio} prioritaires, {discarded_nonprio} non prioritaires). "
        f"Grande SCC : {result.number_of_nodes()} noeuds / {result.number_of_edges()} arcs.",
        UserWarning,
        stacklevel=2,
    )

    return result


def load_graph(
    json_path,
    restrict_to_main_scc: bool = True,
    priority_field: str = "is_crit_security_social",
) -> nx.DiGraph:
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"Graphe introuvable : {path}")

    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)

    G = nx.DiGraph()

    for node_id, attrs in data["nodes"].items():
        G.add_node(
            node_id,
            **attrs,
            x=float(attrs["lon"]),
            y=float(attrs["lat"]),
        )

    for edge in data["edges"]:
        u = edge["source"]
        v = edge["target"]
        attrs = {k: v for k, v in edge.items() if k not in ("source", "target")}
        attrs["weight"] = float(edge["length_km"])
        attrs["priority"] = bool(edge.get(priority_field, False))
        h_neige = edge.get("h_neige", 0.0)
        attrs["needs_clearing"] = bool(
            attrs["priority"] and SEUIL_NEIGE_MIN_CM <= h_neige <= SEUIL_NEIGE_MAX_CM
        )
        G.add_edge(u, v, **attrs)

    if restrict_to_main_scc:
        G = extract_main_scc(G)

    return G
