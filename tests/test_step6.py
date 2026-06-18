"""
Tests for step 6 — compute_tour (DCPP).

Test groups
-----------
T1  — arc coverage: every arc of the zone appears at least once in the circuit
T2  — closed circuit: starts and ends at depot
T3  — circuit continuity: target of arc i == source of arc i+1
T4  — distance lower bound: tour distance ≥ sum of unique arc weights
T5  — already-Eulerian graph with known exact distance
T6  — ValueError on non-strongly-connected zone
T7  — integration smoke-test on the 3 zones from the mock (step 5 output)
T8  — régression : arcs portant un attribut 'key' (graphes OSM réels) ne
      bloquent pas la duplication dans MultiDiGraph (_balance bug)
"""

import pytest
import networkx as nx

from fixtures import make_mock_graph
from src.step5_partition import partition_network
from src.step6_dcpp import compute_tour


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _unique_arc_weight(zone: nx.DiGraph) -> float:
    return sum(d["weight"] for _, _, d in zone.edges(data=True))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _small_non_eulerian_zone():
    """
    Simple zone that is strongly connected but NOT Eulerian.

    Arcs (all weight=1.0):
        0 → 1 → 2 → 0      (3-cycle, back-bone)
        1 → 3 → 2           (detour — creates imbalance at 1, 2, 3)

    Imbalances:
        node 0 : out=1, in=1  → 0
        node 1 : out=2, in=1  → +1   (sink)
        node 2 : out=1, in=2  → -1   (source)
        node 3 : out=1, in=1  → 0

    Optimal DCPP adds path 2→0→1 (cost 2.0) to balance 2 (+1) and 1 (−1)?
    Wait — let me recompute.
    source = node 2 (imbalance -1), sink = node 1 (imbalance +1).
    Shortest path 2→0→1  cost=2.0  →  adds arcs (2,0) and (0,1).
    Total = original 5 arcs + 2 duplicate arcs = 7 traversals.
    Total km = 5*1.0 + 2*1.0 = 7.0.
    """
    G = nx.DiGraph()
    for n in range(4):
        G.add_node(n, x=-73.5 - n * 0.01, y=45.5)
    for u, v in [(0, 1), (1, 2), (2, 0), (1, 3), (3, 2)]:
        G.add_edge(u, v, weight=1.0, h_neige=5.0)
    return G


def _small_eulerian_zone():
    """
    A directed 4-cycle: 0→1→2→3→0, plus a shortcut 1→3→1 (makes every node balanced).

    Arcs & weights:
        0→1  w=1.0
        1→2  w=1.5
        2→3  w=1.0
        3→0  w=1.5
        1→3  w=2.0
        3→1  w=2.0

    Every node: out_degree == in_degree == 2  → Eulerian.
    Total weight = 1+1.5+1+1.5+2+2 = 9.0 km.
    """
    G = nx.DiGraph()
    for n in range(4):
        G.add_node(n, x=-73.5 - n * 0.01, y=45.5)
    edges = [(0, 1, 1.0), (1, 2, 1.5), (2, 3, 1.0), (3, 0, 1.5), (1, 3, 2.0), (3, 1, 2.0)]
    for u, v, w in edges:
        G.add_edge(u, v, weight=w, h_neige=5.0)
    return G


# ---------------------------------------------------------------------------
# T1 — Arc coverage
# ---------------------------------------------------------------------------

class TestArcCoverage:
    def test_every_arc_covered_non_eulerian(self):
        zone = _small_non_eulerian_zone()
        circuit, _ = compute_tour(zone, depot=0)
        traversed = set(circuit)
        for u, v in zone.edges():
            assert (u, v) in traversed, f"Arc ({u},{v}) not covered by tour."

    def test_every_arc_covered_eulerian(self):
        zone = _small_eulerian_zone()
        circuit, _ = compute_tour(zone, depot=0)
        traversed = set(circuit)
        for u, v in zone.edges():
            assert (u, v) in traversed, f"Arc ({u},{v}) not covered by tour."


# ---------------------------------------------------------------------------
# T2 — Closed circuit
# ---------------------------------------------------------------------------

class TestClosedCircuit:
    def test_starts_at_depot(self):
        zone = _small_non_eulerian_zone()
        circuit, _ = compute_tour(zone, depot=0)
        assert circuit[0][0] == 0

    def test_ends_at_depot(self):
        zone = _small_non_eulerian_zone()
        circuit, _ = compute_tour(zone, depot=0)
        assert circuit[-1][1] == 0

    def test_closed_eulerian(self):
        zone = _small_eulerian_zone()
        circuit, _ = compute_tour(zone, depot=0)
        assert circuit[0][0] == circuit[-1][1]


# ---------------------------------------------------------------------------
# T3 — Circuit continuity
# ---------------------------------------------------------------------------

class TestCircuitContinuity:
    def _check_continuity(self, circuit):
        for i in range(len(circuit) - 1):
            assert circuit[i][1] == circuit[i + 1][0], (
                f"Break in circuit at position {i}: "
                f"arc {circuit[i]} followed by {circuit[i+1]}"
            )

    def test_continuity_non_eulerian(self):
        zone = _small_non_eulerian_zone()
        circuit, _ = compute_tour(zone, depot=0)
        self._check_continuity(circuit)

    def test_continuity_eulerian(self):
        zone = _small_eulerian_zone()
        circuit, _ = compute_tour(zone, depot=1)
        self._check_continuity(circuit)


# ---------------------------------------------------------------------------
# T4 — Distance lower bound
# ---------------------------------------------------------------------------

class TestDistanceLowerBound:
    def test_tour_ge_unique_arc_sum_non_eulerian(self):
        zone = _small_non_eulerian_zone()
        _, total_km = compute_tour(zone, depot=0)
        lb = _unique_arc_weight(zone)
        assert total_km >= lb - 1e-9, (
            f"Tour distance {total_km:.4f} < unique arc sum {lb:.4f}"
        )

    def test_tour_ge_unique_arc_sum_eulerian(self):
        zone = _small_eulerian_zone()
        _, total_km = compute_tour(zone, depot=0)
        lb = _unique_arc_weight(zone)
        assert total_km >= lb - 1e-9

    def test_tour_eq_unique_arc_sum_when_eulerian(self):
        """Eulerian graph: optimal tour == sum of unique arcs (no extras needed)."""
        zone = _small_eulerian_zone()
        _, total_km = compute_tour(zone, depot=0)
        assert total_km == pytest.approx(_unique_arc_weight(zone))


# ---------------------------------------------------------------------------
# T5 — Already-Eulerian: known exact distance
# ---------------------------------------------------------------------------

class TestEulerianExactDistance:
    def test_exact_distance(self):
        """4-cycle + shortcut, all arcs traversed exactly once → 9.0 km."""
        zone = _small_eulerian_zone()
        circuit, total_km = compute_tour(zone, depot=0)
        assert total_km == pytest.approx(9.0)
        assert len(circuit) == zone.number_of_edges()


# ---------------------------------------------------------------------------
# T6 — ValueError on non-strongly-connected zone
# ---------------------------------------------------------------------------

class TestNotStronglyConnected:
    def _dead_end_graph(self):
        """Two nodes, one arc — can never form a cycle."""
        G = nx.DiGraph()
        G.add_node(0, x=-73.6, y=45.5)
        G.add_node(1, x=-73.6, y=45.51)
        G.add_edge(0, 1, weight=0.5, h_neige=5.0)
        return G

    def test_raises_value_error(self):
        G = self._dead_end_graph()
        with pytest.raises(ValueError, match="non fortement connexe"):
            compute_tour(G, depot=0)

    def test_error_message_contains_scc_count(self):
        G = self._dead_end_graph()
        with pytest.raises(ValueError, match="2"):
            compute_tour(G, depot=0)


# ---------------------------------------------------------------------------
# T7 — Integration: 3 zones from mock (step 5 output)
# ---------------------------------------------------------------------------

class TestIntegrationMockZones:
    def setup_method(self):
        G, depots = make_mock_graph()
        self.zones = partition_network(G, depots)
        self.depots = depots

    def test_all_zones_produce_valid_tours(self):
        for idx, zone in self.zones.items():
            depot = self.depots[idx]
            if not nx.is_strongly_connected(zone):
                pytest.skip(f"Zone {idx} not strongly connected — skipped in this test.")
            circuit, total_km = compute_tour(zone, depot)

            # Coverage
            covered = set(circuit)
            for u, v in zone.edges():
                assert (u, v) in covered, f"Zone {idx}: arc ({u},{v}) not covered."

            # Closed
            assert circuit[0][0] == depot
            assert circuit[-1][1] == depot

            # Continuity
            for i in range(len(circuit) - 1):
                assert circuit[i][1] == circuit[i + 1][0]

            # Lower bound
            lb = _unique_arc_weight(zone)
            assert total_km >= lb - 1e-9

    def test_print_summary(self, capsys):
        """Print per-zone stats; not an assertion — visual check in output."""
        print("\n--- Step 6 integration: DCPP on mock zones ---")
        for idx, zone in self.zones.items():
            depot = self.depots[idx]
            if not nx.is_strongly_connected(zone):
                print(f"Zone {idx} (dépôt {depot}): NON fortement connexe — skipped")
                continue
            circuit, total_km = compute_tour(zone, depot)
            unique_km = _unique_arc_weight(zone)
            overhead = total_km - unique_km
            print(
                f"Zone {idx} (dépôt {depot}): "
                f"{zone.number_of_edges()} arcs uniques, "
                f"tournée = {total_km:.3f} km, "
                f"surcoût = +{overhead:.3f} km"
            )
        captured = capsys.readouterr()
        print(captured.out)


# ---------------------------------------------------------------------------
# T8 — Régression : attribut 'key' dans les données d'arc (graphes OSM)
# ---------------------------------------------------------------------------

class TestKeyAttributeRegression:
    def _zone_with_key_attr(self):
        """
        Zone SC non-Eulérien dont les arcs portent un attribut 'key': 0
        (présent dans tous les graphes OSM chargés par graph_adapter).
        Sans le fix, _balance échoue à dupliquer les arcs → NetworkXError.
        """
        G = nx.DiGraph()
        for n in range(4):
            G.add_node(n, x=-73.5 - n * 0.01, y=45.5)
        # Tous les arcs portent key=0 comme dans les vrais graphes OSM
        for u, v in [(0, 1), (1, 2), (2, 0), (1, 3), (3, 2)]:
            G.add_edge(u, v, weight=1.0, key=0, highway="primary")
        return G

    def test_compute_tour_succeeds_with_key_attr(self):
        """compute_tour ne doit pas lever NetworkXError même si les arcs ont key=0."""
        zone = self._zone_with_key_attr()
        assert nx.is_strongly_connected(zone)
        # Sans le fix : NetworkXError "G is not Eulerian"
        circuit, total_km = compute_tour(zone, depot=0)
        assert len(circuit) > 0
        assert total_km > 0

    def test_arc_coverage_with_key_attr(self):
        zone = self._zone_with_key_attr()
        circuit, _ = compute_tour(zone, depot=0)
        traversed = set(circuit)
        for u, v in zone.edges():
            assert (u, v) in traversed, f"Arc ({u},{v}) non couvert avec attribut key=0"

    def test_closed_circuit_with_key_attr(self):
        zone = self._zone_with_key_attr()
        circuit, _ = compute_tour(zone, depot=0)
        assert circuit[0][0] == 0
        assert circuit[-1][1] == 0
