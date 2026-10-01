"""Loopback FastAPI interface; no provider reads or data writes in request handlers."""

from contextlib import asynccontextmanager
from copy import deepcopy
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import Field, model_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from football_recruitment import __version__
from football_recruitment.config import RankingRequirement, load_settings
from football_recruitment.domain.models import Contract, PositionGroup
from football_recruitment.ranking.engine import rank_players
from football_recruitment.similarity.engine import find_similar_players
from football_recruitment.similarity.pipeline import load_profiles


class PlayerRef(Contract):
    player_id: str
    team_id: str


class ComparisonRequest(Contract):
    players: Annotated[list[PlayerRef], Field(min_length=2, max_length=3)]

    @model_validator(mode="after")
    def require_distinct_records(self):
        if len({(p.player_id, p.team_id) for p in self.players}) != len(self.players):
            raise ValueError("Choose distinct player/team records")
        return self


def create_app(config_dir: Path, profile_manifest: Path):
    @asynccontextmanager
    async def lifespan(app):
        settings = load_settings(config_dir)
        profiles, _, verified = load_profiles(
            settings, config_dir.resolve().parent, profile_manifest.resolve()
        )
        app.state.settings = settings
        app.state.profiles = profiles
        app.state.index = {(p["player_id"], p["team_id"]): p for p in profiles}
        app.state.verified = verified
        yield
        app.state.index.clear()
        app.state.profiles.clear()

    app = FastAPI(
        title="Football Recruitment Intelligence",
        version=__version__,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
    )
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
    )
    assets = Path(__file__).parent / "web"

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin and origin != "http://" + request.headers.get("host", ""):
            return JSONResponse(
                {"detail": "Cross-origin requests are not supported"}, status_code=403
            )
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; "
            "img-src 'self'; frame-ancestors 'none'; base-uri 'none'"
        )
        return response

    @app.exception_handler(ValueError)
    async def invalid_request(request, error):
        return JSONResponse({"detail": str(error)}, status_code=400)

    def lookup(player_id, team_id):
        row = app.state.index.get((player_id, team_id))
        if row is None:
            raise HTTPException(404, "Player/team record not found in this snapshot")
        return row

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(assets / "index.html")

    @app.get("/assets/app.js", include_in_schema=False)
    def javascript():
        return FileResponse(assets / "app.js", media_type="text/javascript")

    @app.get("/assets/app.css", include_in_schema=False)
    def stylesheet():
        return FileResponse(assets / "app.css", media_type="text/css")

    @app.get("/api/meta")
    def metadata():
        settings = app.state.settings
        return {
            "competition": settings.dataset.competition_name,
            "season": settings.dataset.season_name,
            "source_credit": "StatsBomb Open Data",
            "usage": "Local noncommercial research",
            "revision": settings.dataset.revision,
            "profile_manifest_sha256": app.state.verified["profile_manifest_sha256"],
            "full_cohort": app.state.verified["full_cohort"],
            "profile_count": len(app.state.profiles),
            "unique_players": len({p["player_id"] for p in app.state.profiles}),
            "eligible_profiles": sum(p["peer_eligible"] for p in app.state.profiles),
            "minimum_minutes": settings.cohorts.minimum_minutes,
            "minimum_peers": settings.cohorts.minimum_peer_count,
            "minutes_convention": settings.cohorts.minutes_convention,
            "roles": [p.value for p in PositionGroup],
            "requirements": {
                name: r.model_dump(mode="json") for name, r in settings.ranking.requirements.items()
            },
            "ranking_metrics": {
                role.value: sorted(
                    set(app.state.profiles[0]["metrics"])
                    - {"average_shot_distance", "average_action_x", "average_action_y"}
                )
                if role != PositionGroup.GK
                else ["passes_attempted", "passes_completed", "pass_completion_pct", "long_passes"]
                for role in PositionGroup
            }
            if app.state.profiles
            else {},
            "unsupported_fields": ["age", "market_value", "contracts"],
            "limits": [
                "One historical league; event activity is not overall ability",
                "Goalkeeper comparisons cover distribution only",
                "Expert and predictive validation are unperformed",
            ],
        }

    @app.get("/api/players")
    def players(q: Annotated[str, Query(max_length=100)] = "", role: PositionGroup | None = None):
        return [
            {
                k: p[k]
                for k in (
                    "player_id",
                    "player_name",
                    "team_id",
                    "team_name",
                    "primary_position_group",
                    "denominator_minutes",
                    "peer_eligible",
                    "partial_player_season",
                )
            }
            for p in app.state.profiles
            if (role is None or p["primary_position_group"] == role)
            and q.casefold() in (p["player_name"] + " " + p["team_name"]).casefold()
        ]

    @app.get("/api/profile")
    def profile(player_id: str, team_id: str):
        return deepcopy(lookup(player_id, team_id))

    @app.post("/api/compare")
    def compare(body: ComparisonRequest):
        profiles = [deepcopy(lookup(p.player_id, p.team_id)) for p in body.players]
        warnings = ["Each percentile uses its own position and complete metric peer population"]
        if len({p["primary_position_group"] for p in profiles}) > 1:
            warnings.append(
                "Different position groups: percentile values are not a shared benchmark"
            )
        return {"profiles": profiles, "warnings": warnings}

    @app.get("/api/similar")
    def similar(player_id: str, team_id: str, top_k: Annotated[int, Query(ge=1, le=50)] = 10):
        lookup(player_id, team_id)
        return find_similar_players(
            app.state.profiles, player_id, team_id, app.state.settings, top_k=top_k
        )

    @app.post("/api/rank")
    def rank(body: RankingRequirement):
        return rank_players(app.state.profiles, body, app.state.settings)

    return app


def serve(config_dir, profile_manifest, port=8765):
    if isinstance(port, bool) or not isinstance(port, int) or not 1024 <= port <= 65535:
        raise ValueError("Local interface port must be from 1024 to 65535")
    import uvicorn

    uvicorn.run(
        create_app(config_dir, profile_manifest), host="127.0.0.1", port=port, access_log=False
    )
