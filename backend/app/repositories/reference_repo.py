"""Reference-data queries (§6.2).

Read-only lookup lists. Each returns a projection — column tuples, not hydrated ORM
entities — because nothing here needs identity-map tracking or relationship loading,
and a projection skips both.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import Row, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reference import (
    Directorate,
    Institution,
    PoliceRank,
    ProficiencyLevel,
    QualificationLevel,
    Region,
    Role,
    SpecializationArea,
    Station,
    TrainingCategory,
)


class ReferenceRepository:
    """Queries for the ten reference tables.

    Args:
        session: The request's session.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def roles(self) -> Sequence[Row[Any]]:
        """Return the four system roles, in seniority order of responsibility."""
        result = await self._session.execute(
            select(Role.role_id, Role.name, Role.display_name, Role.description).order_by(
                Role.role_id
            )
        )
        return result.all()

    async def ranks(self) -> Sequence[Row[Any]]:
        """Return the rank ladder, junior to senior.

        Ordered by ``seniority_order``, never by ``code``: 'ACP' sorts before 'PC'
        alphabetically and outranks it by nine steps.
        """
        result = await self._session.execute(
            select(
                PoliceRank.rank_id,
                PoliceRank.code,
                PoliceRank.full_name,
                PoliceRank.management_level,
                PoliceRank.seniority_order,
                PoliceRank.typical_appointments,
            ).order_by(PoliceRank.seniority_order)
        )
        return result.all()

    async def directorates(self) -> Sequence[Row[Any]]:
        """Return the directorates, alphabetically."""
        result = await self._session.execute(
            select(
                Directorate.directorate_id,
                Directorate.name,
                Directorate.abbreviation,
                Directorate.is_training_authority,
            ).order_by(Directorate.name)
        )
        return result.all()

    async def regions(self) -> Sequence[Row[Any]]:
        """Return the policing regions, alphabetically."""
        result = await self._session.execute(
            select(Region.region_id, Region.name, Region.headquarters).order_by(Region.name)
        )
        return result.all()

    async def stations(self, *, active_only: bool = True) -> Sequence[Row[Any]]:
        """Return stations with their region name.

        Args:
            active_only: Exclude decommissioned stations.

        Returns:
            Station rows including ``region_name``.
        """
        query = (
            select(
                Station.station_id,
                Station.name,
                Station.region_id,
                Region.name.label("region_name"),
                Station.district,
                Station.station_type,
                Station.is_active,
            )
            .join(Region, Region.region_id == Station.region_id)
            .order_by(Station.name)
        )
        if active_only:
            query = query.where(Station.is_active)
        result = await self._session.execute(query)
        return result.all()

    async def specializations(self, *, active_only: bool = True) -> Sequence[Row[Any]]:
        """Return the disciplines BR-04 matches against.

        Args:
            active_only: Exclude retired disciplines.
        """
        query = select(
            SpecializationArea.specialization_area_id,
            SpecializationArea.name,
            SpecializationArea.description,
            SpecializationArea.discipline_group,
            SpecializationArea.directorate_id,
            SpecializationArea.is_active,
        ).order_by(SpecializationArea.name)
        if active_only:
            query = query.where(SpecializationArea.is_active)
        result = await self._session.execute(query)
        return result.all()

    async def categories(self, *, active_only: bool = True) -> Sequence[Row[Any]]:
        """Return training delivery categories."""
        query = select(
            TrainingCategory.category_id,
            TrainingCategory.name,
            TrainingCategory.description,
            TrainingCategory.is_active,
        ).order_by(TrainingCategory.name)
        if active_only:
            query = query.where(TrainingCategory.is_active)
        result = await self._session.execute(query)
        return result.all()

    async def institutions(self) -> Sequence[Row[Any]]:
        """Return awarding institutions, police colleges first.

        Ordered so that the institutions attracting the QUALIFICATION bonus appear at
        the top of the dropdown, which is where a UPF officer expects them.
        """
        result = await self._session.execute(
            select(
                Institution.institution_id,
                Institution.name,
                Institution.institution_type,
                Institution.country,
            ).order_by(Institution.institution_type != "POLICE", Institution.name)
        )
        return result.all()

    async def qualification_levels(self) -> Sequence[Row[Any]]:
        """Return qualification levels, lowest to highest."""
        result = await self._session.execute(
            select(
                QualificationLevel.level_id,
                QualificationLevel.code,
                QualificationLevel.name,
                QualificationLevel.rank_order,
                QualificationLevel.score_value,
            ).order_by(QualificationLevel.rank_order)
        )
        return result.all()

    async def proficiency_levels(self) -> Sequence[Row[Any]]:
        """Return proficiency levels, lowest to highest."""
        result = await self._session.execute(
            select(
                ProficiencyLevel.level_id,
                ProficiencyLevel.code,
                ProficiencyLevel.name,
                ProficiencyLevel.rank_order,
                ProficiencyLevel.score_value,
            ).order_by(ProficiencyLevel.rank_order)
        )
        return result.all()
