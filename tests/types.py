from typing import TYPE_CHECKING, Any, Protocol, TypeVar

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import Session


T = TypeVar('T', covariant=True)


class SyncFactoryFunctionProtocol(Protocol[T]):
    """Protocol for Sync functions-factories that create db items."""

    @staticmethod
    def __call__(  # noqa: D102
        session: 'Session',
        *,
        commit: bool = False,
        **kwargs: Any,  # noqa: ANN401
    ) -> T:
        ...


class AsyncFactoryFunctionProtocol(Protocol[T]):
    """Protocol for Sync functions-factories that create db items."""

    @staticmethod
    async def __call__(  # noqa: D102
        session: 'AsyncSession',
        *,
        commit: bool = False,
        **kwargs: Any,  # noqa: ANN401
    ) -> T:
        ...
