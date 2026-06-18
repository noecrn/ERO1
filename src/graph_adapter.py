"""
Couche anti-corruption entre les JSON produits par data_loader.py (étapes 1-4)
et le pipeline interne (étapes 5-7).

Traductions appliquées
----------------------
Arcs  : length_km               → weight   (poids de routage Dijkstra)
        is_crit_security_social → priority (flag RPP, même filtre que p2.py)
Nœuds : lon                     → x        (longitude, convention NetworkX/OSMnx)
        lat                     → y        (latitude,  convention NetworkX/OSMnx)

Tous les attributs originaux sont CONSERVÉS en plus des alias.

Restriction SCC
---------------
Par défaut (restrict_to_main_scc=True), load_graph ne retourne que la plus
grande composante fortement connexe.  Les arcs écartés sont loggés via
warnings.warn.  Cette restriction garantit que step5b et step6 reçoivent
toujours un graphe fortement connexe.

Limitation connue (à signaler à l'équipe)
-----------------------------------------
h_neige n'est pas exporté par save_graph_to_json dans data_loader.py — les arcs
du graphe réel n'ont donc pas cet attribut.  Le pipeline interne n'en a pas
besoin ; si une étape future l'utilise il faudra l'ajouter à l'export.
"""

import json
import warnings
from pathlib import Path

import networkx as nx


def extract_main_scc(G: nx.DiGraph) -> nx.DiGraph:
    """
    Retourne le sous-graphe induit par la plus grande composante fortement
    connexe (SCC) de G.

    Si G est déjà fortement connexe, retourne une copie sans warning.
    Sinon émet un UserWarning détaillant le nombre d'arcs écartés (prioritaires
    et non prioritaires) pour que le dashboard puisse les rapporter.

    Tous les attributs de nœuds et d'arcs sont conservés.
    """
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
        f"extract_main_scc : {discarded_total} arc(s) écartés hors de la grande SCC "
        f"({discarded_prio} prioritaires, {discarded_nonprio} non prioritaires). "
        f"Grande SCC : {result.number_of_nodes()} nœuds / {result.number_of_edges()} arcs.",
        UserWarning,
        stacklevel=2,
    )

    return result


def load_graph(json_path, restrict_to_main_scc: bool = True) -> nx.DiGraph:
    """
    Lire un graph_{quartier}.json et retourner un nx.DiGraph avec les
    attributs canoniques du pipeline interne.

    Parameters
    ----------
    json_path           : str or Path — chemin vers le JSON produit par data_loader.py.
    restrict_to_main_scc: si True (défaut), restreint le graphe à la plus grande SCC.

    Returns
    -------
    nx.DiGraph dont chaque arc porte weight, priority, et les attrs originaux ;
    chaque nœud porte x, y, et les attrs originaux.

    Raises
    ------
    FileNotFoundError si json_path n'existe pas.
    """
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
        attrs["priority"] = bool(edge.get("is_crit_security_social", False))
        G.add_edge(u, v, **attrs)

    if restrict_to_main_scc:
        G = extract_main_scc(G)

    return G
