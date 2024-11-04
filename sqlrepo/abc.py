import datetime
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Generic, Literal, TypeVar

from sqlalchemy.orm import DeclarativeBase as Base

if TYPE_CHECKING:
    # noinspection PyUnresolvedReferences
    from collections.abc import Sequence

    # noinspection PyUnresolvedReferences
    from sqlrepo.types import (
        DataDict,
        DisableField,
        DisableIdField,
        Filters,
        Joins,
        Loads,
        OrderByParams,
        SearchByParams,
    )


T = TypeVar("T", bound=Base)


class AbstractSyncQuery(ABC):
    @abstractmethod
    def get_item(
        self,
        *,
        model: type[T],
        filters: "Filters | None" = None,
        joins: "Joins | None" = None,
        loads: "Loads | None" = None,
    ) -> "T | None": ...

    @abstractmethod
    def get_items_count(
        self,
        *,
        model: type[T],
        joins: "Joins | None" = None,
        filters: "Filters | None" = None,
    ) -> int: ...

    @abstractmethod
    def get_item_list(
        self,
        *,
        model: type[T],
        joins: "Joins | None" = None,
        loads: "Loads | None" = None,
        filters: "Filters | None" = None,
        search: str | None = None,
        search_by: "SearchByParams | None" = None,
        order_by: "OrderByParams | None" = None,
        limit: int | None = None,
        offset: int | None = None,
        unique_items: bool = False,
    ) -> "list[T]": ...

    @abstractmethod
    def db_create(
        self,
        *,
        model: type[T],
        data: "DataDict | Sequence[DataDict] | None" = None,
        use_flush: bool = False,
    ) -> "T | list[T]": ...

    @abstractmethod
    def db_update(
        self,
        *,
        model: type[T],
        data: "DataDict",
        filters: "Filters | None" = None,
        use_flush: bool = False,
    ) -> "list[T]": ...

    @abstractmethod
    def change_item(
        self,
        *,
        data: "DataDict",
        item: "T",
        set_none: bool = False,
        allowed_none_fields: 'Literal["*"] | set[str]' = "*",
        use_flush: bool = False,
    ) -> "tuple[bool, T]": ...

    @abstractmethod
    def db_delete(
        self,
        *,
        model: type[T],
        filters: "Filters | None" = None,
        use_flush: bool = False,
    ) -> int: ...

    @abstractmethod
    def delete_item(
        self,
        *,
        item: "Base",
        use_flush: bool = False,
    ) -> bool: ...

    @abstractmethod
    def disable_items(
        self,
        *,
        model: type[T],
        ids_to_disable: set[Any],
        id_field: "DisableIdField",
        disable_field: "DisableField",
        field_type: type[datetime.datetime] | type[bool] = datetime.datetime,
        allow_filter_by_value: bool = True,
        extra_filters: "Filters | None" = None,
        use_flush: bool = False,
    ) -> int: ...

    @abstractmethod
    def items_exists(
        self,
        model: type[T],
        filters: "Filters | None" = None,
    ) -> bool: ...


class AbstractAsyncQuery(ABC):
    @abstractmethod
    async def get_item(
        self,
        *,
        model: type[T],
        filters: "Filters | None" = None,
        joins: "Joins | None" = None,
        loads: "Loads | None" = None,
    ) -> "T | None": ...

    @abstractmethod
    async def get_items_count(
        self,
        *,
        model: type[T],
        joins: "Joins | None" = None,
        filters: "Filters | None" = None,
    ) -> int: ...

    @abstractmethod
    async def get_item_list(
        self,
        *,
        model: type[T],
        joins: "Joins | None" = None,
        loads: "Loads | None" = None,
        filters: "Filters | None" = None,
        search: str | None = None,
        search_by: "SearchByParams | None" = None,
        order_by: "OrderByParams | None" = None,
        limit: int | None = None,
        offset: int | None = None,
        unique_items: bool = False,
    ) -> "list[T]": ...

    @abstractmethod
    async def db_create(
        self,
        *,
        model: type[T],
        data: "DataDict | Sequence[DataDict] | None" = None,
        use_flush: bool = False,
    ) -> "T | list[T]": ...

    @abstractmethod
    async def db_update(
        self,
        *,
        model: type[T],
        data: "DataDict",
        filters: "Filters | None" = None,
        use_flush: bool = False,
    ) -> "list[T]": ...

    @abstractmethod
    async def change_item(
        self,
        *,
        data: "DataDict",
        item: "T",
        set_none: bool = False,
        allowed_none_fields: 'Literal["*"] | set[str]' = "*",
        use_flush: bool = False,
    ) -> "tuple[bool, T]": ...

    @abstractmethod
    async def db_delete(
        self,
        *,
        model: type[T],
        filters: "Filters | None" = None,
        use_flush: bool = False,
    ) -> int: ...

    @abstractmethod
    async def delete_item(
        self,
        *,
        item: "Base",
        use_flush: bool = False,
    ) -> bool: ...

    @abstractmethod
    async def disable_items(
        self,
        *,
        model: type[T],
        ids_to_disable: set[Any],
        id_field: "DisableIdField",
        disable_field: "DisableField",
        field_type: type[datetime.datetime] | type[bool] = datetime.datetime,
        allow_filter_by_value: bool = True,
        extra_filters: "Filters | None" = None,
        use_flush: bool = False,
    ) -> int: ...

    @abstractmethod
    async def items_exists(
        self,
        model: type[T],
        filters: "Filters | None" = None,
    ) -> bool: ...


class AbstractSyncGetRepository(ABC, Generic[T]):
    @abstractmethod
    def get(
        self,
        *,
        filters: "Filters",
        joins: "Joins | None" = None,
        loads: "Loads | None" = None,
    ) -> T | None:
        raise NotImplementedError


class AbstractSyncCountRepository(ABC):
    @abstractmethod
    def count(
        self,
        *,
        filters: "Filters | None" = None,
        joins: "Joins | None" = None,
    ) -> int:
        raise NotImplementedError


class AbstractSyncExistsRepository(ABC):
    @abstractmethod
    def exists(
        self,
        *,
        filters: "Filters | None" = None,
    ) -> bool:
        raise NotImplementedError


class AbstractSyncListRepository(ABC, Generic[T]):
    @abstractmethod
    def list(
        self,
        *,
        filters: "Filters | None" = None,
        joins: "Joins | None" = None,
        loads: "Loads | None" = None,
        search: str | None = None,
        search_by: "SearchByParams | None" = None,
        order_by: "OrderByParams | None" = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> "list[T]":
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
    ) -> "list[T]":
        raise NotImplementedError


class AbstractSyncUpdateRepository(ABC, Generic[T]):
    @abstractmethod
    def update(
        self,
        *,
        data: "DataDict",
        filters: "Filters | None" = None,
    ) -> "list[T] | None":
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
        filters: "Filters | None" = None,
    ) -> int:
        raise NotImplementedError


class AbstractSyncDisableRepository(ABC):
    @abstractmethod
    def disable(
        self,
        *,
        ids_to_disable: set[Any],
        extra_filters: "Filters | None" = None,
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
        filters: "Filters",
        joins: "Joins | None" = None,
        loads: "Loads | None" = None,
    ) -> T | None:
        raise NotImplementedError


class AbstractAsyncCountRepository(ABC):
    @abstractmethod
    async def count(
        self,
        *,
        filters: "Filters | None" = None,
        joins: "Joins | None" = None,
    ) -> int:
        raise NotImplementedError


class AbstractAsyncExistsRepository(ABC):
    @abstractmethod
    async def exists(
        self,
        *,
        filters: "Filters | None" = None,
    ) -> bool:
        raise NotImplementedError


class AbstractAsyncListRepository(ABC, Generic[T]):
    @abstractmethod
    async def list(
        self,
        *,
        filters: "Filters | None" = None,
        joins: "Joins | None" = None,
        loads: "Loads | None" = None,
        search: str | None = None,
        search_by: "SearchByParams | None" = None,
        order_by: "OrderByParams | None" = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> "list[T]":
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
    ) -> "list[T]":
        raise NotImplementedError


class AbstractAsyncUpdateRepository(ABC, Generic[T]):
    @abstractmethod
    async def update(
        self,
        *,
        data: "DataDict",
        filters: "Filters | None" = None,
    ) -> "list[T] | None":
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
        filters: "Filters | None" = None,
    ) -> int:
        raise NotImplementedError


class AbstractAsyncDisableRepository(ABC):
    @abstractmethod
    async def disable(
        self,
        *,
        ids_to_disable: set[Any],
        extra_filters: "Filters | None" = None,
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
