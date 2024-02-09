import types
from abc import ABC, abstractmethod
from typing import Self

from abstractcp import Abstract, abstract_class_property
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sqlrepo.logging import logger


class BaseUnitOfWork(ABC, Abstract):
    # """Класс единицы работы бизнес-логики."""

    session_factory: 'async_sessionmaker[AsyncSession]' = abstract_class_property(
        async_sessionmaker[AsyncSession],
    )

    async def __aenter__(self: Self) -> Self:
        # """Асинхронный вход в контекстный менеджер единицы работы бизнес-логики."""
        self.session = self.session_factory()
        # NOTE: прокидываем сессию явно, чтобы иметь возможность использовать метод без with
        self.init_repositories(self.session)
        return self

    async def __aexit__(
        self: Self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: types.TracebackType | None,
    ) -> None:
        # """Асинхронный выход из контекстного менеджера единицы работы бизнес-логики."""
        if exc:
            logger.error('UNIT-OF-WORK E0: %s', exc)
            await self.rollback()
        else:
            await self.commit()
        await self.close()

    @abstractmethod
    def init_repositories(self: Self, session: 'AsyncSession') -> None:
        # """Инициализирует классы репозиториев, переданные."""
        raise NotImplementedError()

    async def commit(self: Self) -> None:
        # """Фиксирует изменения транзакции в базе данных (alias к ``commit`` сессии)."""
        if not self.session:
            # NOTE: на случай, если класс был использован не через with
            return
        await self.session.commit()

    async def rollback(self: Self) -> None:
        # """Откатывает изменения транзакции в базе данных (alias к ``rollback`` сессии)."""
        if not self.session:
            # NOTE: на случай, если класс был использован не через with
            return
        await self.session.rollback()

    async def close(self: Self) -> None:
        # """Закрывает сессию (alias к ``close`` сессии.)."""
        if not self.session:
            # NOTE: на случай, если класс был использован не через with
            return
        await self.session.close()
