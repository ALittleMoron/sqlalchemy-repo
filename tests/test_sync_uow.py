import contextlib

import pytest
from sqlalchemy.orm import Session, scoped_session

from sqlrepo.exc import NonContextManagerUOWUsageError
from sqlrepo.uow import BaseSyncUnitOfWork


def test_skip_session_use(db_sync_session_factory: scoped_session[Session]) -> None:
    class SkipUOW(BaseSyncUnitOfWork):
        __skip_session_use__ = True
        session_factory = db_sync_session_factory  # type: ignore

        def init_repositories(self, session: Session) -> None:
            pass

    with SkipUOW() as uow:
        uow.commit()
        uow.rollback()
        uow.close()


def test_incorrect_uow_usage(db_sync_session_factory: scoped_session[Session]) -> None:
    class IncorrectUOW(BaseSyncUnitOfWork):
        session_factory = db_sync_session_factory  # type: ignore

        def init_repositories(self, session: Session) -> None:
            pass

    instance = IncorrectUOW()
    with pytest.raises(NonContextManagerUOWUsageError):
        instance.commit()
    with pytest.raises(NonContextManagerUOWUsageError):
        instance.rollback()
    with pytest.raises(NonContextManagerUOWUsageError):
        instance.close()


def test_raise_in_context_manager(db_sync_session_factory: scoped_session[Session]) -> None:
    class CorrectUOW(BaseSyncUnitOfWork):
        session_factory = db_sync_session_factory  # type: ignore

        def init_repositories(self, session: Session) -> None:
            pass

    with contextlib.suppress(Exception), CorrectUOW():
        msg = "some error."
        raise TypeError(msg)
