import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

"""
Script de démo exécutable — Pipeline complet étapes 5→7 sur un quartier réel.

Utilisation :
    python src/run_pipeline.py --quartier anjou --scenario securite
    python src/run_pipeline.py --quartier anjou --scenario economique

Scénarios supportés
-------------------
securite   : Rural Postman Problem — couvre uniquement les arcs is_crit_security_social,
             connecteurs non-prioritaires greffés pour relier les îlots.
economique : Chinese Postman Problem — couvre tous les arcs is_crit_economique.
baseline   : Chinese Postman Problem — couvre l'intégralité du réseau.

Dépendances d'entrée (format attendu des collègues étapes 1-4)
--------------------------------------------------------------
graph_{quartier}.json avec :
  edges : source, target, length_km (float), is_crit_security_social (bool),
          is_crit_economique (bool), highway (str)
  nodes : lat (float), lon (float)
"""

import argparse
import json
import time
import warnings
from pathlib import Path

from src.graph_adapter import load_graph
from src.p2 import charger_et_filtrer, construire_graphe, trouver_K_optimal, placer_depots
from src.step5_partition import partition_network
from src.step5b_repair import ensure_strong_connectivity
from src.step6_dcpp import compute_tour
from src.step7_output import build_dashboard, build_itinerary, _build_global_dashboard

# Mapping CLI scenario → p2 scenario name + deadline + RPP flag
_SCENARIO_MAP = {
    "securite":  {"p2": "securitaire", "deadline": 10, "priority_only": True},
    "economique": {"p2": "economique",  "deadline": 10, "priority_only": False},
    "baseline":  {"p2": "baseline",    "deadline": 15, "priority_only": False},
}


def run_pipeline(
    quartier: str,
    scenario: str,
    output_dir: str = "output",
) -> dict:
    """
    Exécute le pipeline complet (étapes 5→7) pour un quartier et un scénario.

    Parameters
    ----------
    quartier   : nom du quartier (ex. "anjou", "verdun").
    scenario   : "securite", "economique" ou "baseline".
    output_dir : répertoire racine de sortie. Les fichiers sont écrits dans
                 {output_dir}/{quartier}/{scenario}/.

    Returns
    -------
    dict global dashboard (mêmes clés que _build_global_dashboard).
    """
    if scenario not in _SCENARIO_MAP:
        raise ValueError(
            f"Scénario inconnu : {scenario!r}. "
            f"Valeurs valides : {list(_SCENARIO_MAP)}"
        )

    cfg = _SCENARIO_MAP[scenario]
    graph_path = f"src/graph_{quartier}.json"

    # ── Étape A : chargement du graphe (restriction grande SCC) ──────────────
    with warnings.catch_warnings(record=True) as scc_warns:
        warnings.simplefilter("always")
        G = load_graph(graph_path)
    for w in scc_warns:
        print(f"  [adapter] {w.message}")

    # ── Étape B : dépôts via p2 ───────────────────────────────────────────────
    nodes_p2, edges_p2 = charger_et_filtrer(graph_path, cfg["p2"])
    G_p2     = construire_graphe(nodes_p2, edges_p2)
    K_result = trouver_K_optimal(G_p2, cfg["deadline"])
    K        = K_result["K"]
    depots_raw = placer_depots(G_p2, K)

    # Convertir en liste de node IDs (strings) présents dans G
    depots = [d["noeud_id"] for d in depots_raw if d["noeud_id"] in G]
    if not depots:
        # Fallback : premier nœud du graphe
        depots = [list(G.nodes())[0]]
        print(f"  [warning] Aucun dépôt p2 dans la grande SCC — fallback sur {depots[0]}")

    print(f"  Dépôts ({len(depots)}) : {depots}")

    # ── Étape 5 : partition ───────────────────────────────────────────────────
    zones_raw = partition_network(G, depots)

    # ── Étapes 5b + 6 + 7 par zone ───────────────────────────────────────────
    out_dir = Path(output_dir) / quartier / scenario
    out_dir.mkdir(parents=True, exist_ok=True)

    zone_dashboards = []

    for idx in sorted(zones_raw):
        depot = depots[idx]
        zone  = zones_raw[idx]

        # 5b
        zone_sc = ensure_strong_connectivity(
            zone, G, priority_only=cfg["priority_only"]
        )

        # 6
        circuit, distance_km = compute_tour(zone_sc, depot)

        # 7 — itinéraire
        itinerary = build_itinerary(circuit, G)
        _write_json(out_dir / f"itineraire_zone_{idx}.json", itinerary)

        # 7 — dashboard de zone
        dash = build_dashboard(idx, circuit, distance_km, zone_sc)
        _write_json(out_dir / f"dashboard_zone_{idx}.json", dash)
        zone_dashboards.append(dash)

    # Dashboard global
    global_dash = _build_global_dashboard(zone_dashboards)
    _write_json(out_dir / "dashboard_global.json", global_dash)

    return global_dash


def _write_json(path: Path, data) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def _print_summary(quartier: str, scenario: str, result: dict, elapsed: float) -> None:
    print(f"\n{'='*60}")
    print(f"  Quartier : {quartier}  |  Scénario : {scenario}")
    print(f"{'='*60}")
    print(f"  Déneigeuses          : {result['nb_deneigeuses']}")
    print(f"  Distance totale      : {result['distance_totale_km']:.1f} km")
    print(f"  Coût total flotte    : {result['Z_total_flotte']:.0f} $")
    print(f"  CO₂ total            : {result['CO2_total_kg']:.1f} kg")
    print(f"  Temps opération      : {result['temps_operation_h']:.2f} h")
    print(f"  Surcoût réparation   : {result['surcout_reparation_total_km']:.2f} km")
    print(f"  Surcoût connecteurs  : {result['surcout_connecteur_total_km']:.2f} km")
    print(f"  Temps exécution      : {elapsed:.2f} s")
    print(f"{'='*60}")
    for z in result["zones"]:
        conn = z.get("surcout_connecteur_km", 0)
        rep  = z.get("surcout_reparation_km", 0)
        print(f"  Zone {z['zone_id']}: {z['distance_km']:.1f} km | "
              f"Z={z['Z_total']:.0f}$ | "
              f"conn={conn:.2f} km | rep={rep:.2f} km | dcpp={z['surcout_dcpp_km']:.2f} km")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ERO1 — Pipeline déneigement Montréal")
    parser.add_argument("--quartier", required=True,
                        choices=["anjou", "outremont", "verdun", "riviere_des_prairies"])
    parser.add_argument("--scenario", required=True,
                        choices=list(_SCENARIO_MAP))
    parser.add_argument("--output-dir", default="output")
    args = parser.parse_args()

    t0 = time.time()
    print(f"\nDémarrage : {args.quartier} / {args.scenario}")
    result = run_pipeline(args.quartier, args.scenario, args.output_dir)
    elapsed = time.time() - t0
    _print_summary(args.quartier, args.scenario, result, elapsed)
