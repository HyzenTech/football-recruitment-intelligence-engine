import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from football_recruitment.cli import main
from football_recruitment.config import (
    CohortSettings,
    DataPaths,
    DatasetSettings,
    RankingSettings,
    load_settings,
)

ROOT = Path(__file__).resolve().parents[1]


def test_repository_config_preserves_audit_pin_and_unsupported_filters():
    value = load_settings(ROOT / "config")
    assert (value.dataset.competition_id, value.dataset.season_id) == (37, 281)
    assert value.dataset.revision == "4b73468fc5b0f1950f9f66fada70ad3a4f9327cb"
    assert value.dataset.expected_match_count == 132
    assert value.ranking.age_filter_enabled is False and value.ranking.weights == {}


def test_mutable_branch_and_mismatched_license_pin_are_rejected():
    data = load_settings(ROOT / "config").dataset.model_dump()
    with pytest.raises(ValidationError):
        DatasetSettings.model_validate(data | {"revision": "master"})
    with pytest.raises(ValidationError, match="same pinned revision"):
        DatasetSettings.model_validate(data | {"revision": "a" * 40})


@pytest.mark.parametrize("raw", ["../raw", "/tmp/raw", "C:\\outside", ".", ""])
def test_configuration_cannot_escape_or_equal_project_root(raw):
    with pytest.raises(ValidationError):
        DataPaths(raw=raw, interim="data/interim", processed="data/processed", reports="outputs")


@pytest.mark.parametrize("interim", ["data\\raw", "DATA/RAW"])
def test_data_stages_cannot_alias_or_nest(interim):
    with pytest.raises(ValidationError, match="distinct paths"):
        DataPaths(raw="data/raw", interim=interim, processed="data/processed", reports="outputs")
    with pytest.raises(ValidationError, match="nested"):
        DataPaths(raw="data", interim="data/interim", processed="data/processed", reports="outputs")


def test_role_mapping_cannot_duplicate_or_omit_positions():
    data = load_settings(ROOT / "config").cohorts.model_dump()
    groups = dict(data["position_groups"])
    groups["CM"] = (13, 14, 15, 1)
    with pytest.raises(ValidationError, match="exactly once"):
        CohortSettings.model_validate(data | {"position_groups": groups})


def test_ranking_cannot_enable_age_or_unimplemented_scores():
    data = load_settings(ROOT / "config").ranking.model_dump()
    with pytest.raises(ValidationError):
        RankingSettings.model_validate(data | {"age_filter_enabled": True})
    with pytest.raises(ValidationError, match="named requirements"):
        RankingSettings.model_validate(data | {"weights": {"invented": 1.0}})


def test_cli_check_does_not_claim_data_validation(capsys):
    assert main(["check", "--config-dir", str(ROOT / "config")]) == 0
    value = json.loads(capsys.readouterr().out)
    assert value["configuration"] == "valid"
    assert value["data_validation"] == "not_run"
    assert value["provider_adapter"] == "statsbomb_open_data"
    assert value["network_access"] is False


def test_bad_config_cli_returns_nonzero_with_error(tmp_path, capsys):
    assert main(["check", "--config-dir", str(tmp_path)]) == 2
    assert "Command failed" in capsys.readouterr().err


def test_status_lists_only_implemented_foundation(capsys):
    assert main(["status"]) == 0
    value = json.loads(capsys.readouterr().out)
    assert value["provider_adapters_implemented"] == ["statsbomb_open_data"]
    assert value["completed_phase"] == 10
    assert "external_expert_and_predictive_validation" in value["deferred"]
    assert "transparent_requirement_rankings" in value["implemented"]
