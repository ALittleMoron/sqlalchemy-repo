from typing import TYPE_CHECKING

from fastapi import Depends, Request

from sqlrepo.ext.fastapi.stubs import _get_session_stub  # type: ignore[reportPrivateUsage]

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm.session import Session


class BaseSyncContainer:
    """Base container class with sync interface."""

    def __init__(  # pragma: no coverage
        self,
        request: Request,
        session: "Session" = Depends(_get_session_stub),
    ) -> None:
        self.request = request
        self.session = session


class BaseAsyncContainer:
    """Base container class with async interface."""

    def __init__(  # pragma: no coverage
        self,
        request: Request,
        session: "AsyncSession" = Depends(_get_session_stub),
    ) -> None:
        self.request = request
        self.session = session
