# Projet ERO1 - Optimisation du Déneigement à Montréal

Ce dépôt contient le code source, les configurations et les données pour le projet d'Éléments de Recherche Opérationnelle (ERO1) réalisé par le Groupe 10. L'objectif est de modéliser, d'évaluer et d'optimiser le parcours de déneigement des rues de Montréal à travers différents scénarios d'intervention.

---

## Contexte & Objectifs

Le déneigement de Montréal représente plus de 10 000 km de routes et un budget annuel d'environ 200 M$. Notre étude se focalise sur les opérations de déblaiement lors de chutes de neige allant de 2.5 cm à 15 cm.

Le but est de minimiser le coût d'exploitation des déneigeuses tout en assurant une couverture totale et prioritaire de certains réseaux selon trois scénarios prédéfinis.

---

## Définition des Scénarios de Priorisation

Le projet évalue trois stratégies d'intervention distinctes à partir de priorités géographiques et sociales :

* **Scénario 1 : Axe Sécurité et Social.** Dégagement en priorité absolue des voies permettant de sauver des vies et de rompre l'isolement (accès hôpitaux, cliniques, casernes, écoles, infrastructures PMR, résidences pour aînés).
* **Scénario 2 : Axe Économique.** Dégagement prioritaire des grands axes routiers, des voies réservées aux bus et des zones commerciales pour assurer le flux économique.
* **Scénario 3 : Baseline (Méthode globale).** Déneigement complet de l'ensemble du réseau routier sans distinction ni priorisation.

---

## Modèle de Coût (Contraintes Municipales)

Le coût opérationnel quotidien est modélisé selon les paramètres officiels de la municipalité :

* **Coût fixe :** 500 $ / jour par déneigeuse.
* **Coût kilométrique :** 1.1 $ / km parcouru.
* **Coût horaire (premières 8h) :** 1.1 $ / h.
* **Coût horaire supplémentaire (> 8h) :** 1.3 $ / h.
* **Vitesse moyenne de travail :** 10 km/h.

---

## Formalisation Mathématique

Le passage du problème réel à notre modèle algorithmique repose sur plusieurs règles et choix théoriques :

* **Modélisation du réseau :** Le réseau routier est représenté par un graphe orienté où les intersections sont les nœuds et les rues sont les arcs.
* **Algorithme de routage :** La recherche du chemin optimal s'appuie sur la logique du Problème du Postier Chinois Orienté (DCPP), l'objectif étant de parcourir (nettoyer) tous les arcs requis au moins une fois tout en minimisant la distance totale parcourue à vide.
* **Contrainte de la neige :** L'accumulation de la neige est simulée de manière stochastique. Une rue n'est réellement intégrée dans les tâches de déneigement (`needs_clearing = True`) que si elle est **à la fois** prioritaire pour le scénario actif **et** couverte par une hauteur de neige comprise entre 2.5 cm et 15 cm. Un arc prioritaire hors de ce seuil reste traversable (transit) mais n'est pas compté comme déneigé. Ce calcul est effectué par `graph_adapter.py` à partir du champ `h_neige` ; voir la limitation correspondante ci-dessous si ce champ est absent des données.
* **Continuité du trafic (Conservation du flux) :** Tout véhicule entrant dans une intersection doit obligatoirement en ressortir.

---

## Structure du Rendu

Le projet est structuré de manière modulaire :

- **`main.py`** : Point d'entrée principal pour lancer la démonstration complète.
- **`fixtures.py`** : Graphe fictif (~18 intersections, format Plateau-Mont-Royal/Rosemont) utilisé en interne par `step7_output.py` pour une démo rapide du pipeline sans données géographiques réelles. À remplacer/ignorer une fois `data/` disponible.
- **`demo_visualisation.html`** : Visualisation interactive (carte + animation du trajet de la déneigeuse), à ouvrir directement dans un navigateur.
- **`requirements.txt`** : Liste des dépendances Python requises.
- **`AUTHORS`** : Liste des auteurs du projet.
- **`configs/`** : Contient les configurations des scénarios de priorisation (`scenarios.json`).
- **`data/`** : Graphes par quartier (`graph_{quartier}.json`) et exports GeoJSON intermédiaires (`infrastructures_secours.geojson`, `reseau_rues_complet.geojson`, `scenario_seco_social_strict.geojson`, `tous_quartiers_zones.geojson`) utilisés pour peupler le sélecteur de quartier de la démo. Régénéré par `python main.py --refresh-data` (nécessite une connexion internet pour interroger OSM) ; sinon les fichiers déjà présents sont utilisés tels quels. **C'est ce dossier — et non plus `src/`** — que lit `run_pipeline.py` pour charger un graphe.
- **`src/`** : Logique métier et algorithmique :
  - `data_loader.py` & `exporter.py` : Chargement et transformation des données géographiques.
  - `graph_adapter.py` : Couche anti-corruption entre `data/graph_{quartier}.json` et le pipeline interne ; calcule notamment `needs_clearing` (priorité **et** seuil de neige 2.5–15 cm) et restreint le graphe à sa plus grande composante fortement connexe.
  - `step5_partition.py` & `step5b_repair.py` : Partitionnement du réseau et garantie de forte connectivité (mode CPP classique via arcs `repair=True`, ou mode RPP via arcs `connector=True` greffés autour des seuls arcs `needs_clearing=True`).
  - `step6_dcpp.py` : Résolution du problème du Postier Chinois Orienté (DCPP).
  - `step7_output.py` : Calcul des indicateurs de performance, des coûts, génération des itinéraires GPS (JSON) et des traces GPX.
  - `p2.py` : Modélisation préliminaire et recherche du nombre optimal $K$ de déneigeuses.
- **`output/`** : Résultats générés (itinéraires JSON/GPX et tableaux de bord `.json`).
- **`tests/`** : Tests unitaires et d'intégration pour chaque étape critique du pipeline.
- **`cache/`** : Données géographiques temporaires mises en cache pour accélérer les calculs.

---

## Installation

Assurez-vous d'avoir **Python 3.10 ou supérieur** installé.

```bash
# Cloner le dépôt et se placer à la racine
python -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate
pip install -r requirements.txt
```

---

## Utilisation — Pipeline déneigement (étapes 5 → 7)

```bash
# Scénario Sécurité & Social (Rural Postman Problem)
python src/run_pipeline.py --quartier anjou --scenario securite

# Scénario Économique (Chinese Postman Problem)
python src/run_pipeline.py --quartier anjou --scenario economique

# Scénario Baseline — réseau complet
python src/run_pipeline.py --quartier anjou --scenario baseline
```

**Quartiers disponibles :** `anjou`, `outremont`, `verdun`, `riviere_des_prairies`

Les fichiers sont écrits dans `output/{quartier}/{scenario}/`.

---

## Détail des fichiers générés et du code (étapes 5-7)

```
output/
└── {quartier}/
    └── {scenario}/
        ├── dashboard_global.json     — synthèse flotte (coût, CO₂, temps)
        ├── dashboard_zone_0.json     — métriques par déneigeuse
        ├── dashboard_zone_1.json
        ├── itineraire_zone_0.json    — liste ordonnée de waypoints GPS (JSON interne)
        ├── itineraire_zone_0.gpx     — même itinéraire au format GPX 1.1 (GPS/QGIS/Garmin/OsmAnd)
        └── itineraire_zone_1.json

src/
├── graph_adapter.py      — couche anti-corruption (data/graph_{quartier}.json → pipeline) ;
│                           calcule needs_clearing (priorité + seuil de neige) et restreint
│                           le graphe à sa plus grande SCC
├── run_pipeline.py       — point d'entrée CLI (étapes 5→7), lit data/graph_{quartier}.json
├── step5_partition.py    — partitionnement par dépôt (Dijkstra)
├── step5b_repair.py      — connexité forte ; mode CPP (repair=True) ou RPP sur les seuls
│                           arcs needs_clearing=True (connector=True)
├── step6_dcpp.py         — Postier Chinois Orienté (min-cost flow + Euler)
├── step7_output.py       — dashboard coûts, itinéraires GPS + export GPX
├── p2.py                 — calcul K optimal + placement dépôts (KMeans)
└── data_loader.py        — acquisition OSMnx + annotation priorités (étapes 1-4)

fixtures.py                — graphe fictif (~18 nœuds) pour la démo interne de step7_output.py

tests/                    — 164 tests unitaires et d'intégration
```

Chaque dashboard de zone distingue désormais :
- `distance_parcourue_km` : distance totale roulée par la déneigeuse (inclut les passages DCPP répétés et les arcs de réparation/connecteurs).
- `distance_deneigee_km` : distance réellement déneigée (arcs requis uniquement, comptés une seule fois, hors connecteurs/réparations).
- `distance_km` : alias rétro-compatible de `distance_parcourue_km`.

Les coûts ($Z$) et le CO₂ restent calculés sur la distance **parcourue**, conformément au modèle de facturation municipal.

---

## Contrat d'interface — Format attendu en entrée (étapes 1-4)

Les collègues qui branchent leurs étapes 1-4 doivent produire un fichier
`data/graph_{quartier}.json` (et non plus `src/graph_{quartier}.json`) respectant ce schéma exact :

```json
{
  "quartier": "anjou",
  "nodes": {
    "<osmid>": { "lat": 45.6234, "lon": -73.5841 }
  },
  "edges": [
    {
      "source": "<osmid>",
      "target": "<osmid>",
      "key": 0,
      "length_km": 0.277,
      "highway": "primary",
      "is_crit_security_social": true,
      "is_crit_economique": true,
      "h_neige": 8.3
    }
  ]
}
```

**Attributs obligatoires :**

| Champ | Type | Description |
|-------|------|-------------|
| `nodes[id].lat` | float | Latitude (WGS84) |
| `nodes[id].lon` | float | Longitude (WGS84) |
| `edges[].source` / `target` | string | OSM node IDs |
| `edges[].length_km` | float > 0 | Longueur du segment en km |
| `edges[].is_crit_security_social` | bool | Vrai si l'arc est prioritaire scénario sécurité |
| `edges[].is_crit_economique` | bool | Vrai si l'arc est prioritaire scénario économique |

**Attribut optionnel (mais requis pour le mode RPP) :**

| Champ | Type | Description |
|-------|------|-------------|
| `edges[].h_neige` | float | Hauteur de neige simulée en cm. **Absent ⇒ traité comme 0.0**, donc hors du seuil 2.5–15 cm : l'arc ne sera jamais marqué `needs_clearing=True` même s'il est prioritaire. |

`graph_adapter.py` traduit automatiquement `length_km → weight`, `lat/lon → y/x`,
`is_crit_security_social` **ou** `is_crit_economique` (selon `priority_field`) `→ priority`,
puis `priority + h_neige → needs_clearing`. Tous les attributs originaux sont conservés.

---

## Limitations connues

| Limitation | Impact | Fichier concerné |
|---|---|---|
| Arcs hors grande SCC écartés (bretelles motorway, impasses) | Anjou : 16 arcs prio écartés (3 %) ; Verdun : 145 (26 %) | `graph_adapter.py` — warning émis au chargement |
| `h_neige` absent des JSON réels (`data/graph_{quartier}.json`) | `needs_clearing` retombe systématiquement à `False` (défaut 0.0 cm, hors seuil 2.5–15 cm) même pour les arcs prioritaires → en mode RPP (scénario sécurité/économique), `step5b_repair.py` peut lever `ValueError: aucun arc à déneiger` si aucun arc ne passe le seuil | `graph_adapter.py` (calcul), `data_loader.py` (champ non exporté), `step5b_repair.py` (consommateur) |
| Surcoût DCPP ~37 % sur Anjou | Le réseau prio n'est pas eulérien — l'équilibrage min-cost flow ajoute des repassages | Inhérent au DCPP sur graphes orientés non-eulériens |
| Verdun : grande SCC = 55.7 % des nœuds | Forte fragmentation due aux sens uniques OSM — 145 arcs prioritaires perdus | Structure OSM, pas un bug de fusion |
| `fixtures.py` utilisé uniquement par la démo interne de `step7_output.py` | Ne reflète pas les quartiers réels ; à ignorer une fois `data/` peuplé via `--refresh-data` | `fixtures.py`, `step7_output.run_pipeline()` |

---

## Prérequis et Installation (version complète)

Assurez-vous d'avoir **Python 3.10 ou supérieur** installé.

1. **Cloner ou extraire** le projet dans le répertoire de votre choix.
2. **Ouvrir un terminal** à la racine du projet.
3. **Créer un environnement virtuel** :
   ```bash
   python -m venv .venv
   ```
4. **Activer l'environnement virtuel** :
   ```bash
   source .venv/bin/activate
   ```
5. **Installer les dépendances** :
   ```bash
   pip install -r requirements.txt
   ```

---

## Exécution complète — démo unique (4 quartiers × 3 scénarios)

`main.py` est le point d'entrée unique qui enchaîne le pipeline complet
(P2 : K optimal + dépôts, puis P3 : partition, connexité, DCPP/RPP, export)
sur les 4 quartiers et les 3 scénarios :

```bash
python main.py
```

Options disponibles pour limiter ou affiner l'exécution :

```bash
python main.py --quartier anjou                      # un seul quartier, 3 scénarios
python main.py --quartier anjou --scenario baseline   # une seule combinaison
python main.py --refresh-data                         # régénère les graphes via OSMnx avant (nécessite internet)
```

### Étapes du pipeline exécuté pour chaque combinaison quartier/scénario :
1. **Chargement du graphe** : lecture de `data/graph_{quartier}.json`, restriction à la plus grande composante fortement connexe (`graph_adapter.py`).
2. **Optimisation K** : calcul du nombre optimal de déneigeuses et placement des dépôts (`p2.py`).
3. **Routage** : partitionnement par dépôt, garantie de connexité, résolution DCPP/RPP, export GPS (JSON + GPX) et dashboard de coûts (`src/run_pipeline.py`, étapes 5→7).

Les résultats sont écrits dans `output/{quartier}/{scenario}/`.

Par défaut, `main.py` n'appelle **pas** la régénération OSMnx (étapes 1-4) :
les graphes déjà présents dans `data/graph_{quartier}.json` sont utilisés
directement, pour une démo rapide et sans dépendance réseau. Utiliser
`--refresh-data` uniquement si vous souhaitez re-extraire les données depuis
OpenStreetMap (régénère `data/`).