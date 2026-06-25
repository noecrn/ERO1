import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

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
from src.step7_output import build_dashboard, build_gpx, build_itinerary, _build_global_dashboard

_SCENARIO_MAP = {
    "securite":  {"p2": "securitaire", "deadline": 10, "priority_only": True,  "priority_field": "is_crit_security_social"},
    "economique": {"p2": "economique",  "deadline": 10, "priority_only": True,  "priority_field": "is_crit_economique"},
    "baseline":  {"p2": "baseline",    "deadline": 15, "priority_only": False, "priority_field": "is_crit_security_social"},
}


def run_pipeline(
    quartier: str,
    scenario: str,
    output_dir: str = "output",
) -> dict:
    if scenario not in _SCENARIO_MAP:
        raise ValueError(
            f"Scenario inconnu : {scenario!r}. "
            f"Valeurs valides : {list(_SCENARIO_MAP)}"
        )

    cfg = _SCENARIO_MAP[scenario]
    graph_path = f"data/graph_{quartier}.json"

    with warnings.catch_warnings(record=True) as scc_warns:
        warnings.simplefilter("always")
        G = load_graph(graph_path, priority_field=cfg["priority_field"])
    for w in scc_warns:
        print(f"  [adapter] {w.message}")

    nodes_p2, edges_p2 = charger_et_filtrer(graph_path, cfg["p2"])
    G_p2     = construire_graphe(nodes_p2, edges_p2)
    K_result = trouver_K_optimal(G_p2, cfg["deadline"])
    K        = K_result["K"]
    depots_raw = placer_depots(G_p2, K)

    depots = [d["noeud_id"] for d in depots_raw if d["noeud_id"] in G]
    if not depots:
        depots = [list(G.nodes())[0]]
        print(f"  [warning] Aucun depot p2 dans la grande SCC fallback sur {depots[0]}")

    print(f"  Depots ({len(depots)}) : {depots}")

    zones_raw = partition_network(G, depots)

    out_dir = Path(output_dir) / quartier / scenario
    out_dir.mkdir(parents=True, exist_ok=True)

    zone_dashboards = []

    for idx in sorted(zones_raw):
        depot = depots[idx]
        zone  = zones_raw[idx]

        zone_sc = ensure_strong_connectivity(
            zone, G, priority_only=cfg["priority_only"]
        )

        circuit, distance_km = compute_tour(zone_sc, depot)

        itinerary = build_itinerary(circuit, G)
        _write_json(out_dir / f"itineraire_zone_{idx}.json", itinerary)

        gpx_xml = build_gpx(circuit, G, track_name=f"{quartier}  {scenario}  zone {idx}")
        with open(out_dir / f"itineraire_zone_{idx}.gpx", "w", encoding="utf-8") as fh:
            fh.write(gpx_xml)

        dash = build_dashboard(idx, circuit, distance_km, zone_sc)
        _write_json(out_dir / f"dashboard_zone_{idx}.json", dash)
        zone_dashboards.append(dash)

    global_dash = _build_global_dashboard(zone_dashboards)
    _write_json(out_dir / "dashboard_global.json", global_dash)

    return global_dash


def _write_json(path: Path, data) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def _print_summary(quartier: str, scenario: str, result: dict, elapsed: float) -> None:
    print(f"\n{'='*60}")
    print(f"  Quartier : {quartier}  |  Scenario : {scenario}")
    print(f"{'='*60}")
    print(f"  Deneigeuses          : {result['nb_deneigeuses']}")
    print(f"  Distance totale      : {result['distance_totale_km']:.1f} km")
    print(f"  Cout total flotte    : {result['Z_total_flotte']:.0f} $")
    print(f"  CO2 total            : {result['CO2_total_kg']:.1f} kg")
    print(f"  Temps operation      : {result['temps_operation_h']:.2f} h")
    print(f"  Surcout reparation   : {result['surcout_reparation_total_km']:.2f} km")
    print(f"  Surcout connecteurs  : {result['surcout_connecteur_total_km']:.2f} km")
    print(f"  Temps execution      : {elapsed:.2f} s")
    print(f"{'='*60}")
    for z in result["zones"]:
        conn = z.get("surcout_connecteur_km", 0)
        rep  = z.get("surcout_reparation_km", 0)
        print(f"  Zone {z['zone_id']}: {z['distance_km']:.1f} km | "
              f"Z={z['Z_total']:.0f}$ | "
              f"conn={conn:.2f} km | rep={rep:.2f} km | dcpp={z['surcout_dcpp_km']:.2f} km")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ERO1 - Pipeline deneigement Montreal")
    parser.add_argument("--quartier", required=True,
                        choices=["anjou", "outremont", "verdun", "riviere_des_prairies"])
    parser.add_argument("--scenario", required=True,
                        choices=list(_SCENARIO_MAP))
    parser.add_argument("--output-dir", default="output")
    args = parser.parse_args()

    t0 = time.time()
    print(f"\nDemarrage : {args.quartier} / {args.scenario}")
    result = run_pipeline(args.quartier, args.scenario, args.output_dir)
    elapsed = time.time() - t0
    _print_summary(args.quartier, args.scenario, result, elapsed)
