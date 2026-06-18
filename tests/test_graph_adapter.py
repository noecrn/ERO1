"""
Tests for src/graph_adapter.py — couche anti-corruption entre les JSON
produits par data_loader.py (étapes 1-4) et le pipeline interne (étapes 5-7).

T1  — chaque arc a weight (copié de length_km)
T2  — chaque arc a priority (copié de is_crit_security_social)
T3  — chaque nœud a x (copié de lon) et y (copié de lat)
T4  — au moins un arc priority=True et au moins un priority=False
T5  — le filtre priority donne le même décompte que is_crit_security_social brut
T6  — les attributs originaux sont conservés (length_km, is_crit_security_social, is_crit_economique)
T7  — décomptes réels : nb arcs, nb arcs prioritaires, nb nœuds (affichage)
T8  — fichier inexistant lève FileNotFoundError
T9  — load_graph retourne un graphe fortement connexe par défaut (tous quartiers)
T10 — arcs prioritaires écartés ≤ seuils du diagnostic par quartier
T11 — restrict_to_main_scc=False retourne le graphe complet non filtré
T12 — extract_main_scc : tous les attributs d'arcs et nœuds sont conservés
T13 — extract_main_scc : warning indique les arcs écartés (prio vs non-prio)
"""

import warnings
import pytest
import networkx as nx
from pathlib import Path

from src.graph_adapter import load_graph, extract_main_scc

# Chemin vers un vrai graphe produit par les collègues (présent dans le dépôt)
GRAPH_PATH = Path(__file__).parent.parent / "src" / "graph_anjou.json"


@pytest.fixture(scope="module")
def G():
    return load_graph(GRAPH_PATH)


# ---------------------------------------------------------------------------
# T1 — weight présent sur chaque arc
# ---------------------------------------------------------------------------

class TestWeightAttribute:
    def test_every_edge_has_weight(self, G):
        for u, v, data in G.edges(data=True):
            assert "weight" in data, f"Arc ({u},{v}) manque l'attribut weight"

    def test_weight_is_positive_float(self, G):
        for u, v, data in G.edges(data=True):
            assert isinstance(data["weight"], float), f"weight non float sur ({u},{v})"
            assert data["weight"] > 0, f"weight <= 0 sur ({u},{v})"


# ---------------------------------------------------------------------------
# T2 — priority présent sur chaque arc
# ---------------------------------------------------------------------------

class TestPriorityAttribute:
    def test_every_edge_has_priority(self, G):
        for u, v, data in G.edges(data=True):
            assert "priority" in data, f"Arc ({u},{v}) manque l'attribut priority"

    def test_priority_is_bool(self, G):
        for u, v, data in G.edges(data=True):
            assert isinstance(data["priority"], bool), (
                f"priority non bool sur ({u},{v}) : {data['priority']!r}"
            )


# ---------------------------------------------------------------------------
# T3 — x et y présents sur chaque nœud
# ---------------------------------------------------------------------------

class TestNodeCoordinates:
    def test_every_node_has_x(self, G):
        for n, data in G.nodes(data=True):
            assert "x" in data, f"Nœud {n} manque l'attribut x"

    def test_every_node_has_y(self, G):
        for n, data in G.nodes(data=True):
            assert "y" in data, f"Nœud {n} manque l'attribut y"

    def test_x_y_are_floats(self, G):
        for n, data in G.nodes(data=True):
            assert isinstance(data["x"], float), f"x non float sur nœud {n}"
            assert isinstance(data["y"], float), f"y non float sur nœud {n}"


# ---------------------------------------------------------------------------
# T4 — mix de priority=True et priority=False (RPP non trivial)
# ---------------------------------------------------------------------------

class TestPriorityMix:
    def test_at_least_one_priority_true(self, G):
        has_true = any(d["priority"] for _, _, d in G.edges(data=True))
        assert has_true, "Aucun arc priority=True — le RPP n'a rien à couvrir"

    def test_at_least_one_priority_false(self, G):
        has_false = any(not d["priority"] for _, _, d in G.edges(data=True))
        assert has_false, "Tous les arcs sont prioritaires — pas de connecteurs possibles"


# ---------------------------------------------------------------------------
# T5 — cohérence du mapping : priority == is_crit_security_social
# ---------------------------------------------------------------------------

class TestMappingCoherence:
    def test_priority_matches_is_crit_security_social(self, G):
        for u, v, data in G.edges(data=True):
            expected = bool(data.get("is_crit_security_social", False))
            assert data["priority"] == expected, (
                f"Arc ({u},{v}) : priority={data['priority']} "
                f"mais is_crit_security_social={data.get('is_crit_security_social')}"
            )

    def test_priority_count_equals_raw_flag_count(self, G):
        count_priority = sum(1 for _, _, d in G.edges(data=True) if d["priority"])
        count_raw = sum(
            1 for _, _, d in G.edges(data=True)
            if d.get("is_crit_security_social", False)
        )
        assert count_priority == count_raw


# ---------------------------------------------------------------------------
# T6 — attributs originaux conservés
# ---------------------------------------------------------------------------

class TestOriginalAttributesPreserved:
    def test_length_km_preserved(self, G):
        for u, v, data in G.edges(data=True):
            assert "length_km" in data, f"length_km supprimé sur ({u},{v})"

    def test_is_crit_security_social_preserved(self, G):
        for u, v, data in G.edges(data=True):
            assert "is_crit_security_social" in data

    def test_is_crit_economique_preserved(self, G):
        for u, v, data in G.edges(data=True):
            assert "is_crit_economique" in data

    def test_weight_equals_length_km(self, G):
        for u, v, data in G.edges(data=True):
            assert data["weight"] == pytest.approx(data["length_km"]), (
                f"weight != length_km sur ({u},{v})"
            )


# ---------------------------------------------------------------------------
# T7 — décomptes réels (affichage + assertions de seuil minimal)
# ---------------------------------------------------------------------------

class TestRealCounts:
    def test_print_graph_stats(self, G, capsys):
        nb_arcs = G.number_of_edges()
        nb_noeuds = G.number_of_nodes()
        nb_prioritaires = sum(1 for _, _, d in G.edges(data=True) if d["priority"])
        pct = 100 * nb_prioritaires / nb_arcs if nb_arcs else 0

        print(f"\n--- Décomptes réels graph_anjou ---")
        print(f"  Nœuds          : {nb_noeuds}")
        print(f"  Arcs total     : {nb_arcs}")
        print(f"  Arcs priorit.  : {nb_prioritaires} ({pct:.1f} %)")
        print(f"  Arcs connecteur: {nb_arcs - nb_prioritaires} ({100-pct:.1f} %)")

        captured = capsys.readouterr()
        print(captured.out)

        # Seuils minimaux : un vrai graphe de quartier doit être non trivial
        assert nb_noeuds >= 10
        assert nb_arcs >= 20
        assert nb_prioritaires >= 1


# ---------------------------------------------------------------------------
# T8 — FileNotFoundError sur fichier absent
# ---------------------------------------------------------------------------

class TestFileNotFound:
    def test_raises_on_missing_file(self):
        with pytest.raises(FileNotFoundError):
            load_graph("/tmp/ce_fichier_nexiste_pas_du_tout.json")


# ---------------------------------------------------------------------------
# T9 — load_graph retourne un graphe fortement connexe par défaut
# ---------------------------------------------------------------------------

QUARTIER_PATHS = {
    "anjou":                Path("src/graph_anjou.json"),
    "outremont":            Path("src/graph_outremont.json"),
    "riviere_des_prairies": Path("src/graph_riviere_des_prairies.json"),
    "verdun":               Path("src/graph_verdun.json"),
}

class TestStronglyConnectedByDefault:
    @pytest.mark.parametrize("name,path", QUARTIER_PATHS.items())
    def test_load_graph_is_strongly_connected(self, name, path):
        G = load_graph(path)
        assert nx.is_strongly_connected(G), (
            f"{name}: load_graph() doit retourner un graphe fortement connexe "
            f"(restrict_to_main_scc=True par défaut)"
        )


# ---------------------------------------------------------------------------
# T10 — arcs prioritaires écartés ≤ seuils du diagnostic
# (les seuils viennent du diagnostic SCC réel ; +1 pour robustesse)
# ---------------------------------------------------------------------------

# seuil = nb arcs prio hors grande SCC mesuré lors du diagnostic
PRIO_DISCARDED_CAPS = {
    "anjou":                16,
    "outremont":            1,
    "riviere_des_prairies": 15,
    "verdun":               145,
}

class TestDiscardedPriorityArcs:
    @pytest.mark.parametrize("name,path", QUARTIER_PATHS.items())
    def test_discarded_prio_arcs_within_cap(self, name, path):
        G_full = load_graph(path, restrict_to_main_scc=False)
        G_scc  = load_graph(path, restrict_to_main_scc=True)

        prio_full = sum(1 for _, _, d in G_full.edges(data=True) if d.get("priority"))
        prio_scc  = sum(1 for _, _, d in G_scc.edges(data=True)  if d.get("priority"))
        discarded = prio_full - prio_scc

        cap = PRIO_DISCARDED_CAPS[name]
        assert discarded <= cap, (
            f"{name}: {discarded} arcs prioritaires écartés, attendu ≤ {cap}"
        )

    @pytest.mark.parametrize("name,path", QUARTIER_PATHS.items())
    def test_print_discarded_counts(self, name, path, capsys):
        G_full = load_graph(path, restrict_to_main_scc=False)
        G_scc  = load_graph(path, restrict_to_main_scc=True)

        total_full = G_full.number_of_edges()
        total_scc  = G_scc.number_of_edges()
        prio_full  = sum(1 for _, _, d in G_full.edges(data=True) if d.get("priority"))
        prio_scc   = sum(1 for _, _, d in G_scc.edges(data=True)  if d.get("priority"))

        print(f"\n--- {name} ---")
        print(f"  Arcs total  : {total_full} → {total_scc} (écartés: {total_full - total_scc})")
        print(f"  Arcs prio   : {prio_full}  → {prio_scc}  (écartés: {prio_full - prio_scc})")
        captured = capsys.readouterr()
        print(captured.out)


# ---------------------------------------------------------------------------
# T11 — restrict_to_main_scc=False retourne le graphe complet non filtré
# ---------------------------------------------------------------------------

class TestRestrictFalseReturnsFullGraph:
    @pytest.mark.parametrize("name,path", QUARTIER_PATHS.items())
    def test_full_graph_larger_than_scc_graph(self, name, path):
        G_full = load_graph(path, restrict_to_main_scc=False)
        G_scc  = load_graph(path, restrict_to_main_scc=True)
        # La grande SCC est toujours ≤ graphe complet en nombre d'arcs
        assert G_scc.number_of_edges() <= G_full.number_of_edges()

    @pytest.mark.parametrize("name,path", [
        # Seuls les quartiers avec des nœuds hors SCC ont G_scc < G_full
        ("anjou",                Path("src/graph_anjou.json")),
        ("verdun",               Path("src/graph_verdun.json")),
    ])
    def test_scc_strictly_smaller_than_full(self, name, path):
        G_full = load_graph(path, restrict_to_main_scc=False)
        G_scc  = load_graph(path, restrict_to_main_scc=True)
        assert G_scc.number_of_nodes() < G_full.number_of_nodes(), (
            f"{name}: la grande SCC devrait avoir moins de nœuds que G_full"
        )


# ---------------------------------------------------------------------------
# T12 — extract_main_scc conserve tous les attributs d'arcs et nœuds
# ---------------------------------------------------------------------------

class TestExtractMainSccPreservesAttributes:
    def _make_test_graph(self):
        """Petit graphe avec une grande SCC (0,1,2) et un nœud satellite (3)."""
        G = nx.DiGraph()
        G.add_node(0, x=-73.6, y=45.5, label="depot")
        G.add_node(1, x=-73.59, y=45.5)
        G.add_node(2, x=-73.58, y=45.5)
        G.add_node(3, x=-73.57, y=45.5)  # satellite : pas de retour vers SCC
        G.add_edge(0, 1, weight=1.0, priority=True,  length_km=1.0)
        G.add_edge(1, 2, weight=1.5, priority=False, length_km=1.5)
        G.add_edge(2, 0, weight=1.0, priority=True,  length_km=1.0)
        G.add_edge(2, 3, weight=0.5, priority=False, length_km=0.5)  # hors SCC
        return G

    def test_scc_is_strongly_connected(self):
        G = self._make_test_graph()
        result = extract_main_scc(G)
        assert nx.is_strongly_connected(result)

    def test_edge_attributes_preserved(self):
        G = self._make_test_graph()
        result = extract_main_scc(G)
        for u, v, data in result.edges(data=True):
            assert "weight"   in data
            assert "priority" in data
            assert "length_km" in data

    def test_node_attributes_preserved(self):
        G = self._make_test_graph()
        result = extract_main_scc(G)
        for n, data in result.nodes(data=True):
            assert "x" in data
            assert "y" in data

    def test_satellite_node_excluded(self):
        G = self._make_test_graph()
        result = extract_main_scc(G)
        assert 3 not in result.nodes()

    def test_scc_nodes_included(self):
        G = self._make_test_graph()
        result = extract_main_scc(G)
        assert 0 in result.nodes()
        assert 1 in result.nodes()
        assert 2 in result.nodes()


# ---------------------------------------------------------------------------
# T13 — extract_main_scc émet un warning avec les décomptes écartés
# ---------------------------------------------------------------------------

class TestExtractMainSccWarning:
    def _make_graph_with_outlier(self):
        G = nx.DiGraph()
        for n in range(4):
            G.add_node(n, x=-73.6 + n*0.01, y=45.5)
        G.add_edge(0, 1, weight=1.0, priority=True,  length_km=1.0)
        G.add_edge(1, 2, weight=1.0, priority=False, length_km=1.0)
        G.add_edge(2, 0, weight=1.0, priority=True,  length_km=1.0)
        G.add_edge(2, 3, weight=0.5, priority=True,  length_km=0.5)  # arc prio hors SCC
        return G

    def test_warning_emitted_when_arcs_discarded(self):
        G = self._make_graph_with_outlier()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            extract_main_scc(G)
        assert len(caught) >= 1

    def test_warning_mentions_discarded_counts(self):
        G = self._make_graph_with_outlier()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            extract_main_scc(G)
        messages = " ".join(str(w.message) for w in caught)
        # Le warning doit mentionner qu'il y a des arcs écartés
        assert any(char.isdigit() for char in messages), (
            "Le warning devrait contenir des chiffres (décomptes d'arcs écartés)"
        )

    def test_no_warning_when_already_sc(self):
        G = nx.DiGraph()
        for n in range(3):
            G.add_node(n, x=-73.6 + n*0.01, y=45.5)
        G.add_edge(0, 1, weight=1.0, priority=True,  length_km=1.0)
        G.add_edge(1, 2, weight=1.0, priority=False, length_km=1.0)
        G.add_edge(2, 0, weight=1.0, priority=True,  length_km=1.0)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            extract_main_scc(G)
        assert len(caught) == 0, "Aucun warning si le graphe est déjà fortement connexe"
