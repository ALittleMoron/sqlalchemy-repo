import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_scoped_session

from sqlrepo.exc import NonContextManagerUOWUsageError
from sqlrepo.uow import BaseAsyncUnitOfWork


@pytest.mark.asyncio()
async def test_skip_session_use(
    db_async_session_factory: async_scoped_session[AsyncSession],
) -> None:
    class SkipUOW(BaseAsyncUnitOfWork):
        __skip_session_use__ = True
        session_factory = db_async_session_factory  # type: ignore

        def init_repositories(self, session: AsyncSession) -> None:
            pass

    async with SkipUOW() as uow:
        await uow.commit()
        await uow.rollback()
        await uow.close()


@pytest.mark.asyncio()
async def test_incorrect_uow_usage(
    db_async_session_factory: async_scoped_session[AsyncSession],
) -> None:
    class IncorrectUOW(BaseAsyncUnitOfWork):
        session_factory = db_async_session_factory  # type: ignore

        def init_repositories(self, session: AsyncSession) -> None:
            pass

    instance = IncorrectUOW()
    with pytest.raises(NonContextManagerUOWUsageError):
        await instance.commit()
    with pytest.raises(NonContextManagerUOWUsageError):
        await instance.rollback()
    with pytest.raises(NonContextManagerUOWUsageError):
        await instance.close()
