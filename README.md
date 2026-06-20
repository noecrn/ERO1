# Projet ERO1 - Optimisation du Déneigement à Montréal

Ce rendu contient les résultats, les données et la visualisation du projet d'Éléments de Recherche Opérationnelle (ERO1) réalisé par le Groupe 10. L'objectif était de modéliser, d'évaluer et d'optimiser le parcours de déneigement des rues de Montréal à travers différents scénarios d'intervention.

**Ce rendu ne contient pas le code source du pipeline** (algorithmes de partitionnement, DCPP/RPP, etc.) : il regroupe uniquement les données d'entrée, les résultats déjà calculés et une démo de visualisation à ouvrir dans un navigateur.

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
* **CO₂ :** 0.27 kg / km parcouru.

---

## Formalisation Mathématique

Le passage du problème réel à notre modèle algorithmique repose sur plusieurs règles et choix théoriques :

* **Modélisation du réseau :** Le réseau routier est représenté par un graphe orienté où les intersections sont les nœuds et les rues sont les arcs.
* **Algorithme de routage :** La recherche du chemin optimal s'appuie sur la logique du Problème du Postier Chinois Orienté (DCPP) — pour les scénarios couvrant un réseau connexe — et sur sa variante Postier Rural (RPP) lorsque le sous-réseau prioritaire est fragmenté en îlots déconnectés. L'objectif est de parcourir (nettoyer) tous les arcs requis au moins une fois tout en minimisant la distance totale parcourue à vide.
* **Contrainte de la neige :** L'accumulation de la neige est simulée de manière stochastique. Une rue n'est réellement comptée comme déneigée que si elle est **à la fois** prioritaire pour le scénario actif **et** couverte par une hauteur de neige comprise entre 2.5 cm et 15 cm. Un arc prioritaire hors de ce seuil reste traversable (transit) mais n'est pas compté comme déneigé.
* **Continuité du trafic (Conservation du flux) :** Tout véhicule entrant dans une intersection doit obligatoirement en ressortir.

---

## Contenu du Rendu

Ce rendu contient uniquement les éléments suivants :

- **`README.md`** : ce document.
- **`AUTHORS`** : liste des auteurs du projet.
- **`configs/`** : configurations des scénarios de priorisation (`scenarios.json`).
- **`data/`** : graphes routiers par quartier et exports géographiques utilisés en entrée du pipeline (voir détail ci-dessous).
- **`output/`** : résultats calculés — itinéraires GPS et tableaux de bord de coûts pour chaque combinaison quartier/scénario (voir détail ci-dessous).
- **`demo_visualisation.html`** : visualisation interactive (carte + animation du trajet de la déneigeuse). **À ouvrir directement dans un navigateur**, aucune installation requise.

---

## Comment consulter les résultats

1. **Visualisation interactive :** ouvrir `demo_visualisation.html` dans un navigateur (double-clic, ou clic droit → "Ouvrir avec..."). Elle charge les données de `data/` et `output/` pour afficher la carte et l'animation du trajet.
2. **Données chiffrées détaillées :** consulter directement les fichiers `.json` dans `output/{quartier}/{scenario}/` (voir structure ci-dessous).
3. **Itinéraire GPS brut :** les fichiers `.gpx` dans `output/{quartier}/{scenario}/` sont importables dans n'importe quel logiciel ou appareil GPS standard (Garmin, OsmAnd, QGIS, etc.).

---

## Détail du dossier `data/`

```
data/
├── graph_anjou.json
├── graph_outremont.json
├── graph_riviere_des_prairies.json
├── graph_verdun.json
├── infrastructures_secours.geojson      — hôpitaux, casernes, cliniques, etc.
├── reseau_rues_complet.geojson          — réseau routier complet (référence)
├── scenario_seco_social_strict.geojson  — sous-réseau prioritaire scénario sécurité/social
└── tous_quartiers_zones.geojson         — découpage des zones par dépôt, tous quartiers
```

Chaque `graph_{quartier}.json` décrit le graphe orienté du quartier : nœuds (latitude/longitude) et arcs (longueur, type de voie, flags de priorité par scénario). C'est la donnée d'entrée à partir de laquelle les résultats de `output/` ont été calculés.

---

## Détail du dossier `output/`

```
output/
└── {quartier}/
    └── {scenario}/
        ├── dashboard_global.json     — synthèse flotte (coût, CO₂, temps)
        ├── dashboard_zone_0.json     — métriques par déneigeuse
        ├── dashboard_zone_1.json
        ├── itineraire_zone_0.json    — liste ordonnée de waypoints GPS (JSON)
        ├── itineraire_zone_0.gpx     — même itinéraire au format GPX 1.1
        └── itineraire_zone_1.json
```

**Quartiers disponibles :** `anjou`, `outremont`, `verdun`, `riviere_des_prairies`
**Scénarios disponibles :** `securite`, `economique`, `baseline`

Chaque `dashboard_zone_{id}.json` distingue notamment :
- `distance_parcourue_km` : distance totale roulée par la déneigeuse (inclut les passages répétés et les arcs de réparation/connecteurs nécessaires à la connexité du circuit).
- `distance_deneigee_km` : distance réellement déneigée (arcs prioritaires et couverts de neige uniquement, comptés une seule fois).
- `Z_total`, `CO2_kg`, `temps_h`, `cout_fixe`, `cout_km`, `cout_horaire` : détail du coût selon le modèle municipal ci-dessus.

`dashboard_global.json` agrège ces métriques sur l'ensemble des déneigeuses du quartier/scénario.

---

## Limitations connues

| Limitation | Impact |
|---|---|
| Arcs hors de la plus grande composante fortement connexe du réseau écartés (bretelles, impasses) | Anjou : 16 arcs prioritaires écartés (3 %) ; Verdun : 145 (26 %) |
| Hauteur de neige (`h_neige`) parfois absente des données sources | Une rue prioritaire mais sans hauteur de neige connue n'est jamais comptée comme déneigée (seuil 2.5–15 cm non atteint par défaut) |
| Surcoût de l'algorithme de routage ~37 % sur Anjou | Le réseau prioritaire n'est pas eulérien — l'équilibrage du circuit ajoute des repassages |
| Verdun : plus grande composante connexe = 55.7 % des nœuds | Forte fragmentation due aux sens uniques du réseau — 145 arcs prioritaires perdus |