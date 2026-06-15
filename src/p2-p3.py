from p2 import charger_et_filtrer, construire_graphe, trouver_K_optimal, placer_depots


FICHIERS = {
    "outremont":            "graph_outremont.json",
    "verdun":               "graph_verdun.json",
    "anjou":                "graph_anjou.json",
    "riviere_des_prairies": "graph_riviere_des_prairies.json",
}
#FIXME: mettre les deadlins voulu combien d'heures max pour chaque opération
DEADLINES = {
    "securitaire_social": 10,
    "economique":         10,
    "baseline":           15,
}

for quartier, fichier in FICHIERS.items():
    for scenario, deadline in DEADLINES.items():

        #action de P2
        nodes, edges = charger_et_filtrer(fichier, scenario)
        G            = construire_graphe(nodes, edges)
        K_res        = trouver_K_optimal(G, deadline_h=deadline)
        depots       = placer_depots(G, K_res["K"])
        #action de P3