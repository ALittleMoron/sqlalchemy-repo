"""Main implementations for sqlrepo project."""

import importlib
import warnings
from inspect import isclass
from typing import (
    TYPE_CHECKING,
    Any,
    ForwardRef,
    Generic,
    NotRequired,
    TypeAlias,
    TypedDict,
    TypeVar,
    get_args,
    overload,
)

from sqlalchemy.orm import DeclarativeBase as Base

from sqlrepo import exc as sqlrepo_exc
from sqlrepo.config import RepositoryConfig
from sqlrepo.constants import (
    REPOSITORY_GENERIC_TYPE_IS_NOT_CLASS_WARNING,
    REPOSITORY_GENERIC_TYPE_IS_NOT_MODEL,
    REPOSITORY_GENERIC_TYPE_NOT_PASSED_WARNING,
    REPOSITORY_GET_MODULE_INSTANCE_ERROR_TEMPLATE,
    REPOSITORY_GETTING_GENERIC_INFO_WARNING_TEMPLATE,
    REPOSITORY_MODEL_ALREADY_DEFINED_WARNING,
    REPOSITORY_RESOLVE_FORWARD_REF_WARNING_TEMPLATE,
    REPOSITORY_VALIDATE_DISABLE_ATTRIBUTES_ERROR,
)
from sqlrepo.logger import default_logger
from sqlrepo.queries import BaseAsyncQuery, BaseSyncQuery
from sqlrepo.wrappers import wrap_any_exception_manager

if TYPE_CHECKING:
    # noinspection PyUnresolvedReferences
    from collections.abc import Iterable, Sequence

    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm.attributes import QueryableAttribute
    from sqlalchemy.orm.session import Session
    from sqlalchemy.orm.strategy_options import _AbstractLoad  # type: ignore[reportPrivateUsage]
    from sqlalchemy.sql._typing import (
        _ColumnExpressionOrStrLabelArgument,  # type: ignore[reportPrivateUsage]
    )
    from sqlalchemy.sql.elements import ColumnElement

    from sqlrepo.types import FilterType, LoggerProtocol

    class JoinKwargs(TypedDict):
        """Kwargs for join."""

        isouter: NotRequired[bool]
        full: NotRequired[bool]

    Count = int
    Deleted = bool
    Model = type[Base]
    JoinClause = ColumnElement[bool]
    ModelWithOnclause = tuple[Model, JoinClause]
    CompleteModel = tuple[Model, JoinClause, JoinKwargs]
    Join = str | Model | ModelWithOnclause | CompleteModel
    Load = _AbstractLoad
    SearchParam = str | QueryableAttribute[Any]
    OrderByParam = _ColumnExpressionOrStrLabelArgument[Any]
    DataDict = dict[str, Any]


StrField: TypeAlias = str
BaseSQLAlchemyModel = TypeVar("BaseSQLAlchemyModel", bound=Base)
IsUpdated: TypeAlias = bool


class RepositoryModelClassIncorrectUseWarning(Warning):
    """Warning about Repository model_class attribute incorrect usage."""


class BaseRepository(Generic[BaseSQLAlchemyModel]):
    """Base repository class.

    Don't Use it directly. Use BaseAsyncRepository and BaseSyncRepository, or pass query_class
    directly (not recommended.)
    """

    __inheritance_check_model_class__: bool = True
    """
    Private custom magic property.

    Use it, if you want to inherit Repository without checking model_class attribute.
    """

    model_class: type["BaseSQLAlchemyModel"]
    """
    Model class for repository.

    You can set this option manually, but it is not recommended. Repository will automatically
    add model_class attribute by extracting it from Generic type.

    Use case:

    ```
    from my_package.models import Admin

    class AdminRepository(BaseSyncRepository[Admin]):
        pass

    # So, when you will use AdminRepository, model_class attribute will be set with Admin
    # automatically.
    ```
    """

    config = RepositoryConfig()
    """Repository config, that contains all settings.

    To add your own settings, inherit RepositoryConfig and add your own fields, then init it in
    your Repository class as class variable.
    """

    @classmethod
    def _validate_disable_attributes(cls) -> None:
        if (
            cls.config.disable_id_field is None
            or cls.config.disable_field is None
            or cls.config.disable_field_type is None
        ):
            raise sqlrepo_exc.RepositoryAttributeError(REPOSITORY_VALIDATE_DISABLE_ATTRIBUTES_ERROR)

    def __init_subclass__(cls) -> None:  # noqa: D105 PLR0911
        super().__init_subclass__()
        if cls.__inheritance_check_model_class__ is False:
            cls.__inheritance_check_model_class__ = True
            return
        if hasattr(cls, "model_class"):
            warnings.warn(
                REPOSITORY_MODEL_ALREADY_DEFINED_WARNING,
                RepositoryModelClassIncorrectUseWarning,
                stacklevel=2,
            )
            return
        try:
            # PEP-560: https://peps.python.org/pep-0560/
            # NOTE: this code is needed for getting type from generic: Generic[int] -> int type
            # get_args get params from __orig_bases__, that contains Generic passed types.
            model, *_ = get_args(cls.__orig_bases__[0])  # type: ignore[reportAttributeAccessIssue]
        except (AttributeError, IndexError, TypeError) as exc:
            warnings.warn(
                REPOSITORY_GETTING_GENERIC_INFO_WARNING_TEMPLATE.format(cls=cls, exc=exc),
                RepositoryModelClassIncorrectUseWarning,
                stacklevel=2,
            )
            return
        if isinstance(model, ForwardRef):
            try:
                repo_module = vars(cls).get("__module__")
                if not repo_module:  # pragma: no coverage
                    msg = REPOSITORY_GET_MODULE_INSTANCE_ERROR_TEMPLATE.format(cls=cls)
                    raise TypeError(msg)  # noqa: TRY301
                model_globals = vars(importlib.import_module(repo_module))
                model = eval(model.__forward_arg__, model_globals)  # noqa: S307
            except (ImportError, TypeError, AttributeError, NameError) as exc:
                warnings.warn(
                    REPOSITORY_RESOLVE_FORWARD_REF_WARNING_TEMPLATE.format(exc=exc),
                    RepositoryModelClassIncorrectUseWarning,
                    stacklevel=2,
                )
                return
        if isinstance(model, TypeVar):
            warnings.warn(
                REPOSITORY_GENERIC_TYPE_NOT_PASSED_WARNING,
                RepositoryModelClassIncorrectUseWarning,
                stacklevel=2,
            )
            return
        if not isclass(model):
            warnings.warn(
                REPOSITORY_GENERIC_TYPE_IS_NOT_CLASS_WARNING,
                RepositoryModelClassIncorrectUseWarning,
                stacklevel=2,
            )
            return
        if not issubclass(model, Base):
            warnings.warn(
                REPOSITORY_GENERIC_TYPE_IS_NOT_MODEL,
                RepositoryModelClassIncorrectUseWarning,
                stacklevel=2,
            )
            return
        cls.model_class = model  # type: ignore[reportAttributeAccessIssue]


class BaseAsyncRepository(BaseRepository[BaseSQLAlchemyModel]):
    """Base repository class with async interface.

    Has main CRUD methods for working with model. Use async session of SQLAlchemy to work with this
    class.
    """

    __inheritance_check_model_class__ = False
    query_class: type["BaseAsyncQuery"] = BaseAsyncQuery

    def __init__(
        self,
        session: "AsyncSession",
        logger: "LoggerProtocol" = default_logger,
    ) -> None:
        self.session = session
        self.logger = logger
        self.queries = self.query_class(
            session=session,
            filter_converter_class=self.config.get_filter_convert_class(),
            specific_column_mapping=self.config.specific_column_mapping,
            logger=logger,
        )

    async def _get(
        self,
        *,
        filters: "FilterType",
        joins: "Sequence[Join] | None" = None,
        loads: "Sequence[Load] | None" = None,
    ) -> "BaseSQLAlchemyModel | None":
        """Get one instance of model_class by given filters."""
        with wrap_any_exception_manager():
            return await self.queries.get_item(
                model=self.model_class,
                joins=joins,
                loads=loads,
                filters=filters,
            )

    async def _count(
        self,
        *,
        filters: "FilterType | None" = None,
        joins: "Sequence[Join] | None" = None,
    ) -> int:
        """Get count of instances of model_class by given filters."""
        with wrap_any_exception_manager():
            return await self.queries.get_items_count(
                model=self.model_class,
                joins=joins,
                filters=filters,
            )

    async def _exists(
        self,
        *,
        filters: "FilterType | None" = None,
    ) -> bool:
        """Check rows in table for existing."""
        with wrap_any_exception_manager():
            return await self.queries.items_exists(
                model=self.model_class,
                filters=filters,
            )

    async def _list(
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
    ) -> "Sequence[BaseSQLAlchemyModel]":
        """Get list of instances of model_class."""
        with wrap_any_exception_manager():
            return await self.queries.get_item_list(
                model=self.model_class,
                joins=joins,
                loads=loads,
                filters=filters,
                search=search,
                search_by=search_by,
                order_by=order_by,
                limit=limit,
                offset=offset,
                unique_items=self.config.unique_list_items,
            )

    @overload
    async def _create(
        self,
        *,
        data: "DataDict | None",
    ) -> "BaseSQLAlchemyModel": ...

    @overload
    async def _create(
        self,
        *,
        data: "Sequence[DataDict]",
    ) -> "Sequence[BaseSQLAlchemyModel]": ...

    async def _create(
        self,
        *,
        data: "DataDict | Sequence[DataDict] | None",
    ) -> "BaseSQLAlchemyModel | Sequence[BaseSQLAlchemyModel]":
        """Create model_class instance from given data."""
        with wrap_any_exception_manager():
            return await self.queries.db_create(
                model=self.model_class,
                data=data,
            )

    async def _update(
        self,
        *,
        data: "DataDict",
        filters: "FilterType | None" = None,
    ) -> "Sequence[BaseSQLAlchemyModel] | None":
        """Update model_class from given data."""
        with wrap_any_exception_manager():
            return await self.queries.db_update(
                model=self.model_class,
                data=data,
                filters=filters,
                use_flush=self.config.use_flush,
            )

    async def _update_instance(
        self,
        *,
        instance: "BaseSQLAlchemyModel",
        data: "DataDict",
    ) -> "tuple[IsUpdated, BaseSQLAlchemyModel]":
        """Update model_class instance from given data.

        Returns tuple with boolean (was instance updated or not) and updated instance.
        """
        with wrap_any_exception_manager():
            return await self.queries.change_item(
                data=data,
                item=instance,
                set_none=self.config.update_set_none,
                allowed_none_fields=self.config.update_allowed_none_fields,
                use_flush=self.config.use_flush,
            )

    async def _delete(
        self,
        *,
        filters: "FilterType | None" = None,
    ) -> "Count":
        """Delete model_class in db by given filters."""
        with wrap_any_exception_manager():
            return await self.queries.db_delete(
                model=self.model_class,
                filters=filters,
                use_flush=self.config.use_flush,
            )

    async def _disable(
        self,
        *,
        ids_to_disable: set[Any],
        extra_filters: "FilterType | None" = None,
    ) -> "Count":
        """Disable model_class instances with given ids and extra_filters."""
        with wrap_any_exception_manager():
            self._validate_disable_attributes()
            return await self.queries.disable_items(
                model=self.model_class,
                ids_to_disable=ids_to_disable,
                id_field=self.config.disable_id_field,  # type: ignore[reportArgumentType]
                disable_field=self.config.disable_field,  # type: ignore[reportArgumentType]
                field_type=self.config.disable_field_type,  # type: ignore[reportArgumentType]
                allow_filter_by_value=self.config.allow_disable_filter_by_value,
                extra_filters=extra_filters,
                use_flush=self.config.use_flush,
            )


class BaseSyncRepository(BaseRepository[BaseSQLAlchemyModel]):
    """Base repository class with sync interface.

    Has main CRUD methods for working with model. Use sync session of SQLAlchemy to work with this
    class.
    """

    __inheritance_check_model_class__ = False
    query_class: type["BaseSyncQuery"] = BaseSyncQuery

    def __init__(self, session: "Session", logger: "LoggerProtocol" = default_logger) -> None:
        self.session = session
        self.logger = logger
        self.queries = self.query_class(
            session=session,
            filter_converter_class=self.config.get_filter_convert_class(),
            specific_column_mapping=self.config.specific_column_mapping,
            logger=logger,
        )

    def _get(
        self,
        *,
        filters: "FilterType",
        joins: "Sequence[Join] | None" = None,
        loads: "Sequence[Load] | None" = None,
    ) -> "BaseSQLAlchemyModel | None":
        """Get one instance of model_class by given filters."""
        with wrap_any_exception_manager():
            return self.queries.get_item(
                model=self.model_class,
                joins=joins,
                loads=loads,
                filters=filters,
            )

    def _count(
        self,
        *,
        filters: "FilterType | None" = None,
        joins: "Sequence[Join] | None" = None,
    ) -> int:
        """Get count of instances of model_class by given filters."""
        with wrap_any_exception_manager():
            return self.queries.get_items_count(
                model=self.model_class,
                joins=joins,
                filters=filters,
            )

    def _exists(
        self,
        *,
        filters: "FilterType | None" = None,
    ) -> bool:
        """Check rows in table for existing."""
        with wrap_any_exception_manager():
            return self.queries.items_exists(
                model=self.model_class,
                filters=filters,
            )

    def _list(
        self,
        *,
        joins: "Sequence[Join] | None" = None,
        loads: "Sequence[Load] | None" = None,
        filters: "FilterType | None" = None,
        search: str | None = None,
        search_by: "SearchParam | Iterable[SearchParam] | None" = None,
        order_by: "OrderByParam | Iterable[OrderByParam] | None" = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> "Sequence[BaseSQLAlchemyModel]":
        """Get list of instances of model_class."""
        with wrap_any_exception_manager():
            return self.queries.get_item_list(
                model=self.model_class,
                joins=joins,
                loads=loads,
                filters=filters,
                search=search,
                search_by=search_by,
                order_by=order_by,
                limit=limit,
                offset=offset,
                unique_items=self.config.unique_list_items,
            )

    @overload
    def _create(
        self,
        *,
        data: "DataDict | None",
    ) -> "BaseSQLAlchemyModel": ...

    @overload
    def _create(
        self,
        *,
        data: "Sequence[DataDict]",
    ) -> "Sequence[BaseSQLAlchemyModel]": ...

    def _create(
        self,
        *,
        data: "DataDict | Sequence[DataDict] | None",
    ) -> "BaseSQLAlchemyModel | Sequence[BaseSQLAlchemyModel]":
        """Create model_class instance from given data."""
        with wrap_any_exception_manager():
            return self.queries.db_create(
                model=self.model_class,
                data=data,
            )

    def _update(
        self,
        *,
        data: "DataDict",
        filters: "FilterType | None" = None,
    ) -> "Sequence[BaseSQLAlchemyModel] | None":
        """Update model_class from given data."""
        with wrap_any_exception_manager():
            return self.queries.db_update(
                model=self.model_class,
                data=data,
                filters=filters,
                use_flush=self.config.use_flush,
            )

    def _update_instance(
        self,
        *,
        instance: "BaseSQLAlchemyModel",
        data: "DataDict",
    ) -> "tuple[IsUpdated, BaseSQLAlchemyModel]":
        """Update model_class instance from given data.

        Returns tuple with boolean (was instance updated or not) and updated instance.
        """
        with wrap_any_exception_manager():
            return self.queries.change_item(
                data=data,
                item=instance,
                set_none=self.config.update_set_none,
                allowed_none_fields=self.config.update_allowed_none_fields,
                use_flush=self.config.use_flush,
            )

    def _delete(
        self,
        *,
        filters: "FilterType | None" = None,
    ) -> "Count":
        """Delete model_class in db by given filters."""
        with wrap_any_exception_manager():
            return self.queries.db_delete(
                model=self.model_class,
                filters=filters,
                use_flush=self.config.use_flush,
            )

    def _disable(
        self,
        *,
        ids_to_disable: set[Any],
        extra_filters: "FilterType | None" = None,
    ) -> "Count":
        """Disable model_class instances with given ids and extra_filters."""
        with wrap_any_exception_manager():
            self._validate_disable_attributes()
            return self.queries.disable_items(
                model=self.model_class,
                ids_to_disable=ids_to_disable,
                id_field=self.config.disable_id_field,  # type: ignore[reportArgumentType]
                disable_field=self.config.disable_field,  # type: ignore[reportArgumentType]
                field_type=self.config.disable_field_type,  # type: ignore[reportArgumentType]
                allow_filter_by_value=self.config.allow_disable_filter_by_value,
                extra_filters=extra_filters,
                use_flush=self.config.use_flush,
            )


class AsyncRepository(BaseAsyncRepository[BaseSQLAlchemyModel]):
    """Async repository class with implemented base methods."""

    __inheritance_check_model_class__ = False

    async def get(
        self,
        *,
        filters: "FilterType",
        joins: "Sequence[Join] | None" = None,
        loads: "Sequence[Load] | None" = None,
    ) -> "BaseSQLAlchemyModel | None":
        """Get one instance of model_class by given filters."""
        return await self._get(filters=filters, joins=joins, loads=loads)

    async def count(
        self,
        *,
        filters: "FilterType | None" = None,
        joins: "Sequence[Join] | None" = None,
    ) -> int:
        """Get count of instances of model_class by given filters."""
        return await self._count(filters=filters, joins=joins)

    async def exists(
        self,
        *,
        filters: "FilterType | None" = None,
    ) -> bool:
        """Check rows in table for existing."""
        return await self._exists(filters=filters)

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
    ) -> "Sequence[BaseSQLAlchemyModel]":
        """Get list of instances of model_class."""
        return await self._list(
            filters=filters,
            joins=joins,
            loads=loads,
            search=search,
            search_by=search_by,
            order_by=order_by,
            limit=limit,
            offset=offset,
        )

    @overload
    async def create(
        self,
        *,
        data: "DataDict | None",
    ) -> "BaseSQLAlchemyModel": ...

    @overload
    async def create(
        self,
        *,
        data: "Sequence[DataDict]",
    ) -> "Sequence[BaseSQLAlchemyModel]": ...

    async def create(
        self,
        *,
        data: "DataDict | Sequence[DataDict] | None",
    ) -> "BaseSQLAlchemyModel | Sequence[BaseSQLAlchemyModel]":
        """Create model_class instance from given data."""
        return await self._create(data=data)

    async def update(
        self,
        *,
        data: "DataDict",
        filters: "FilterType | None" = None,
    ) -> "Sequence[BaseSQLAlchemyModel] | None":
        """Update model_class from given data."""
        return await self._update(data=data, filters=filters)

    async def update_instance(
        self,
        *,
        instance: "BaseSQLAlchemyModel",
        data: "DataDict",
    ) -> "tuple[IsUpdated, BaseSQLAlchemyModel]":
        """Update model_class instance from given data.

        Returns tuple with boolean (was instance updated or not) and updated instance.
        """
        return await self._update_instance(instance=instance, data=data)

    async def delete(
        self,
        *,
        filters: "FilterType | None" = None,
    ) -> "Count":
        """Delete model_class in db by given filters."""
        return await self._delete(filters=filters)

    async def disable(
        self,
        *,
        ids_to_disable: set[Any],
        extra_filters: "FilterType | None" = None,
    ) -> "Count":
        """Disable model_class instances with given ids and extra_filters."""
        return await self._disable(ids_to_disable=ids_to_disable, extra_filters=extra_filters)


class SyncRepository(BaseSyncRepository[BaseSQLAlchemyModel]):
    """Sync repository class with implemented base methods."""

    __inheritance_check_model_class__ = False

    def get(
        self,
        *,
        filters: "FilterType",
        joins: "Sequence[Join] | None" = None,
        loads: "Sequence[Load] | None" = None,
    ) -> "BaseSQLAlchemyModel | None":
        """Get one instance of model_class by given filters."""
        return self._get(filters=filters, joins=joins, loads=loads)

    def count(
        self,
        *,
        filters: "FilterType | None" = None,
        joins: "Sequence[Join] | None" = None,
    ) -> int:
        """Get count of instances of model_class by given filters."""
        return self._count(filters=filters, joins=joins)

    def exists(
        self,
        *,
        filters: "FilterType | None" = None,
    ) -> bool:
        """Check rows in table for existing."""
        return self._exists(filters=filters)

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
    ) -> "Sequence[BaseSQLAlchemyModel]":
        """Get list of instances of model_class."""
        return self._list(
            filters=filters,
            joins=joins,
            loads=loads,
            search=search,
            search_by=search_by,
            order_by=order_by,
            limit=limit,
            offset=offset,
        )

    @overload
    def create(
        self,
        *,
        data: "DataDict | None",
    ) -> "BaseSQLAlchemyModel": ...

    @overload
    def create(
        self,
        *,
        data: "Sequence[DataDict]",
    ) -> "Sequence[BaseSQLAlchemyModel]": ...

    def create(
        self,
        *,
        data: "DataDict | Sequence[DataDict] | None",
    ) -> "BaseSQLAlchemyModel | Sequence[BaseSQLAlchemyModel]":
        """Create model_class instance from given data."""
        return self._create(data=data)

    def update(
        self,
        *,
        data: "DataDict",
        filters: "FilterType | None" = None,
    ) -> "Sequence[BaseSQLAlchemyModel] | None":
        """Update model_class from given data."""
        return self._update(data=data, filters=filters)

    def update_instance(
        self,
        *,
        instance: "BaseSQLAlchemyModel",
        data: "DataDict",
    ) -> "tuple[IsUpdated, BaseSQLAlchemyModel]":
        """Update model_class instance from given data.

        Returns tuple with boolean (was instance updated or not) and updated instance.
        """
        return self._update_instance(instance=instance, data=data)

    def delete(
        self,
        *,
        filters: "FilterType | None" = None,
    ) -> "Count":
        """Delete model_class in db by given filters."""
        return self._delete(filters=filters)

    def disable(
        self,
        *,
        ids_to_disable: set[Any],
        extra_filters: "FilterType | None" = None,
    ) -> "Count":
        """Disable model_class instances with given ids and extra_filters."""
        return self._disable(ids_to_disable=ids_to_disable, extra_filters=extra_filters)
