import datetime
from typing import Any, Sequence

import pytest
import zoneinfo
from freezegun import freeze_time
from sqlalchemy import delete, insert, inspect, select, update
from sqlalchemy.orm import joinedload, selectinload, subqueryload

from sqlrepo import utils
from tests.utils import Base, MyModel, OtherModel, generate_datetime_list


@pytest.mark.parametrize(
    'dt',
    generate_datetime_list(n=10, tz=zoneinfo.ZoneInfo('UTC')),
)
def test_get_utc_now(dt: datetime.datetime) -> None:  # noqa
    with freeze_time(dt):
        assert utils.get_utc_now() == dt


@pytest.mark.parametrize(
    ('field', 'expected_result'),
    [
        ('id', MyModel.id),
        ('name', MyModel.name),
        ('full_name', MyModel.full_name),
        ('get_full_name', MyModel.get_full_name()),
    ],
)
def test_get_sqlalchemy_field(field: str, expected_result: Any) -> None:  # noqa
    assert str(utils.get_sqlalchemy_field(MyModel, field)) == str(expected_result)


@pytest.mark.parametrize(
    ('stmt', 'expected_result'),
    [
        (select(MyModel), [MyModel]),
        (select(MyModel, OtherModel), [MyModel, OtherModel]),
        (select(), []),
        (insert(MyModel), [MyModel]),
        (update(MyModel), [MyModel]),
        (delete(MyModel), [MyModel]),
    ],
)
def test_get_model_classes_from_statement(  # noqa
    stmt: utils.Statement,
    expected_result: Sequence[type[Base]],
) -> None:
    assert utils.get_model_classes_from_statement(stmt) == expected_result


def test_get_registry_class() -> None:  # noqa
    assert utils.get_registry_class(MyModel) == MyModel.registry._class_registry  # type: ignore


@pytest.mark.parametrize(
    ('name', 'expected_result'),
    [
        ('MyModel', MyModel),
        ('OtherModel', OtherModel),
        ('NoModel', None),
    ],
)
def test_get_model_class_by_name(name: str, expected_result: type[Base] | None) -> None:  # noqa
    register = utils.get_registry_class(MyModel)
    assert utils.get_model_class_by_name(register, name) == expected_result


def test_get_valid_model_class_names() -> None:  # noqa
    register = utils.get_registry_class(MyModel)
    assert utils.get_valid_model_class_names(register) == set(['MyModel', 'OtherModel'])


def test_get_valid_field_names() -> None:  # noqa
    assert utils.get_valid_field_names(MyModel) == {
        'id',
        'name',
        'other_name',
        'dt',
        'bl',
        'full_name',
        'get_full_name',
    }


@pytest.mark.parametrize(
    ('field', 'expected_result'),
    [
        ('id', False),
        ('name', False),
        ('other_name', False),
        ('full_name', True),
        ('get_full_name', False),
    ],
)
def test_is_hybrid_property(field: str, expected_result: bool) -> None:  # noqa
    insp = inspect(MyModel).all_orm_descriptors
    assert utils.is_hybrid_property(insp[field]) == expected_result


@pytest.mark.parametrize(
    ('field', 'expected_result'),
    [
        ('id', False),
        ('name', False),
        ('other_name', False),
        ('full_name', False),
        ('get_full_name', True),
    ],
)
def test_is_hybrid_method(field: str, expected_result: bool) -> None:  # noqa
    insp = inspect(MyModel).all_orm_descriptors
    assert utils.is_hybrid_method(insp[field]) == expected_result


@pytest.mark.parametrize(
    ('stmt', 'relationship_names', 'load_strategy', 'expected_result'),
    [
        (
            select(MyModel),
            ('other_models',),
            joinedload,
            select(MyModel).options(joinedload(MyModel.other_models)),
        ),
        (
            select(MyModel),
            ('other_models', 'wrong_relation_name'),
            joinedload,
            select(MyModel).options(joinedload(MyModel.other_models)),
        ),
        (
            select(MyModel),
            ('other_models',),
            selectinload,
            select(MyModel).options(selectinload(MyModel.other_models)),
        ),
        (
            select(MyModel),
            ('other_models',),
            subqueryload,
            select(MyModel).options(subqueryload(MyModel.other_models)),
        ),
        (
            select(MyModel),
            'wrong_relation_name',
            joinedload,
            select(MyModel),
        ),
    ],
)
def test_apply_loads(  # noqa
    stmt: Any,  # noqa
    relationship_names: tuple[str, ...],
    load_strategy: Any,  # noqa
    expected_result: Any,  # noqa
) -> None:  # noqa
    assert str(
        utils.apply_loads(
            stmt,
            *relationship_names,
            load_strategy=load_strategy,
        ),
    ) == str(  # type: ignore
        expected_result,
    )


@pytest.mark.parametrize(
    ('stmt', 'relationship_names', 'left_outer_join', 'full_join', 'expected_result'),
    [
        (
            select(MyModel),
            ('other_models',),
            False,
            False,
            select(MyModel).join(MyModel.other_models),
        ),
        (
            select(MyModel),
            ('other_models',),
            True,
            False,
            select(MyModel).join(MyModel.other_models, isouter=True),
        ),
        (
            select(MyModel),
            ('other_models',),
            False,
            True,
            select(MyModel).join(MyModel.other_models, full=True),
        ),
        (
            select(MyModel),
            ('other_models', 'wrong_relation_name'),
            False,
            False,
            select(MyModel).join(MyModel.other_models),
        ),
        (
            select(MyModel),
            ('wrong_relation_name',),
            False,
            False,
            select(MyModel),
        ),
    ],
)
def test_apply_joins(  # noqa
    stmt: Any,  # noqa
    relationship_names: tuple[str, ...],
    left_outer_join: bool,  # noqa
    full_join: bool,  # noqa
    expected_result: Any,  # noqa
) -> None:  # noqa
    assert str(
        utils.apply_joins(
            stmt,
            *relationship_names,
            left_outer_join=left_outer_join,
            full_join=full_join,
        ),
    ) == str(  # type: ignore
        expected_result,
    )
