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

## Prérequis et Installation

Assurez-vous d'avoir **Python 3.8 ou supérieur** installé.

1. **Cloner ou extraire** le projet dans le répertoire de votre choix.
2. **Ouvrir un terminal** à la racine du projet.
3. **Créer un environnement virtuel** :
   ```bash
   python -m venv venv
   ```
4. **Activer l'environnement virtuel** :
   ```bash
   source venv/bin/activate
   ```
5. **Installer les dépendances** :
   ```bash
   pip install -r requirements.txt
   ```

---

## Exécution et Démonstration

Pour lancer le pipeline d'optimisation complet (chargement, filtrage, partitionnement, routage DCPP, calcul des coûts et export) :

```bash
python main.py
```

### Étapes du pipeline exécuté :
1. **Chargement** : Lecture du graphe du réseau routier et des scénarios.
2. **Filtrage** : Application de la hauteur de neige stochastique et marquage des rues prioritaires.
3. **Optimisation** : Découpage du réseau en zones et calcul des parcours minimisant le trajet à vide.
4. **Exportation** : Génération des itinéraires et indicateurs détaillés dans le dossier `output/`.
