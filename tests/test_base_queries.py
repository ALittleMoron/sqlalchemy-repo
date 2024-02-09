import datetime
from typing import Any

import pytest
from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.orm import joinedload, selectinload

from sqlrepo.filters.converters import SimpleFilterConverter
from sqlrepo.queries import BaseQuery
from tests.utils import MyModel, OtherModel


@pytest.mark.parametrize(
    ('specific_column_mapping', 'elements', 'expected_result'),
    [
        (
            None,
            ['other_model_id', MyModel.name],
            ['other_model_id', MyModel.name],
        ),
        (
            {'other_model_id': OtherModel.id, 'some_other_model_field': OtherModel.name},
            ['other_model_id', MyModel.name],
            [OtherModel.id, MyModel.name],
        ),
        (
            {'other_model_id': OtherModel.id, 'some_other_model_field': OtherModel.name},
            ['not_presented_field', 'other_model_id'],
            ['not_presented_field', OtherModel.id],
        ),
    ],
)
def test_resolve_specific_columns(  # noqa
    specific_column_mapping: dict[str, ColumnElement[Any]],
    elements: list[str | ColumnElement[Any]],
    expected_result: list[str | ColumnElement[Any]],  # noqa
) -> None:
    query = BaseQuery(SimpleFilterConverter, specific_column_mapping)
    converted_columns = query._resolve_specific_columns(elements=elements)  # type: ignore
    assert converted_columns == expected_result


@pytest.mark.parametrize(
    ('stmt', 'joins', 'expected_result'),
    [
        (
            select(MyModel),
            [OtherModel],
            select(MyModel).join(OtherModel),
        ),
        (
            select(MyModel),
            ['other_models'],
            select(MyModel).join(OtherModel),
        ),
        (
            select(MyModel),
            ['incorrect_value'],
            select(MyModel),
        ),
        (
            select(MyModel),
            [(OtherModel, MyModel.id == OtherModel.my_model_id)],
            select(MyModel).join(OtherModel),
        ),
        (
            select(MyModel),
            [(OtherModel, MyModel.id == OtherModel.my_model_id, {'isouter': True})],
            select(MyModel).join(OtherModel, isouter=True),
        ),
        (
            select(MyModel),
            [(OtherModel, MyModel.id == OtherModel.my_model_id, {'full': True})],
            select(MyModel).join(OtherModel, full=True),
        ),
    ],
)
def test_resolve_and_apply_joins(  # noqa
    stmt: Any,  # noqa
    joins: Any,  # noqa
    expected_result: Any,  # noqa
) -> None:
    query = BaseQuery(SimpleFilterConverter)
    new_stmt = query._resolve_and_apply_joins(stmt=stmt, joins=joins)  # type: ignore
    assert str(new_stmt) == str(expected_result)


@pytest.mark.parametrize(
    ('stmt', 'strategy', 'loads', 'expected_result'),
    [
        (
            select(MyModel),
            joinedload,
            ['other_models'],
            select(MyModel).options(joinedload(MyModel.other_models)),
        ),
        (
            select(MyModel),
            joinedload,
            ['incorrect_value'],
            select(MyModel),
        ),
        (
            select(MyModel),
            selectinload,
            ['other_models'],
            select(MyModel).options(selectinload(MyModel.other_models)),
        ),
    ],
)
def test_resolve_and_apply_loads(  # noqa
    stmt: Any,  # noqa
    strategy: Any,  # noqa
    loads: Any,  # noqa
    expected_result: Any,  # noqa
) -> None:
    query = BaseQuery(SimpleFilterConverter, load_strategy=strategy)
    new_stmt = query._resolve_and_apply_loads(stmt=stmt, loads=loads)  # type: ignore
    assert str(new_stmt) == str(expected_result)


@pytest.mark.parametrize(
    (
        'id_field',
        'ids_to_disable',
        'disable_field',
        'field_type',
        'allow_filter_by_value',
        'extra_filters',
        'expected_result',
    ),
    [
        (
            MyModel.id,
            {1, 2, 3, 4, 5},
            MyModel.dt,
            datetime.datetime,
            False,
            None,
            [MyModel.id.in_({1, 2, 3, 4, 5})],
        ),
        (
            MyModel.id,
            {1, 2, 3, 4, 5},
            MyModel.dt,
            datetime.datetime,
            False,
            {'name': 'aboba'},
            [MyModel.id.in_({1, 2, 3, 4, 5}), MyModel.name == 'aboba'],
        ),
        (
            MyModel.id,
            {1, 2, 3, 4, 5},
            MyModel.dt,
            datetime.datetime,
            True,
            None,
            [MyModel.id.in_({1, 2, 3, 4, 5}), MyModel.dt.is_(None)],
        ),
        (
            MyModel.id,
            {1, 2, 3, 4, 5},
            MyModel.bl,
            bool,
            True,
            None,
            [MyModel.id.in_({1, 2, 3, 4, 5}), MyModel.bl.is_not(True)],
        ),
    ],
)
def test_make_disable_filters(  # noqa
    id_field: Any,  # noqa
    ids_to_disable: set[Any],
    disable_field: Any,  # noqa
    field_type: type[datetime.datetime] | type[bool],
    allow_filter_by_value: bool,  # noqa
    extra_filters: Any,  # noqa
    expected_result: Any,  # noqa
) -> None:
    query = BaseQuery(SimpleFilterConverter)
    disable_filters = query._make_disable_filters(  # type: ignore
        model=MyModel,
        id_field=id_field,
        ids_to_disable=ids_to_disable,
        disable_field=disable_field,
        field_type=field_type,
        allow_filter_by_value=allow_filter_by_value,
        extra_filters=extra_filters,
    )
    assert list(map(str, disable_filters)) == list(map(str, expected_result))


@pytest.mark.parametrize(
    ('search', 'search_by_args', 'use_and_clause', 'expected_result'),
    [
        (
            'value',
            (MyModel.name, MyModel.other_name),
            False,
            or_(MyModel.name.ilike(r'%value%'), MyModel.other_name.ilike(r'%value%')),
        ),
        (
            'value',
            (MyModel.name, MyModel.other_name),
            True,
            and_(MyModel.name.ilike(r'%value%'), MyModel.other_name.ilike(r'%value%')),
        ),
        (
            'value',
            ('name', 'other_name'),
            False,
            or_(MyModel.name.ilike(r'%value%'), MyModel.other_name.ilike(r'%value%')),
        ),
    ],
)
def test_make_search_filter(  # noqa
    search: str,
    search_by_args: tuple[Any, ...],
    use_and_clause: bool,  # noqa
    expected_result: Any,  # noqa
) -> None:
    query = BaseQuery(SimpleFilterConverter)
    search_filter = query._make_search_filter(  # type: ignore
        search,
        MyModel,
        *search_by_args,
        use_and_clause=use_and_clause,
    )
    assert str(search_filter) == str(expected_result)


@pytest.mark.parametrize(
    ('filters', 'joins', 'loads', 'expected_result'),
    [
        (
            None,
            None,
            None,
            select(MyModel),
        ),
        (
            {'name': 'aboba'},
            None,
            None,
            select(MyModel).where(MyModel.name == 'aboba'),
        ),
        (
            None,
            ['other_models'],
            None,
            select(MyModel).join(OtherModel),
        ),
        (
            None,
            None,
            ['other_models'],
            select(MyModel).options(joinedload(MyModel.other_models)),
        ),
    ],
)
def test_get_item_stmt(  # noqa
    filters: Any,  # noqa
    joins: Any,  # noqa
    loads: Any,  # noqa
    expected_result: Any,  # noqa
) -> None:
    query = BaseQuery(SimpleFilterConverter)
    get_item_stmt = query._get_item_stmt(  # type: ignore
        model=MyModel,
        filters=filters,
        joins=joins,
        loads=loads,
    )
    assert str(get_item_stmt) == str(expected_result)


@pytest.mark.parametrize(
    ('filters', 'joins', 'expected_result'),
    [
        (
            None,
            None,
            select(func.count()).select_from(MyModel),
        ),
        (
            {'name': 'aboba'},
            None,
            select(func.count()).select_from(MyModel).where(MyModel.name == 'aboba'),
        ),
        # TODO: поправить баг с join'ом с select(func...)
        (
            None,
            ['other_models'],
            select(func.count()).select_from(MyModel).join(OtherModel),
        ),
        (
            [OtherModel.name == 'aboba'],
            ['other_models'],
            select(func.count())
            .select_from(MyModel)
            .join(OtherModel)
            .where(OtherModel.name == 'aboba'),
        ),
    ],
)
def test_get_items_count_stmt(
    filters: Any,  # noqa
    joins: Any,  # noqa
    expected_result: Any,  # noqa
) -> None:
    query = BaseQuery(SimpleFilterConverter)
    get_items_count_stmt = query._get_items_count_stmt(  # type: ignore
        model=MyModel,
        joins=joins,
        filters=filters,
    )
    assert str(get_items_count_stmt) == str(expected_result)
