from typing import TYPE_CHECKING, Protocol

from fastapi import Depends, Request

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator

    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm.session import Session

    class SyncSessionDependsProtocol(Protocol):
        """Sync session depends protocol for FastAPI framework."""

        @staticmethod
        def __call__() -> Session | Generator[Session, None, None]: ...  # noqa: D102

    class AsyncSessionDependsProtocol(Protocol):
        """Async session depends protocol for FastAPI framework."""

        @staticmethod
        async def __call__() -> AsyncSession | AsyncGenerator[AsyncSession, None]: ...  # noqa: D102


def _get_session_stub() -> None:
    """Stub function, that will be overridden by main plug functions."""


def add_container_overrides(
    app: "FastAPI",
    session_depends: "SyncSessionDependsProtocol | AsyncSessionDependsProtocol",
) -> "FastAPI":
    """Container plugin function.

    Add dependency override for user-defined SQLAlchemy session (sync or async) and return app back.
    """
    app.dependency_overrides[_get_session_stub] = session_depends
    return app


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
