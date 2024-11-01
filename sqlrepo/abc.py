from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Generic, NotRequired, TypedDict, TypeVar

from sqlalchemy.orm import DeclarativeBase as Base

if TYPE_CHECKING:

    # noinspection PyUnresolvedReferences
    from collections.abc import Iterable, Sequence

    from sqlalchemy.orm.attributes import QueryableAttribute
    from sqlalchemy.orm.strategy_options import (  # type: ignore[reportPrivateUsage]
        _AbstractLoad as Load,
    )
    from sqlalchemy.sql._typing import (
        _ColumnExpressionOrStrLabelArgument,  # type: ignore[reportPrivateUsage]
    )
    from sqlalchemy.sql.elements import ColumnElement

    from sqlrepo.types import FilterType

    class JoinKwargs(TypedDict):
        """Kwargs for join."""

        isouter: NotRequired[bool]
        full: NotRequired[bool]

    Model = type[Base]
    JoinClause = ColumnElement[bool]
    ModelWithOnclause = tuple[Model, JoinClause]
    CompleteModel = tuple[Model, JoinClause, JoinKwargs]
    Join = str | Model | ModelWithOnclause | CompleteModel
    SearchParam = str | QueryableAttribute[Any]
    OrderByParam = _ColumnExpressionOrStrLabelArgument[Any]
    DataDict = dict[str, Any]


T = TypeVar("T", bound=Base)


class AbstractSyncGetRepository(ABC, Generic[T]):
    @abstractmethod
    def get(
        self,
        *,
        filters: "FilterType",
        joins: "Sequence[Join] | None" = None,
        loads: "Sequence[Load] | None" = None,
    ) -> T | None:
        raise NotImplementedError


class AbstractSyncCountRepository(ABC):
    @abstractmethod
    def count(
        self,
        *,
        filters: "FilterType | None" = None,
        joins: "Sequence[Join] | None" = None,
    ) -> int:
        raise NotImplementedError


class AbstractSyncExistsRepository(ABC):
    @abstractmethod
    def exists(
        self,
        *,
        filters: "FilterType | None" = None,
    ) -> bool:
        raise NotImplementedError


class AbstractSyncListRepository(ABC, Generic[T]):
    @abstractmethod
    def list(
        self,
        *,
        filters: "FilterType | None" = None,
        joins: "Sequence[Join] | None" = None,
        loads: "Sequence[Load] | None" = None,
        search: str | None = None,
        search_by: "SearchParam | Iterable[SearchParam] | None" = None,
        order_by: "OrderByParam | Iterable[OrderByParam] | None" = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> "Sequence[T]":
        raise NotImplementedError


class AbstractSyncCreateRepository(ABC, Generic[T]):
    @abstractmethod
    def create(
        self,
        *,
        data: "DataDict | None",
    ) -> T:
        raise NotImplementedError


class AbstractSyncBulkCreateRepository(ABC, Generic[T]):
    @abstractmethod
    def bulk_create(
        self,
        *,
        data: "Sequence[DataDict]",
    ) -> "Sequence[T]":
        raise NotImplementedError


class AbstractSyncUpdateRepository(ABC, Generic[T]):
    @abstractmethod
    def update(
        self,
        *,
        data: "DataDict",
        filters: "FilterType | None" = None,
    ) -> "Sequence[T] | None":
        raise NotImplementedError


class AbstractSyncUpdateInstanceRepository(ABC, Generic[T]):
    @abstractmethod
    def update_instance(
        self,
        *,
        instance: "T",
        data: "DataDict",
    ) -> "tuple[bool, T]":
        raise NotImplementedError


class AbstractSyncDeleteRepository(ABC):
    @abstractmethod
    def delete(
        self,
        *,
        filters: "FilterType | None" = None,
    ) -> int:
        raise NotImplementedError


class AbstractSyncDisableRepository(ABC):
    @abstractmethod
    def disable(
        self,
        *,
        ids_to_disable: set[Any],
        extra_filters: "FilterType | None" = None,
    ) -> int:
        raise NotImplementedError


class AbstractSyncRepository(
    AbstractSyncGetRepository,
    AbstractSyncCountRepository,
    AbstractSyncExistsRepository,
    AbstractSyncListRepository,
    AbstractSyncCreateRepository,
    AbstractSyncBulkCreateRepository,
    AbstractSyncUpdateRepository,
    AbstractSyncUpdateInstanceRepository,
    AbstractSyncDeleteRepository,
    AbstractSyncDisableRepository,
    ABC,
):
    pass


class AbstractAsyncGetRepository(ABC, Generic[T]):
    @abstractmethod
    async def get(
        self,
        *,
        filters: "FilterType",
        joins: "Sequence[Join] | None" = None,
        loads: "Sequence[Load] | None" = None,
    ) -> T | None:
        raise NotImplementedError


class AbstractAsyncCountRepository(ABC):
    @abstractmethod
    async def count(
        self,
        *,
        filters: "FilterType | None" = None,
        joins: "Sequence[Join] | None" = None,
    ) -> int:
        raise NotImplementedError


class AbstractAsyncExistsRepository(ABC):
    @abstractmethod
    async def exists(
        self,
        *,
        filters: "FilterType | None" = None,
    ) -> bool:
        raise NotImplementedError


class AbstractAsyncListRepository(ABC, Generic[T]):
    @abstractmethod
    async def list(
        self,
        *,
        filters: "FilterType | None" = None,
        joins: "Sequence[Join] | None" = None,
        loads: "Sequence[Load] | None" = None,
        search: str | None = None,
        search_by: "SearchParam | Iterable[SearchParam] | None" = None,
        order_by: "OrderByParam | Iterable[OrderByParam] | None" = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> "Sequence[T]":
        raise NotImplementedError


class AbstractAsyncCreateRepository(ABC, Generic[T]):
    @abstractmethod
    async def create(
        self,
        *,
        data: "DataDict | None",
    ) -> T:
        raise NotImplementedError


class AbstractAsyncBulkCreateRepository(ABC, Generic[T]):
    @abstractmethod
    async def bulk_create(
        self,
        *,
        data: "Sequence[DataDict]",
    ) -> "Sequence[T]":
        raise NotImplementedError


class AbstractAsyncUpdateRepository(ABC, Generic[T]):
    @abstractmethod
    async def update(
        self,
        *,
        data: "DataDict",
        filters: "FilterType | None" = None,
    ) -> "Sequence[T] | None":
        raise NotImplementedError


class AbstractAsyncUpdateInstanceRepository(ABC, Generic[T]):
    @abstractmethod
    async def update_instance(
        self,
        *,
        instance: "T",
        data: "DataDict",
    ) -> "tuple[bool, T]":
        raise NotImplementedError


class AbstractAsyncDeleteRepository(ABC):
    @abstractmethod
    async def delete(
        self,
        *,
        filters: "FilterType | None" = None,
    ) -> int:
        raise NotImplementedError


class AbstractAsyncDisableRepository(ABC):
    @abstractmethod
    async def disable(
        self,
        *,
        ids_to_disable: set[Any],
        extra_filters: "FilterType | None" = None,
    ) -> int:
        raise NotImplementedError


class AbstractAsyncRepository(
    AbstractAsyncGetRepository,
    AbstractAsyncCountRepository,
    AbstractAsyncExistsRepository,
    AbstractAsyncListRepository,
    AbstractAsyncCreateRepository,
    AbstractAsyncBulkCreateRepository,
    AbstractAsyncUpdateRepository,
    AbstractAsyncUpdateInstanceRepository,
    AbstractAsyncDeleteRepository,
    AbstractAsyncDisableRepository,
    ABC,
):
    pass
