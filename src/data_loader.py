import osmnx as ox
import geopandas as gpd
import os

def check_and_create_data_dir():
    """S'assure que le dossier data/ existe."""
    if not os.path.exists("data"):
        os.makedirs("data")
        print("Dossier 'data/' créé.")

def export_quartier_data(quartier_name, short_name):
    """
    Télécharge et exporte la zone (polygone) et le réseau de rues enrichi
    pour un quartier spécifique de Montréal.
    """
    print(f"\n=== TRACE ET EXTRACTION : {quartier_name.upper()} ===")
    
    # 1. EXTRACTION ET EXPORT DE LA ZONE (POLYGONE)
    try:
        print(f"[{short_name}] Récupération de la limite administrative (polygone)...")
        area_gdf = ox.geocode_to_gdf(quartier_name)
        area_filtered = area_gdf[['geometry', 'display_name']]
        
        zone_filename = f"data/{short_name}_zone.geojson"
        area_filtered.to_file(zone_filename, driver="GeoJSON")
        print(f"-> Succès : {zone_filename} créé.")
    except Exception as e:
        print(f" Erreur lors de l'extraction de la zone pour {short_name} : {e}")

    # 2. EXTRACTION ET ENRICHISSEMENT DES RUES (GRAPH/LIGNES)
    try:
        print(f"[{short_name}] Récupération du réseau routier (drive)...")
        G = ox.graph_from_place(quartier_name, network_type="drive")
        
        print(f"[{short_name}] Enrichissement du graphe avec les règles métiers...")
        for u, v, k, data in G.edges(keys=True, data=True):
            # Distance en km (d_ij)
            data['length_km'] = data.get('length', 0) / 1000.0
            
            # Type de route
            highway_type = data.get('highway', 'residential')
            if isinstance(highway_type, list):
                highway_type = highway_type[0]
                
            # Scénario 1 : Axe Économique & Mobilité (Artères majeures)
            if highway_type in ['primary', 'secondary', 'motorway', 'tertiary']:
                data['is_crit_economique'] = True
            else:
                data['is_crit_economique'] = False
                
            # Scénario 2 : Axe Social & Sécuritaire (Voies rapides / Proximité bus)
            if highway_type in ['primary', 'secondary'] or data.get('bus_guideway') == 'yes':
                data['is_crit_securitaire'] = True
            else:
                data['is_crit_securitaire'] = False

        # Conversion des arêtes en GeoDataFrame
        _, edges_gdf = ox.graph_to_gdfs(G, nodes=True, edges=True)
        
        # Sélection des colonnes utiles pour Felt
        columns_to_keep = ['geometry', 'highway', 'length_km', 'is_crit_economique', 'is_crit_securitaire']
        
        rues_filename = f"data/{short_name}_rues.geojson"
        edges_gdf[columns_to_keep].to_file(rues_filename, driver="GeoJSON")
        print(f"-> Succès : {rues_filename} créé (Arcs E_crit et E_res taggués).")
        
    except Exception as e:
        print(f" Erreur lors de l'extraction des rues pour {short_name} : {e}")


if __name__ == "__main__":
    check_and_create_data_dir()
    
    # Dictionnaire des 4 secteurs demandés dans l'énoncé de l'AP3
    # Format : "Nom exact pour OpenStreetMap": "Nom court pour le fichier"
    quartiers_montreal = {
        "Outremont, Montreal, Canada": "outremont",
        "Verdun, Montreal, Canada": "verdun",
        "Anjou, Montreal, Canada": "anjou",
        "Rivière-des-Prairies-Pointe-aux-Trembles, Montreal, Canada": "riviere_des_prairies"
    }
    
    # Boucle d'exécution automatique
    for full_name, short_name in quartiers_montreal.items():
        export_quartier_data(full_name, short_name)
        
    print("\n Tout est prêt ! Tes 8 fichiers GeoJSON t'attendent dans le dossier data/.")