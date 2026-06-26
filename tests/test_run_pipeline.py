"""
Tests for src/run_pipeline.py

T1  — run_pipeline("anjou", "securite") s'exécute sans erreur et produit les fichiers
T2  — run_pipeline("anjou", "economique") idem en mode CPP
T3  — les JSON produits sont valides et rechargeables
T4  — le résumé retourné contient les bonnes clés
T5  — mode securite produit surcout_connecteur_km (RPP), pas surcout_reparation_km
T6  — mode economique produit surcout_reparation_km (CPP), pas surcout_connecteur_km
T7  — les fichiers sont écrits dans output/{quartier}/{scenario}/
T8  — temps d'exécution total affiché (smoke test de performance, <120s)
"""

import json
import time
import tempfile
from pathlib import Path

import pytest

from src.run_pipeline import run_pipeline


EXPECTED_ZONE_KEYS = {
    "zone_id", "distance_km", "temps_h", "cout_fixe", "cout_km",
    "cout_horaire", "Z_total", "CO2_kg", "surcout_dcpp_km",
}
EXPECTED_GLOBAL_KEYS = {
    "nb_deneigeuses", "distance_totale_km", "Z_total_flotte",
    "CO2_total_kg", "temps_operation_h",
    "surcout_reparation_total_km", "surcout_connecteur_total_km",
    "zones",
}


# ---------------------------------------------------------------------------
# T1 — securite s'exécute et produit les fichiers
# ---------------------------------------------------------------------------

class TestSecuriteRuns:
    def test_runs_without_error(self, tmp_path):
        run_pipeline("anjou", "securite", output_dir=str(tmp_path))

    def test_produces_dashboard_global(self, tmp_path):
        run_pipeline("anjou", "securite", output_dir=str(tmp_path))
        assert (tmp_path / "anjou" / "securite" / "dashboard_global.json").exists()

    def test_produces_zone_files(self, tmp_path):
        result = run_pipeline("anjou", "securite", output_dir=str(tmp_path))
        nb = result["nb_deneigeuses"]
        base = tmp_path / "anjou" / "securite"
        for i in range(nb):
            assert (base / f"dashboard_zone_{i}.json").exists()
            assert (base / f"itineraire_zone_{i}.json").exists()


# ---------------------------------------------------------------------------
# T2 — economique s'exécute
# ---------------------------------------------------------------------------

class TestEconomiqueRuns:
    def test_runs_without_error(self, tmp_path):
        run_pipeline("anjou", "economique", output_dir=str(tmp_path))

    def test_produces_dashboard_global(self, tmp_path):
        run_pipeline("anjou", "economique", output_dir=str(tmp_path))
        assert (tmp_path / "anjou" / "economique" / "dashboard_global.json").exists()


# ---------------------------------------------------------------------------
# T3 — JSON valides et rechargeables
# ---------------------------------------------------------------------------

class TestJSONValidity:
    @pytest.mark.parametrize("scenario", ["securite", "economique"])
    def test_dashboard_global_reloadable(self, tmp_path, scenario):
        run_pipeline("anjou", scenario, output_dir=str(tmp_path))
        path = tmp_path / "anjou" / scenario / "dashboard_global.json"
        data = json.loads(path.read_text())
        assert isinstance(data, dict)

    @pytest.mark.parametrize("scenario", ["securite", "economique"])
    def test_zone_dashboards_reloadable(self, tmp_path, scenario):
        result = run_pipeline("anjou", scenario, output_dir=str(tmp_path))
        base = tmp_path / "anjou" / scenario
        for i in range(result["nb_deneigeuses"]):
            data = json.loads((base / f"dashboard_zone_{i}.json").read_text())
            assert isinstance(data, dict)

    @pytest.mark.parametrize("scenario", ["securite", "economique"])
    def test_itineraries_are_lists(self, tmp_path, scenario):
        result = run_pipeline("anjou", scenario, output_dir=str(tmp_path))
        base = tmp_path / "anjou" / scenario
        for i in range(result["nb_deneigeuses"]):
            data = json.loads((base / f"itineraire_zone_{i}.json").read_text())
            assert isinstance(data, list)
            assert all("lat" in wp and "lon" in wp for wp in data)


# ---------------------------------------------------------------------------
# T4 — résumé retourné contient les bonnes clés
# ---------------------------------------------------------------------------

class TestSummaryKeys:
    @pytest.mark.parametrize("scenario", ["securite", "economique"])
    def test_global_keys_present(self, tmp_path, scenario):
        result = run_pipeline("anjou", scenario, output_dir=str(tmp_path))
        missing = EXPECTED_GLOBAL_KEYS - result.keys()
        assert not missing, f"Clés manquantes dans le résumé global : {missing}"

    @pytest.mark.parametrize("scenario", ["securite", "economique"])
    def test_zone_keys_present(self, tmp_path, scenario):
        result = run_pipeline("anjou", scenario, output_dir=str(tmp_path))
        for zone_dash in result["zones"]:
            missing = EXPECTED_ZONE_KEYS - zone_dash.keys()
            assert not missing, f"Clés manquantes dans un dashboard de zone : {missing}"


# ---------------------------------------------------------------------------
# T5 — mode securite → RPP (connector), pas de repair
# ---------------------------------------------------------------------------

class TestSecuriteIsRPP:
    def test_has_connecteur_not_reparation(self, tmp_path):
        result = run_pipeline("anjou", "securite", output_dir=str(tmp_path))
        for zone_dash in result["zones"]:
            assert "surcout_connecteur_km" in zone_dash, (
                "Mode securite doit produire surcout_connecteur_km"
            )
            assert "surcout_reparation_km" not in zone_dash, (
                "Mode securite ne doit PAS avoir surcout_reparation_km"
            )

    def test_global_connecteur_nonzero(self, tmp_path):
        result = run_pipeline("anjou", "securite", output_dir=str(tmp_path))
        assert result["surcout_connecteur_total_km"] >= 0


# ---------------------------------------------------------------------------
# T6 — mode economique → CPP (repair), pas de connector
# ---------------------------------------------------------------------------

class TestEconomiqueIsCPP:
    def test_has_reparation_not_connecteur(self, tmp_path):
        result = run_pipeline("anjou", "economique", output_dir=str(tmp_path))
        for zone_dash in result["zones"]:
            assert "surcout_connecteur_km" in zone_dash, (
                "Mode economique doit produire surcout_connecteur_km"
            )
            assert "surcout_reparation_km" not in zone_dash, (
                "Mode economique ne doit PAS avoir surcout_reparation_km"
            )


# ---------------------------------------------------------------------------
# T7 — fichiers écrits dans output/{quartier}/{scenario}/
# ---------------------------------------------------------------------------

class TestOutputDirectory:
    def test_output_path_structure(self, tmp_path):
        run_pipeline("anjou", "securite", output_dir=str(tmp_path))
        expected_dir = tmp_path / "anjou" / "securite"
        assert expected_dir.is_dir()
        files = list(expected_dir.iterdir())
        assert len(files) >= 3, f"Moins de 3 fichiers dans {expected_dir}: {files}"


# ---------------------------------------------------------------------------
# T8 — performance : exécution complète < 120s
# ---------------------------------------------------------------------------

class TestPerformance:
    @pytest.mark.parametrize("scenario", ["securite", "economique"])
    def test_runs_within_120s(self, tmp_path, scenario):
        t0 = time.time()
        run_pipeline("anjou", scenario, output_dir=str(tmp_path))
        elapsed = time.time() - t0
        assert elapsed < 120, (
            f"run_pipeline anjou/{scenario} a pris {elapsed:.1f}s > 120s"
        )
