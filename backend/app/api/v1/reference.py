"""Reference-data routes (§6.2).

Every dropdown in the frontend is populated from here. These lists change perhaps once
a year, so responses carry ``Cache-Control: max-age=300`` and the browser stops asking.

``/reference/all`` returns every list in one response. The programme form alone needs
six of them, and six round trips to render one form is the kind of waste that is
invisible on a developer's laptop and obvious over a district's connection.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.api.deps import CurrentUser, DbSession
from app.repositories.reference_repo import ReferenceRepository
from app.schemas.reference import (
    CategoryRef,
    DirectorateRef,
    InstitutionRef,
    LevelRef,
    RankRef,
    ReferenceBundle,
    RegionRef,
    RoleRef,
    SpecializationRef,
    StationRef,
)

router = APIRouter(prefix="/reference", tags=["Reference data"])

#: Five minutes. Long enough to spare the round trips, short enough that an
#: administrator adding a station sees it within one coffee break.
CACHE_SECONDS = 300


def get_repo(session: DbSession) -> ReferenceRepository:
    """Construct the reference repository for this request."""
    return ReferenceRepository(session)


RepoDep = Annotated[ReferenceRepository, Depends(get_repo)]


def _cache(response: Response) -> None:
    """Apply the shared cache header."""
    response.headers["Cache-Control"] = f"max-age={CACHE_SECONDS}, private"


@router.get(
    "/all",
    summary="Every lookup list in one response",
    description=(
        "Returns all ten reference lists together. Preferred over the individual "
        "endpoints when a screen needs more than one — the programme form needs six, "
        "and one request is better than six."
    ),
    response_model=ReferenceBundle,
    responses={200: {"description": "Every reference list."}},
)
async def all_reference(repo: RepoDep, user: CurrentUser, response: Response) -> ReferenceBundle:
    """Return every reference list.

    Args:
        repo: Reference repository.
        user: The authenticated caller.
        response: Used to set the cache header.

    Returns:
        Every lookup list.
    """
    _ = user
    _cache(response)
    return ReferenceBundle(
        roles=[RoleRef.model_validate(r) for r in await repo.roles()],
        ranks=[RankRef.model_validate(r) for r in await repo.ranks()],
        directorates=[DirectorateRef.model_validate(r) for r in await repo.directorates()],
        regions=[RegionRef.model_validate(r) for r in await repo.regions()],
        stations=[StationRef.model_validate(r) for r in await repo.stations()],
        specializations=[SpecializationRef.model_validate(r) for r in await repo.specializations()],
        categories=[CategoryRef.model_validate(r) for r in await repo.categories()],
        institutions=[InstitutionRef.model_validate(r) for r in await repo.institutions()],
        qualification_levels=[
            LevelRef.model_validate(r) for r in await repo.qualification_levels()
        ],
        proficiency_levels=[LevelRef.model_validate(r) for r in await repo.proficiency_levels()],
    )


@router.get(
    "/specializations",
    summary="Training disciplines",
    description=(
        "The controlled vocabulary BR-04 matches against. `disciplineGroup` is the "
        "subject grouping that drives the specialisation breadth bonus and decides "
        "whether a past evaluation counts as relevant to a given course."
    ),
    response_model=list[SpecializationRef],
    responses={200: {"description": "Active specialisation areas."}},
)
async def specializations(
    repo: RepoDep, user: CurrentUser, response: Response
) -> list[SpecializationRef]:
    """Return the specialisation areas."""
    _ = user
    _cache(response)
    return [SpecializationRef.model_validate(r) for r in await repo.specializations()]


@router.get(
    "/categories",
    summary="Training delivery categories",
    description=(
        "How a course is run — Refresher, Induction, Pre-Deployment — which is a "
        "different axis from what it is *about*. A Refresher course may be about "
        "Cybercrime Investigation; see `/reference/specializations` for subject."
    ),
    response_model=list[CategoryRef],
    responses={200: {"description": "Active training categories."}},
)
async def categories(repo: RepoDep, user: CurrentUser, response: Response) -> list[CategoryRef]:
    """Return the training categories."""
    _ = user
    _cache(response)
    return [CategoryRef.model_validate(r) for r in await repo.categories()]


@router.get(
    "/stations",
    summary="Stations, headquarters, and training institutions",
    description="Postings and course venues, with their region.",
    response_model=list[StationRef],
    responses={200: {"description": "Active stations."}},
)
async def stations(repo: RepoDep, user: CurrentUser, response: Response) -> list[StationRef]:
    """Return the stations."""
    _ = user
    _cache(response)
    return [StationRef.model_validate(r) for r in await repo.stations()]


@router.get(
    "/regions",
    summary="Policing regions",
    response_model=list[RegionRef],
    description="UPF policing regions with their headquarters town.",
    responses={200: {"description": "Regions."}},
)
async def regions(repo: RepoDep, user: CurrentUser, response: Response) -> list[RegionRef]:
    """Return the regions."""
    _ = user
    _cache(response)
    return [RegionRef.model_validate(r) for r in await repo.regions()]


@router.get(
    "/ranks",
    summary="The rank ladder",
    description=(
        "Junior to senior. Sort and compare on `seniorityOrder`, never on `code` — "
        "'ACP' sorts before 'PC' alphabetically and outranks it by nine steps."
    ),
    response_model=list[RankRef],
    responses={200: {"description": "Police ranks, junior first."}},
)
async def ranks(repo: RepoDep, user: CurrentUser, response: Response) -> list[RankRef]:
    """Return the rank ladder."""
    _ = user
    _cache(response)
    return [RankRef.model_validate(r) for r in await repo.ranks()]


@router.get(
    "/directorates",
    summary="UPF directorates",
    description="`isTrainingAuthority` marks Human Resource Development, which owns training.",
    response_model=list[DirectorateRef],
    responses={200: {"description": "Directorates."}},
)
async def directorates(
    repo: RepoDep, user: CurrentUser, response: Response
) -> list[DirectorateRef]:
    """Return the directorates."""
    _ = user
    _cache(response)
    return [DirectorateRef.model_validate(r) for r in await repo.directorates()]


@router.get(
    "/institutions",
    summary="Qualification-awarding institutions",
    description=(
        "Police colleges appear first. `institutionType == 'POLICE'` is load-bearing: "
        "it earns the qualification scoring bonus, and it is a column rather than a "
        "hard-coded name list, so a newly added school qualifies automatically."
    ),
    response_model=list[InstitutionRef],
    responses={200: {"description": "Institutions, police colleges first."}},
)
async def institutions(
    repo: RepoDep, user: CurrentUser, response: Response
) -> list[InstitutionRef]:
    """Return the institutions."""
    _ = user
    _cache(response)
    return [InstitutionRef.model_validate(r) for r in await repo.institutions()]


@router.get(
    "/qualification-levels",
    summary="Qualification levels",
    description=(
        "Ordered lowest to highest, with the `scoreValue` the algorithm assigns. The "
        "score lives in the database so policy can be retuned with an UPDATE rather "
        "than a deployment (NFR-10)."
    ),
    response_model=list[LevelRef],
    responses={200: {"description": "Qualification levels, lowest first."}},
)
async def qualification_levels(
    repo: RepoDep, user: CurrentUser, response: Response
) -> list[LevelRef]:
    """Return qualification levels."""
    _ = user
    _cache(response)
    return [LevelRef.model_validate(r) for r in await repo.qualification_levels()]


@router.get(
    "/proficiency-levels",
    summary="Proficiency levels",
    description="Basic to Expert, with the score each contributes to the specialisation match.",
    response_model=list[LevelRef],
    responses={200: {"description": "Proficiency levels, lowest first."}},
)
async def proficiency_levels(
    repo: RepoDep, user: CurrentUser, response: Response
) -> list[LevelRef]:
    """Return proficiency levels."""
    _ = user
    _cache(response)
    return [LevelRef.model_validate(r) for r in await repo.proficiency_levels()]


@router.get(
    "/roles",
    summary="System roles",
    description="The four SRS actors, for the user-administration screens.",
    response_model=list[RoleRef],
    responses={200: {"description": "Roles."}},
)
async def roles(repo: RepoDep, user: CurrentUser, response: Response) -> list[RoleRef]:
    """Return the system roles."""
    _ = user
    _cache(response)
    return [RoleRef.model_validate(r) for r in await repo.roles()]
