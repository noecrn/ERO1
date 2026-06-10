# Projet ERO1 : Optimisation Hivernale - Ville de Montréal

## Contexte du projet

**Objectif principal :** Résoudre un problème d'optimisation de tournées (variante du problème du Postier Chinois / *Chinese Postman Problem*) pour le déneigement des rues de Montréal (secteurs : Outremont, Verdun, Anjou, Rivière-des-prairies-pointe-aux-trembles).
Le but est de minimiser le coût de déblaiement (basé sur un modèle de coût horaire et kilométrique) tout en respectant **trois scénarios de priorisation** (Économique, Social, Sécuritaire).

---

## Définition des Scénarios de Priorisation

Le projet évalue trois stratégies d'intervention distinctes. L'algorithme reste mathématiquement identique pour chaque scénario ; c'est uniquement le fichier de configuration (l'input) qui modifie le comportement de l'optimisation.

* **Scénario 1 : Axe Sécurité et Social.** Dégagement en priorité absolue des voies permettant de sauver des vies et de rompre l'isolement (hôpitaux, cliniques, casernes, écoles, infrastructures PMR).
* **Scénario 2 : Axe Économique.** Dégagement prioritaire des grands axes et des voies de transport en commun pour assurer la continuité du trafic commercial. Ce scénario offre une flexibilité financière à la ville en acceptant que certaines zones purement résidentielles soient traitées ultérieurement.
* **Scénario 3 : Baseline (Méthode globale).** Modélisation d'un déneigement complet de l'ensemble du graphe routier sans priorisation. Ce scénario sert d'étalon de mesure pour valider l'efficacité brute de l'algorithme sur un réseau étendu.

---

## Formalisation Mathématique

Le passage du monde réel à notre modèle algorithmique repose sur plusieurs règles et contraintes strictes :

* **Modélisation du réseau :** Le réseau routier est représenté sous la forme d'un graphe mathématique où les intersections sont les nœuds et les rues sont les arcs.
* **Choix de l'algorithme :** Le problème repose sur la logique du Problème du Postier Chinois (CPP), car l'objectif est de nettoyer l'intégralité des arcs (rues) et non de simplement visiter des points (nœuds).
* **Contrainte de la neige :** L'accumulation de la neige est générée de manière stochastique. Une rue ne peut être intégrée au parcours de déneigement que si la hauteur de neige est comprise entre 2,5 cm et 15 cm.
* **Couverture obligatoire :** Toutes les routes identifiées comme prioritaires dans le fichier de configuration du scénario doivent être parcourues au moins une fois par une déneigeuse.
* **Continuité du trafic :** Si une déneigeuse entre dans une intersection, elle doit obligatoirement en sortir. Aucune "téléportation" de véhicule n'est autorisée d'un point à un autre de la ville.

---

## Architecture et Flux de données (Data Flow)

Le projet est divisé en 3 phases distinctes :

### 1. Phase d'Acquisition (Module : `src/data_loader.py`)

**Action :** Requête l'API OpenStreetMap (via `osmnx`) pour récupérer les graphes routiers et les Points d'Intérêt (hôpitaux, écoles, etc.).
**Inputs :** Noms des quartiers en dur dans le script.
**Outputs :**
* `data/scenario_*.geojson` : Tracés des rues par scénario.
* `data/infrastructures_secours.geojson` : Points d'intérêt (hôpitaux, casernes) séparés.
* `data/tous_quartiers_zones.geojson` : Limites administratives.
**Logique métier :** Le script enrichit chaque arête (rue) avec des booléens de priorité et préserve la topologie du graphe (nœuds source `u` et cible `v`).

### 2. Phase de Transformation RO (Module : `src/exporter.py`)

**Action :** Convertit les données géographiques brutes en une structure mathématique de graphe exploitable par nos algorithmes de Recherche Opérationnelle (RO).
**Inputs :** `data/scenario_economique.geojson` (utilisé pour la structure du réseau).
**Outputs :** `data/reseau_arcs_ro.json`
**Schéma de données généré (Crucial pour les solvers) :**

```json
{
  "id_arc": "int",
  "noeud_source": "int",
  "noeud_cible": "int",
  "quartier": "string",
  "type_route": "string",
  "distance_km": "float",
  "priorites": {
    "securitaire": "bool",
    "social": "bool",
    "economique": "bool"
  }
}

```

### 3. Phase d'Optimisation et Calculs (Modules : `src/solvers.py`, `src/metrics.py`, `main.py`)

**Action :** Charge le graphe RO, applique les algorithmes de parcours (Eulerien/Postier Chinois) pour minimiser les distances à vide, et calcule les coûts financiers.
**Inputs :** `data/reseau_arcs_ro.json` + fichiers de configuration dans `configs/`.
**Outputs :** Résultats dans la console, itinéraires générés et métriques d'évaluation.

---

## Structure du Rendu

```text
.
├── AUTHORS                     # Liste des auteurs (noe.cornu, clara.verrier, etc.)
├── README.md                   # Documentation actuelle
├── cache/                      # Fichiers de cache générés par OSMnx
├── configs/                    # Configurations des paramètres pour les 3 scénarios
│   ├── scenario_economique.json
│   ├── scenario_securitaire.json
│   └── scenario_social.json
├── data/                       # [INPUTS/OUTPUTS] Données générées et formatées
│   ├── reseau_arcs_ro.json          # [INPUT SOLVER] Graphe modélisé pour la RO
│   ├── scenario_*.geojson           # Tracés cartographiques des scénarios
│   ├── infrastructures_secours.geojson # POIs (Hôpitaux, casernes)
│   └── tous_quartiers_zones.geojson # Limites géographiques des quartiers
├── demo_visualisation.ipynb    # Notebook d'analyse et de visualisation
├── main.py                     # [ENTRY POINT] Script principal de la démonstration
├── requirements.txt            # Dépendances (osmnx, geopandas, networkx, etc.)
└── src/                        # [SOURCE CODE] Logique métier
    ├── __init__.py
    ├── data_loader.py          # [ETL] Récupération OSM -> GeoJSON
    ├── exporter.py             # [ETL] GeoJSON -> JSON RO
    ├── metrics.py              # Calcul des coûts (fixe, km, horaire) et KPIs
    ├── solvers.py              # Algorithmes RO (Postier Chinois, Euler)
    └── weather.py              # Facteurs météo (neige 2.5cm à 15cm)

```

---

## Modèle de Coût (Contraintes Métier)

Lors des calculs dans `metrics.py` ou `solvers.py`, le programme applique les données officielles fournies par la municipalité :

* **Coût fixe :** 500 $/jour par déneigeuse.
* **Coût kilométrique :** 1.1 $/km.
* **Coût horaire (<= 8h) :** 1.1 $/h.
* **Coût horaire (> 8h) :** 1.3 $/h.
* **Vitesse moyenne :** 10 km/h.

---

## Instructions d'exécution

**1. Installation des dépendances**

```bash
pip install -r requirements.txt

```

**2. Génération du jeu de données (Data Pipeline)**
Si le dossier `data/` est vide ou obsolète, regénérer les données spatiales et le graphe de RO :

```bash
python src/data_loader.py
python src/exporter.py

```

**3. Lancement de la résolution globale**

```bash
python main.py

```