"""Implementation of Unit of Work patterns."""

import types
from abc import ABC, abstractmethod
from typing import Self

from dev_utils.core.abstract import Abstract, abstract_class_property
from sqlalchemy.ext.asyncio import AsyncSession, async_scoped_session, async_sessionmaker
from sqlalchemy.orm import Session, scoped_session, sessionmaker

from sqlrepo.exc import NonContextManagerUOWUsageError
from sqlrepo.logging import logger

_uow_non_context_manager_usage_msg = (
    "Unit of work only provide context manager access. "
    "Don't initialize your Unit of work class directly."
)


class BaseAsyncUnitOfWork(ABC, Abstract):
    """Base async unit of work pattern."""

    __skip_session_use__: bool = False
    session_factory: "async_sessionmaker[AsyncSession] | async_scoped_session[AsyncSession]" = (
        abstract_class_property(
            async_sessionmaker[AsyncSession],
        )
    )

    @abstractmethod
    def init_repositories(self, session: "AsyncSession") -> None:
        """Init repositories.

        Define your own method for it and specify your own methods for working with repositories.
        """
        raise NotImplementedError()

    async def __aenter__(self) -> Self:  # noqa: D105
        self.session = self.session_factory()
        self.init_repositories(self.session)
        return self

    async def __aexit__(  # noqa: D105
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: types.TracebackType | None,
    ) -> None:
        if exc:
            logger.error("UNIT-OF-WORK E0: %s", exc)
            await self.rollback()
        else:
            await self.commit()
        await self.close()

    async def commit(self) -> None:
        """Alias for session ``commit``."""
        if self.__skip_session_use__:
            return
        if not hasattr(self, 'session'):
            raise NonContextManagerUOWUsageError(_uow_non_context_manager_usage_msg)
        await self.session.commit()  # pragma: no coverage

    async def rollback(self) -> None:
        """Alias for session ``rollback``."""
        if self.__skip_session_use__:
            return
        if not hasattr(self, 'session'):
            raise NonContextManagerUOWUsageError(_uow_non_context_manager_usage_msg)
        await self.session.rollback()  # pragma: no coverage

    async def close(self) -> None:
        """Alias for session ``close``."""
        if self.__skip_session_use__:
            return
        if not hasattr(self, 'session'):
            raise NonContextManagerUOWUsageError(_uow_non_context_manager_usage_msg)
        await self.session.close()  # pragma: no coverage


class BaseSyncUnitOfWork(ABC, Abstract):
    """Base sync unit of work pattern."""

    __skip_session_use__: bool = False
    session_factory: "sessionmaker[Session] | scoped_session[Session]" = abstract_class_property(
        sessionmaker[Session],
    )

    @abstractmethod
    def init_repositories(self, session: "Session") -> None:
        """Init repositories.

        Define your own method for it and specify your own methods for working with repositories.
        """
        raise NotImplementedError()

    def __enter__(self) -> Self:  # noqa: D105
        self.session = self.session_factory()
        self.init_repositories(self.session)
        return self

    def __exit__(  # noqa: D105
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: types.TracebackType | None,
    ) -> None:
        if exc:
            logger.error("UNIT-OF-WORK E0: %s", exc)
            self.rollback()
        else:
            self.commit()
        self.close()

    def commit(self) -> None:
        """Alias for session ``commit``."""
        if self.__skip_session_use__:
            return
        if not hasattr(self, 'session'):
            raise NonContextManagerUOWUsageError(_uow_non_context_manager_usage_msg)
        self.session.commit()  # pragma: no coverage

    def rollback(self) -> None:
        """Alias for session ``rollback``."""
        if self.__skip_session_use__:
            return
        if not hasattr(self, 'session'):
            raise NonContextManagerUOWUsageError(_uow_non_context_manager_usage_msg)
        self.session.rollback()  # pragma: no coverage

    def close(self) -> None:
        """Alias for session ``close``."""
        if self.__skip_session_use__:
            return
        if not hasattr(self, 'session'):
            raise NonContextManagerUOWUsageError(_uow_non_context_manager_usage_msg)
        self.session.close()  # pragma: no coverage
