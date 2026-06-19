"""
Step 7 — GPS itineraries and cost dashboard.

Billing conventions (fixed, do not alter):
  speed          : 10 km/h
  time           : T = distance_km / 10  (hours)
  hourly cost    : 1.1 * min(T, 8) + 1.3 * max(0, T - 8)
  fixed cost     : 500 $ per snowplow (one per zone)
  per-km cost    : 1.1 $ / km
  zone total     : Z = 500 + 1.1 * distance_km + hourly_cost
  CO2            : 0.27 * distance_km  (kg)
  billed distance: full tour distance (DCPP repeats + repair arcs included)
"""

import json
from collections import Counter
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, ElementTree

import networkx as nx

from fixtures import make_mock_graph
from src.step5_partition import partition_network
from src.step5b_repair import ensure_strong_connectivity
from src.step6_dcpp import compute_tour


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def build_itinerary(circuit: list, G: nx.DiGraph) -> list:
    """
    Convert an ordered arc list into an ordered GPS waypoint list.

    Each waypoint is {"lat": float, "lon": float}, read from node attributes
    y (latitude) and x (longitude).  The list length is len(circuit) + 1:
    one point per arc-start plus the final destination of the last arc.

    Parameters
    ----------
    circuit : ordered list of (u, v) arcs, as returned by compute_tour.
    G       : any DiGraph that contains all nodes in the circuit with x/y attrs.

    Returns
    -------
    list of {"lat": ..., "lon": ...} dicts, ready for a navigation system.
    """
    if not circuit:
        return []

    waypoints = []
    for u, v in circuit:
        waypoints.append({"lat": G.nodes[u]["y"], "lon": G.nodes[u]["x"]})
    # Append the final destination (last arc's target).
    last_v = circuit[-1][1]
    waypoints.append({"lat": G.nodes[last_v]["y"], "lon": G.nodes[last_v]["x"]})
    return waypoints


def build_gpx(circuit: list, G: nx.DiGraph, track_name: str = "Itinéraire déneigeuse") -> str:
    """
    Convert an ordered arc list into a standard GPX 1.1 track (<trk>/<trkseg>/<trkpt>),
    importable by any GPS device or mapping software (Garmin, OsmAnd, QGIS, etc.).

    Parameters
    ----------
    circuit    : ordered list of (u, v) arcs, as returned by compute_tour.
    G          : any DiGraph containing all nodes in the circuit with x/y attrs.
    track_name : <name> shown by the GPS device/software for this track.

    Returns
    -------
    GPX 1.1 XML document as a string (UTF-8, includes XML declaration).
    """
    gpx = Element("gpx", {
        "version": "1.1",
        "creator": "ERO1",
        "xmlns": "http://www.topografix.com/GPX/1/1",
    })
    trk = SubElement(gpx, "trk")
    SubElement(trk, "name").text = track_name
    trkseg = SubElement(trk, "trkseg")

    waypoints = build_itinerary(circuit, G)
    for wp in waypoints:
        SubElement(trkseg, "trkpt", {"lat": str(wp["lat"]), "lon": str(wp["lon"])})

    from xml.dom import minidom
    rough = ElementTree(gpx)
    import io
    buf = io.BytesIO()
    rough.write(buf, encoding="utf-8", xml_declaration=True)
    return minidom.parseString(buf.getvalue()).toprettyxml(indent="  ")


def build_dashboard(
    zone_id: int,
    circuit: list,
    distance_km: float,
    G: nx.DiGraph,
) -> dict:
    """
    Compute cost metrics for one snowplow zone.

    Le mode est détecté automatiquement depuis les attributs d'arcs de G :
    - Mode CPP (arcs repair=True présents)    → clé surcout_reparation_km
    - Mode RPP (arcs connector=True présents) → clé surcout_connecteur_km
    Les deux modes sont mutuellement exclusifs dans la clé de surcoût retournée.
    surcout_dcpp_km est présent dans les deux modes.

    Parameters
    ----------
    zone_id     : integer zone index (0-based, matching partition_network keys).
    circuit     : ordered arc list from compute_tour (on the zone DiGraph).
    distance_km : total tour distance returned by compute_tour.
    G           : zone DiGraph avec arcs repair=True (CPP) ou connector=True (RPP).

    Returns
    -------
    dict avec les clés communes :
        zone_id, distance_km, temps_h, cout_fixe, cout_km, cout_horaire,
        Z_total, CO2_kg, surcout_dcpp_km
    + en mode CPP : surcout_reparation_km
    + en mode RPP : surcout_connecteur_km
    """
    T = distance_km / 10.0
    cout_horaire = 1.1 * min(T, 8.0) + 1.3 * max(0.0, T - 8.0)
    cout_fixe    = 500.0
    cout_km      = 1.1 * distance_km
    Z_total      = cout_fixe + cout_km + cout_horaire
    CO2_kg       = 0.27 * distance_km

    # DCPP extra km: repeated traversals only (each arc beyond the 1st pass).
    arc_counts = Counter(circuit)
    surcout_dcpp_km = sum(
        G.edges[u, v]["weight"] * (cnt - 1)
        for (u, v), cnt in arc_counts.items()
    )

    # distance_deneigee_km : arcs réellement requis (ni connecteur RPP, ni
    # réparation CPP), comptés une seule fois même si traversés plusieurs fois
    # par le DCPP — c'est la neige effectivement enlevée, pas la route parcourue.
    distance_deneigee_km = sum(
        d["weight"] for _, _, d in G.edges(data=True)
        if not d.get("connector") and not d.get("repair")
    )

    base = {
        "zone_id":              zone_id,
        "distance_parcourue_km": round(distance_km, 4),
        "distance_deneigee_km":  round(distance_deneigee_km, 4),
        "distance_km":          round(distance_km, 4),  # alias rétro-compat
        "temps_h":              round(T, 4),
        "cout_fixe":            round(cout_fixe, 4),
        "cout_km":              round(cout_km, 4),
        "cout_horaire":         round(cout_horaire, 4),
        "Z_total":              round(Z_total, 4),
        "CO2_kg":               round(CO2_kg, 4),
        "surcout_dcpp_km":      round(surcout_dcpp_km, 4),
    }

    # Détection du mode — connector=True → RPP, sinon CPP par défaut.
    is_rpp = any(d.get("connector") is True for _, _, d in G.edges(data=True))

    if is_rpp:
        connector_arcs = {
            (u, v) for u, v, d in G.edges(data=True) if d.get("connector") is True
        }
        surcout_connecteur_km = sum(G.edges[u, v]["weight"] for u, v in connector_arcs)
        base["surcout_connecteur_km"] = round(surcout_connecteur_km, 4)
    else:
        repair_arcs = {
            (u, v) for u, v, d in G.edges(data=True) if d.get("repair") is True
        }
        surcout_reparation_km = sum(G.edges[u, v]["weight"] for u, v in repair_arcs)
        base["surcout_reparation_km"] = round(surcout_reparation_km, 4)

    return base


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run_pipeline(output_dir: str = ".") -> dict:
    """
    Run the full mock pipeline (steps 5 → 5b → 6 → 7) and write output files.

    Files written to *output_dir*:
        itineraire_zone_{id}.json   — ordered GPS waypoints
        dashboard_zone_{id}.json    — per-zone cost metrics
        dashboard_global.json       — aggregated summary

    Returns the global dashboard dict.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    G_full, depots = make_mock_graph()
    zones_raw = partition_network(G_full, depots)

    zone_dashboards = []

    for idx in sorted(zones_raw):
        depot    = depots[idx]
        zone_rep = ensure_strong_connectivity(zones_raw[idx], G_full)
        circuit, distance_km = compute_tour(zone_rep, depot)

        # GPS itinerary
        itinerary = build_itinerary(circuit, G_full)
        _write_json(out / f"itineraire_zone_{idx}.json", itinerary)

        # Per-zone dashboard
        dash = build_dashboard(idx, circuit, distance_km, zone_rep)
        _write_json(out / f"dashboard_zone_{idx}.json", dash)
        zone_dashboards.append(dash)

    # Global dashboard
    global_dash = _build_global_dashboard(zone_dashboards)
    _write_json(out / "dashboard_global.json", global_dash)

    return global_dash


def _build_global_dashboard(zone_dashboards: list) -> dict:
    """Aggregate per-zone dashboards into a fleet-level summary."""
    return {
        "nb_deneigeuses":               len(zone_dashboards),
        "distance_totale_km":           round(sum(d["distance_km"] for d in zone_dashboards), 4),
        "distance_parcourue_totale_km": round(sum(d["distance_parcourue_km"] for d in zone_dashboards), 4),
        "distance_deneigee_totale_km":  round(sum(d["distance_deneigee_km"]  for d in zone_dashboards), 4),
        "Z_total_flotte":               round(sum(d["Z_total"]     for d in zone_dashboards), 4),
        "CO2_total_kg":                 round(sum(d["CO2_kg"]      for d in zone_dashboards), 4),
        # Snowplows run in parallel → operation ends when the slowest finishes.
        "temps_operation_h":            round(max(d["temps_h"]     for d in zone_dashboards), 4),
        # Surcharges agrégées séparément par mode
        "surcout_reparation_total_km":  round(sum(d.get("surcout_reparation_km", 0.0) for d in zone_dashboards), 4),
        "surcout_connecteur_total_km":  round(sum(d.get("surcout_connecteur_km", 0.0) for d in zone_dashboards), 4),
        "zones":                        zone_dashboards,
    }


def _write_json(path: Path, data) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
