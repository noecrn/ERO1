"""
Utility module to transform geospatial data into formats suitable for
Operations Research (RO) and routing algorithms.
"""

import geopandas as gpd
import json
import os
import numpy as np

def exporter_pour_algorithmes(geojson_rues_path):
    """
    Transforms unified GeoJSON street data into an in-memory 
    Operations Research (RO) structure.
    
    Args:
        geojson_rues_path (str): Path to the unified GeoJSON file.
        
    Returns:
        list: A list of dictionaries representing graph arcs.
    """
    if not os.path.exists(geojson_rues_path):
        print(f"ERROR: File {geojson_rues_path} does not exist.")
        return []

    print(f"Reading {geojson_rues_path} for in-memory transformation...")
    gdf = gpd.read_file(geojson_rues_path)
    
    arcs_pour_ro = []
    
    for index, row in gdf.iterrows():
        # Handle potential list or array types in the highway column from OSMnx
        highway_raw = row.get("highway", "residential")
        if isinstance(highway_raw, (list, tuple, np.ndarray)):
            type_route = str(highway_raw[0]) if len(highway_raw) > 0 else "residential"
        else:
            type_route = str(highway_raw)

        # Construct the standardized arc object
        arc = {
            "id_arc": int(row.get("key", index)),
            "source_node": int(row.get("u", -1)),
            "target_node": int(row.get("v", -1)),
            "neighborhood": str(row.get("quartier", "unknown")),
            "road_type": type_route,
            "distance_km": float(row.get("length_km", 0.0)),
            "priorities": {
                "security": bool(row.get("is_crit_security", False)),
                "social": bool(row.get("is_crit_social", False)),
                "economic": bool(row.get("is_crit_economique", False))
            },
            "scenarios": {
                "1": bool(row.get("scenario_1", False)),
                "2": bool(row.get("scenario_2", False)),
                "3": bool(row.get("scenario_3", True))
            }
        }
        arcs_pour_ro.append(arc)
        
    print(f"SUCCESS: {len(arcs_pour_ro)} arcs transformed in memory.")
    return arcs_pour_ro

if __name__ == "__main__":
    # Internal module test
    transformed_data = exporter_pour_algorithmes("data/reseau_rues_complet.geojson")
