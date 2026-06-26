"""
Tests for step 5b — ensure_strong_connectivity + priority_only mode (RPP).

Test groups (mode classique CPP — backward-compatible)
-----------
T1  — Zone 1 (broken) is strongly connected after repair
T2  — Original arcs of Zone 1 are all preserved (repair only adds, never removes)
T3  — Already-SC zones (0 and 2) come back with identical arc sets
T4  — Repair arc count for Zone 1 is reported (regression anchor)
T5  — compute_tour raises ValueError if a NON-repaired zone is passed (guard-rail intact)
T6  — End-to-end: partition → repair → compute_tour produces valid tours for all 3 zones
T7  — ValueError when G_full has no return path (genuine dead-end)

Test groups (mode RPP — priority_only=True)
-------------------------------------------
T8  — résultat contient exactement les arcs priority=True de la zone + connecteurs
T9  — résultat est fortement connexe
T10 — arcs connecteurs portent connector=True, arcs originaux pas de repair/connector
T11 — si tous les arcs prio sont déjà SC, aucun connecteur ajouté
T12 — si aucun arc prioritaire dans la zone, ValueError explicite
T13 — connecteurs viennent uniquement de G_full (pas inventés)
T14 — end-to-end : priority_only zone → compute_tour produit un circuit valide
T15 — backward compat : priority_only=False == comportement actuel
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

        with pytest.raises(ValueError, match="cul-de-sac reel"):
            ensure_strong_connectivity(zone, G_full)


# ===========================================================================
# Tests RPP — priority_only=True
# ===========================================================================

def _make_rpp_fixture():
    """
    Graphe de test pour le mode RPP.

    Zone (sous-graphe d'une déneigeuse) :
        Arcs prioritaires (priority=True) :
            0→1  w=1.0   (îlot A)
            1→0  w=1.0   (îlot A — bidirectionnel → déjà SC en lui-même)
            3→4  w=1.0   (îlot B — isolé du reste)
            4→3  w=1.0   (îlot B — bidirectionnel)
        Arcs non prioritaires (priority=False) :
            0→2  w=0.5
            2→3  w=0.5   ← pont potentiel A→B dans G_full
            4→5  w=0.5
            5→0  w=0.5   ← pont potentiel B→A dans G_full

    G_full = zone + arcs de retour qui permettent de relier B→A :
        3→2  w=0.3  (non prioritaire)
        2→1  w=0.3  (non prioritaire)

    Après priority_only : on extrait {0→1, 1→0, 3→4, 4→3}, deux îlots SC.
    On greffe des connecteurs depuis G_full pour relier A↔B.
    Le résultat doit être SC et contenir des arcs connector=True.
    """
    zone = nx.DiGraph()
    for n in range(6):
        zone.add_node(n, x=-73.6 + n * 0.01, y=45.5)

    # Prioritaires — deux îlots SC
    zone.add_edge(0, 1, weight=1.0, priority=True, h_neige=8.0, needs_clearing=True)
    zone.add_edge(1, 0, weight=1.0, priority=True, h_neige=8.0, needs_clearing=True)
    zone.add_edge(3, 4, weight=1.0, priority=True, h_neige=8.0, needs_clearing=True)
    zone.add_edge(4, 3, weight=1.0, priority=True, h_neige=8.0, needs_clearing=True)
    # Non prioritaires
    zone.add_edge(0, 2, weight=0.5, priority=False)
    zone.add_edge(2, 3, weight=0.5, priority=False)
    zone.add_edge(4, 5, weight=0.5, priority=False)
    zone.add_edge(5, 0, weight=0.5, priority=False)

    # G_full = zone + arcs retour supplémentaires
    G_full = zone.copy()
    G_full.add_edge(3, 2, weight=0.3, priority=False)
    G_full.add_edge(2, 1, weight=0.3, priority=False)

    return zone, G_full


# ---------------------------------------------------------------------------
# T8 — résultat contient exactement les arcs priority=True + connecteurs
# ---------------------------------------------------------------------------

class TestPriorityOnlyContainsPriorityArcs:
    def test_all_original_priority_arcs_present(self):
        zone, G_full = _make_rpp_fixture()
        result = ensure_strong_connectivity(zone, G_full, priority_only=True)
        for u, v, d in zone.edges(data=True):
            if d.get("priority"):
                assert result.has_edge(u, v), f"Arc prioritaire ({u},{v}) absent du résultat"

    def test_no_non_priority_zone_arcs_in_result(self):
        """Les arcs non-prioritaires de la zone ne doivent PAS être dans le résultat
        (sauf s'ils sont greffés comme connecteurs depuis G_full)."""
        zone, G_full = _make_rpp_fixture()
        result = ensure_strong_connectivity(zone, G_full, priority_only=True)
        for u, v, d in zone.edges(data=True):
            if not d.get("priority") and result.has_edge(u, v):
                # Toléré seulement si marqué connector=True
                assert result.edges[u, v].get("connector") is True, (
                    f"Arc non-prioritaire ({u},{v}) présent sans marqueur connector=True"
                )


# ---------------------------------------------------------------------------
# T9 — résultat fortement connexe
# ---------------------------------------------------------------------------

class TestPriorityOnlyResultIsStronglyConnected:
    def test_result_sc(self):
        zone, G_full = _make_rpp_fixture()
        result = ensure_strong_connectivity(zone, G_full, priority_only=True)
        assert nx.is_strongly_connected(result), (
            "Le sous-graphe prioritaire augmenté doit être fortement connexe"
        )


# ---------------------------------------------------------------------------
# T10 — connecteurs portent connector=True, originaux pas de repair/connector
# ---------------------------------------------------------------------------

class TestConnectorMarkers:
    def test_added_arcs_have_connector_true(self):
        zone, G_full = _make_rpp_fixture()
        result = ensure_strong_connectivity(zone, G_full, priority_only=True)
        prio_arcs = {(u, v) for u, v, d in zone.edges(data=True) if d.get("priority")}
        for u, v, d in result.edges(data=True):
            if (u, v) not in prio_arcs:
                assert d.get("connector") is True, (
                    f"Arc ajouté ({u},{v}) ne porte pas connector=True"
                )

    def test_original_priority_arcs_not_marked_connector(self):
        zone, G_full = _make_rpp_fixture()
        result = ensure_strong_connectivity(zone, G_full, priority_only=True)
        for u, v, d in zone.edges(data=True):
            if d.get("priority") and result.has_edge(u, v):
                assert result.edges[u, v].get("connector") is not True, (
                    f"Arc prioritaire original ({u},{v}) marqué à tort connector=True"
                )

    def test_no_repair_marker_in_priority_only_mode(self):
        """En mode priority_only, on utilise connector=True, jamais repair=True."""
        zone, G_full = _make_rpp_fixture()
        result = ensure_strong_connectivity(zone, G_full, priority_only=True)
        repair_arcs = [(u, v) for u, v, d in result.edges(data=True) if d.get("repair")]
        assert repair_arcs == [], (
            f"Mode priority_only ne doit pas poser repair=True : {repair_arcs}"
        )


# ---------------------------------------------------------------------------
# T11 — si arcs prio déjà SC, aucun connecteur ajouté
# ---------------------------------------------------------------------------

class TestNoConnectorWhenAlreadySC:
    def test_no_connector_when_prio_already_sc(self):
        """Deux arcs prioritaires formant un cycle — déjà SC, pas de connecteur."""
        zone = nx.DiGraph()
        G_full = nx.DiGraph()
        for n in range(3):
            zone.add_node(n, x=-73.6 + n * 0.01, y=45.5)
            G_full.add_node(n, x=-73.6 + n * 0.01, y=45.5)
        # Cycle prioritaire SC
        zone.add_edge(0, 1, weight=1.0, priority=True, h_neige=8.0, needs_clearing=True)
        zone.add_edge(1, 2, weight=1.0, priority=True, h_neige=8.0, needs_clearing=True)
        zone.add_edge(2, 0, weight=1.0, priority=True, h_neige=8.0, needs_clearing=True)
        G_full.add_edge(0, 1, weight=1.0, priority=True, h_neige=8.0, needs_clearing=True)
        G_full.add_edge(1, 2, weight=1.0, priority=True, h_neige=8.0, needs_clearing=True)
        G_full.add_edge(2, 0, weight=1.0, priority=True, h_neige=8.0, needs_clearing=True)

        result = ensure_strong_connectivity(zone, G_full, priority_only=True)
        connector_arcs = [(u, v) for u, v, d in result.edges(data=True) if d.get("connector")]
        assert connector_arcs == [], (
            f"Aucun connecteur attendu si le sous-graphe prio est déjà SC : {connector_arcs}"
        )


# ---------------------------------------------------------------------------
# T12 — aucun arc prioritaire → ValueError explicite
# ---------------------------------------------------------------------------

class TestNoPriorityArcsRaisesValueError:
    def test_raises_when_no_priority_arcs(self):
        zone = nx.DiGraph()
        G_full = nx.DiGraph()
        for n in range(2):
            zone.add_node(n, x=-73.6 + n * 0.01, y=45.5)
            G_full.add_node(n, x=-73.6 + n * 0.01, y=45.5)
        zone.add_edge(0, 1, weight=1.0, priority=False)
        G_full.add_edge(0, 1, weight=1.0, priority=False)
        G_full.add_edge(1, 0, weight=1.0, priority=False)

        with pytest.raises(ValueError, match="deneiger"):
            ensure_strong_connectivity(zone, G_full, priority_only=True)


# ---------------------------------------------------------------------------
# T13 — connecteurs viennent de G_full (pas d'arcs inventés)
# ---------------------------------------------------------------------------

class TestConnectorsFromGFull:
    def test_connector_arcs_exist_in_gfull(self):
        zone, G_full = _make_rpp_fixture()
        result = ensure_strong_connectivity(zone, G_full, priority_only=True)
        prio_arcs = {(u, v) for u, v, d in zone.edges(data=True) if d.get("priority")}
        for u, v, d in result.edges(data=True):
            if (u, v) not in prio_arcs:
                assert G_full.has_edge(u, v), (
                    f"Arc connecteur ({u},{v}) absent de G_full — inventé de nulle part"
                )


# ---------------------------------------------------------------------------
# T14 — end-to-end priority_only → compute_tour produit un circuit valide
# ---------------------------------------------------------------------------

class TestPriorityOnlyEndToEnd:
    def test_compute_tour_on_priority_only_result(self):
        zone, G_full = _make_rpp_fixture()
        result = ensure_strong_connectivity(zone, G_full, priority_only=True)
        # depot = nœud 0 (dans l'îlot A)
        circuit, total_km = compute_tour(result, depot=0)

        # Circuit fermé
        assert circuit[0][0] == 0
        assert circuit[-1][1] == 0

        # Continuité
        for i in range(len(circuit) - 1):
            assert circuit[i][1] == circuit[i + 1][0]

        # Couverture : tous les arcs prioritaires originaux
        traversed = set(circuit)
        for u, v, d in zone.edges(data=True):
            if d.get("priority"):
                assert (u, v) in traversed, f"Arc prioritaire ({u},{v}) non couvert"

        # Borne inférieure de distance
        assert total_km > 0

    def test_print_rpp_summary(self, capsys):
        zone, G_full = _make_rpp_fixture()
        result = ensure_strong_connectivity(zone, G_full, priority_only=True)
        circuit, total_km = compute_tour(result, depot=0)

        nb_prio  = sum(1 for _, _, d in zone.edges(data=True) if d.get("priority"))
        nb_conn  = sum(1 for _, _, d in result.edges(data=True) if d.get("connector"))
        print(f"\n--- RPP fixture end-to-end ---")
        print(f"  Arcs prioritaires : {nb_prio}")
        print(f"  Arcs connecteurs  : {nb_conn}")
        print(f"  Arcs dans résultat: {result.number_of_edges()}")
        print(f"  Longueur tournée  : {total_km:.3f} km")
        captured = capsys.readouterr()
        print(captured.out)


# ---------------------------------------------------------------------------
# T15 — backward compat : priority_only=False == comportement actuel
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    def test_false_is_default_behavior(self):
        """priority_only=False doit se comporter exactement comme avant."""
        G, _, zones = _get_zones_and_full()
        result_default = ensure_strong_connectivity(zones[1], G)
        result_explicit = ensure_strong_connectivity(zones[1], G, priority_only=False)
        assert set(result_default.edges()) == set(result_explicit.edges())

    def test_false_preserves_repair_marker(self):
        G, _, zones = _get_zones_and_full()
        result = ensure_strong_connectivity(zones[1], G, priority_only=False)
        added = set(result.edges()) - set(zones[1].edges())
        for u, v in added:
            assert result.edges[u, v].get("repair") is True
