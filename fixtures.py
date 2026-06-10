"""
Mock fixture for pipeline steps 1-4.

make_mock_graph() returns a (G, depots) pair that mimics the output of steps 1-4:
  - G: nx.DiGraph already filtered (h_neige kept for traceability only)
  - depots: list of node IDs representing snowplow garages

Replace this module once real step-4 output is available.
"""

import networkx as nx


def make_mock_graph() -> tuple[nx.DiGraph, list]:
    """
    Build a toy directed graph of ~18 Montreal intersections.

    Nodes carry:
        x  (float) — longitude  (~-73.57)
        y  (float) — latitude   (~45.50)

    Edges carry:
        weight  (float) — road segment length in km (0.10 – 1.50)
        h_neige (float) — snow depth in cm (2.5 – 15.0), kept for traceability

    A handful of arcs are one-way (no reverse arc) to exercise directed logic.

    Returns
    -------
    G      : nx.DiGraph
    depots : list of 3 node IDs that exist in G
    """
    G = nx.DiGraph()

    # ------------------------------------------------------------------
    # Nodes — rough 3-column grid around Plateau-Mont-Royal / Rosemont
    # IDs 0-17, positions in (lon, lat) = (x, y)
    # ------------------------------------------------------------------
    nodes = [
        # Column west  (x ≈ -73.600)
        (0,  {"x": -73.600, "y": 45.515}),
        (1,  {"x": -73.600, "y": 45.510}),
        (2,  {"x": -73.600, "y": 45.505}),
        (3,  {"x": -73.600, "y": 45.500}),
        (4,  {"x": -73.600, "y": 45.495}),
        (5,  {"x": -73.600, "y": 45.490}),
        # Column centre (x ≈ -73.585)
        (6,  {"x": -73.585, "y": 45.515}),
        (7,  {"x": -73.585, "y": 45.510}),
        (8,  {"x": -73.585, "y": 45.505}),
        (9,  {"x": -73.585, "y": 45.500}),
        (10, {"x": -73.585, "y": 45.495}),
        (11, {"x": -73.585, "y": 45.490}),
        # Column east   (x ≈ -73.570)
        (12, {"x": -73.570, "y": 45.515}),
        (13, {"x": -73.570, "y": 45.510}),
        (14, {"x": -73.570, "y": 45.505}),
        (15, {"x": -73.570, "y": 45.500}),
        (16, {"x": -73.570, "y": 45.495}),
        (17, {"x": -73.570, "y": 45.490}),
    ]
    G.add_nodes_from(nodes)

    # ------------------------------------------------------------------
    # Edges — (u, v, weight_km, h_neige_cm)
    # Vertical arteries are bidirectional; a few cross-streets are one-way.
    # ------------------------------------------------------------------
    edges = [
        # West column — bidirectional N↔S
        (0, 1, 0.55, 8.0),  (1, 0, 0.55, 8.0),
        (1, 2, 0.55, 9.5),  (2, 1, 0.55, 9.5),
        (2, 3, 0.55, 7.0),  (3, 2, 0.55, 7.0),
        (3, 4, 0.55, 11.0), (4, 3, 0.55, 11.0),
        (4, 5, 0.55, 6.5),  (5, 4, 0.55, 6.5),

        # Centre column — bidirectional N↔S
        (6,  7,  0.55, 10.0), (7,  6,  0.55, 10.0),
        (7,  8,  0.55, 12.5), (8,  7,  0.55, 12.5),
        (8,  9,  0.55, 5.0),  (9,  8,  0.55, 5.0),
        (9,  10, 0.55, 14.0), (10, 9,  0.55, 14.0),
        (10, 11, 0.55, 3.5),  (11, 10, 0.55, 3.5),

        # East column — bidirectional N↔S
        (12, 13, 0.55, 7.5),  (13, 12, 0.55, 7.5),
        (13, 14, 0.55, 13.0), (14, 13, 0.55, 13.0),
        (14, 15, 0.55, 4.5),  (15, 14, 0.55, 4.5),
        (15, 16, 0.55, 9.0),  (16, 15, 0.55, 9.0),
        (16, 17, 0.55, 6.0),  (17, 16, 0.55, 6.0),

        # Cross-streets W↔C — bidirectional
        (0, 6,  1.10, 8.5),  (6,  0,  1.10, 8.5),
        (3, 9,  1.10, 11.5), (9,  3,  1.10, 11.5),
        (5, 11, 1.10, 5.5),  (11, 5,  1.10, 5.5),

        # Cross-streets C↔E — bidirectional
        (6,  12, 1.10, 9.5),  (12, 6,  1.10, 9.5),
        (9,  15, 1.10, 7.5),  (15, 9,  1.10, 7.5),
        (11, 17, 1.10, 4.0),  (17, 11, 1.10, 4.0),

        # One-way cross-streets (no reverse arc — directed only)
        (1, 7,  1.10, 6.0),   # W→C, north area, one-way east
        (7, 13, 1.10, 8.0),   # C→E, north area, one-way east
        (4, 10, 1.10, 12.0),  # W→C, south area, one-way east
        (10, 16, 1.10, 9.0),  # C→E, south area, one-way east

        # Diagonal shortcut (one-way) for variety
        (2, 8,  0.80, 15.0),  # W→C diagonal
        (8, 14, 0.80, 10.5),  # C→E diagonal
    ]

    for u, v, w, h in edges:
        G.add_edge(u, v, weight=w, h_neige=h)

    # ------------------------------------------------------------------
    # Depots — three garage locations, one per zone
    # Node 0: north-west depot
    # Node 9: centre depot
    # Node 17: south-east depot
    # ------------------------------------------------------------------
    depots = [0, 9, 17]

    return G, depots
