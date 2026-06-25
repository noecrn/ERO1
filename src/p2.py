import json
import argparse
import numpy as np
import networkx as nx
from sklearn.cluster import KMeans

C_FIXE  = 500   # $/jour/deneigeuse
C_KM    = 1.1   # $/km
C_H1    = 1.1   # $/h < 8h
C_H2    = 1.3   # $/h > 8h
V_MOY   = 10    # km/h
T_SHIFT = 8     # before h sup


SCENARIOS = {
    "securitaire": {
        "filtre":   lambda e: e.get("is_crit_security_social", False),
        "deadline": 8,
        "label":    "Securitaire & Social",
    },
    "economique": {
        "filtre":   lambda e: e.get("is_crit_economique", False),
        "deadline": 8,
        "label":    "Economique",
    },
    "baseline": {
        "filtre":   lambda e: True,
        "deadline": 15,
        "label":    "Baseline (tout le reseau)",
    },
}


def charger_et_filtrer(fichier, scenario):
    with open(fichier, encoding="utf-8") as f:
        data = json.load(f)

    filtre = SCENARIOS[scenario]["filtre"]

    nodes = data["nodes"]
    edges = [e for e in data["edges"] if filtre(e)]

    return nodes, edges


def construire_graphe(nodes, edges):
    G = nx.DiGraph()

    for edge in edges:
        u = edge["source"]
        v = edge["target"]
        G.add_edge(u, v,
                   weight=edge["length_km"],
                   highway=edge.get("highway", "unknown"))
    for node_id, coords in nodes.items():
        if node_id in G.nodes:
            G.nodes[node_id]["lat"] = coords["lat"]
            G.nodes[node_id]["lon"] = coords["lon"]

    return G


def cout_horaire(temps_h, K):
    if temps_h <= T_SHIFT:
        return K * temps_h * C_H1
    return K * (T_SHIFT * C_H1 + (temps_h - T_SHIFT) * C_H2)


def trouver_K_optimal(G, deadline_h):
    dist_totale = sum(d["weight"] for _, _, d in G.edges(data=True))

    if dist_totale == 0:
        return {"K": 0, "Z": 0, "temps_h": 0,
                "dist_km": 0, "overtime_h": 0}

    tous_resultats = []

    for K in range(1, 21):
        temps = dist_totale / (K * V_MOY)
        overtime = max(0, temps - T_SHIFT)
        Z = K * C_FIXE + dist_totale * C_KM + cout_horaire(temps, K)

        tous_resultats.append({
            "K":          K,
            "Z":          round(Z, 2),
            "temps_h":    round(temps, 2),
            "dist_km":    round(dist_totale, 2),
            "overtime_h": round(overtime, 2),
            "ok":         temps <= deadline_h,
        })

    faisables = [r for r in tous_resultats if r["ok"]]
    if faisables:
        return min(faisables, key=lambda x: x["Z"])

    return min(tous_resultats, key=lambda x: x["temps_h"])


def placer_depots(G, K):
    if K == 0:
        return []

    noeuds = [
        (n, G.nodes[n]["lon"], G.nodes[n]["lat"])
        for n in G.nodes()
        if "lat" in G.nodes[n] and "lon" in G.nodes[n]
    ]

    if len(noeuds) < K:
        return [{"noeud_id": n[0], "lon": n[1], "lat": n[2]}
                for n in noeuds[:K]]

    coords = np.array([[n[1], n[2]] for n in noeuds])
    ids    = [n[0] for n in noeuds]

    km = KMeans(n_clusters=K, random_state=42, n_init=10).fit(coords)

    depots = []
    for center in km.cluster_centers_:
        dists      = np.linalg.norm(coords - center, axis=1)
        depot_id   = ids[int(np.argmin(dists))]
        depots.append({
            "noeud_id": depot_id,
            "lon":      float(G.nodes[depot_id]["lon"]),
            "lat":      float(G.nodes[depot_id]["lat"]),
        })

    return depots
