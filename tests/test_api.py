"""HTTP contracts and engine parity; startup verification covered separately."""

from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_profiles import calculate, row

from football_recruitment.api import app as interface
from football_recruitment.config import RankingRequirement, load_settings
from football_recruitment.ranking.engine import rank_players
from football_recruitment.similarity.engine import find_similar_players


@pytest.fixture
def client(monkeypatch):
    settings = load_settings(Path("config"))
    profiles, _ = calculate([row(str(i), float(i)) for i in range(12)])
    original = deepcopy(profiles)
    monkeypatch.setattr(interface, "load_settings", lambda _: settings)
    monkeypatch.setattr(
        interface,
        "load_profiles",
        lambda *_: (profiles, {}, {"profile_manifest_sha256": "fixture", "full_cohort": False}),
    )
    with TestClient(interface.create_app(Path("config"), Path("fixture.json"))) as http:
        yield http, profiles, settings
        assert profiles == original


def test_explorer_assets_and_local_boundary(client):
    http, _, _ = client
    meta = http.get("/api/meta").json()
    assert meta["profile_count"] == 12
    assert meta["unsupported_fields"] == ["age", "market_value", "contracts"]
    assert len(http.get("/api/players?role=CB").json()) == 12
    assert http.get("/api/players?role=invalid").status_code == 422
    assert http.get("/api/profile?player_id=missing&team_id=team:1").status_code == 404
    for path in ("/", "/assets/app.js", "/assets/app.css"):
        result = http.get(path)
        assert result.status_code == 200
        assert result.headers["cache-control"] == "no-store"
        assert "frame-ancestors 'none'" in result.headers["content-security-policy"]
    assert http.get("/assets/unknown.json").status_code == 404
    assert http.get("/api/meta", headers={"Host": "untrusted.example"}).status_code == 400
    assert http.get("/api/meta", headers={"Origin": "https://other.example"}).status_code == 403
    assert http.get("/api/meta", headers={"Origin": "http://testserver"}).status_code == 200


def test_comparison_and_calculations_match_engines(client):
    http, profiles, settings = client
    refs = [{"player_id": str(i), "team_id": "team:1"} for i in range(3)]
    for count in (2, 3):
        result = http.post("/api/compare", json={"players": refs[:count]})
        assert result.status_code == 200
        assert result.json()["profiles"] == profiles[:count]
    for invalid in ([refs[0]], [refs[0], refs[0]], refs + [refs[0]]):
        assert http.post("/api/compare", json={"players": invalid}).status_code == 422
    assert http.get("/api/similar?player_id=0&team_id=team:1&top_k=3").json() == (
        find_similar_players(profiles, "0", "team:1", settings, top_k=3)
    )
    body = {"name": "Activity", "position_group": "CB", "weights": {"passes_attempted": 1}}
    assert http.post("/api/rank", json=body).json() == rank_players(
        profiles, RankingRequirement.model_validate(body), settings
    )
    for extra in ({"maximum_age": 23}, {"unexpected": True}, {"weights": {"shots": -1}}):
        assert http.post("/api/rank", json=body | extra).status_code == 422
    assert http.post("/api/rank", json=body | {"minimum_minutes": 400}).status_code == 400


def test_startup_verification_failure_has_no_fallback(monkeypatch):
    monkeypatch.setattr(interface, "load_settings", lambda _: load_settings(Path("config")))

    def corrupt(*args):
        raise ValueError("Corrupt profile manifest")

    monkeypatch.setattr(interface, "load_profiles", corrupt)
    with pytest.raises(ValueError, match="Corrupt profile manifest"):
        with TestClient(interface.create_app(Path("config"), Path("corrupt.json"))):
            pass
