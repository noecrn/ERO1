import osmnx as ox
import geopandas as gpd
import pandas as pd
import os
import json
import networkx as nx

def check_and_create_data_dir():
    """
    Ensures that the output data directory exists.
    """
    if not os.path.exists("data"):
        os.makedirs("data")
        print("Data directory created.")

def save_graph_to_json(G, short_name, output_dir="data"):
    """
    Converts an enriched NetworkX graph into a structured JSON file.
    Includes node coordinates (latitude/longitude) and edge attributes
    for clustering and routing algorithms.
    """
    print(f"[{short_name}] Serializing graph to JSON...")
    
    # Extract nodes with their GPS coordinates
    nodes_dict = {}
    for node_id, data in G.nodes(data=True):
        nodes_dict[str(node_id)] = {
            "lat": data.get("y"),
            "lon": data.get("x")
        }

    # Extract edges with their priority attributes
    edges_list = []
    for u, v, k, data in G.edges(keys=True, data=True):
        edge_entry = {
            "source": str(u),
            "target": str(v),
            "key": k,
            "length_km": data.get("length_km", data.get("length", 0) / 1000.0),
            "highway": data.get("highway", "residential"),
            "is_crit_security": data.get("is_crit_security", False),
            "is_crit_social": data.get("is_crit_social", False),
            "is_crit_economique": data.get("is_crit_economique", False)
        }
        edges_list.append(edge_entry)

    # Build final structure
    graph_json = {
        "quartier": short_name,
        "nodes": nodes_dict,
        "edges": edges_list
    }

    # Write to file
    output_path = os.path.join(output_dir, f"graph_{short_name}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(graph_json, f, indent=2, ensure_ascii=False)
        
    print(f"DONE: JSON graph saved at {output_path}")

def get_administrative_boundary(quartier_name, short_name):
    """
    Retrieves the administrative boundary for a specific neighborhood.
    """
    try:
        print(f"[{short_name}] Fetching administrative boundary...")
        area_gdf = ox.geocode_to_gdf(quartier_name)
        area_filtered = area_gdf[['geometry', 'display_name']].copy()
        area_filtered['quartier'] = short_name
        return area_filtered
    except Exception as e:
        print(f"ERROR: Could not retrieve boundary for {short_name}: {e}")
        return None

def annotate_graph_priorities(G):
    """
    Enriches the NetworkX graph edges with priority indicators
    based on road type and naming conventions.
    """
    for u, v, k, data in G.edges(keys=True, data=True):
        highway_type = data.get('highway', 'residential')
        if isinstance(highway_type, list): 
            highway_type = highway_type[0]
        
        nom_rue = str(data.get('name', '')).lower()
        
        # Security criteria: Hospitals, fire stations, major roads
        is_secu_infra = any(keyword in nom_rue for keyword in ['hopital', 'hospital', 'clinique', 'sante', 'pompier'])
        is_major_secu = highway_type in ['motorway', 'trunk', 'primary']
        data['is_crit_security'] = bool(is_secu_infra or is_major_secu)

        # Social criteria: Schools, secondary roads
        is_social_infra = any(keyword in nom_rue for keyword in ['ecole', 'school', 'college'])
        is_major_social = highway_type in ['secondary', 'tertiary']
        data['is_crit_social'] = bool(is_social_infra or is_major_social)

        # Economic criteria: Bus lanes, commercial areas, major economic axes
        is_bus = data.get('bus_guideway') == 'yes' or data.get('lanes:bus') is not None
        is_major_eco = highway_type in ['primary', 'secondary', 'motorway', 'tertiary']
        data['is_crit_economique'] = bool(is_bus or is_major_eco or 'commercial' in nom_rue)
        
        # Ensure length is available in kilometers
        data['length_km'] = data.get('length', 0) / 1000.0
        
    return G

def get_street_network(quartier_name, short_name):
    """
    Downloads and processes the road network for a neighborhood.
    """
    try:
        print(f"[{short_name}] Fetching road network...")
        if short_name == "verdun":
            # Verdun requires merging with Nuns' Island (Île des Sœurs)
            G_main = ox.graph_from_place("Verdun, Montreal, Canada", network_type="drive")
            G_ile = ox.graph_from_place("Île des Sœurs, Montreal, Canada", network_type="drive")
            G = nx.compose(G_main, G_ile)
        else:
            G = ox.graph_from_place(quartier_name, network_type="drive")
        
        # Annotate priorities directly on the graph object
        G = annotate_graph_priorities(G)
        
        # Convert to GeoDataFrame for spatial exports
        _, edges_gdf = ox.graph_to_gdfs(G, nodes=True, edges=True)
        edges_gdf = edges_gdf.reset_index()
        
        # Select relevant columns for the final dataset
        cols = ['u', 'v', 'key', 'geometry', 'highway', 'length_km', 'is_crit_security', 'is_crit_social', 'is_crit_economique']
        existing_cols = [c for c in cols if c in edges_gdf.columns]
        edges_filtered = edges_gdf[existing_cols].copy()
        edges_filtered['quartier'] = short_name
        
        return edges_filtered, G
    except Exception as e:
        print(f"ERROR: Could not retrieve streets for {short_name}: {e}")
        return None, None

def get_security_pois(quartier_name, short_name):
    """
    Retrieves security-related Points of Interest (hospitals, fire stations).
    """
    try:
        print(f"[{short_name}] Fetching security infrastructure POIs...")
        tags = {
            'amenity': ['hospital', 'fire_station', 'clinic', 'police', 'doctors'],
            'healthcare': True
        }
        if short_name == "verdun":
            p1 = ox.features_from_place("Verdun, Montreal, Canada", tags=tags)
            p2 = ox.features_from_place("Île des Sœurs, Montreal, Canada", tags=tags)
            pois = pd.concat([p1, p2])
        else:
            pois = ox.features_from_place(quartier_name, tags=tags)
        
        if not pois.empty:
            # Keep only point geometries to avoid large building polygons
            pois = pois[pois.geometry.type == 'Point'].copy()
            if not pois.empty:
                if 'name' not in pois.columns: 
                    pois['name'] = "Unknown"
                pois_filtered = pois[['geometry', 'name']].copy()
                pois_filtered['quartier'] = short_name
                pois_filtered['type'] = "infrastructure_secours"
                return pois_filtered
    except Exception:
        # Some areas might not return POIs for these specific tags
        print(f"WARNING: No security POIs found for {short_name}")
    
    return None

def run_data_pipeline():
    """
    Main entry point for the data acquisition and preparation pipeline.
    """
    check_and_create_data_dir()
    
    # Neighborhoods configuration
    quartiers = {
        "Outremont, Montreal, Canada": "outremont",
        "Verdun, Montreal, Canada": "verdun",
        "Anjou, Montreal, Canada": "anjou",
        "Rivière-des-Prairies-Pointe-aux-Trembles, Montreal, Canada": "riviere_des_prairies"
    }
    
    all_areas = []
    all_streets = []
    all_pois = []
    
    for full_name, short_name in quartiers.items():
        print(f"\n--- EXTRACTION: {short_name.upper()} ---")
        
        # 1. Neighborhood boundaries
        area = get_administrative_boundary(full_name, short_name)
        if area is not None: 
            all_areas.append(area)
        
        # 2. Road network and Graph JSONs for solvers
        streets_gdf, G = get_street_network(full_name, short_name)
        if streets_gdf is not None: 
            all_streets.append(streets_gdf)
            save_graph_to_json(G, short_name)
        
        # 3. Security Points of Interest
        pois = get_security_pois(full_name, short_name)
        if pois is not None: 
            all_pois.append(pois)
            
    # Export global neighborhood zones
    if all_areas:
        combined_areas = gpd.GeoDataFrame(pd.concat(all_areas, ignore_index=True), crs=all_areas[0].crs)
        combined_areas.to_file("data/tous_quartiers_zones.geojson", driver="GeoJSON")

    # Export simplified security POIs
    if all_pois:
        combined_pois = gpd.GeoDataFrame(pd.concat(all_pois, ignore_index=True), crs=all_pois[0].crs)
        combined_pois.to_file("data/infrastructures_secours.geojson", driver="GeoJSON")

    # Export unified street network with scenario flags
    if all_streets:
        combined_streets = gpd.GeoDataFrame(pd.concat(all_streets, ignore_index=True), crs=all_streets[0].crs)
        
        # Scenario 1: Security and Social Priority
        combined_streets['scenario_1'] = (combined_streets['is_crit_security'] == True) | (combined_streets['is_crit_social'] == True)
        
        # Scenario 2: Economic Priority
        combined_streets['scenario_2'] = (combined_streets['is_crit_economique'] == True)
        
        # Scenario 3: Baseline (Global Network)
        combined_streets['scenario_3'] = True
        
        combined_streets.to_file("data/reseau_rues_complet.geojson", driver="GeoJSON")
        print("\nSUCCESS: Global street network exported with scenario flags.")
        
    print("\nData pipeline completed.")

if __name__ == "__main__":
    run_data_pipeline()
