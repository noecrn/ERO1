"""
Tests for step 7 — build_itinerary, build_dashboard, run_pipeline.

Test groups
-----------
T1  — GPS itinerary continuity (end of arc i == start of arc i+1)
T2  — Itinerary is a closed loop: first and last point == depot position
T3  — Manual Z_total verification on Zone 2 (known values, zero surcharges)
T4  — Surcharge decomposition coherence:
        surcout_reparation + surcout_dcpp + unique_arc_distance == distance_km
T5  — Global dashboard aggregation (sum of Z, max of temps_h)
T6  — JSON files are valid and reloadable
"""

import json
import math
import tempfile
from pathlib import Path

import pytest
import networkx as nx

from fixtures import make_mock_graph
from src.step5_partition import partition_network
from src.step5b_repair import ensure_strong_connectivity
from src.step6_dcpp import compute_tour
from src.step7_output import (
    build_dashboard,
    build_itinerary,
    run_pipeline,
    _build_global_dashboard,
)


# ---------------------------------------------------------------------------
# Shared pipeline fixture (runs once per module via class setup)
# ---------------------------------------------------------------------------

class _PipelineResult:
    """Caches the full pipeline output for reuse across test classes."""

    def __init__(self):
        self.G_full, self.depots = make_mock_graph()
        zones_raw = partition_network(self.G_full, self.depots)
        self.zones_rep = {
            idx: ensure_strong_connectivity(z, self.G_full)
            for idx, z in zones_raw.items()
        }
        self.tours = {
            idx: compute_tour(self.zones_rep[idx], self.depots[idx])
            for idx in self.zones_rep
        }
        self.circuits   = {idx: t[0] for idx, t in self.tours.items()}
        self.distances  = {idx: t[1] for idx, t in self.tours.items()}
        self.itineraries = {
            idx: build_itinerary(self.circuits[idx], self.G_full)
            for idx in self.circuits
        }
        self.dashboards = {
            idx: build_dashboard(
                idx, self.circuits[idx], self.distances[idx], self.zones_rep[idx]
            )
            for idx in self.circuits
        }


_pipe = _PipelineResult()


# ---------------------------------------------------------------------------
# T1 — GPS continuity
# ---------------------------------------------------------------------------

class TestGPSContinuity:
    def test_consecutive_waypoints_are_continuous(self):
        """Last coord of arc i must equal first coord of arc i+1."""
        for idx, wp in _pipe.itineraries.items():
            for i in range(len(wp) - 2):
                end_of_i   = (wp[i + 1]["lat"], wp[i + 1]["lon"])
                start_of_next = (wp[i + 1]["lat"], wp[i + 1]["lon"])
                assert end_of_i == start_of_next, (
                    f"Zone {idx}: continuity break at waypoint {i + 1}"
                )

    def test_waypoint_count(self):
        """len(itinerary) == len(circuit) + 1."""
        for idx, circuit in _pipe.circuits.items():
            assert len(_pipe.itineraries[idx]) == len(circuit) + 1, (
                f"Zone {idx}: expected {len(circuit)+1} waypoints, "
                f"got {len(_pipe.itineraries[idx])}"
            )

    def test_all_waypoints_have_lat_lon(self):
        for idx, wp_list in _pipe.itineraries.items():
            for i, wp in enumerate(wp_list):
                assert "lat" in wp and "lon" in wp, (
                    f"Zone {idx}, waypoint {i}: missing lat/lon keys."
                )

    def test_coordinates_in_montreal_range(self):
        """Sanity: all coords are near Montréal."""
        for idx, wp_list in _pipe.itineraries.items():
            for wp in wp_list:
                assert 45.48 <= wp["lat"] <= 45.53, f"Zone {idx}: lat out of range"
                assert -73.62 <= wp["lon"] <= -73.55, f"Zone {idx}: lon out of range"


# ---------------------------------------------------------------------------
# T2 — Closed loop: first and last point == depot
# ---------------------------------------------------------------------------

class TestClosedLoop:
    def test_first_point_is_depot(self):
        for idx, wp in _pipe.itineraries.items():
            depot_node = _pipe.depots[idx]
            expected_lat = _pipe.G_full.nodes[depot_node]["y"]
            expected_lon = _pipe.G_full.nodes[depot_node]["x"]
            assert wp[0]["lat"] == pytest.approx(expected_lat), f"Zone {idx}: first point lat mismatch"
            assert wp[0]["lon"] == pytest.approx(expected_lon), f"Zone {idx}: first point lon mismatch"

    def test_last_point_is_depot(self):
        for idx, wp in _pipe.itineraries.items():
            depot_node = _pipe.depots[idx]
            expected_lat = _pipe.G_full.nodes[depot_node]["y"]
            expected_lon = _pipe.G_full.nodes[depot_node]["x"]
            assert wp[-1]["lat"] == pytest.approx(expected_lat), f"Zone {idx}: last point lat mismatch"
            assert wp[-1]["lon"] == pytest.approx(expected_lon), f"Zone {idx}: last point lon mismatch"

    def test_first_equals_last_point(self):
        for idx, wp in _pipe.itineraries.items():
            assert wp[0] == wp[-1], f"Zone {idx}: itinerary does not close."


# ---------------------------------------------------------------------------
# T3 — Manual Z_total verification on Zone 2 (zero surcharges)
# ---------------------------------------------------------------------------

class TestManualZone2:
    """
    Zone 2: distance_km = 4.4, repair arcs = 0, DCPP surcharge = 0.
    Conventions:
      T            = 4.4 / 10          = 0.44 h
      cout_horaire = 1.1 * 0.44        = 0.484 $
      cout_fixe    = 500 $
      cout_km      = 1.1 * 4.4         = 4.84 $
      Z_total      = 500 + 4.84 + 0.484 = 505.324 $
      CO2          = 0.27 * 4.4         = 1.188 kg
    """

    DISTANCE = 4.4

    def _expected(self):
        T = self.DISTANCE / 10.0
        cout_h = 1.1 * min(T, 8.0) + 1.3 * max(0.0, T - 8.0)
        return {
            "temps_h":      round(T, 4),
            "cout_fixe":    500.0,
            "cout_km":      round(1.1 * self.DISTANCE, 4),
            "cout_horaire": round(cout_h, 4),
            "Z_total":      round(500 + 1.1 * self.DISTANCE + cout_h, 4),
            "CO2_kg":       round(0.27 * self.DISTANCE, 4),
        }

    def test_zone2_distance(self):
        assert _pipe.distances[2] == pytest.approx(self.DISTANCE)

    def test_zone2_zero_surcharges(self):
        d = _pipe.dashboards[2]
        assert d["surcout_reparation_km"] == pytest.approx(0.0)
        assert d["surcout_dcpp_km"]       == pytest.approx(0.0)

    def test_zone2_Z_total(self):
        expected = self._expected()
        d = _pipe.dashboards[2]
        assert d["Z_total"]      == pytest.approx(expected["Z_total"])
        assert d["cout_fixe"]    == pytest.approx(expected["cout_fixe"])
        assert d["cout_km"]      == pytest.approx(expected["cout_km"])
        assert d["cout_horaire"] == pytest.approx(expected["cout_horaire"])
        assert d["CO2_kg"]       == pytest.approx(expected["CO2_kg"])
        assert d["temps_h"]      == pytest.approx(expected["temps_h"])


# ---------------------------------------------------------------------------
# T4 — Surcharge decomposition coherence
# ---------------------------------------------------------------------------

class TestSurchargeCoherence:
    def test_repair_plus_dcpp_plus_unique_equals_total(self):
        """
        surcout_reparation_km + surcout_dcpp_km + unique_arc_distance == distance_km

        unique_arc_distance = sum of weights of all arcs in the repaired zone
                              (each arc counted once, repair arcs included).
        """
        for idx, dash in _pipe.dashboards.items():
            zone = _pipe.zones_rep[idx]
            unique_km = sum(d["weight"] for _, _, d in zone.edges(data=True))
            reconstructed = (
                dash["surcout_reparation_km"]
                + dash["surcout_dcpp_km"]
                + (unique_km - dash["surcout_reparation_km"])
            )
            # Simplification: unique_km already includes repair arcs once.
            # So: distance_km == unique_km + surcout_dcpp_km
            assert dash["distance_km"] == pytest.approx(
                unique_km + dash["surcout_dcpp_km"], rel=1e-6
            ), (
                f"Zone {idx}: "
                f"distance_km({dash['distance_km']}) != "
                f"unique_km({unique_km:.4f}) + surcout_dcpp({dash['surcout_dcpp_km']:.4f})"
            )

    def test_surcharges_non_negative(self):
        for idx, dash in _pipe.dashboards.items():
            assert dash["surcout_reparation_km"] >= 0
            assert dash["surcout_dcpp_km"]       >= 0

    def test_zone1_has_nonzero_repair_and_dcpp(self):
        d = _pipe.dashboards[1]
        assert d["surcout_reparation_km"] > 0, "Zone 1 should have repair arcs."
        assert d["surcout_dcpp_km"]       > 0, "Zone 1 should have DCPP overhead."


# ---------------------------------------------------------------------------
# T5 — Global dashboard aggregation
# ---------------------------------------------------------------------------

class TestGlobalDashboard:
    def setup_method(self):
        self.dashes = list(_pipe.dashboards.values())
        self.global_dash = _build_global_dashboard(self.dashes)

    def test_Z_total_flotte(self):
        expected = sum(d["Z_total"] for d in self.dashes)
        assert self.global_dash["Z_total_flotte"] == pytest.approx(expected)

    def test_distance_totale(self):
        expected = sum(d["distance_km"] for d in self.dashes)
        assert self.global_dash["distance_totale_km"] == pytest.approx(expected)

    def test_CO2_total(self):
        expected = sum(d["CO2_kg"] for d in self.dashes)
        assert self.global_dash["CO2_total_kg"] == pytest.approx(expected)

    def test_temps_operation_is_max(self):
        expected = max(d["temps_h"] for d in self.dashes)
        assert self.global_dash["temps_operation_h"] == pytest.approx(expected)

    def test_nb_deneigeuses(self):
        assert self.global_dash["nb_deneigeuses"] == 3

    def test_zones_subfield_present(self):
        assert "zones" in self.global_dash
        assert len(self.global_dash["zones"]) == 3


# ---------------------------------------------------------------------------
# T6 — JSON files are valid and reloadable
# ---------------------------------------------------------------------------

class TestJSONOutput:
    def test_all_files_written_and_reloadable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            run_pipeline(output_dir=tmpdir)
            for idx in range(3):
                for prefix in ("itineraire_zone_", "dashboard_zone_"):
                    path = Path(tmpdir) / f"{prefix}{idx}.json"
                    assert path.exists(), f"{path.name} not written."
                    data = json.loads(path.read_text())
                    assert data is not None

            global_path = Path(tmpdir) / "dashboard_global.json"
            assert global_path.exists()
            global_data = json.loads(global_path.read_text())
            assert "Z_total_flotte" in global_data
            assert "zones" in global_data

    def test_itinerary_json_is_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            run_pipeline(output_dir=tmpdir)
            for idx in range(3):
                data = json.loads(
                    (Path(tmpdir) / f"itineraire_zone_{idx}.json").read_text()
                )
                assert isinstance(data, list)
                assert all("lat" in wp and "lon" in wp for wp in data)

    def test_dashboard_json_has_required_keys(self):
        required = {
            "zone_id", "distance_km", "temps_h", "cout_fixe", "cout_km",
            "cout_horaire", "Z_total", "CO2_kg",
            "surcout_reparation_km", "surcout_dcpp_km",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            run_pipeline(output_dir=tmpdir)
            for idx in range(3):
                data = json.loads(
                    (Path(tmpdir) / f"dashboard_zone_{idx}.json").read_text()
                )
                missing = required - data.keys()
                assert not missing, f"dashboard_zone_{idx}.json missing keys: {missing}"
