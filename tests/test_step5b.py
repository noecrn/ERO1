"""
Tests for step 5b — ensure_strong_connectivity.

Test groups
-----------
T1  — Zone 1 (broken) is strongly connected after repair
T2  — Original arcs of Zone 1 are all preserved (repair only adds, never removes)
T3  — Already-SC zones (0 and 2) come back with identical arc sets
T4  — Repair arc count for Zone 1 is reported (regression anchor)
T5  — compute_tour raises ValueError if a NON-repaired zone is passed (guard-rail intact)
T6  — End-to-end: partition → repair → compute_tour produces valid tours for all 3 zones
T7  — ValueError when G_full has no return path (genuine dead-end)
"""

import pytest
import networkx as nx

from fixtures import make_mock_graph
from src.step5_partition import partition_network
from src.step5b_repair import ensure_strong_connectivity
from src.step6_dcpp import compute_tour


# ---------------------------------------------------------------------------
# Shared setup
# ---------------------------------------------------------------------------

def _get_zones_and_full():
    G, depots = make_mock_graph()
    zones = partition_network(G, depots)
    return G, depots, zones


# ---------------------------------------------------------------------------
# T1 — Zone 1 becomes strongly connected after repair
# ---------------------------------------------------------------------------

class TestZone1BecomesStronglyConnected:
    def test_zone1_not_sc_before_repair(self):
        _, _, zones = _get_zones_and_full()
        assert not nx.is_strongly_connected(zones[1]), (
            "Pre-condition: zone 1 should NOT be strongly connected before repair."
        )

    def test_zone1_sc_after_repair(self):
        G, _, zones = _get_zones_and_full()
        repaired = ensure_strong_connectivity(zones[1], G)
        assert nx.is_strongly_connected(repaired)

    def test_original_zone_not_mutated(self):
        """ensure_strong_connectivity must not modify its inputs."""
        G, _, zones = _get_zones_and_full()
        original_edges = set(zones[1].edges())
        _ = ensure_strong_connectivity(zones[1], G)
        assert set(zones[1].edges()) == original_edges


# ---------------------------------------------------------------------------
# T2 — Original arcs preserved in Zone 1 after repair
# ---------------------------------------------------------------------------

class TestOriginalArcsPreserved:
    def test_all_original_arcs_present(self):
        G, _, zones = _get_zones_and_full()
        zone1 = zones[1]
        repaired = ensure_strong_connectivity(zone1, G)
        missing = set(zone1.edges()) - set(repaired.edges())
        assert not missing, f"Arcs lost during repair: {missing}"

    def test_original_arc_count_does_not_decrease(self):
        G, _, zones = _get_zones_and_full()
        repaired = ensure_strong_connectivity(zones[1], G)
        assert repaired.number_of_edges() >= zones[1].number_of_edges()

    def test_repair_only_adds_arcs(self):
        G, _, zones = _get_zones_and_full()
        zone1 = zones[1]
        repaired = ensure_strong_connectivity(zone1, G)
        added = set(repaired.edges()) - set(zone1.edges())
        # Every added arc must be marked repair=True
        for u, v in added:
            assert repaired.edges[u, v].get("repair") is True, (
                f"Added arc ({u},{v}) lacks repair=True marker."
            )

    def test_existing_arcs_not_marked_repair(self):
        """Arcs that were already in the zone should NOT carry repair=True."""
        G, _, zones = _get_zones_and_full()
        zone1 = zones[1]
        repaired = ensure_strong_connectivity(zone1, G)
        for u, v in zone1.edges():
            assert repaired.edges[u, v].get("repair") is not True, (
                f"Original arc ({u},{v}) was incorrectly marked repair=True."
            )


# ---------------------------------------------------------------------------
# T3 — Already-SC zones come back with identical arc sets
# ---------------------------------------------------------------------------

class TestAlreadySCZonesUnchanged:
    @pytest.mark.parametrize("zone_idx", [0, 2])
    def test_sc_zone_edges_unchanged(self, zone_idx):
        G, _, zones = _get_zones_and_full()
        zone = zones[zone_idx]
        assert nx.is_strongly_connected(zone), (
            f"Pre-condition: zone {zone_idx} should already be strongly connected."
        )
        repaired = ensure_strong_connectivity(zone, G)
        assert set(repaired.edges()) == set(zone.edges()), (
            f"Zone {zone_idx}: repair altered an already-SC zone."
        )

    @pytest.mark.parametrize("zone_idx", [0, 2])
    def test_no_repair_arcs_added_to_sc_zone(self, zone_idx):
        G, _, zones = _get_zones_and_full()
        repaired = ensure_strong_connectivity(zones[zone_idx], G)
        repair_arcs = [
            (u, v) for u, v, d in repaired.edges(data=True) if d.get("repair")
        ]
        assert repair_arcs == [], (
            f"Zone {zone_idx}: unexpected repair arcs on an already-SC zone: {repair_arcs}"
        )


# ---------------------------------------------------------------------------
# T4 — Repair arc count for Zone 1 (regression anchor)
# ---------------------------------------------------------------------------

class TestRepairArcCount:
    def test_repair_arc_count_reported(self, capsys):
        G, _, zones = _get_zones_and_full()
        repaired = ensure_strong_connectivity(zones[1], G)
        repair_arcs = [
            (u, v) for u, v, d in repaired.edges(data=True) if d.get("repair")
        ]
        n_repair = len(repair_arcs)
        print(f"\nZone 1 — arcs de réparation ajoutés : {n_repair}")
        print(f"  arcs : {sorted(repair_arcs)}")
        assert n_repair > 0, "Zone 1 should require at least one repair arc."
        # Regression: record the count so future changes are visible.
        # Current expected value is stored as a known lower bound only (>=1).
        captured = capsys.readouterr()
        print(captured.out)


# ---------------------------------------------------------------------------
# T5 — compute_tour guard-rail: still raises on non-repaired zone
# ---------------------------------------------------------------------------

class TestGuardRailIntact:
    def test_compute_tour_raises_on_zone1_without_repair(self):
        G, depots, zones = _get_zones_and_full()
        with pytest.raises(ValueError, match="non fortement connexe"):
            compute_tour(zones[1], depots[1])


# ---------------------------------------------------------------------------
# T6 — End-to-end: partition → repair → compute_tour
# ---------------------------------------------------------------------------

class TestEndToEnd:
    def setup_method(self):
        self.G, self.depots, self.zones = _get_zones_and_full()

    def _repaired_zones(self):
        return {
            idx: ensure_strong_connectivity(zone, self.G)
            for idx, zone in self.zones.items()
        }

    def test_no_value_error_after_repair(self):
        for idx, zone in self._repaired_zones().items():
            depot = self.depots[idx]
            compute_tour(zone, depot)  # must not raise

    def test_all_original_arcs_covered(self):
        repaired = self._repaired_zones()
        for idx, zone in repaired.items():
            depot = self.depots[idx]
            circuit, _ = compute_tour(zone, depot)
            traversed = set(circuit)
            original_arcs = set(self.zones[idx].edges())
            missing = original_arcs - traversed
            assert not missing, (
                f"Zone {idx}: original arcs not covered: {missing}"
            )

    def test_all_circuits_closed(self):
        repaired = self._repaired_zones()
        for idx, zone in repaired.items():
            depot = self.depots[idx]
            circuit, _ = compute_tour(zone, depot)
            assert circuit[0][0] == depot
            assert circuit[-1][1] == depot

    def test_all_circuits_continuous(self):
        repaired = self._repaired_zones()
        for idx, zone in repaired.items():
            depot = self.depots[idx]
            circuit, _ = compute_tour(zone, depot)
            for i in range(len(circuit) - 1):
                assert circuit[i][1] == circuit[i + 1][0], (
                    f"Zone {idx}: circuit break at position {i}"
                )

    def test_print_summary(self, capsys):
        """Visual summary — not a hard assertion."""
        repaired = self._repaired_zones()
        print("\n--- Step 5b + 6 end-to-end summary ---")
        for idx, zone in repaired.items():
            depot = self.depots[idx]
            circuit, total_km = compute_tour(zone, depot)

            original_arcs = self.zones[idx].number_of_edges()
            repair_arcs = sum(
                1 for _, _, d in zone.edges(data=True) if d.get("repair")
            )
            unique_km = sum(
                d["weight"] for _, _, d in self.zones[idx].edges(data=True)
            )
            overhead = total_km - unique_km

            print(
                f"Zone {idx} (dépôt {self.depots[idx]}): "
                f"{original_arcs} arcs originaux + {repair_arcs} arcs réparation | "
                f"tournée = {total_km:.3f} km | surcoût total = +{overhead:.3f} km"
            )
        captured = capsys.readouterr()
        print(captured.out)


# ---------------------------------------------------------------------------
# T7 — ValueError on genuine dead-end in G_full
# ---------------------------------------------------------------------------

class TestGenuineDeadEnd:
    def test_raises_when_gfull_has_no_return_path(self):
        """
        Zone has two SCCs: {0} and {1}.  G_full only has arc 0→1 and nothing
        back — so it is impossible to connect 1 back to 0 via G_full.
        """
        zone = nx.DiGraph()
        zone.add_node(0, x=-73.6, y=45.5)
        zone.add_node(1, x=-73.6, y=45.51)
        zone.add_edge(0, 1, weight=0.5, h_neige=5.0)

        # G_full also has only 0→1 — no return path anywhere.
        G_full = nx.DiGraph()
        G_full.add_node(0, x=-73.6, y=45.5)
        G_full.add_node(1, x=-73.6, y=45.51)
        G_full.add_edge(0, 1, weight=0.5, h_neige=5.0)

        with pytest.raises(ValueError, match="cul-de-sac réel"):
            ensure_strong_connectivity(zone, G_full)
