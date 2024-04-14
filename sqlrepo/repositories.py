import datetime
import warnings
from collections.abc import Callable
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Final,
    ForwardRef,
    Generic,
    Literal,
    NotRequired,
    TypedDict,
    TypeVar,
    get_args,
)

from dev_utils.sqlalchemy.filters.converters import (  # type: ignore
    AdvancedOperatorFilterConverter,
    BaseFilterConverter,
    DjangoLikeFilterConverter,
    SimpleFilterConverter,
)
from dev_utils.sqlalchemy.filters.types import FilterConverterStrategiesLiteral  # type: ignore
from sqlalchemy.orm import DeclarativeBase as Base
from sqlalchemy.orm import joinedload

from sqlrepo import exc as sqlrepo_exc
from sqlrepo.logging import logger as default_logger
from sqlrepo.queries import BaseAsyncQuery, BaseSyncQuery

if TYPE_CHECKING:
    from collections.abc import Sequence
    from logging import Logger

    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm.attributes import InstrumentedAttribute, QueryableAttribute
    from sqlalchemy.orm.session import Session
    from sqlalchemy.orm.strategy_options import _AbstractLoad  # type: ignore
    from sqlalchemy.sql._typing import _ColumnExpressionOrStrLabelArgument  # type: ignore
    from sqlalchemy.sql.elements import ColumnElement

    class JoinKwargs(TypedDict):
        """Kwargs for join."""

        isouter: NotRequired[bool]
        full: NotRequired[bool]

    Count = int
    Model = type[Base]
    JoinClause = ColumnElement[bool]
    ModelWithOnclause = tuple[Model, JoinClause]
    CompleteModel = tuple[Model, JoinClause, JoinKwargs]
    Join = str | Model | ModelWithOnclause | CompleteModel
    Filter = dict[str, Any] | Sequence[dict[str, Any] | ColumnElement[bool]] | ColumnElement[bool]
    Load = str | _AbstractLoad
    SearchParam = str | QueryableAttribute[Any]
    OrderByParam = _ColumnExpressionOrStrLabelArgument[Any]
    DataDict = dict[str, Any]


StrField = str
BaseSQLAlchemyModel = TypeVar("BaseSQLAlchemyModel", bound=Base)


class BaseRepository(Generic[BaseSQLAlchemyModel]):
    """Base repository class.

    Don't Use it directly. Use BaseAsyncRepository and BaseSyncRepository, or pass query_class
    directly (not recommended.)
    """

    __inheritance_check_model_class__: bool = True
    _model_class: type["BaseSQLAlchemyModel"]

    # TODO: добавить specific_column_mapping в фильтры, joins и loads.
    specific_column_mapping: ClassVar["dict[str, ColumnElement[Any]]"] = {}
    """
    Uses as mapping for some attributes, that you need to alias or need to specify column
    from other models.

    Warning: if you specify column from other model, it may cause errors. For example, update
    doesn't use it for filters, because joins are not presents in update.
    """
    use_flush: ClassVar[bool] = True
    """
    Uses as flag of flush method in SQLAlchemy session.

    By default, True, because repository has (mostly) multiple methods evaluate use. For example,
    generally, you want to create some model instances, create some other (for example, log table)
    and then receive other model instance in one use (for example, in Unit of work pattern).

    If you will work with repositories as single methods uses, switch to use_flush=False. It will
    make queries commit any changes.
    """
    allow_disable_filter_by_value: ClassVar[bool] = True
    """
    Uses as flag of filtering in disable method.

    If True, make additional filter, which will exclude items, which already disabled.
    Logic of disable depends on type of disable column. See ``disable_field`` docstring for more
    information.

    By default True, because it will make more efficient query to not override disable column. In
    some cases (like datetime disable field) it may be better to turn off this flag to save disable
    with new context (repeat disable, if your domain supports repeat disable and it make sense).
    """
    update_set_none: ClassVar[bool] = False
    update_allowed_none_fields: ClassVar['Literal["*"] | set[StrField]'] = "*"
    disable_field_type: ClassVar[type[datetime.datetime] | type[bool]] = datetime.datetime
    unique_list_items: ClassVar[bool] = False
    filter_convert_strategy: ClassVar[FilterConverterStrategiesLiteral] = "simple"
    load_strategy: ClassVar[Callable[..., "_AbstractLoad"]] = joinedload
    id_field: ClassVar["InstrumentedAttribute[Any] | None"] = None
    disable_field: ClassVar["InstrumentedAttribute[Any] | None"] = None

    _filter_convert_classes: Final[
        dict[FilterConverterStrategiesLiteral, type[BaseFilterConverter]]
    ] = {
        "simple": SimpleFilterConverter,
        "advanced": AdvancedOperatorFilterConverter,
        "django": DjangoLikeFilterConverter,
    }

    def __init_subclass__(cls) -> None:  # noqa: D105
        if hasattr(cls, "_model_class"):
            msg = (
                "Don't change _model_class attribute to class. Use generic syntax instead. "
                "See PEP 646 (https://peps.python.org/pep-0646/)"
            )
            warnings.warn(msg, stacklevel=2)
            return
        if cls.__inheritance_check_model_class__ is False:
            cls.__inheritance_check_model_class__ = True
            return
        try:
            # PEP-560: https://peps.python.org/pep-0560/
            # NOTE: this code is needed for getting type from generic: Generic[int] -> int type
            # get_args get params from __orig_bases__, that contains Generic passed types.
            model, *_ = get_args(cls.__orig_bases__[0])  # type: ignore
        except Exception as exc:
            msg = f"Error during getting information about Generic types for {cls.__name__}."
            raise sqlrepo_exc.RepositoryAttributeError(msg) from exc
        if isinstance(model, ForwardRef):
            try:
                model = eval(model.__forward_arg__)  # noqa: S307
            except Exception as exc:
                msg = (
                    "Can't evaluate ForwardRef of generic type. "
                    "Don't use type in generic with quotes. "
                    f"Original exception: {str(exc)}"
                )
                warnings.warn(msg, stacklevel=2)
                return
        if isinstance(model, TypeVar):
            msg = "GenericType was not passed for SQLAlchemy model declarative class."
            warnings.warn(msg, stacklevel=2)
            return
        if not issubclass(model, Base):
            msg = "Passed GenericType is not SQLAlchemy model declarative class."
            warnings.warn(msg, stacklevel=2)
            return
        cls._model_class = model  # type: ignore

    def get_filter_convert_class(self) -> type[BaseFilterConverter]:
        """Get filter convert class from passed strategy."""
        return self._filter_convert_classes[self.filter_convert_strategy]


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
            self.get_filter_convert_class(),
            self.specific_column_mapping,
            self.load_strategy,
        )

    async def get(
        self,
        *,
        filters: "Filter | None" = None,
        joins: "Sequence[Join] | None" = None,
        loads: "Sequence[Load] | None" = None,
    ) -> "BaseSQLAlchemyModel | None":
        result = await self.queries.get_item(
            model=self._model_class,
            joins=joins,
            loads=loads,
            filters=filters,
        )
        return result

    async def count(
        self,
        *,
        joins: "Sequence[Join] | None" = None,
        filters: "Filter | None" = None,
    ) -> int:
        result = await self.queries.get_items_count(
            model=self._model_class,
            joins=joins,
            filters=filters,
        )
        return result

    async def list(  # noqa: A003
        self,
        *,
        # TODO: улучшить интерфейс, чтобы можно было принимать как 1 элемент, так и несколько
        joins: "Sequence[Join] | None" = None,
        loads: "Sequence[Load] | None" = None,
        filters: "Filter | None" = None,
        search: str | None = None,
        search_by: "Sequence[SearchParam] | None" = None,
        order_by: "Sequence[OrderByParam] | None" = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> "Sequence[BaseSQLAlchemyModel]":
        result = await self.queries.get_item_list(
            model=self._model_class,
            joins=joins,
            loads=loads,
            filters=filters,
            search=search,
            search_by=search_by,
            order_by=order_by,
            limit=limit,
            offset=offset,
            unique_items=self.unique_list_items,
        )
        return result

    async def create_instance(
        self,
        *,
        data: "DataDict | None" = None,
    ) -> "BaseSQLAlchemyModel":
        result = await self.queries.create_item(
            model=self._model_class,
            data=data,
            use_flush=self.use_flush,
        )
        return result

    async def update(
        self,
        *,
        data: "DataDict",
        filters: "Filter | None" = None,
    ) -> "Sequence[BaseSQLAlchemyModel] | None":
        result = await self.queries.db_update(
            model=self._model_class,
            data=data,
            filters=filters,
            use_flush=self.use_flush,
        )
        return result

    async def update_instance(
        self,
        *,
        instance: "BaseSQLAlchemyModel",
        data: "DataDict",
    ) -> "tuple[bool, BaseSQLAlchemyModel]":
        result = await self.queries.change_item(
            data=data,
            item=instance,
            set_none=self.update_set_none,
            allowed_none_fields=self.update_allowed_none_fields,
            use_flush=self.use_flush,
        )
        return result

    async def disable(
        self,
        *,
        ids_to_disable: set[Any],
        extra_filters: "Filter | None" = None,
    ) -> "Count":
        if self.id_field is None or self.disable_field is None:
            msg = (
                'Attribute "id_field" or "disable_field" not set in your repository class. '
                "Can't disable entities."
            )
            raise sqlrepo_exc.RepositoryAttributeError(msg)
        result = await self.queries.disable_items(
            model=self._model_class,
            ids_to_disable=ids_to_disable,
            id_field=self.id_field,
            disable_field=self.disable_field,
            field_type=self.disable_field_type,
            allow_filter_by_value=self.allow_disable_filter_by_value,
            extra_filters=extra_filters,
            use_flush=self.use_flush,
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
    ) -> None:
        self.session = session
        self.queries = self.query_class(
            session,
            self.get_filter_convert_class(),
            self.specific_column_mapping,
            self.load_strategy,
        )

    def get(
        self,
        *,
        filters: "Filter | None" = None,
        joins: "Sequence[Join] | None" = None,
        loads: "Sequence[Load] | None" = None,
    ) -> "BaseSQLAlchemyModel | None":
        result = self.queries.get_item(
            model=self._model_class,
            joins=joins,
            loads=loads,
            filters=filters,
        )
        return result

    def count(
        self,
        *,
        joins: "Sequence[Join] | None" = None,
        filters: "Filter | None" = None,
    ) -> int:
        result = self.queries.get_items_count(
            model=self._model_class,
            joins=joins,
            filters=filters,
        )
        return result

    async def list(  # noqa: A003
        self,
        *,
        # TODO: улучшить интерфейс, чтобы можно было принимать как 1 элемент, так и несколько
        joins: "Sequence[Join] | None" = None,
        loads: "Sequence[Load] | None" = None,
        filters: "Filter | None" = None,
        search: str | None = None,
        search_by: "Sequence[SearchParam] | None" = None,
        order_by: "Sequence[OrderByParam] | None" = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> "Sequence[BaseSQLAlchemyModel]":
        result = self.queries.get_item_list(
            model=self._model_class,
            joins=joins,
            loads=loads,
            filters=filters,
            search=search,
            search_by=search_by,
            order_by=order_by,
            limit=limit,
            offset=offset,
            unique_items=self.unique_list_items,
        )
        return result

    async def create_instance(
        self,
        *,
        data: "DataDict | None" = None,
    ) -> "BaseSQLAlchemyModel":
        result = self.queries.create_item(
            model=self._model_class,
            data=data,
            use_flush=self.use_flush,
        )
        return result

    async def update(
        self,
        *,
        data: "DataDict",
        filters: "Filter | None" = None,
    ) -> "Sequence[BaseSQLAlchemyModel] | None":
        result = self.queries.db_update(
            model=self._model_class,
            data=data,
            filters=filters,
            use_flush=self.use_flush,
        )
        return result

    def update_instance(
        self,
        *,
        instance: "BaseSQLAlchemyModel",
        data: "DataDict",
    ) -> "tuple[bool, BaseSQLAlchemyModel]":
        result = self.queries.change_item(
            data=data,
            item=instance,
            set_none=self.update_set_none,
            allowed_none_fields=self.update_allowed_none_fields,
            use_flush=self.use_flush,
        )
        return result

    def disable(
        self,
        *,
        ids_to_disable: set[Any],
        extra_filters: "Filter | None" = None,
    ) -> "Count":
        if self.id_field is None or self.disable_field is None:
            msg = (
                'Attribute "id_field" or "disable_field" not set in your repository class. '
                "Can't disable entities."
            )
            raise sqlrepo_exc.RepositoryAttributeError(msg)
        result = self.queries.disable_items(
            model=self._model_class,
            ids_to_disable=ids_to_disable,
            id_field=self.id_field,
            disable_field=self.disable_field,
            field_type=self.disable_field_type,
            allow_filter_by_value=self.allow_disable_filter_by_value,
            extra_filters=extra_filters,
            use_flush=self.use_flush,
        )
        return result
