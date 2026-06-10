"""
Tests for step 5 — partition_network.

Four test groups:
  T1 — every arc of G appears in exactly one zone (no loss, no duplicate)
  T2 — number of zones == number of depots
  T3 — edge attributes (weight, h_neige) are preserved in subgraphs
  T4 — deterministic partition on a hand-crafted graph with known assignment
"""

import math
import warnings

import networkx as nx
import pytest

from fixtures import make_mock_graph
from src.step5_partition import partition_network


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _all_edges(zones: dict) -> list[tuple]:
    """Flatten all (u, v) edges across every zone subgraph."""
    return [(u, v) for sg in zones.values() for u, v in sg.edges()]


# ---------------------------------------------------------------------------
# T1 — Coverage and uniqueness
# ---------------------------------------------------------------------------

class TestCoverageAndUniqueness:
    def setup_method(self):
        self.G, self.depots = make_mock_graph()
        self.zones = partition_network(self.G, self.depots)
        self.original_edges = set(self.G.edges())
        self.zone_edges = _all_edges(self.zones)

    def test_no_arc_lost(self):
        """Every arc in G appears in some zone."""
        assigned = set(self.zone_edges)
        assert assigned == self.original_edges, (
            f"Missing arcs: {self.original_edges - assigned}"
        )

    def test_no_arc_duplicated(self):
        """No arc appears in more than one zone."""
        assert len(self.zone_edges) == len(set(self.zone_edges)), (
            "Some arcs appear in multiple zones."
        )

    def test_total_edge_count_preserved(self):
        """Total edge count across zones equals G's edge count."""
        assert len(self.zone_edges) == self.G.number_of_edges()


# ---------------------------------------------------------------------------
# T2 — Zone count
# ---------------------------------------------------------------------------

class TestZoneCount:
    def test_zone_count_equals_depot_count(self):
        G, depots = make_mock_graph()
        zones = partition_network(G, depots)
        assert len(zones) == len(depots)

    def test_zone_count_single_depot(self):
        G, depots = make_mock_graph()
        single = depots[:1]
        zones = partition_network(G, single)
        assert len(zones) == 1
        # All edges must be in zone 0.
        assert set(zones[0].edges()) == set(G.edges())

    def test_zone_count_two_depots(self):
        G, depots = make_mock_graph()
        zones = partition_network(G, depots[:2])
        assert len(zones) == 2


# ---------------------------------------------------------------------------
# T3 — Attribute preservation
# ---------------------------------------------------------------------------

class TestAttributePreservation:
    def setup_method(self):
        self.G, self.depots = make_mock_graph()
        self.zones = partition_network(self.G, self.depots)

    def test_weight_preserved(self):
        for sg in self.zones.values():
            for u, v, data in sg.edges(data=True):
                assert "weight" in data
                original = self.G.edges[u, v]["weight"]
                assert data["weight"] == pytest.approx(original)

    def test_h_neige_preserved(self):
        for sg in self.zones.values():
            for u, v, data in sg.edges(data=True):
                assert "h_neige" in data
                original = self.G.edges[u, v]["h_neige"]
                assert data["h_neige"] == pytest.approx(original)

    def test_node_attributes_preserved(self):
        """x and y node attributes survive in subgraphs."""
        for sg in self.zones.values():
            for node, attrs in sg.nodes(data=True):
                assert "x" in attrs
                assert "y" in attrs
                assert attrs["x"] == pytest.approx(self.G.nodes[node]["x"])
                assert attrs["y"] == pytest.approx(self.G.nodes[node]["y"])


# ---------------------------------------------------------------------------
# T4 — Deterministic partition on a hand-crafted mini-graph
# ---------------------------------------------------------------------------

class TestDeterministicPartition:
    """
    Mini-graph (7 nodes, 8 arcs) with two depots whose zones are unambiguous.

    Layout (all weights are 1.0 km unless noted):

        Depot A = node 0          Depot B = node 6

        0 → 1 → 2 → 3            6 → 5 → 4 → 3
                      ↑                         |
                      └─────────────────────────┘  (3→3 self is not added)

    Shortest distances from depot 0:  0→0=0, 0→1=1, 0→2=2, 0→3=3
                                      0→6=∞, 0→5=∞, 0→4=∞
    Shortest distances from depot 6:  6→6=0, 6→5=1, 6→4=2, 6→3=3
                                      6→0=∞, 6→1=∞, 6→2=∞

    Arc assignments (using min-endpoint distance):
        0→1 : min(dist_A[0], dist_A[1]) = min(0,1) = 0   vs  min(∞,∞) = ∞  → zone A (idx 0)
        1→2 : min(1,2)=1   vs  min(∞,∞)=∞   → zone A
        2→3 : min(2,3)=2   vs  min(∞,∞)=∞   → zone A
        6→5 : min(∞,∞)=∞  vs  min(0,1)=0    → zone B (idx 1)
        5→4 : min(∞,∞)=∞  vs  min(1,2)=1    → zone B
        4→3 : min(∞,∞)=∞  vs  min(2,3)=2    → zone B

    Node 3 is reachable from BOTH depots at cost 3. Arcs *leading to* node 3
    are 2→3 (zone A score=2) and 4→3 (zone B score=2) — a tie broken by depot
    index order (first depot in list wins). Both already assigned above without
    a tie because their source nodes differ in reachability.

    One extra arc tests true tie-breaking:
        extra arc: 2→4, weight=0.5
        dist_A to 2=2, dist_A to 4=∞  → score_A = 2
        dist_B to 2=∞, dist_B to 4=2  → score_B = 2
        Tie → first depot wins → zone A (idx 0).
    """

    def _build_graph(self):
        G = nx.DiGraph()
        for n in range(7):
            G.add_node(n, x=-73.5 - n * 0.01, y=45.5)
        edges = [
            (0, 1, 1.0), (1, 2, 1.0), (2, 3, 1.0),
            (6, 5, 1.0), (5, 4, 1.0), (4, 3, 1.0),
            (2, 4, 0.5),  # tie arc — assigned to zone A by tie-break
        ]
        for u, v, w in edges:
            G.add_edge(u, v, weight=w, h_neige=5.0)
        return G

    def test_known_zone_assignment(self):
        G = self._build_graph()
        depots = [0, 6]
        zones = partition_network(G, depots)

        zone_a = set(zones[0].edges())
        zone_b = set(zones[1].edges())

        # Arcs unambiguously in zone A
        assert (0, 1) in zone_a
        assert (1, 2) in zone_a
        assert (2, 3) in zone_a

        # Arcs unambiguously in zone B
        assert (6, 5) in zone_b
        assert (5, 4) in zone_b
        assert (4, 3) in zone_b

        # Tie arc (2→4): first depot wins → zone A
        assert (2, 4) in zone_a, "(2,4) should break tie in favour of zone A (first depot)"

    def test_no_arc_lost_mini(self):
        G = self._build_graph()
        zones = partition_network(G, [0, 6])
        all_assigned = set(_all_edges(zones))
        assert all_assigned == set(G.edges())

    def test_no_arc_duplicated_mini(self):
        G = self._build_graph()
        zones = partition_network(G, [0, 6])
        flat = _all_edges(zones)
        assert len(flat) == len(set(flat))


# ---------------------------------------------------------------------------
# T5 — Edge cases and guard-rails
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_depots_raises(self):
        G, _ = make_mock_graph()
        with pytest.raises(ValueError, match="depots"):
            partition_network(G, [])

    def test_missing_depot_raises(self):
        G, _ = make_mock_graph()
        with pytest.raises(ValueError, match="not found"):
            partition_network(G, [9999])

    def test_unreachable_arc_fallback(self):
        """Arc isolated from all depots is assigned to zone 0 with a warning."""
        G = nx.DiGraph()
        # Two disconnected components.
        G.add_node(0, x=-73.6, y=45.5)
        G.add_node(1, x=-73.6, y=45.51)
        G.add_node(99, x=-73.7, y=45.5)  # isolated
        G.add_node(100, x=-73.7, y=45.51)
        G.add_edge(0, 1, weight=0.5, h_neige=5.0)
        G.add_edge(99, 100, weight=0.5, h_neige=5.0)  # unreachable from depot

        depots = [0]
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            zones = partition_network(G, depots)

        assert any("unreachable" in str(w.message).lower() for w in caught), (
            "Expected a UserWarning about unreachable arcs."
        )
        # Both arcs fall into zone 0 (the only zone).
        assert set(zones[0].edges()) == {(0, 1), (99, 100)}
