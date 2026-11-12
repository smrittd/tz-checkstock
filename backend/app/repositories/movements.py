from uuid import UUID

from sqlalchemy import func, select

from app.models.movement import Movement
from app.repositories.base import BaseRepository


class MovementsRepository(BaseRepository):
    async def movement(self, movement_id: UUID) -> Movement | None:
        return await self._session.get(Movement, movement_id)

    async def movement_quantities(self):
        return (
            await self._session.execute(
                select(
                    Movement.product_id, Movement.kind, Movement.status, func.sum(Movement.quantity)
                ).group_by(Movement.product_id, Movement.kind, Movement.status)
            )
        ).all()

    async def marketplace_quantities(self):
        return (
            await self._session.execute(
                select(
                    Movement.product_id, Movement.external_destination, func.sum(Movement.quantity)
                )
                .where(Movement.kind == "fbo", Movement.status == "received")
                .group_by(Movement.product_id, Movement.external_destination)
                .order_by(Movement.external_destination)
            )
        ).all()

    async def movements(
        self, kind: str | None, status: str | None, product_id: int | None, limit: int, offset: int
    ) -> tuple[list[Movement], int]:
        query = select(Movement)
        if kind is not None:
            query = query.where(Movement.kind == kind)
        if status is not None:
            query = query.where(Movement.status == status)
        if product_id is not None:
            query = query.where(Movement.product_id == product_id)
        total = await self._session.scalar(select(func.count()).select_from(query.subquery()))
        items = await self._session.scalars(
            query.order_by(Movement.created_at.desc(), Movement.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(items), total
