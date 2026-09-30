"""HTTP endpoints. Everything under /v1 is JSON; errors are RFC 9457 problem+json."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Annotated, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Query, Request, Security
from fastapi.security import APIKeyHeader

from hora_api.api.cards import Card, day_card, personal_card, rasi_card
from hora_api.api.keys import LOCAL, KeyFileError, Principal
from hora_api.api.models import (
    BlockedOut,
    DashaOut,
    DayResponse,
    GowriOut,
    HealthResponse,
    HoraOut,
    Meta,
    PersonalResponse,
    ProfilesResponse,
    ProfileSummary,
    RasiResponse,
    ReadyResponse,
    SunOut,
    TransitionOut,
    localise,
)
from hora_api.api.problems import ProblemDetail, ProblemError
from hora_api.api.profiles import ProfileFileError
from hora_api.api.service import (
    ComputedDay,
    RequestParams,
    Services,
    compute_day,
    top_windows,
)
from hora_api.core import astro
from hora_api.core import day as D
from hora_api.core.astro import Ayanamsa
from hora_api.core.day import Convention
from hora_api.scoring.personal import Profile, resolve_dasha, score_horas
from hora_api.scoring.rasi import score_rasis

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

_PROBLEMS: dict[int | str, dict[str, Any]] = {
    401: {"model": ProblemDetail, "description": "Missing, invalid or revoked X-API-Key"},
    403: {"model": ProblemDetail, "description": "The key's tier does not allow this endpoint"},
    422: {"model": ProblemDetail, "description": "Invalid parameters"},
}


def services(request: Request) -> Services:
    svc: Services = request.app.state.services
    return svc


def authenticate(
    request: Request, key: Annotated[str | None, Security(api_key_header)] = None
) -> Principal:
    """Identify the caller from X-API-Key. Authentication is off when no key is configured."""
    keys = services(request).keys
    try:
        if not keys.auth_required():
            request.state.principal_id = LOCAL.id
            return LOCAL
        principal = keys.lookup(key)
    except KeyFileError as e:  # fail closed: a broken keys file never opens the API
        raise ProblemError(
            503, "Keys unavailable", "The keys file could not be loaded.",
            type_="urn:hora-api:problem:keys-unavailable",
        ) from e  # fmt: skip
    if principal is None:
        raise ProblemError(
            401, "Unauthorized", "A valid X-API-Key header is required.",
            type_="urn:hora-api:problem:unauthorized", headers={"WWW-Authenticate": "ApiKey"},
        )  # fmt: skip
    request.state.principal_id = principal.id
    return principal


Caller = Annotated[Principal, Depends(authenticate)]


def require_paid(caller: Caller) -> Principal:
    """Refuse free keys on the endpoints that need a subscription."""
    if not caller.is_paid:
        raise ProblemError(
            403, "Paid tier required",
            "This endpoint needs a paid subscription; your key is on the free tier.",
            type_="urn:hora-api:problem:tier-required", tier=caller.tier, required_tier="paid",
        )  # fmt: skip
    return caller


def request_params(
    request: Request,
    date_: Annotated[
        date | None, Query(alias="date", description="Local date; default today")
    ] = None,
    lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    lon: Annotated[float | None, Query(ge=-180, le=180)] = None,
    tz: Annotated[str | None, Query(description="IANA timezone, e.g. Asia/Kuala_Lumpur")] = None,
    convention: Annotated[Convention, Query(description="Hora convention")] = "tamil",
    ayanamsa: Annotated[Ayanamsa, Query()] = Ayanamsa.LAHIRI,
) -> RequestParams:
    cfg = services(request).settings
    tz_name = tz or cfg.default_tz
    try:
        zone = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError, OSError) as e:
        raise ProblemError(
            422, "Unknown timezone", f"{tz_name!r} is not an IANA timezone.",
            type_="urn:hora-api:problem:unknown-timezone",
        ) from e  # fmt: skip
    return RequestParams(
        date=date_ or datetime.now(zone).date(),
        lat=cfg.default_lat if lat is None else lat,
        lon=cfg.default_lon if lon is None else lon,
        tz_name=tz_name,
        tz=zone,
        convention=convention,
        ayanamsa=ayanamsa,
    )


Params = Annotated[RequestParams, Depends(request_params)]


def _meta(p: RequestParams) -> Meta:
    return Meta(
        date=p.date, weekday=p.date.strftime("%A"), tz=p.tz_name, lat=p.lat, lon=p.lon,
        convention=p.convention, ayanamsa=p.ayanamsa,
    )  # fmt: skip


def _computed(svc: Services, p: RequestParams) -> ComputedDay:
    try:
        return compute_day(svc, p)
    except ValueError as e:
        raise ProblemError(
            422, "No sunrise or sunset", str(e), type_="urn:hora-api:problem:no-sun-event"
        ) from e


def _unverified(svc: Services, used: set[str]) -> list[str]:
    known = svc.tables.unverified | svc.scoring_tables.unverified
    return sorted(used & known)


router = APIRouter(prefix="/v1", dependencies=[Depends(authenticate)], responses=_PROBLEMS)
PAID = [Depends(require_paid)]


@router.get("/day", response_model=DayResponse, summary="Panchangam day")
def get_day(request: Request, p: Params) -> DayResponse:
    """Sun events, nakshatra/rasi/tithi transitions, horas, blocked windows and the Gowri layer."""
    svc = services(request)
    cd = _computed(svc, p)
    names = svc.scoring_tables.names
    transitions = []
    for t in cd.transitions:
        pool = {"nakshatra": names.nakshatras, "rasi": names.rasis}.get(t.kind)
        transitions.append(
            TransitionOut(
                kind=t.kind,
                time=t.time,
                from_index=t.from_index,
                to_index=t.to_index,
                from_name=pool[t.from_index] if pool else None,
                to_name=pool[t.to_index] if pool else None,
            )  # fmt: skip
        )
    blocked = D.blocked_windows(cd.day, svc.tables)
    resp = DayResponse(
        meta=_meta(p),
        sun=SunOut(sunrise=cd.day.sunrise, sunset=cd.day.sunset, next_sunrise=cd.day.next_sunrise),
        transitions=transitions,
        horas=[
            HoraOut(start=h.start, end=h.end, lord=h.lord, is_night=h.is_night) for h in cd.horas
        ],
        blocked=[BlockedOut(start=b.start, end=b.end, reasons=list(b.reasons)) for b in blocked],
        gowri=[
            GowriOut(start=g.start, end=g.end, name=g.name, nature=g.nature, is_night=g.is_night)
            for g in cd.gowri
        ],
        unverified_tables=_unverified(svc, {"durmuhurta", "varjyam", "gowri"}),
    )
    return localise(resp, p.tz)


def _personal(svc: Services, p: RequestParams, profile: Profile) -> PersonalResponse:
    cd = _computed(svc, p)
    scored = score_horas(
        list(cd.horas), cd.day, profile, svc.tables, svc.scoring, svc.scoring_tables, p.ayanamsa
    )
    periods = resolve_dasha(profile, svc.tables, svc.scoring, p.ayanamsa) or []
    resp = PersonalResponse(
        meta=_meta(p),
        profile=ProfileSummary(id=profile.id, display_name=profile.display_name),
        horas=scored,
        dasha=[
            DashaOut(level=d.level, lord=d.lord, start=d.start, end=d.end)
            for d in periods
            if d.start < cd.day.next_sunrise and d.end > cd.day.sunrise
        ],
        top=top_windows(scored, cd.day, p.tz, svc.settings.min_window_minutes),
        unverified_tables=_unverified(svc, {"durmuhurta", "varjyam", "functional"}),
    )
    return localise(resp, p.tz)


def _stored_profile(svc: Services, profile_id: str, caller: Principal) -> Profile:
    try:
        profiles = svc.profiles.get()
    except ProfileFileError as e:
        raise ProblemError(
            503, "Profiles unavailable", "The profiles file could not be loaded.",
            type_="urn:hora-api:problem:profiles-unavailable",
        ) from e  # fmt: skip
    profile = profiles.get(profile_id)
    if profile is None or not caller.can_use(profile_id):  # same answer: no existence leak
        raise ProblemError(
            404, "Profile not found", f"No profile with id {profile_id!r}.",
            type_="urn:hora-api:problem:profile-not-found",
        )  # fmt: skip
    return profile


@router.get(
    "/horas/personal",
    response_model=PersonalResponse,
    summary="Scored horas for a stored profile",
    dependencies=PAID,
)
def personal_get(
    request: Request,
    p: Params,
    caller: Caller,
    profile_id: Annotated[str, Query(description="Id from GET /v1/profiles")],
) -> PersonalResponse:
    svc = services(request)
    return _personal(svc, p, _stored_profile(svc, profile_id, caller))


@router.post(
    "/horas/personal",
    response_model=PersonalResponse,
    summary="Scored horas for an inline profile",
    dependencies=PAID,
)
def personal_post(request: Request, p: Params, profile: Profile) -> PersonalResponse:
    """For clients that do not store profiles. Nothing in the body is stored."""
    return _personal(services(request), p, profile)


@router.get(
    "/horas/rasi", response_model=RasiResponse, summary="12 x 24 rasi matrix", dependencies=PAID
)
def rasi_matrix(request: Request, p: Params) -> RasiResponse:
    """Every rasi against every hora by chandrabala alone, plus per-rasi day percentages."""
    svc = services(request)
    cd = _computed(svc, p)
    m = score_rasis(list(cd.horas), cd.day, svc.tables, svc.scoring, svc.scoring_tables)
    used = {"durmuhurta", "varjyam"} | (
        {"hora_generic"} if svc.scoring.rasi_hora_generic else set()
    )
    resp = RasiResponse(
        meta=_meta(p), horas=m.horas, rasis=m.rasis, unverified_tables=_unverified(svc, used)
    )
    return localise(resp, p.tz)


@router.get("/cards/day", response_model=Card, summary="Day summary chat card")
def card_day(request: Request, p: Params) -> Card:
    """Client-neutral card: sun, moon, windows to avoid, Nalla Neram (Gowri) and horas."""
    svc = services(request)
    cd = _computed(svc, p)
    unverified = _unverified(svc, {"durmuhurta", "varjyam", "gowri"})
    return day_card(p, cd, svc.tables, svc.scoring_tables.names, unverified)


@router.get(
    "/cards/rasi", response_model=Card, summary="Rasi overview chat card", dependencies=PAID
)
def card_rasi(request: Request, p: Params) -> Card:
    """Client-neutral card: Chandrashtama rasis, best rasis and all twelve day percentages."""
    svc = services(request)
    cd = _computed(svc, p)
    matrix = score_rasis(list(cd.horas), cd.day, svc.tables, svc.scoring, svc.scoring_tables)
    used = {"durmuhurta", "varjyam"} | (
        {"hora_generic"} if svc.scoring.rasi_hora_generic else set()
    )
    return rasi_card(p, cd, matrix, svc.scoring_tables.names, _unverified(svc, used))


@router.get(
    "/cards/personal", response_model=Card, summary="Personal windows chat card", dependencies=PAID
)
def card_personal(
    request: Request,
    p: Params,
    caller: Caller,
    profile_id: Annotated[str, Query(description="Id from GET /v1/profiles")],
) -> Card:
    """Client-neutral card: best windows, why horas are blocked, and tara/chandra for a profile."""
    svc = services(request)
    profile = _stored_profile(svc, profile_id, caller)
    cd = _computed(svc, p)
    scored = score_horas(
        list(cd.horas), cd.day, profile, svc.tables, svc.scoring, svc.scoring_tables, p.ayanamsa
    )
    top = top_windows(scored, cd.day, p.tz, svc.settings.min_window_minutes)
    unverified = _unverified(svc, {"durmuhurta", "varjyam", "functional"})
    return personal_card(p, cd, profile, scored, top, svc.scoring_tables, svc.scoring, unverified)


@router.get(
    "/profiles", response_model=ProfilesResponse, summary="Stored profile ids", dependencies=PAID
)
def list_profiles(request: Request, caller: Caller) -> ProfilesResponse:
    """Ids and display names of the stored profiles this key may use; never birth data."""
    try:
        profiles = services(request).profiles.get()
    except ProfileFileError as e:
        raise ProblemError(
            503, "Profiles unavailable", "The profiles file could not be loaded.",
            type_="urn:hora-api:problem:profiles-unavailable",
        ) from e  # fmt: skip
    return ProfilesResponse(
        profiles=[
            ProfileSummary(id=p.id, display_name=p.display_name)
            for p in profiles.values()
            if caller.can_use(p.id)
        ]
    )


health = APIRouter(tags=["health"])


@health.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    """Liveness: the process is up."""
    return HealthResponse(status="ok")


@health.get("/readyz", response_model=ReadyResponse, responses={503: {"model": ProblemDetail}})
def readyz(request: Request) -> ReadyResponse:
    """Readiness: the ephemeris answers and the profiles and keys files load."""
    try:
        astro.moon_state(datetime.now(UTC))
    except Exception as e:  # swisseph raises assorted errors
        raise ProblemError(
            503, "Ephemeris unavailable", "The ephemeris could not be used.",
            type_="urn:hora-api:problem:ephemeris-unavailable",
        ) from e  # fmt: skip
    try:
        services(request).keys.auth_required()
    except KeyFileError as e:
        raise ProblemError(
            503, "Keys unavailable", "The keys file could not be loaded.",
            type_="urn:hora-api:problem:keys-unavailable",
        ) from e  # fmt: skip
    try:
        count = len(services(request).profiles.get())
    except ProfileFileError as e:
        raise ProblemError(
            503, "Profiles unavailable", "The profiles file could not be loaded.",
            type_="urn:hora-api:problem:profiles-unavailable",
        ) from e  # fmt: skip
    return ReadyResponse(status="ready", profiles=count)
