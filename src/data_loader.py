import osmnx as ox
import geopandas as gpd
import pandas as pd
import os
import json
import networkx as nx
import random

def check_and_create_data_dir():
    if not os.path.exists("data"):
        os.makedirs("data")
        print("Data directory created.")

def save_graph_to_json(G, short_name, output_dir="data"):
    print(f"[{short_name}] Serializing graph to JSON...")

    nodes_dict = {}
    for node_id, data in G.nodes(data=True):
        nodes_dict[str(node_id)] = {
            "lat": data.get("y"),
            "lon": data.get("x")
        }

    edges_list = []
    for u, v, k, data in G.edges(keys=True, data=True):
        edge_entry = {
            "source": str(u),
            "target": str(v),
            "key": k,
            "length_km": data.get("length_km", data.get("length", 0) / 1000.0),
            "h_neige": data.get("h_neige", 0.0),
            "highway": data.get("highway", "residential"),
            "is_crit_security_social": data.get("is_crit_security_social", False),
            "is_crit_economique": data.get("is_crit_economique", False)
        }
        edges_list.append(edge_entry)

    graph_json = {
        "quartier": short_name,
        "nodes": nodes_dict,
        "edges": edges_list
    }

    output_path = os.path.join(output_dir, f"graph_{short_name}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(graph_json, f, indent=2, ensure_ascii=False)

    print(f"DONE: JSON graph saved at {output_path}")

def get_administrative_boundary(quartier_name, short_name):
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
    for u, v, k, data in G.edges(keys=True, data=True):
        highway_type = data.get('highway', 'residential')
        if isinstance(highway_type, list):
            highway_type = highway_type[0]

        nom_rue = str(data.get('name', '')).lower()

        is_secu_social_infra = any(keyword in nom_rue for keyword in ['hopital', 'hospital', 'hopital', 'clinique', 'sante', 'sante', 'pompier', 'ecole', 'ecole', 'school', 'college', 'caserne'])

        if highway_type in ['tertiary', 'residential']:
            is_crit_secu = is_secu_social_infra
        else:
            is_crit_secu = highway_type in ['primary', 'secondary']

        data['is_crit_security_social'] = bool(is_crit_secu)

        is_bus = data.get('bus_guideway') == 'yes' or data.get('lanes:bus') is not None
        is_major_eco = highway_type in ['primary', 'secondary', 'motorway', 'tertiary']
        data['is_crit_economique'] = bool(is_bus or is_major_eco or 'commercial' in nom_rue)

        data['length_km'] = data.get('length', 0) / 1000.0
        data['h_neige'] = round(random.uniform(0.0, 20.0), 2)

    return G

def get_street_network(quartier_name, short_name):
    try:
        print(f"[{short_name}] Fetching road network...")
        if short_name == "verdun":
            # Verdun requires merging with Nuns' Island (Ile des Soeurs)
            G_main = ox.graph_from_place("Verdun, Montreal, Canada", network_type="drive")
            G_ile = ox.graph_from_place("Ile des Soeurs, Montreal, Canada", network_type="drive")
            G = nx.compose(G_main, G_ile)
        else:
            G = ox.graph_from_place(quartier_name, network_type="drive")

        G = annotate_graph_priorities(G)

        _, edges_gdf = ox.graph_to_gdfs(G, nodes=True, edges=True)
        edges_gdf = edges_gdf.reset_index()

        cols = ['u', 'v', 'key', 'geometry', 'highway', 'length_km', 'h_neige', 'is_crit_security_social', 'is_crit_economique']
        existing_cols = [c for c in cols if c in edges_gdf.columns]
        edges_filtered = edges_gdf[existing_cols].copy()
        edges_filtered['quartier'] = short_name

        return edges_filtered, G
    except Exception as e:
        print(f"ERROR: Could not retrieve streets for {short_name}: {e}")
        return None, None

def get_infrastructure_pois(quartier_name, short_name):
    try:
        print(f"[{short_name}] Fetching infrastructure POIs (Security & Social)...")
        tags = {
            'amenity': ['hospital', 'fire_station', 'clinic', 'police', 'doctors', 'school', 'university', 'college', 'social_facility'],
            'healthcare': True,
            'social_facility:for': ['senior', 'disability', 'disabled']
        }

        if short_name == "verdun":
            p1 = ox.features_from_place("Verdun, Montreal, Canada", tags=tags)
            p2 = ox.features_from_place("Ile des Soeurs, Montreal, Canada", tags=tags)
            pois = pd.concat([p1, p2])
        else:
            pois = ox.features_from_place(quartier_name, tags=tags)

        if not pois.empty:
            pois = pois[pois.geometry.type == 'Point'].copy()

            if not pois.empty:
                if 'name' not in pois.columns:
                    pois['name'] = "Unknown"

                def categorize(row):
                    name = str(row.get('name', '')).lower()
                    amenity = row.get('amenity')
                    social = row.get('social_facility:for')

                    if amenity == 'hospital' or row.get('healthcare') == 'hospital' or 'hopital' in name:
                        return 'hospital', 'hospital', '#e74c3c', 'medium', 2
                    if amenity == 'fire_station' or 'caserne' in name:
                        return 'fire_station', 'fire-station', '#e67e22', 'medium', 2
                    if amenity == 'police' or 'poste de quartier' in name:
                        return 'police', 'police', '#2980b9', 'medium', 2
                    if amenity in ['clinic', 'doctors'] or 'clinique' in name or 'clsc' in name:
                        return 'clinic', 'hospital', '#e74c3c', 'medium', 2
                    if amenity in ['school', 'university', 'college'] or 'ecole' in name:
                        return 'school', 'school', '#3498db', 'medium', 2
                    if social in ['senior', 'elderly'] or 'residence' in name:
                        return 'senior_home', 'home', '#a0522d', 'medium', 2
                    if social in ['disability', 'disabled'] or row.get('wheelchair') == 'yes' or 'pmr' in name:
                        return 'pmr_facility', 'wheelchair', '#9b59b6', 'medium', 2

                    return 'infrastructure_secours', 'marker', '#7f8c8d', 'medium', 2

                results = pois.apply(categorize, axis=1)
                pois['type'] = [r[0] for r in results]
                pois['marker-symbol'] = [r[1] for r in results]
                pois['marker-color'] = [r[2] for r in results]
                pois['marker-size'] = [r[3] for r in results]
                pois['stroke-width'] = [r[4] for r in results]
                pois['stroke'] = pois['marker-color']

                pois_filtered = pois[['geometry', 'name', 'type', 'marker-symbol', 'marker-color', 'marker-size', 'stroke', 'stroke-width']].copy()
                pois_filtered['quartier'] = short_name
                return pois_filtered
    except Exception as e:
        print(f"WARNING: Issue fetching POIs for {short_name}: {e}")

    return None

def run_data_pipeline():
    check_and_create_data_dir()

    quartiers = {
        "Outremont, Montreal, Canada": "outremont",
        "Verdun, Montreal, Canada": "verdun",
        "Anjou, Montreal, Canada": "anjou",
        "Riviere-des-Prairies-Pointe-aux-Trembles, Montreal, Canada": "riviere_des_prairies"
    }

    all_areas = []
    all_streets = []
    all_pois = []

    for full_name, short_name in quartiers.items():
        print(f"\n--- EXTRACTION: {short_name.upper()} ---")

        area = get_administrative_boundary(full_name, short_name)
        if area is not None:
            all_areas.append(area)

        pois = get_infrastructure_pois(full_name, short_name)
        if pois is not None:
            all_pois.append(pois)

        streets_gdf, G = get_street_network(full_name, short_name)

        if streets_gdf is not None and pois is not None:
            # buffer 150m projet en metrique pour precision (UTM zone 18N pour Montreal)
            pois_metric = pois.to_crs(epsg=32618)
            streets_metric = streets_gdf.to_crs(epsg=32618)

            poi_buffer = pois_metric.buffer(150).unary_union
            is_near_poi = streets_metric.intersects(poi_buffer)

            def check_crit(row, near_poi):
                h_type = row['highway']
                if isinstance(h_type, list): h_type = h_type[0]
                if h_type in ['primary', 'secondary']:
                    return True
                if h_type in ['tertiary', 'residential']:
                    return near_poi
                return False

            new_flags = []
            for idx, row in streets_gdf.iterrows():
                val = bool(check_crit(row, is_near_poi.iloc[idx]))
                new_flags.append(val)
                u, v, k = row['u'], row['v'], row['key']
                G[u][v][k]['is_crit_security_social'] = val

            streets_gdf['is_crit_security_social'] = new_flags

        if streets_gdf is not None:
            all_streets.append(streets_gdf)
            save_graph_to_json(G, short_name)

    if all_areas:
        combined_areas = gpd.GeoDataFrame(pd.concat(all_areas, ignore_index=True), crs=all_areas[0].crs)
        combined_areas.to_file("data/tous_quartiers_zones.geojson", driver="GeoJSON")

    if all_pois:
        combined_pois = gpd.GeoDataFrame(pd.concat(all_pois, ignore_index=True), crs=all_pois[0].crs)
        combined_pois.to_file("data/infrastructures_secours.geojson", driver="GeoJSON")

    if all_streets:
        combined_streets = gpd.GeoDataFrame(pd.concat(all_streets, ignore_index=True), crs=all_streets[0].crs)

        types_autorises = ['primary', 'secondary', 'tertiary', 'residential']

        combined_streets['scenario_1'] = (combined_streets['is_crit_security_social'] == True) & (combined_streets['highway'].isin(types_autorises))
        combined_streets['scenario_2'] = (combined_streets['is_crit_economique'] == True)
        combined_streets['scenario_3'] = True

        combined_streets.to_file("data/reseau_rues_complet.geojson", driver="GeoJSON")

        geojson_seco_social = combined_streets[combined_streets['scenario_1'] == True].copy()
        geojson_seco_social.to_file("data/scenario_seco_social_strict.geojson", driver="GeoJSON")

        print("\nSUCCESS: Fichiers de scenarios exportes.")

    print("\nData pipeline completed.")

if __name__ == "__main__":
    run_data_pipeline()
