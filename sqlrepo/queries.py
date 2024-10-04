"""Queries classes with executable statements and methods with them."""

import datetime
import re
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, Literal, NotRequired, TypedDict, TypeVar, overload

from dev_utils.common import get_utc_now
from sqlalchemy import CursorResult, and_, delete, desc, exists, func, insert, or_, select, update
from sqlalchemy import exc as sqlalchemy_exc
from sqlalchemy_dev_utils import apply_joins, get_sqlalchemy_attribute, is_queryable_attribute
from sqlalchemy_filter_converter import BaseFilterConverter

from sqlrepo.exc import QueryError
from sqlrepo.logger import default_logger


class JoinKwargs(TypedDict):
    """Kwargs for join statement."""

    isouter: NotRequired[bool]
    full: NotRequired[bool]


if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import DeclarativeBase as Base
    from sqlalchemy.orm import QueryableAttribute
    from sqlalchemy.orm.attributes import InstrumentedAttribute
    from sqlalchemy.orm.session import Session
    from sqlalchemy.orm.strategy_options import _AbstractLoad  # type: ignore[reportPrivateUsage]
    from sqlalchemy.sql._typing import (
        _ColumnExpressionOrStrLabelArgument,  # type: ignore[reportPrivateUsage]
    )
    from sqlalchemy.sql.dml import Delete, ReturningInsert, ReturningUpdate, Update
    from sqlalchemy.sql.elements import ColumnElement
    from sqlalchemy.sql.selectable import Select

    # noinspection PyUnresolvedReferences
    from sqlrepo.types import FilterType, LoggerProtocol

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
    Load = _AbstractLoad
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
        logger: "LoggerProtocol" = default_logger,
    ) -> None:
        self.specific_column_mapping = specific_column_mapping
        self.filter_converter_class = filter_converter_class
        self.logger = logger

    def _resolve_specific_columns(
        self,
        *,
        model: "Model",
        elements: "Iterable[Any]",
    ) -> "Iterable[ColumnElement[Any] | QueryableAttribute[Any]]":
        """Get all SQLAlchemy columns from strings (uses specific columns)."""
        new_elements: "list[ColumnElement[Any] | QueryableAttribute[Any]]" = []
        for idx, ele in enumerate(elements):
            if is_queryable_attribute(ele):
                new_elements.append(ele)
            elif (
                isinstance(ele, str)
                and self.specific_column_mapping is not None
                and ele in self.specific_column_mapping
            ):
                new_elements.append(self.specific_column_mapping[ele])
            elif isinstance(ele, str):
                func = None
                if ele.startswith("-"):
                    func = desc
                    ele = ele[1:]  # noqa: PLW2901
                attr = get_sqlalchemy_attribute(model, ele)
                if func is not None:
                    attr = func(attr)
                new_elements.append(attr)
            else:
                msg = f"Type of {idx} element of given elements is incorrect. Type: {type(ele)}"
                raise ValueError(msg)
        return new_elements

    def _resolve_and_apply_joins(
        self,
        *,
        stmt: "Select[tuple[T]]",
        joins: "Sequence[Join]",
    ) -> "Select[tuple[T]]":
        """Resolve joins from strings."""
        # FIX: may cause situation, when user passed Join as tuple may cause error.
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

    def _make_disable_filters(
        self,
        *,
        model: "type[BaseSQLAlchemyModel]",
        id_field: "QueryableAttribute[Any]",
        ids_to_disable: set[Any],
        disable_field: "QueryableAttribute[Any]",
        field_type: type[datetime.datetime] | type[bool] = datetime.datetime,
        allow_filter_by_value: bool = True,
        extra_filters: "FilterType | None" = None,
    ) -> list["ColumnElement[bool]"]:
        """Generate disable filters from given data."""
        filters: list["ColumnElement[bool]"] = [id_field.in_(ids_to_disable)]
        if allow_filter_by_value and field_type is bool:
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
        search_by_args_resolved = self._resolve_specific_columns(
            model=model,
            elements=search_by_args,
        )
        for search_by in search_by_args_resolved:
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
        filters: "FilterType | None" = None,
        joins: "Sequence[Join] | None" = None,
        loads: "Sequence[Load] | None" = None,
    ) -> "Select[tuple[BaseSQLAlchemyModel]]":
        """Generate SQLAlchemy stmt to get one item from filters, joins and loads."""
        stmt = select(model)
        if joins is not None:
            stmt = self._resolve_and_apply_joins(stmt=stmt, joins=joins)
        if loads is not None:
            stmt = stmt.options(*loads)
        if filters is not None:
            sqlalchemy_filters = self.filter_converter_class.convert(model, filters)
            stmt = stmt.where(*sqlalchemy_filters)
        return stmt

    def _get_items_count_stmt(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        joins: "Sequence[Join] | None" = None,
        filters: "FilterType | None" = None,
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
        filters: "FilterType | None" = None,
        search: str | None = None,
        search_by: "SearchParam | Iterable[SearchParam] | None" = None,
        order_by: "OrderByParam | Iterable[OrderByParam] | None" = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> "Select[tuple[BaseSQLAlchemyModel]]":
        """Generate SQLAlchemy stmt to get list of items from given data."""
        stmt = self._get_item_stmt(model=model, filters=filters, joins=joins, loads=loads)
        if search is not None and search_by is not None:
            search = re.escape(search)
            search = search.translate(str.maketrans({"%": r"\%", "_": r"\_", "/": r"\/"}))
            if isinstance(search_by, str) or not isinstance(search_by, Iterable):
                search_by = (search_by,)
            stmt = stmt.where(self._make_search_filter(search, model, *search_by))
        if order_by is not None:
            if isinstance(order_by, str) or not isinstance(order_by, Iterable):
                order_by = (order_by,)
            order_by_resolved = self._resolve_specific_columns(model=model, elements=order_by)
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
        return stmt.returning(model)

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
        return [model() if data_ele is None else model(**data_ele) for data_ele in data]

    def _db_update_stmt(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        data: "DataDict",
        filters: "FilterType | None" = None,
    ) -> "ReturningUpdate[tuple[BaseSQLAlchemyModel]]":
        """Generate SQLAlchemy stmt to update items with given data."""
        stmt = update(model)
        if filters is not None:
            sqlalchemy_filters = self.filter_converter_class.convert(model, filters)
            stmt = stmt.where(*sqlalchemy_filters)
        return stmt.values(**data).returning(model)

    def _db_delete_stmt(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        filters: "FilterType | None" = None,
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
        extra_filters: "FilterType | None" = None,
    ) -> "Update":
        """Generate SQLAlchemy stmt to disable items with given data."""
        if not issubclass(field_type, datetime.datetime | bool):
            msg = f'Parameter "field_type" should be datetime or bool type. {field_type} was passed'
            self.logger.exception(msg)
            raise QueryError(msg)
        field_value = True if field_type is bool else get_utc_now()
        if len(ids_to_disable) == 0:
            msg = 'Parameter "ids_to_disable" should contains at least one element.'
            self.logger.exception(msg)
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
        return update(model).where(*filters).values({disable_field: field_value})

    def _exists_items_stmt(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        filters: "FilterType | None" = None,
    ) -> "Select[tuple[bool]]":
        """Generate SQLAlchemy stmt to check items for exist in database."""
        exist_stmt = exists().select_from(model)
        if filters is not None:
            sqlalchemy_filters = self.filter_converter_class.convert(model, filters)
            exist_stmt = exist_stmt.where(*sqlalchemy_filters)
        return select(exist_stmt)


class BaseSyncQuery(BaseQuery):
    """Base query class with sync interface."""

    def __init__(
        self,
        session: "Session",
        filter_converter_class: type[BaseFilterConverter],
        specific_column_mapping: dict[str, "InstrumentedAttribute[Any]"] | None = None,
        logger: "LoggerProtocol" = default_logger,
    ) -> None:
        self.session = session
        super().__init__(
            filter_converter_class=filter_converter_class,
            specific_column_mapping=specific_column_mapping,
            logger=logger,
        )

    def get_item(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        filters: "FilterType | None" = None,
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
        filters: "FilterType | None" = None,
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
        filters: "FilterType | None" = None,
        search: str | None = None,
        search_by: "SearchParam | Iterable[SearchParam] | None" = None,
        order_by: "OrderByParam | Iterable[OrderByParam] | None" = None,
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
        self.logger.info(msg)
        if len(items) == 1:
            return items[0]
        return items

    def db_update(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        data: "DataDict",
        filters: "FilterType | None" = None,
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
            f"Update database row success. Item: {item!r}. Params: {data}, "
            f"set_none: {set_none}, use_flush: {use_flush}."
        )
        self.logger.info(msg)
        return is_updated, item

    def db_delete(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        filters: "FilterType | None" = None,
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
        if isinstance(  # pragma: no coverage  # type: ignore[reportUnnecessaryIsInstance]
            result,
            CursorResult,
        ):
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
            msg = f"Error delete db_item: {exc}"
            self.logger.exception(msg)
            return False
        msg = f"Success delete db_item. Item: {item_repr}"
        self.logger.info(msg)
        return True

    def disable_items(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        ids_to_disable: set[Any],
        id_field: "InstrumentedAttribute[Any] | StrField",
        disable_field: "InstrumentedAttribute[Any] | StrField",
        field_type: type[datetime.datetime] | type[bool] = datetime.datetime,
        allow_filter_by_value: bool = True,
        extra_filters: "FilterType | None" = None,
        use_flush: bool = False,
    ) -> "Count":
        """Disable model instances with given ids and extra_filters."""
        stmt = self._disable_items_stmt(
            model=model,
            ids_to_disable=ids_to_disable,
            id_field=(
                get_sqlalchemy_attribute(model, id_field, only_columns=True)
                if isinstance(id_field, str)
                else id_field
            ),
            disable_field=(
                get_sqlalchemy_attribute(model, disable_field, only_columns=True)
                if isinstance(disable_field, str)
                else disable_field
            ),
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
        if isinstance(  # pragma: no coverage  # type: ignore[reportUnnecessaryIsInstance]
            result,
            CursorResult,
        ):
            return result.rowcount
        return 0  # pragma: no coverage

    def items_exists(
        self,
        model: type["BaseSQLAlchemyModel"],
        filters: "FilterType | None" = None,
    ) -> bool:
        """Check rows in table for existing."""
        stmt = self._exists_items_stmt(model=model, filters=filters)
        result = self.session.scalar(stmt)
        return result if result is not None else False


class BaseAsyncQuery(BaseQuery):
    """Base query class with async interface."""

    def __init__(
        self,
        session: "AsyncSession",
        filter_converter_class: type[BaseFilterConverter],
        specific_column_mapping: dict[str, "InstrumentedAttribute[Any]"] | None = None,
        logger: "LoggerProtocol" = default_logger,
    ) -> None:
        self.session = session
        super().__init__(
            filter_converter_class=filter_converter_class,
            specific_column_mapping=specific_column_mapping,
            logger=logger,
        )

    async def get_item(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        filters: "FilterType | None" = None,
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
        filters: "FilterType | None" = None,
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
        filters: "FilterType | None" = None,
        search: str | None = None,
        search_by: "SearchParam | Iterable[SearchParam] | None" = None,
        order_by: "OrderByParam | Iterable[OrderByParam] | None" = None,
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
        self.logger.info(msg)
        if len(items) == 1:
            return items[0]
        return items

    async def db_update(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        data: "DataDict",
        filters: "FilterType | None" = None,
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
            f"Update database row success. Item: {item!r}. Params: {data}, "
            f"set_none: {set_none}, use_flush: {use_flush}."
        )
        self.logger.info(msg)
        return is_updated, item

    async def db_delete(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        filters: "FilterType | None" = None,
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
        if isinstance(  # pragma: no coverage  # type: ignore[reportUnnecessaryIsInstance]
            result,
            CursorResult,
        ):
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
            msg = f"Error delete db_item: {exc}"
            self.logger.exception(msg)
            return False
        msg = f"Success delete db_item. Item: {item_repr}"
        self.logger.info(msg)
        return True

    async def disable_items(
        self,
        *,
        model: type["BaseSQLAlchemyModel"],
        ids_to_disable: set[Any],
        id_field: "InstrumentedAttribute[Any] | StrField",
        disable_field: "InstrumentedAttribute[Any] | StrField",
        field_type: type[datetime.datetime] | type[bool] = datetime.datetime,
        allow_filter_by_value: bool = True,
        extra_filters: "FilterType | None" = None,
        use_flush: bool = False,
    ) -> "Count":
        """Disable model instances with given ids and extra_filters."""
        stmt = self._disable_items_stmt(
            model=model,
            ids_to_disable=ids_to_disable,
            id_field=(
                get_sqlalchemy_attribute(model, id_field, only_columns=True)
                if isinstance(id_field, str)
                else id_field
            ),
            disable_field=(
                get_sqlalchemy_attribute(model, disable_field, only_columns=True)
                if isinstance(disable_field, str)
                else disable_field
            ),
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
        if isinstance(  # pragma: no coverage  # type: ignore[reportUnnecessaryIsInstance]
            result,
            CursorResult,
        ):
            return result.rowcount
        return 0  # pragma: no coverage

    async def items_exists(
        self,
        model: type["BaseSQLAlchemyModel"],
        filters: "FilterType | None" = None,
    ) -> bool:
        """Check rows in table for existing."""
        stmt = self._exists_items_stmt(model=model, filters=filters)
        result = await self.session.scalar(stmt)
        return result if result is not None else False
