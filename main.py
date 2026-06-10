import os
from src.data_loader import run_data_pipeline

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

    print("\nNext steps: Implement clustering and routing algorithms using the JSON graphs.")
    print("---------------------------------------------------------")

if __name__ == "__main__":
    main()
