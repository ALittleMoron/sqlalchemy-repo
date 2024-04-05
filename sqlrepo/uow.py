import types
from abc import ABC, abstractmethod
from typing import Self

from dev_utils.core.abstract import Abstract, abstract_class_property  # type: ignore
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session, sessionmaker

from sqlrepo.logging import logger


class BaseAsyncUnitOfWork(ABC, Abstract):

    session_factory: 'async_sessionmaker[AsyncSession]' = abstract_class_property(
        async_sessionmaker[AsyncSession],
    )

    @abstractmethod
    def init_repositories(self, session: 'AsyncSession') -> None:
        raise NotImplementedError()

    async def __aenter__(self) -> Self:
        self.session = self.session_factory()
        self.init_repositories(self.session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: types.TracebackType | None,
    ) -> None:
        if exc:
            logger.error('UNIT-OF-WORK E0: %s', exc)
            await self.rollback()
        else:
            await self.commit()
        await self.close()

    async def commit(self) -> None:
        if not self.session:
            return
        await self.session.commit()

    async def rollback(self) -> None:
        if not self.session:
            return
        await self.session.rollback()

    async def close(self) -> None:
        if not self.session:
            return
        await self.session.close()


class BaseSyncUnitOfWork(ABC, Abstract):

    session_factory: 'sessionmaker[Session]' = abstract_class_property(
        sessionmaker[Session],
    )

    @abstractmethod
    def init_repositories(self, session: 'Session') -> None:
        raise NotImplementedError()

    def __enter__(self) -> Self:
        self.session = self.session_factory()
        self.init_repositories(self.session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: types.TracebackType | None,
    ) -> None:
        if exc:
            logger.error('UNIT-OF-WORK E0: %s', exc)
            self.rollback()
        else:
            self.commit()
        self.close()

    def commit(self) -> None:
        if not self.session:
            return
        self.session.commit()

    def rollback(self) -> None:
        if not self.session:
            return
        self.session.rollback()

    def close(self) -> None:
        if not self.session:
            return
        self.session.close()
