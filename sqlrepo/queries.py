"""Queries classes with executable statements and methods with them."""

import datetime
import re
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal, NotRequired, TypedDict, TypeVar, overload

from dev_utils.core.utils import get_utc_now
from dev_utils.sqlalchemy.filters.converters import BaseFilterConverter
from dev_utils.sqlalchemy.utils import apply_joins, apply_loads, get_sqlalchemy_attribute
from sqlalchemy import CursorResult, and_, delete
from sqlalchemy import exc as sqlalchemy_exc
from sqlalchemy import func, insert, or_, select, text, update
from sqlalchemy.orm import joinedload

from sqlrepo.exc import QueryError
from sqlrepo.logging import logger as default_logger


class JoinKwargs(TypedDict):
    """Kwargs for join statement."""

    isouter: NotRequired[bool]
    full: NotRequired[bool]


if TYPE_CHECKING:
    from collections.abc import Sequence
    from logging import Logger

    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import DeclarativeBase as Base
    from sqlalchemy.orm import QueryableAttribute
    from sqlalchemy.orm.attributes import InstrumentedAttribute
    from sqlalchemy.orm.session import Session
    from sqlalchemy.orm.strategy_options import _AbstractLoad  # type: ignore
    from sqlalchemy.sql._typing import _ColumnExpressionOrStrLabelArgument  # type: ignore
    from sqlalchemy.sql.dml import Delete, ReturningInsert, ReturningUpdate, Update
    from sqlalchemy.sql.elements import ColumnElement
    from sqlalchemy.sql.selectable import Select

    BaseSQLAlchemyModel = TypeVar("BaseSQLAlchemyModel", bound=Base)
    T = TypeVar("T")
    Count = int
    Deleted = bool
    Updated = bool
    Model = type[Base]
    JoinClause = ColumnElement[bool]
    ModelWithOnclause = tuple[Model, JoinClause]
    CompleteModel = tuple[Model, JoinClause, JoinKwargs]
    Join = str | Model | ModelWithOnclause | CompleteModel
    Filter = dict[str, Any] | Sequence[dict[str, Any] | ColumnElement[bool]] | ColumnElement[bool]
    Load = str | _AbstractLoad
    SearchParam = str | QueryableAttribute[Any]
    ColumnParam = str | QueryableAttribute[Any]
    OrderByParam = _ColumnExpressionOrStrLabelArgument[Any]
    DataDict = dict[str, Any]
    StrField = str


class BaseQuery:
    """Base query class.

    Implements base logic for queries like generating statements or filters. Don't use it directly.
    """

    def __init__(
        self,
        filter_converter_class: type[BaseFilterConverter],
        specific_column_mapping: dict[str, "InstrumentedAttribute[Any]"] | None = None,
        load_strategy: Callable[..., "_AbstractLoad"] = joinedload,
        logger: "Logger" = default_logger,
    ) -> None:
        self.specific_column_mapping = specific_column_mapping
        self.filter_converter_class = filter_converter_class
        self.load_strategy = load_strategy
        self.logger = logger

    def _resolve_specific_columns(
        self,
        *,
        elements: "Sequence[T]",
    ) -> "Sequence[T]":
        """Get all SQLAlchemy columns from strings (uses specific columns)."""
        if not self.specific_column_mapping:
            return elements
        new_elements: "list[T]" = []
        for ele in elements:
            if not isinstance(ele, str) or ele not in self.specific_column_mapping:
                new_elements.append(ele)
            else:
                new_elements.append(self.specific_column_mapping[ele])  # type: ignore
        return new_elements

    def _resolve_and_apply_joins(
        self,
        *,
        stmt: "Select[tuple[T]]",
        joins: "Sequence[Join]",
    ) -> "Select[tuple[T]]":
        """Resolve joins from strings."""
        # FIXME: may cause situation, when user passed Join as tuple may cause error.
        # (Model, Model.id == OtherModel.model_id)  # noqa: ERA001
        # or
        # (Model, Model.id == OtherModel.model_id, {"isouter": True})  # noqa: ERA001
        if isinstance(joins, str):
            joins = [joins]
        for join in joins:
            if isinstance(join, tuple | list):
                target, clause, *kw_list = join
                join_kwargs = kw_list[0] if len(kw_list) == 1 else JoinKwargs()
                stmt = stmt.join(target, clause, **join_kwargs)
            elif isinstance(join, str):
                stmt = apply_joins(stmt, join)
            else:
                stmt = stmt.join(join)
        return stmt

    def _resolve_and_apply_loads(
        self,
        *,
        stmt: "Select[tuple[T]]",
        loads: "Sequence[Load]",
    ) -> "Select[tuple[T]]":
        if isinstance(loads, str):
            loads = [loads]
        for load in loads:
            stmt = (
                apply_loads(stmt, load, load_strategy=self.load_strategy)
                if isinstance(load, str)
                else stmt.options(load)
            )
        return stmt

    def _make_disable_filters(  # noqa: C901
        self,
        *,
        model: "type[BaseSQLAlchemyModel]",
        id_field: "QueryableAttribute[Any]",
        ids_to_disable: set[Any],
        disable_field: "QueryableAttribute[Any]",
        field_type: type[datetime.datetime] | type[bool] = datetime.datetime,
        allow_filter_by_value: bool = True,
        extra_filters: "Filter | None" = None,
    ) -> list["ColumnElement[bool]"]:
        """Generate disable filters from given data."""
        filters: list["ColumnElement[bool]"] = list()
        filters.append(id_field.in_(ids_to_disable))
        if allow_filter_by_value and field_type == bool:
            filters.append(disable_field.is_not(True))
        elif allow_filter_by_value and field_type == datetime.datetime:
            filters.append(disable_field.is_(None))
        if extra_filters is not None:
            sqlalchemy_filters = self.filter_converter_class.convert(model, extra_filters)
            filters.extend(sqlalchemy_filters)
        return filters

    def _make_search_filter(
        self,
        search: str,
        model: type["BaseSQLAlchemyModel"],
        *search_by_args: "SearchParam",
        use_and_clause: bool = False,
        case_insensitive: bool = True,
    ) -> "ColumnElement[bool]":
        """Generate search filters from given data."""
        filters: list["ColumnElement[bool]"] = []
        search_by_args = self._resolve_specific_columns(elements=search_by_args)  # type: ignore
        for search_by in search_by_args:
            if isinstance(search_by, str):
                search_by = get_sqlalchemy_attribute(model, search_by)
            (
                filters.append(search_by.ilike(f"%{search}%"))
                if case_insensitive
                else search_by.like(f"%{search}%")
            )
        if use_and_clause:
            return and_(*filters)
        return or_(*filters)

    def _get_item_stmt(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        filters: "Filter | None" = None,
        joins: "Sequence[Join] | None" = None,
        loads: "Sequence[Load] | None" = None,
    ) -> "Select[tuple[BaseSQLAlchemyModel]]":
        """Generate SQLAlchemy stmt to get one item from filters, joins and loads."""
        stmt = select(model)
        if joins is not None:
            stmt = self._resolve_and_apply_joins(stmt=stmt, joins=joins)
        if loads is not None:
            stmt = self._resolve_and_apply_loads(
                stmt=stmt,
                loads=loads,
            )
        if filters is not None:
            sqlalchemy_filters = self.filter_converter_class.convert(model, filters)
            stmt = stmt.where(*sqlalchemy_filters)
        return stmt

    def _get_items_count_stmt(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        joins: "Sequence[Join] | None" = None,
        filters: "Filter | None" = None,
    ) -> "Select[tuple[int]]":
        """Generate SQLAlchemy stmt to get count of items from filters and joins."""
        stmt = select(func.count()).select_from(model)
        if joins is not None:
            stmt = self._resolve_and_apply_joins(stmt=stmt, joins=joins)
        if filters is not None:
            sqlalchemy_filters = self.filter_converter_class.convert(model, filters)
            stmt = stmt.where(*sqlalchemy_filters)
        return stmt

    def _get_item_list_stmt(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        joins: "Sequence[Join] | None" = None,
        loads: "Sequence[Load] | None" = None,
        filters: "Filter | None" = None,
        search: str | None = None,
        search_by: "Sequence[SearchParam] | None" = None,
        order_by: "Sequence[OrderByParam] | None" = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> "Select[tuple[BaseSQLAlchemyModel]]":
        """Generate SQLAlchemy stmt to get list of items from given data."""
        stmt = self._get_item_stmt(model=model, filters=filters, joins=joins, loads=loads)
        if search is not None and search_by is not None:
            search = re.escape(search)
            search = search.translate(str.maketrans({"%": r"\%", "_": r"\_", "/": r"\/"}))
            stmt = stmt.where(self._make_search_filter(search, model, *search_by))
        if order_by is not None:
            order_by_resolved = self._resolve_specific_columns(elements=order_by)
            order_by_resolved = [
                text(ele) if isinstance(ele, str) else ele for ele in order_by_resolved
            ]
            stmt = stmt.order_by(*order_by_resolved)
        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)
        return stmt

    def _db_insert_stmt(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        data: "DataDict | Sequence[DataDict] | None" = None,
    ) -> "ReturningInsert[tuple[BaseSQLAlchemyModel]]":
        """Generate SQLAlchemy stmt to insert data."""
        stmt = insert(model)
        stmt = stmt.values() if data is None else stmt.values(data)
        stmt = stmt.returning(model)
        return stmt

    def _prepare_create_items(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        data: "DataDict | Sequence[DataDict | None] | None" = None,
    ) -> "Sequence[BaseSQLAlchemyModel]":
        """Prepare items to create.

        Initialize model instances by given data.
        """
        if isinstance(data, dict) or data is None:
            data = [data]
        items: list["BaseSQLAlchemyModel"] = []
        for data_ele in data:
            items.append(model() if data_ele is None else model(**data_ele))
        return items

    def _db_update_stmt(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        data: "DataDict",
        filters: "Filter | None" = None,
    ) -> "ReturningUpdate[tuple[BaseSQLAlchemyModel]]":
        """Generate SQLAlchemy stmt to update items with given data."""
        stmt = update(model)
        if filters is not None:
            sqlalchemy_filters = self.filter_converter_class.convert(model, filters)
            stmt = stmt.where(*sqlalchemy_filters)
        stmt = stmt.values(**data).returning(model)
        return stmt

    def _db_delete_stmt(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        filters: "Filter | None" = None,
    ) -> "Delete":
        """Generate SQLAlchemy stmt to delete items with given data."""
        stmt = delete(model)
        if filters is not None:
            sqlalchemy_filters = self.filter_converter_class.convert(model, filters)
            stmt = stmt.where(*sqlalchemy_filters)
        return stmt

    def _disable_items_stmt(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        ids_to_disable: set[Any],
        id_field: "InstrumentedAttribute[Any]",
        disable_field: "InstrumentedAttribute[Any]",
        field_type: type[datetime.datetime] | type[bool] = datetime.datetime,
        allow_filter_by_value: bool = True,
        extra_filters: "Filter | None" = None,
    ) -> "Update":
        """Generate SQLAlchemy stmt to disable items with given data."""
        if issubclass(field_type, bool):
            field_value = True
        elif issubclass(field_type, datetime.datetime):  # type: ignore
            field_value = get_utc_now()
        else:
            msg = (
                'Parameter "field_type" should be one of the following: bool, datetime. '
                f"{field_type} was passed."
            )
            self.logger.error(msg)
            raise QueryError(msg)
        if len(ids_to_disable) == 0:
            msg = 'Parameter "ids_to_disable" should contains at least one element.'
            self.logger.error(msg)
            raise QueryError(msg)
        filters = self._make_disable_filters(
            model=model,
            ids_to_disable=ids_to_disable,
            id_field=id_field,
            disable_field=disable_field,
            field_type=field_type,
            allow_filter_by_value=allow_filter_by_value,
            extra_filters=extra_filters,
        )
        stmt = update(model).where(*filters).values({disable_field: field_value})
        return stmt


class BaseSyncQuery(BaseQuery):
    """Base query class with sync interface."""

    def __init__(
        self,
        session: "Session",
        filter_converter_class: type[BaseFilterConverter],
        specific_column_mapping: dict[str, "InstrumentedAttribute[Any]"] | None = None,
        load_strategy: Callable[[Any], "_AbstractLoad"] = joinedload,
        logger: "Logger" = default_logger,
    ) -> None:
        self.session = session
        super().__init__(filter_converter_class, specific_column_mapping, load_strategy, logger)

    def get_item(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        filters: "Filter | None" = None,
        joins: "Sequence[Join] | None" = None,
        loads: "Sequence[Load] | None" = None,
    ) -> "BaseSQLAlchemyModel | None":
        """Get one instance of model by given filters."""
        stmt = self._get_item_stmt(
            model=model,
            filters=filters,
            joins=joins,
            loads=loads,
        )
        result = self.session.scalars(stmt)
        return result.first()

    def get_items_count(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        joins: "Sequence[Join] | None" = None,
        filters: "Filter | None" = None,
    ) -> int:
        """Get count of instances of model by given filters."""
        stmt = self._get_items_count_stmt(
            model=model,
            joins=joins,
            filters=filters,
        )
        count = self.session.scalar(stmt)
        # NOTE: code block for sure.
        if count is None:  # pragma: no cover
            count = 0
        return count

    def get_item_list(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        joins: "Sequence[Join] | None" = None,
        loads: "Sequence[Load] | None" = None,
        filters: "Filter | None" = None,
        search: str | None = None,
        search_by: "Sequence[SearchParam] | None" = None,
        order_by: "Sequence[OrderByParam] | None" = None,
        limit: int | None = None,
        offset: int | None = None,
        unique_items: bool = False,
    ) -> "Sequence[BaseSQLAlchemyModel]":
        """Get list of instances of model."""
        stmt = self._get_item_list_stmt(
            model=model,
            joins=joins,
            loads=loads,
            filters=filters,
            search=search,
            search_by=search_by,
            order_by=order_by,
            limit=limit,
            offset=offset,
        )
        result = self.session.scalars(stmt)
        if unique_items:
            return result.unique().all()
        return result.all()

    @overload
    def db_create(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        data: "DataDict | None",
        use_flush: bool = False,
    ) -> "BaseSQLAlchemyModel": ...

    @overload
    def db_create(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        data: "Sequence[DataDict]",
        use_flush: bool = False,
    ) -> "Sequence[BaseSQLAlchemyModel]": ...

    def db_create(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        data: "DataDict | Sequence[DataDict] | None" = None,
        use_flush: bool = False,
    ) -> "BaseSQLAlchemyModel | Sequence[BaseSQLAlchemyModel]":
        """Insert data to given model by given data."""
        stmt = self._db_insert_stmt(model=model, data=data)
        if isinstance(data, dict) or data is None:
            result = self.session.scalar(stmt)
        else:
            result = self.session.scalars(stmt)
            result = result.unique().all()
        if use_flush:
            self.session.flush()
        else:
            self.session.commit()
        if not result:  # pragma: no coverage
            msg = f'No data was insert for model "{model}" and data {data}.'
            raise QueryError(msg)
        return result

    @overload
    def create_item(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        data: "DataDict | None",
        use_flush: bool = False,
    ) -> "BaseSQLAlchemyModel": ...

    @overload
    def create_item(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        data: "Sequence[DataDict | None]",
        use_flush: bool = False,
    ) -> "Sequence[BaseSQLAlchemyModel]": ...

    def create_item(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        data: "DataDict | Sequence[DataDict | None] | None" = None,
        use_flush: bool = False,
    ) -> "BaseSQLAlchemyModel | Sequence[BaseSQLAlchemyModel]":
        """Create model instance from given data."""
        items = self._prepare_create_items(model=model, data=data)
        self.session.add_all(items)
        if use_flush:
            self.session.flush()
        else:
            self.session.commit()

        msg = (
            f"Create row in database. Item: {items}. "
            f"{'Flush used.' if use_flush else 'Commit used.'}."
        )
        self.logger.debug(msg)
        if len(items) == 1:
            return items[0]
        return items

    def db_update(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        data: "DataDict",
        filters: "Filter | None" = None,
        use_flush: bool = False,
    ) -> "Sequence[BaseSQLAlchemyModel]":
        """Update model from given data."""
        stmt = self._db_update_stmt(
            model=model,
            data=data,
            filters=filters,
        )
        result = self.session.scalars(stmt)
        if use_flush:
            self.session.flush()
        else:
            self.session.commit()
        return result.unique().all()

    def change_item(
        self,
        *,
        data: "DataDict",
        item: "BaseSQLAlchemyModel",
        set_none: bool = False,
        allowed_none_fields: 'Literal["*"] | set[str]' = "*",
        use_flush: bool = False,
    ) -> "tuple[Updated, BaseSQLAlchemyModel]":
        """Update model instance from given data.

        Returns tuple with boolean (was instance updated or not) and updated instance.
        """
        is_updated = False
        if not set_none:
            data = {key: value for key, value in data.items() if value is not None}
        for field, value in data.items():
            if (
                set_none
                and value is None
                and (allowed_none_fields != "*" and field not in allowed_none_fields)
            ):
                continue
            if not is_updated and getattr(item, field, None) != value:
                is_updated = True
            setattr(item, field, value)
        if use_flush:
            self.session.flush()
        else:
            self.session.commit()
        msg = (
            f"Update database row success. Item: {repr(item)}. Params: {data}, "
            f"set_none: {set_none}, use_flush: {use_flush}."
        )
        self.logger.debug(msg)
        return is_updated, item

    def db_delete(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        filters: "Filter | None" = None,
        use_flush: bool = False,
    ) -> "Count":
        """Delete model in db by given filters."""
        stmt = self._db_delete_stmt(
            model=model,
            filters=filters,
        )
        result = self.session.execute(stmt)
        if use_flush:
            self.session.flush()
        else:
            self.session.commit()
        if isinstance(result, CursorResult):  # type: ignore  # pragma: no coverage
            return result.rowcount
        return 0  # pragma: no coverage

    def delete_item(  # pragma: no coverage
        self,
        *,
        item: "Base",
        use_flush: bool = False,
    ) -> "Deleted":
        """Delete model_class instance."""
        item_repr = repr(item)
        try:
            self.session.delete(item)
            if use_flush:
                self.session.flush()
            else:
                self.session.commit()
        except sqlalchemy_exc.SQLAlchemyError as exc:
            self.session.rollback()
            msg = f"Delete from database error: {exc}"  # noqa: S608
            self.logger.warning(msg)
            return False
        msg = f"Delete from database success. Item: {item_repr}"  # noqa: S608
        self.logger.debug(msg)
        return True

    def disable_items(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        ids_to_disable: set[Any],
        id_field: "StrField",
        disable_field: "StrField",
        field_type: type[datetime.datetime] | type[bool] = datetime.datetime,
        allow_filter_by_value: bool = True,
        extra_filters: "Filter | None" = None,
        use_flush: bool = False,
    ) -> "Count":
        """Disable model instances with given ids and extra_filters."""
        stmt = self._disable_items_stmt(
            model=model,
            ids_to_disable=ids_to_disable,
            id_field=get_sqlalchemy_attribute(model, id_field, only_columns=True),
            disable_field=get_sqlalchemy_attribute(model, disable_field, only_columns=True),
            field_type=field_type,
            allow_filter_by_value=allow_filter_by_value,
            extra_filters=extra_filters,
        )
        if isinstance(stmt, int):  # pragma: no coverage
            return stmt
        result = self.session.execute(stmt)
        if use_flush:
            self.session.flush()
        else:
            self.session.commit()
        if isinstance(result, CursorResult):  # type: ignore  # pragma: no coverage
            return result.rowcount
        return 0  # pragma: no coverage


class BaseAsyncQuery(BaseQuery):
    """Base query class with async interface."""

    def __init__(
        self,
        session: "AsyncSession",
        filter_converter_class: type[BaseFilterConverter],
        specific_column_mapping: dict[str, "InstrumentedAttribute[Any]"] | None = None,
        load_strategy: Callable[..., "_AbstractLoad"] = joinedload,
        logger: "Logger" = default_logger,
    ) -> None:
        self.session = session
        super().__init__(filter_converter_class, specific_column_mapping, load_strategy, logger)

    async def get_item(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        filters: "Filter | None" = None,
        joins: "Sequence[Join] | None" = None,
        loads: "Sequence[Load] | None" = None,
    ) -> "BaseSQLAlchemyModel | None":
        """Get one instance of model by given filters."""
        stmt = self._get_item_stmt(
            model=model,
            filters=filters,
            joins=joins,
            loads=loads,
        )
        result = await self.session.scalars(stmt)
        return result.first()

    async def get_items_count(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        joins: "Sequence[Join] | None" = None,
        filters: "Filter | None" = None,
    ) -> int:
        """Get count of instances of model by given filters."""
        stmt = self._get_items_count_stmt(
            model=model,
            joins=joins,
            filters=filters,
        )
        count = await self.session.scalar(stmt)
        # NOTE: code block for sure.
        if count is None:  # pragma: no cover
            count = 0
        return count

    async def get_item_list(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        joins: "Sequence[Join] | None" = None,
        loads: "Sequence[Load] | None" = None,
        filters: "Filter | None" = None,
        search: str | None = None,
        search_by: "Sequence[SearchParam] | None" = None,
        order_by: "Sequence[OrderByParam] | None" = None,
        limit: int | None = None,
        offset: int | None = None,
        unique_items: bool = False,
    ) -> "Sequence[BaseSQLAlchemyModel]":
        """Get list of instances of model."""
        stmt = self._get_item_list_stmt(
            model=model,
            joins=joins,
            loads=loads,
            filters=filters,
            search=search,
            search_by=search_by,
            order_by=order_by,
            limit=limit,
            offset=offset,
        )
        result = await self.session.scalars(stmt)
        if unique_items:
            return result.unique().all()
        return result.all()

    @overload
    async def db_create(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        data: "DataDict | None",
        use_flush: bool = False,
    ) -> "BaseSQLAlchemyModel": ...

    @overload
    async def db_create(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        data: "Sequence[DataDict]",
        use_flush: bool = False,
    ) -> "Sequence[BaseSQLAlchemyModel]": ...

    async def db_create(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        data: "DataDict | Sequence[DataDict] | None" = None,
        use_flush: bool = False,
    ) -> "BaseSQLAlchemyModel | Sequence[BaseSQLAlchemyModel]":
        """Insert data to given model by given data."""
        stmt = self._db_insert_stmt(model=model, data=data)
        if isinstance(data, dict) or data is None:
            result = await self.session.scalar(stmt)
        else:
            result = await self.session.scalars(stmt)
            result = result.unique().all()
        if use_flush:
            await self.session.flush()
        else:
            await self.session.commit()
        if not result:  # pragma: no coverage
            msg = f'No data was insert for model "{model}" and data {data}.'
            raise QueryError(msg)
        return result

    @overload
    async def create_item(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        data: "DataDict | None",
        use_flush: bool = False,
    ) -> "BaseSQLAlchemyModel": ...

    @overload
    async def create_item(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        data: "Sequence[DataDict | None]",
        use_flush: bool = False,
    ) -> "Sequence[BaseSQLAlchemyModel]": ...

    async def create_item(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        data: "DataDict | Sequence[DataDict | None] | None" = None,
        use_flush: bool = False,
    ) -> "BaseSQLAlchemyModel | Sequence[BaseSQLAlchemyModel]":
        """Create model instance from given data."""
        items = self._prepare_create_items(model=model, data=data)
        self.session.add_all(items)
        if use_flush:
            await self.session.flush()
        else:
            await self.session.commit()

        msg = (
            f"Create row in database. Items: {items}. "
            f"{'Flush used.' if use_flush else 'Commit used.'}."
        )
        self.logger.debug(msg)
        if len(items) == 1:
            return items[0]
        return items

    async def db_update(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        data: "DataDict",
        filters: "Filter | None" = None,
        use_flush: bool = False,
    ) -> "Sequence[BaseSQLAlchemyModel]":
        """Update model from given data."""
        stmt = self._db_update_stmt(
            model=model,
            data=data,
            filters=filters,
        )
        result = await self.session.scalars(stmt)
        if use_flush:
            await self.session.flush()
        else:
            await self.session.commit()
        return result.unique().all()

    async def change_item(
        self,
        *,
        data: "DataDict",
        item: "BaseSQLAlchemyModel",
        set_none: bool = False,
        allowed_none_fields: 'Literal["*"] | set[str]' = "*",
        use_flush: bool = False,
    ) -> "tuple[bool, BaseSQLAlchemyModel]":
        """Update model instance from given data.

        Returns tuple with boolean (was instance updated or not) and updated instance.
        """
        is_updated = False
        if not set_none:
            data = {key: value for key, value in data.items() if value is not None}
        for field, value in data.items():
            if (
                set_none
                and value is None
                and (allowed_none_fields != "*" and field not in allowed_none_fields)
            ):
                continue
            if not is_updated and getattr(item, field, None) != value:
                is_updated = True
            setattr(item, field, value)
        if use_flush:
            await self.session.flush()
        else:
            await self.session.commit()
        msg = (
            f"Update database row success. Item: {repr(item)}. Params: {data}, "
            f"set_none: {set_none}, use_flush: {use_flush}."
        )
        self.logger.debug(msg)
        return is_updated, item

    async def db_delete(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        filters: "Filter | None" = None,
        use_flush: bool = False,
    ) -> "Count":
        """Delete model in db by given filters."""
        stmt = self._db_delete_stmt(
            model=model,
            filters=filters,
        )
        result = await self.session.execute(stmt)
        if use_flush:
            await self.session.flush()
        else:
            await self.session.commit()
        if isinstance(result, CursorResult):  # type: ignore  # pragma: no coverage
            return result.rowcount
        return 0  # pragma: no coverage

    async def delete_item(  # pragma: no coverage
        self,
        *,
        item: "Base",
        use_flush: bool = False,
    ) -> "Deleted":
        """Delete model_class instance."""
        item_repr = repr(item)
        try:
            await self.session.delete(item)
            if use_flush:
                await self.session.flush()
            else:
                await self.session.commit()
        except sqlalchemy_exc.SQLAlchemyError as exc:
            await self.session.rollback()
            msg = f"Delete from database error: {exc}"  # noqa: S608
            self.logger.warning(msg)
            return False
        msg = f"Delete from database success. Item: {item_repr}"  # noqa: S608
        self.logger.debug(msg)
        return True

    async def disable_items(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        ids_to_disable: set[Any],
        id_field: "StrField",
        disable_field: "StrField",
        field_type: type[datetime.datetime] | type[bool] = datetime.datetime,
        allow_filter_by_value: bool = True,
        extra_filters: "Filter | None" = None,
        use_flush: bool = False,
    ) -> "Count":
        """Disable model instances with given ids and extra_filters."""
        stmt = self._disable_items_stmt(
            model=model,
            ids_to_disable=ids_to_disable,
            id_field=get_sqlalchemy_attribute(model, id_field, only_columns=True),
            disable_field=get_sqlalchemy_attribute(model, disable_field, only_columns=True),
            field_type=field_type,
            allow_filter_by_value=allow_filter_by_value,
            extra_filters=extra_filters,
        )
        if isinstance(stmt, int):  # pragma: no coverage
            return stmt
        result = await self.session.execute(stmt)
        if use_flush:
            await self.session.flush()
        else:
            await self.session.commit()
        if isinstance(result, CursorResult):  # type: ignore  # pragma: no coverage
            return result.rowcount
        return 0  # pragma: no coverage
