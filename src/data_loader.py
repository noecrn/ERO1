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
    
    # Appliquer le rouge pour les rues critiques
    mask = new_gdf[criteria_column] == True
    new_gdf.loc[mask, 'stroke'] = color_hex
    new_gdf.loc[mask, 'stroke-opacity'] = 1.0
    
    return new_gdf

def export_quartier_data(quartier_name, short_name):
    """
    Télécharge la zone, le réseau de rues et les POIs de sécurité.
    """
    print(f"\n=== TRACE ET EXTRACTION : {quartier_name.upper()} ===")
    area_filtered = None
    edges_filtered = None
    pois_filtered = None
    
    # 1. ZONE (POLYGONE)
    try:
        print(f"[{short_name}] Récupération de la limite administrative...")
        area_gdf = ox.geocode_to_gdf(quartier_name)
        area_filtered = area_gdf[['geometry', 'display_name']].copy()
        area_filtered['quartier'] = short_name
    except Exception as e:
        print(f" ❌ Erreur zone : {e}")

    # 2. RUES (GRAPH)
    try:
        print(f"[{short_name}] Récupération du réseau routier...")
        if short_name == "verdun":
            G_main = ox.graph_from_place("Verdun, Montreal, Canada", network_type="drive")
            G_ile = ox.graph_from_place("Île des Sœurs, Montreal, Canada", network_type="drive")
            G = nx.compose(G_main, G_ile)
        else:
            G = ox.graph_from_place(quartier_name, network_type="drive")
        
        for u, v, k, data in G.edges(keys=True, data=True):
            data['length_km'] = data.get('length', 0) / 1000.0
            highway_type = data.get('highway', 'residential')
            if isinstance(highway_type, list): highway_type = highway_type[0]
            nom_rue = str(data.get('name', '')).lower()
            
            # AXES CRITIQUES
            is_secu_infra = any(mot in nom_rue for mot in ['hopital', 'hospital', 'clinique', 'sante', 'pompier'])
            is_major = highway_type in ['motorway', 'trunk', 'primary']
            data['is_crit_security'] = bool(is_secu_infra or is_major)

            data['is_crit_social'] = bool(any(mot in nom_rue for mot in ['ecole', 'school', 'college']) or highway_type in ['secondary', 'tertiary'])

            is_bus = data.get('bus_guideway') == 'yes' or data.get('lanes:bus') is not None
            data['is_crit_economique'] = bool(is_bus or highway_type in ['primary', 'secondary', 'motorway'] or 'commercial' in nom_rue)

        _, edges_gdf = ox.graph_to_gdfs(G, nodes=True, edges=True)
        cols = ['geometry', 'highway', 'length_km', 'is_crit_security', 'is_crit_social', 'is_crit_economique']
        edges_filtered = edges_gdf[cols].copy()
        edges_filtered['quartier'] = short_name
    except Exception as e:
        print(f" ❌ Erreur rues : {e}")

    # 3. POINTS D'INTÉRÊT (POIs) - SECURITE
    try:
        print(f"[{short_name}] Récupération des infrastructures de secours (points)...")
        tags = {
            'amenity': ['hospital', 'fire_station', 'clinic', 'police', 'doctors'],
            'healthcare': True
        }
        if short_name == "verdun":
            p1 = ox.features_from_place("Verdun, Montreal, Canada", tags=tags)
            p2 = ox.features_from_place("Île des Sœurs, Montreal, Canada", tags=tags)
            pois = gpd.pd.concat([p1, p2])
        else:
            pois = ox.features_from_place(quartier_name, tags=tags)
        
        if not pois.empty:
            # On ne garde que les points (pour éviter les gros polygones de bâtiments)
            pois = pois[pois.geometry.type == 'Point'].copy()
            if not pois.empty:
                pois['marker-color'] = '#E74C3C'
                pois['marker-size'] = 'medium'
                pois['marker-symbol'] = 'hospital'
                # Nettoyage colonnes
                if 'name' not in pois.columns: pois['name'] = "Inconnu"
                pois_filtered = pois[['geometry', 'name', 'marker-color', 'marker-size', 'marker-symbol']].copy()
                pois_filtered['quartier'] = short_name
                pois_filtered['type'] = "infrastructure_secours"
    except Exception as e:
        print(f" ⚠️ Aucun point de sécurité trouvé pour {short_name}")

    return area_filtered, edges_filtered, pois_filtered

if __name__ == "__main__":
    check_and_create_data_dir()
    
    quartiers = {
        "Outremont, Montreal, Canada": "outremont",
        "Verdun, Montreal, Canada": "verdun",
        "Anjou, Montreal, Canada": "anjou",
        "Rivière-des-Prairies-Pointe-aux-Trembles, Montreal, Canada": "riviere_des_prairies"
    }
    
    all_z, all_r, all_p = [], [], []
    
    for full, short in quartiers.items():
        z, r, p = export_quartier_data(full, short)
        if z is not None: all_z.append(z)
        if r is not None: all_r.append(r)
        if p is not None: all_p.append(p)
            
    # EXPORT ZONES
    if all_z:
        gpd.GeoDataFrame(gpd.pd.concat(all_z, ignore_index=True), crs=all_z[0].crs).to_file("data/tous_quartiers_zones.geojson", driver="GeoJSON")

    # EXPORT RUES ET POIS
    if all_r:
        combined_r = gpd.GeoDataFrame(gpd.pd.concat(all_r, ignore_index=True), crs=all_r[0].crs)
        
        # Scénarios standards
        for sc, col in [("social", "is_crit_social"), ("economique", "is_crit_economique")]:
            apply_scenario_style(combined_r, col, "#E74C3C").to_file(f"data/tous_quartiers_rues_{sc}.geojson", driver="GeoJSON")
        
        # Scénario Sécurité (Rues + Points)
        print("Fusion des rues et des points pour le scénario Sécurité...")
        secu_rues = apply_scenario_style(combined_r, "is_crit_security", "#E74C3C")
        if all_p:
            combined_p = gpd.GeoDataFrame(gpd.pd.concat(all_p, ignore_index=True), crs=all_p[0].crs)
            # Fusion des types de géométrie (Lignes + Points) dans le même GeoJSON
            final_secu = gpd.GeoDataFrame(gpd.pd.concat([secu_rues, combined_p], ignore_index=True), crs=secu_rues.crs)
            final_secu.to_file("data/tous_quartiers_rues_securitaire.geojson", driver="GeoJSON")
        else:
            secu_rues.to_file("data/tous_quartiers_rues_securitaire.geojson", driver="GeoJSON")
        
    print("\n[FIN] Tes fichiers GeoJSON (incluant les points de secours) sont prêts !")
