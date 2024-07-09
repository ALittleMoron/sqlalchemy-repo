"""Main implementations for sqlrepo project."""

import importlib
import warnings
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
from sqlrepo.logging import logger as default_logger
from sqlrepo.queries import BaseAsyncQuery, BaseSyncQuery
from sqlrepo.wrappers import wrap_any_exception_manager

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from logging import Logger

    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm.attributes import QueryableAttribute
    from sqlalchemy.orm.session import Session
    from sqlalchemy.orm.strategy_options import _AbstractLoad  # type: ignore
    from sqlalchemy.sql._typing import _ColumnExpressionOrStrLabelArgument  # type: ignore
    from sqlalchemy.sql.elements import ColumnElement

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
    Filter = dict[str, Any] | Sequence[dict[str, Any] | ColumnElement[bool]] | ColumnElement[bool]
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
            msg = (
                'Attribute "disable_id_field" or "disable_field" or "disable_field_type" not '
                "set in your repository class. Can't disable entities."
            )
            raise sqlrepo_exc.RepositoryAttributeError(msg)

    def __init_subclass__(cls) -> None:  # noqa: D105
        super().__init_subclass__()
        if hasattr(cls, "model_class"):
            msg = (
                "Don't change model_class attribute to class. Use generic syntax instead. "
                "See PEP 646 (https://peps.python.org/pep-0646/). Repository will automatically "
                "add model_class attribute by extracting it from Generic type."
            )
            warnings.warn(msg, RepositoryModelClassIncorrectUseWarning, stacklevel=2)
            return
        if cls.__inheritance_check_model_class__ is False:
            cls.__inheritance_check_model_class__ = True
            return
        try:
            # PEP-560: https://peps.python.org/pep-0560/
            # NOTE: this code is needed for getting type from generic: Generic[int] -> int type
            # get_args get params from __orig_bases__, that contains Generic passed types.
            model, *_ = get_args(cls.__orig_bases__[0])  # type: ignore
        except Exception as exc:  # pragma: no coverage
            msg = (
                f"Error during getting information about Generic types for {cls.__name__}. "
                f"Original exception: {str(exc)}"
            )
            warnings.warn(msg, RepositoryModelClassIncorrectUseWarning, stacklevel=2)
            return
        if isinstance(model, ForwardRef):
            try:
                repo_module = vars(cls).get("__module__")
                if not repo_module:  # pragma: no coverage
                    msg = (
                        f"No attribute __module__ in {cls}. Can't import global context for "
                        "ForwardRef resolving."
                    )
                    raise TypeError(msg)  # noqa: TRY301
                model_globals = vars(importlib.import_module(repo_module))
                model = eval(model.__forward_arg__, model_globals)  # noqa: S307
            except Exception as exc:
                msg = (
                    "Can't evaluate ForwardRef of generic type. "
                    "Don't use type in generic with quotes. "
                    f"Original exception: {str(exc)}"
                )
                warnings.warn(msg, RepositoryModelClassIncorrectUseWarning, stacklevel=2)
                return
        if isinstance(model, TypeVar):
            msg = "GenericType was not passed for SQLAlchemy model declarative class."
            warnings.warn(msg, RepositoryModelClassIncorrectUseWarning, stacklevel=2)
            return
        if not issubclass(model, Base):
            msg = "Passed GenericType is not SQLAlchemy model declarative class."
            warnings.warn(msg, RepositoryModelClassIncorrectUseWarning, stacklevel=2)
            return
        cls.model_class = model  # type: ignore


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
        logger: "Logger" = default_logger,
    ) -> None:
        self.session = session
        self.logger = logger
        self.queries = self.query_class(
            session,
            self.config.get_filter_convert_class(),
            self.config.specific_column_mapping,
            logger,
        )

    async def get(
        self,
        filters: "Filter",
        *,
        joins: "Sequence[Join] | None" = None,
        loads: "Sequence[Load] | None" = None,
    ) -> "BaseSQLAlchemyModel | None":
        """Get one instance of model_class by given filters."""
        with wrap_any_exception_manager():
            result = await self.queries.get_item(
                model=self.model_class,
                joins=joins,
                loads=loads,
                filters=filters,
            )
        return result

    async def count(
        self,
        *,
        filters: "Filter | None" = None,
        joins: "Sequence[Join] | None" = None,
    ) -> int:
        """Get count of instances of model_class by given filters."""
        with wrap_any_exception_manager():
            result = await self.queries.get_items_count(
                model=self.model_class,
                joins=joins,
                filters=filters,
            )
        return result

    async def list(  # noqa: A003
        self,
        *,
        filters: "Filter | None" = None,
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
            result = await self.queries.get_item_list(
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
        return result

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
        with wrap_any_exception_manager():
            result = await self.queries.db_create(
                model=self.model_class,
                data=data,
            )
        return result

    async def update(
        self,
        *,
        data: "DataDict",
        filters: "Filter | None" = None,
    ) -> "Sequence[BaseSQLAlchemyModel] | None":
        """Update model_class from given data."""
        with wrap_any_exception_manager():
            result = await self.queries.db_update(
                model=self.model_class,
                data=data,
                filters=filters,
                use_flush=self.config.use_flush,
            )
        return result

    async def update_instance(
        self,
        *,
        instance: "BaseSQLAlchemyModel",
        data: "DataDict",
    ) -> "tuple[IsUpdated, BaseSQLAlchemyModel]":
        """Update model_class instance from given data.

        Returns tuple with boolean (was instance updated or not) and updated instance.
        """
        with wrap_any_exception_manager():
            result = await self.queries.change_item(
                data=data,
                item=instance,
                set_none=self.config.update_set_none,
                allowed_none_fields=self.config.update_allowed_none_fields,
                use_flush=self.config.use_flush,
            )
        return result

    async def delete(
        self,
        *,
        filters: "Filter | None" = None,
    ) -> "Count":
        """Delete model_class in db by given filters."""
        with wrap_any_exception_manager():
            result = await self.queries.db_delete(
                model=self.model_class,
                filters=filters,
                use_flush=self.config.use_flush,
            )
        return result

    async def disable(
        self,
        *,
        ids_to_disable: set[Any],
        extra_filters: "Filter | None" = None,
    ) -> "Count":
        """Disable model_class instances with given ids and extra_filters."""
        with wrap_any_exception_manager():
            self._validate_disable_attributes()
            result = await self.queries.disable_items(
                model=self.model_class,
                ids_to_disable=ids_to_disable,
                id_field=self.config.disable_id_field,  # type: ignore
                disable_field=self.config.disable_field,  # type: ignore
                field_type=self.config.disable_field_type,  # type: ignore
                allow_filter_by_value=self.config.allow_disable_filter_by_value,
                extra_filters=extra_filters,
                use_flush=self.config.use_flush,
            )
        return result


class BaseSyncRepository(BaseRepository[BaseSQLAlchemyModel]):
    """Base repository class with sync interface.

    Has main CRUD methods for working with model. Use sync session of SQLAlchemy to work with this
    class.
    """

    __inheritance_check_model_class__ = False
    query_class: type["BaseSyncQuery"] = BaseSyncQuery

    def __init__(
        self,
        session: "Session",
        logger: "Logger" = default_logger,
    ) -> None:
        self.session = session
        self.queries = self.query_class(
            session,
            self.config.get_filter_convert_class(),
            self.config.specific_column_mapping,
            logger,
        )

    def get(
        self,
        *,
        filters: "Filter",
        joins: "Sequence[Join] | None" = None,
        loads: "Sequence[Load] | None" = None,
    ) -> "BaseSQLAlchemyModel | None":
        """Get one instance of model_class by given filters."""
        with wrap_any_exception_manager():
            result = self.queries.get_item(
                model=self.model_class,
                joins=joins,
                loads=loads,
                filters=filters,
            )
        return result

    def count(
        self,
        *,
        filters: "Filter | None" = None,
        joins: "Sequence[Join] | None" = None,
    ) -> int:
        """Get count of instances of model_class by given filters."""
        with wrap_any_exception_manager():
            result = self.queries.get_items_count(
                model=self.model_class,
                joins=joins,
                filters=filters,
            )
        return result

    def list(  # noqa: A003
        self,
        *,
        joins: "Sequence[Join] | None" = None,
        loads: "Sequence[Load] | None" = None,
        filters: "Filter | None" = None,
        search: str | None = None,
        search_by: "SearchParam | Iterable[SearchParam] | None" = None,
        order_by: "OrderByParam | Iterable[OrderByParam] | None" = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> "Sequence[BaseSQLAlchemyModel]":
        """Get list of instances of model_class."""
        with wrap_any_exception_manager():
            result = self.queries.get_item_list(
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
        return result

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
        with wrap_any_exception_manager():
            result = self.queries.db_create(
                model=self.model_class,
                data=data,
            )
        return result

    def update(
        self,
        *,
        data: "DataDict",
        filters: "Filter | None" = None,
    ) -> "Sequence[BaseSQLAlchemyModel] | None":
        """Update model_class from given data."""
        with wrap_any_exception_manager():
            result = self.queries.db_update(
                model=self.model_class,
                data=data,
                filters=filters,
                use_flush=self.config.use_flush,
            )
        return result

    def update_instance(
        self,
        *,
        instance: "BaseSQLAlchemyModel",
        data: "DataDict",
    ) -> "tuple[IsUpdated, BaseSQLAlchemyModel]":
        """Update model_class instance from given data.

        Returns tuple with boolean (was instance updated or not) and updated instance.
        """
        with wrap_any_exception_manager():
            result = self.queries.change_item(
                data=data,
                item=instance,
                set_none=self.config.update_set_none,
                allowed_none_fields=self.config.update_allowed_none_fields,
                use_flush=self.config.use_flush,
            )
        return result

    def delete(
        self,
        *,
        filters: "Filter | None" = None,
    ) -> "Count":
        """Delete model_class in db by given filters."""
        with wrap_any_exception_manager():
            result = self.queries.db_delete(
                model=self.model_class,
                filters=filters,
                use_flush=self.config.use_flush,
            )
        return result

    def disable(
        self,
        *,
        ids_to_disable: set[Any],
        extra_filters: "Filter | None" = None,
    ) -> "Count":
        """Disable model_class instances with given ids and extra_filters."""
        with wrap_any_exception_manager():
            self._validate_disable_attributes()
            result = self.queries.disable_items(
                model=self.model_class,
                ids_to_disable=ids_to_disable,
                id_field=self.config.disable_id_field,  # type: ignore
                disable_field=self.config.disable_field,  # type: ignore
                field_type=self.config.disable_field_type,  # type: ignore
                allow_filter_by_value=self.config.allow_disable_filter_by_value,
                extra_filters=extra_filters,
                use_flush=self.config.use_flush,
            )
        return result
