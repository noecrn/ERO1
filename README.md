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
* **Contrainte de la neige :** L'accumulation de la neige est simulée de manière stochastique. Une rue n'est intégrée dans les tâches de déneigement que si la hauteur de neige y est comprise entre 2.5 cm et 15 cm.
* **Continuité du trafic (Conservation du flux) :** Tout véhicule entrant dans une intersection doit obligatoirement en ressortir.

---

## Structure du Rendu

Le projet est structuré de manière modulaire :

- **`main.py`** : Point d'entrée principal pour lancer la démonstration complète.
- **`requirements.txt`** : Liste des dépendances Python requises.
- **`AUTHORS`** : Liste des auteurs du projet.
- **`configs/`** : Contient les configurations des scénarios de priorisation (`scenarios.json`).
- **`data/`** : Graphes routiers modélisés pour les différents quartiers (`graph_*.json`) et tracés `.geojson`.
- **`src/`** : Logique métier et algorithmique :
  - `data_loader.py` & `exporter.py` : Chargement et transformation des données géographiques.
  - `step5_partition.py` & `step5b_repair.py` : Partitionnement du réseau et garantie de forte connectivité.
  - `step6_dcpp.py` : Résolution du problème du Postier Chinois Orienté (DCPP).
  - `step7_output.py` : Calcul des indicateurs de performance, des coûts et génération des métriques de sortie.
  - `p2.py` & `p2-p3.py` : Modélisation préliminaire et recherche du nombre optimal $K$ de déneigeuses.
- **`output/`** : Résultats générés (itinéraires et tableaux de bord `.json`).
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

## Structure du rendu

```
output/
└── {quartier}/
    └── {scenario}/
        ├── dashboard_global.json     — synthèse flotte (coût, CO₂, temps)
        ├── dashboard_zone_0.json     — métriques par déneigeuse
        ├── dashboard_zone_1.json
        ├── itineraire_zone_0.json    — liste ordonnée de waypoints GPS
        └── itineraire_zone_1.json

src/
├── graph_adapter.py      — couche anti-corruption (format étapes 1-4 → pipeline)
├── run_pipeline.py       — point d'entrée CLI (étapes 5→7)
├── step5_partition.py    — partitionnement par dépôt (Dijkstra)
├── step5b_repair.py      — connexité forte + mode RPP (connecteurs)
├── step6_dcpp.py         — Postier Chinois Orienté (min-cost flow + Euler)
├── step7_output.py       — dashboard coûts, itinéraires GPS
├── p2.py                 — calcul K optimal + placement dépôts (KMeans)
├── data_loader.py        — acquisition OSMnx + annotation priorités (étapes 1-4)
└── graph_{quartier}.json — graphes pré-calculés (Anjou, Outremont, Verdun, RDP)

tests/                    — 164 tests unitaires et d'intégration
```

---

## Contrat d'interface — Format attendu en entrée (étapes 1-4)

Les collègues qui branchent leurs étapes 1-4 doivent produire un fichier
`graph_{quartier}.json` respectant ce schéma exact :

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
      "is_crit_economique": true
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

`graph_adapter.py` traduit automatiquement `length_km → weight`, `lat/lon → y/x`,
`is_crit_security_social → priority`. Tous les attributs originaux sont conservés.

---

## Limitations connues

| Limitation | Impact | Fichier concerné |
|---|---|---|
| Arcs hors grande SCC écartés (bretelles motorway, impasses) | Anjou : 16 arcs prio écartés (3 %) ; Verdun : 145 (26 %) | `graph_adapter.py` — warning émis au chargement |
| `h_neige` absent des JSON réels | Hauteur de neige non exploitée dans le routage | `data_loader.py` — non exporté par `save_graph_to_json` |
| Surcoût DCPP ~37 % sur Anjou | Le réseau prio n'est pas eulérien — l'équilibrage min-cost flow ajoute des repassages | Inhérent au DCPP sur graphes orientés non-eulériens |
| Verdun : grande SCC = 55.7 % des nœuds | Forte fragmentation due aux sens uniques OSM — 145 arcs prioritaires perdus | Structure OSM, pas un bug de fusion |

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

## Exécution complète (étapes 1-4 incluses)

Pour régénérer les graphes depuis OSMnx (nécessite une connexion internet) :

```bash
python main.py
```

### Étapes du pipeline exécuté :
1. **Chargement** : Récupération OSMnx + annotation priorités (`data_loader.py`).
2. **Optimisation K** : Calcul du nombre optimal de déneigeuses (`p2.py`).
3. **Routage** : Partitionnement, connexité, DCPP/RPP, export (`src/run_pipeline.py`).
