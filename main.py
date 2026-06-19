# import os
# from src.data_loader import run_data_pipeline
# import json
# from pathlib import Path
# from src.p2 import charger_et_filtrer, construire_graphe, trouver_K_optimal, placer_depots

# FICHIERS = {
#     "outremont":            "data/graph_outremont.json",
#     "verdun":               "data/graph_verdun.json",
#     "anjou":                "data/graph_anjou.json",
#     "riviere_des_prairies": "data/graph_riviere_des_prairies.json",
# }

# SCENARIOS = {
#     "securitaire": 10,
#     "economique":  10,
#     "baseline":    15,
# }







# RAJOUT CLARAAAAAAAAAAAA


import argparse
import time
 
from src.run_pipeline import run_pipeline, _SCENARIO_MAP, _print_summary

# function pour p2 et p3 (je laisse la p2 pour l'instant mais il faudrait l'enlever)
QUARTIERS = ["anjou", "outremont", "verdun", "riviere_des_prairies"]
SCENARIOS = list(_SCENARIO_MAP) 
 
def run_all(quartiers=None, scenarios=None, output_dir="output"):
    quartiers = quartiers or QUARTIERS
    scenarios = scenarios or SCENARIOS
    resultats = {}

    for quartier in quartiers:
        for scenario in scenarios:
            print(f"\n>>> {quartier} / {scenario}")
            t0 = time.time()
            try:
                result = run_pipeline(quartier, scenario, output_dir)
                elapsed = time.time() - t0
                _print_summary(quartier, scenario, result, elapsed)
                resultats[(quartier, scenario)] = result
            except Exception as exc:
                print(f"  [ERREUR] {quartier}/{scenario} : {exc}")
                resultats[(quartier, scenario)] = None
    return resultats


# def run_p2():
#     out = Path("output")
#     out.mkdir(exist_ok=True)

#     for quartier, fichier in FICHIERS.items():
#         print(f"\n{quartier.upper()}")

#         for scenario, deadline in SCENARIOS.items():
#             nodes, edges = charger_et_filtrer(fichier, scenario)
#             G             = construire_graphe(nodes, edges)
#             K_res         = trouver_K_optimal(G, deadline_h=deadline)
#             depots        = placer_depots(G, K_res["K"])

#             print(f"  [{scenario}] K={K_res['K']}, dist={K_res['dist_km']} km, Z={K_res['Z']}$")
#             result = {
#                 "quartier": quartier,
#                 "scenario": scenario,
#                 "K":        K_res["K"],
#                 "dist_km":  K_res["dist_km"],
#                 "Z":        K_res["Z"],
#                 "temps_h":  K_res["temps_h"],
#                 "depots":   depots,
#             }

#             with open(out / f"p2_{quartier}_{scenario}.json", "w", encoding="utf-8") as f:
#                 json.dump(result, f, indent=2, ensure_ascii=False)






# def main():
#     """
#     Main entry point for the ERO1 project.
#     Orchestrates the data acquisition and preparation phase.
#     """
#     print("Starting ERO1 Project: Snow Removal Optimization (Montreal)")
#     print("---------------------------------------------------------")
    
#     # 1. Data Acquisition and Preparation
#     print("\nPHASE 1: DATA ACQUISITION AND PREPARATION")
#     run_data_pipeline()
    
#     # 2. Output Summary
#     print("\nPHASE 2: GENERATED DATA SUMMARY")
#     essential_files = [
#         "data/reseau_rues_complet.geojson",
#         "data/tous_quartiers_zones.geojson",
#         "data/infrastructures_secours.geojson"
#     ]
    
#     for file_path in essential_files:
#         if os.path.exists(file_path):
#             print(f"Verified: {file_path}")
#         else:
#             print(f"Missing: {file_path}")
            
#     print("\nNeighborhood JSON Graphs (for clustering and routing):")
#     if os.path.exists("data"):
#         json_graphs = [f for f in os.listdir("data") if f.startswith("graph_") and f.endswith(".json")]
#         for graph in sorted(json_graphs):
#             print(f"  - data/{graph}")
#     run_p2()


def main():
    parser = argparse.ArgumentParser(
        description="ERO1 — Démo complète : pipeline unique P2+P3 sur 4 quartiers x 3 scénarios"
    )
    parser.add_argument("--quartier", choices=QUARTIERS, help="Limiter à un seul quartier")
    parser.add_argument("--scenario", choices=SCENARIOS, help="Limiter à un seul scénario")
    parser.add_argument("--output-dir", default="output")
    parser.add_argument(
        "--refresh-data",
        action="store_true",
        help="Régénère les graphes via OSMnx avant de lancer le pipeline (nécessite internet)",
    )
    args = parser.parse_args()
 
    if args.refresh_data:
        from src.data_loader import run_data_pipeline
        print("Régénération des données via OSMnx...")
        run_data_pipeline()
 
    quartiers = [args.quartier] if args.quartier else QUARTIERS
    scenarios = [args.scenario] if args.scenario else SCENARIOS
 
    print("ERO1 — Groupe 10")
    print(f"Quartiers : {quartiers}")
    print(f"Scénarios : {scenarios}")
 
    resultats = run_all(quartiers, scenarios, args.output_dir)
 
    ok = sum(1 for v in resultats.values() if v is not None)
    total = len(resultats)
    print(f"\n{ok}/{total} combinaisons terminées avec succès.")
    if ok < total:
        echecs = [f"{q}/{s}" for (q, s), v in resultats.items() if v is None]
        print(f"Échecs : {echecs}")



if __name__ == "__main__":
    main()
