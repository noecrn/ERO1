import os
from src.data_loader import run_data_pipeline
import json
from pathlib import Path
from src.p2 import charger_et_filtrer, construire_graphe, trouver_K_optimal, placer_depots

FICHIERS = {
    "outremont":            "data/graph_outremont.json",
    "verdun":               "data/graph_verdun.json",
    "anjou":                "data/graph_anjou.json",
    "riviere_des_prairies": "data/graph_riviere_des_prairies.json",
}

SCENARIOS = {
    "securitaire": 10,
    "economique":  10,
    "baseline":    15,
}


def run_p2():
    out = Path("output")
    out.mkdir(exist_ok=True)

    for quartier, fichier in FICHIERS.items():
        print(f"\n{quartier.upper()}")

        for scenario, deadline in SCENARIOS.items():
            nodes, edges = charger_et_filtrer(fichier, scenario)
            G             = construire_graphe(nodes, edges)
            K_res         = trouver_K_optimal(G, deadline_h=deadline)
            depots        = placer_depots(G, K_res["K"])

            print(f"  [{scenario}] K={K_res['K']}, dist={K_res['dist_km']} km, Z={K_res['Z']}$")
            result = {
                "quartier": quartier,
                "scenario": scenario,
                "K":        K_res["K"],
                "dist_km":  K_res["dist_km"],
                "Z":        K_res["Z"],
                "temps_h":  K_res["temps_h"],
                "depots":   depots,
            }

            with open(out / f"p2_{quartier}_{scenario}.json", "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)






def main():
    """
    Main entry point for the ERO1 project.
    Orchestrates the data acquisition and preparation phase.
    """
    print("Starting ERO1 Project: Snow Removal Optimization (Montreal)")
    print("---------------------------------------------------------")
    
    # 1. Data Acquisition and Preparation
    print("\nPHASE 1: DATA ACQUISITION AND PREPARATION")
    run_data_pipeline()
    
    # 2. Output Summary
    print("\nPHASE 2: GENERATED DATA SUMMARY")
    essential_files = [
        "data/reseau_rues_complet.geojson",
        "data/tous_quartiers_zones.geojson",
        "data/infrastructures_secours.geojson"
    ]
    
    for file_path in essential_files:
        if os.path.exists(file_path):
            print(f"Verified: {file_path}")
        else:
            print(f"Missing: {file_path}")
            
    print("\nNeighborhood JSON Graphs (for clustering and routing):")
    if os.path.exists("data"):
        json_graphs = [f for f in os.listdir("data") if f.startswith("graph_") and f.endswith(".json")]
        for graph in sorted(json_graphs):
            print(f"  - data/{graph}")
    run_p2()

if __name__ == "__main__":
    main()
