import osmnx as ox
import geopandas as gpd
import os
import networkx as nx

def check_and_create_data_dir():
    """S'assure que le dossier data/ existe."""
    if not os.path.exists("data"):
        os.makedirs("data")
        print("Dossier 'data/' créé.")

def apply_scenario_style(gdf, criteria_column, color_hex):
    """
    Applique le style GeoJSON à un GeoDataFrame basé sur une colonne de critère.
    """
    new_gdf = gdf.copy()
    # Couleur par défaut beaucoup plus sombre et visible (Midnight Blue)
    default_stroke = '#2C3E50'
    
    new_gdf['stroke'] = default_stroke
    new_gdf['stroke-width'] = 3.0
    new_gdf['stroke-opacity'] = 0.6
    
    # Appliquer le rouge pour les rues critiques (conformément à la demande)
    mask = new_gdf[criteria_column] == True
    new_gdf.loc[mask, 'stroke'] = color_hex
    new_gdf.loc[mask, 'stroke-opacity'] = 1.0
    
    return new_gdf

def export_quartier_data(quartier_name, short_name):
    """
    Télécharge la zone (polygone) et le réseau de rues enrichi.
    Ajoute les tags spécifiques aux 3 scénarios (Sécuritaire, Social, Économique).
    Retourne (area_gdf, edges_gdf).
    """
    print(f"\n=== TRACE ET EXTRACTION : {quartier_name.upper()} ===")
    area_filtered = None
    edges_filtered = None
    
    # 1. EXTRACTION DE LA ZONE (POLYGONE EXACT)
    try:
        print(f"[{short_name}] Récupération de la limite administrative (polygone)...")
        area_gdf = ox.geocode_to_gdf(quartier_name)
        area_filtered = area_gdf[['geometry', 'display_name']].copy()
        area_filtered['quartier'] = short_name
        
    except Exception as e:
        print(f" ❌ Erreur zone pour {short_name} : {e}")

    # 2. EXTRACTION ET ENRICHISSEMENT DES RUES (GRAPH/LIGNES)
    try:
        print(f"[{short_name}] Récupération du réseau routier (drive)...")
        
        if short_name == "verdun":
            print(f"[{short_name}] Téléchargement combiné de Verdun et de l'Île des Sœurs...")
            G_main = ox.graph_from_place("Verdun, Montreal, Canada", network_type="drive")
            G_ile = ox.graph_from_place("Île des Sœurs, Montreal, Canada", network_type="drive")
            G = nx.compose(G_main, G_ile)
        else:
            G = ox.graph_from_place(quartier_name, network_type="drive")
        
        print(f"[{short_name}] Enrichissement du graphe avec les 3 axes de priorisation...")
        
        for u, v, k, data in G.edges(keys=True, data=True):
            data['length_km'] = data.get('length', 0) / 1000.0
            highway_type = data.get('highway', 'residential')
            if isinstance(highway_type, list):
                highway_type = highway_type[0]
            nom_rue = str(data.get('name', '')).lower()
            
            # AXE SÉCURITAIRE
            is_secu_infrastructure = any(mot in nom_rue for mot in ['hopital', 'hospital', 'clinique', 'sante', 'pompier'])
            is_major_axis = highway_type in ['motorway', 'trunk', 'primary']
            data['is_crit_security'] = bool(is_secu_infrastructure or is_major_axis)

            # AXE SOCIAL
            is_social_infrastructure = any(mot in nom_rue for mot in ['ecole', 'school', 'college', 'recreation', 'communautaire'])
            data['is_crit_social'] = bool(is_social_infrastructure or highway_type in ['secondary', 'tertiary'])

            # AXE ÉCONOMIQUE
            is_bus_route = data.get('bus_guideway') == 'yes' or data.get('lanes:bus') is not None
            is_commercial_axis = highway_type in ['primary', 'secondary', 'motorway', 'tertiary']
            data['is_crit_economique'] = bool(is_bus_route or is_commercial_axis or 'commercial' in nom_rue)

        _, edges_gdf = ox.graph_to_gdfs(G, nodes=True, edges=True)
        
        columns_to_keep = [
            'geometry', 'highway', 'length_km', 
            'is_crit_security', 'is_crit_social', 'is_crit_economique'
        ]
        edges_filtered = edges_gdf[columns_to_keep].copy()
        edges_filtered['quartier'] = short_name
        
    except Exception as e:
        print(f" ❌ Erreur rues pour {short_name} : {e}")

    return area_filtered, edges_filtered


if __name__ == "__main__":
    check_and_create_data_dir()
    
    quartiers_montreal = {
        "Outremont, Montreal, Canada": "outremont",
        "Verdun, Montreal, Canada": "verdun",
        "Anjou, Montreal, Canada": "anjou",
        "Rivière-des-Prairies-Pointe-aux-Trembles, Montreal, Canada": "riviere_des_prairies"
    }
    
    all_zones = []
    all_rues = []
    
    for full_name, short_name in quartiers_montreal.items():
        zone_gdf, rues_gdf = export_quartier_data(full_name, short_name)
        if zone_gdf is not None:
            all_zones.append(zone_gdf)
        if rues_gdf is not None:
            all_rues.append(rues_gdf)
            
    # 1. EXPORTATION DES ZONES (UN SEUL FICHIER)
    if all_zones:
        print("\n=== EXPORTATION CONSOLIDÉE DES ZONES ===")
        combined_zones = gpd.GeoDataFrame(gpd.pd.concat(all_zones, ignore_index=True), crs=all_zones[0].crs)
        combined_zones.to_file("data/tous_quartiers_zones.geojson", driver="GeoJSON")
        print("-> data/tous_quartiers_zones.geojson créé.")

    # 2. EXPORTATION DES RUES PAR SCÉNARIO
    if all_rues:
        print("\n=== EXPORTATION CONSOLIDÉE DES RUES PAR SCÉNARIO ===")
        combined_rues_base = gpd.GeoDataFrame(gpd.pd.concat(all_rues, ignore_index=True), crs=all_rues[0].crs)
        
        # Toutes les routes critiques en Rouge (#E74C3C) pour tous les scénarios
        scenarios = {
            "securitaire": ("is_crit_security", "#E74C3C"),
            "social": ("is_crit_social", "#E74C3C"),
            "economique": ("is_crit_economique", "#E74C3C")
        }
        
        for name, (col, color) in scenarios.items():
            print(f"Génération du scénario {name}...")
            scenario_gdf = apply_scenario_style(combined_rues_base, col, color)
            filename = f"data/tous_quartiers_rues_{name}.geojson"
            scenario_gdf.to_file(filename, driver="GeoJSON")
            print(f"-> {filename} créé.")
        
    print("\n[FIN] Tes fichiers GeoJSON sont prêts !")
