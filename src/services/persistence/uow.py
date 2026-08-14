"""Application transaction boundary implemented with AsyncSession."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.application.ports.persistence import CanonicalRepository, PlaythroughRepository, UowFactory, WorldRepository

from .canonical import SqlAlchemyCanonicalRepository
from .database import Database
from .repositories import SqlAlchemyPlaythroughRepository, SqlAlchemyWorldRepository


class SqlAlchemyUnitOfWork:
    """Own exactly one session and one transaction for an application use case."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session = session_factory()
        self._completed = False
        self.worlds: WorldRepository = SqlAlchemyWorldRepository(self._session)
        self.playthroughs: PlaythroughRepository = SqlAlchemyPlaythroughRepository(self._session)
        self.canonical: CanonicalRepository = SqlAlchemyCanonicalRepository(self._session)

    async def __aenter__(self) -> SqlAlchemyUnitOfWork:
        await self._session.begin()
        return self

    async def __aexit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        if not self._completed:
            await self._session.rollback()
        await self._session.close()

    async def commit(self) -> None:
        await self._session.commit()
        self._completed = True

    async def rollback(self) -> None:
        await self._session.rollback()
        self._completed = True


def make_uow_factory(database: Database) -> UowFactory:
    """Return a factory that creates a fresh Unit of Work per use case."""
    return lambda: SqlAlchemyUnitOfWork(database.session_factory)


__all__ = ["SqlAlchemyUnitOfWork", "make_uow_factory"]
