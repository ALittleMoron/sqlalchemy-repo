from typing import TYPE_CHECKING, Protocol, TypeAlias

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator

    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm.session import Session

    class SyncSessionGeneratorDependsProtocol(Protocol):
        """Sync session depends protocol for FastAPI framework."""

        @staticmethod
        def __call__() -> Generator[Session, None, None]: ...  # noqa: D102

    class SyncSessionDependsProtocol(Protocol):
        """Sync session depends protocol for FastAPI framework."""

        @staticmethod
        def __call__() -> Session: ...  # noqa: D102

    class AsyncSessionGeneratorDependsProtocol(Protocol):
        """Async session depends protocol for FastAPI framework."""

        @staticmethod
        async def __call__() -> AsyncGenerator[AsyncSession, None]: ...  # noqa: D102

    class AsyncSessionDependsProtocol(Protocol):
        """Async session depends protocol for FastAPI framework."""

        @staticmethod
        async def __call__() -> AsyncSession: ...  # noqa: D102

    SessionDepends: TypeAlias = (
        SyncSessionDependsProtocol
        | AsyncSessionDependsProtocol
        | SyncSessionGeneratorDependsProtocol
        | AsyncSessionGeneratorDependsProtocol
    )


def _get_session_stub() -> None:
    """Stub function, that will be overridden by main plug functions."""


def add_session_stub_overrides(
    app: "FastAPI",
    session_depends: "SessionDepends",
) -> "FastAPI":
    """Container plugin function.

    Add dependency override for user-defined SQLAlchemy session (sync or async) and return app back.
    """
    app.dependency_overrides[_get_session_stub] = session_depends
    return app
