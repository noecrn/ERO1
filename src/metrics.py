"""
Module de calcul des métriques et des coûts selon les contraintes municipales.
"""

def calculer_couts_tournee(distance_totale_km, temps_total_h, nb_vehicules=1):
    """
    Calcule le coût financier d'une tournée selon le barème du README.
    """
    COUT_FIXE_JOUR = 500.0
    COUT_KM = 1.1
    COUT_HORAIRE_BASE = 1.1
    COUT_HORAIRE_SUPP = 1.3
    
    # Coût fixe
    cout_fixe = nb_vehicules * COUT_FIXE_JOUR
    
    # Coût kilométrique
    cout_km = distance_totale_km * COUT_KM
    
    # Coût horaire
    if temps_total_h <= 8:
        cout_h = temps_total_h * COUT_HORAIRE_BASE
    else:
        cout_h = (8 * COUT_HORAIRE_BASE) + ((temps_total_h - 8) * COUT_HORAIRE_SUPP)
        
    return {
        "cout_total": cout_fixe + cout_km + cout_h,
        "detail": {
            "fixe": cout_fixe,
            "km": cout_km,
            "horaire": cout_h
        }
    }
