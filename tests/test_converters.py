import datetime
import zoneinfo
from typing import Any

import pytest
from sqlalchemy import Date, Time, cast, extract, func

from sqlrepo.exceptions import FilterError
from sqlrepo.filters.converters import (
    AdvancedOperatorFilterConverter,
    BaseFilterConverter,
    DjangoLikeFilterConverter,
    SimpleFilterConverter,
)
from tests.utils import MyModel

now = datetime.datetime.now(tz=zoneinfo.ZoneInfo('UTC'))
_date = now.date()
_time = now.time()


@pytest.mark.parametrize(
    ('converter_class', 'filters', 'expected_result'),
    [
        (
            SimpleFilterConverter,
            None,
            [],
        ),
        (
            SimpleFilterConverter,
            [MyModel.id == 25],
            [str(MyModel.id == 25)],
        ),
        (
            SimpleFilterConverter,
            {'id': 25, 'name': 'name'},
            [str(MyModel.id == 25), str(MyModel.name == 'name')],
        ),
        (
            SimpleFilterConverter,
            [{'id': 25}, {'name': 'name'}],
            [str(MyModel.id == 25), str(MyModel.name == 'name')],
        ),
        (
            SimpleFilterConverter,
            {'full_name': 'abc'},
            [str(MyModel.full_name == 'abc')],
        ),
        (
            AdvancedOperatorFilterConverter,
            [{'field': 'id', 'value': 25}, {'field': 'name', 'value': 'abc'}],
            [str(MyModel.id == 25), str(MyModel.name == 'abc')],
        ),
        (
            AdvancedOperatorFilterConverter,
            [
                {'field': 'id', 'value': 25, 'operator': '=='},
                {'field': 'id', 'value': 25, 'operator': '>'},
                {'field': 'id', 'value': 25, 'operator': '>='},
                {'field': 'id', 'value': 25, 'operator': '<'},
                {'field': 'id', 'value': 25, 'operator': '<='},
                {'field': 'id', 'value': (25, 28), 'operator': 'between'},
                {'field': 'id', 'value': [1, 2, 3], 'operator': 'contains'},
            ],
            [
                str(MyModel.id == 25),
                str(MyModel.id > 25),
                str(MyModel.id >= 25),
                str(MyModel.id < 25),
                str(MyModel.id <= 25),
                str(MyModel.id.between(25, 28)),
                str(MyModel.id.in_([1, 2, 3])),
            ],
        ),
        (
            DjangoLikeFilterConverter,
            {
                'id': 25,
                'id__exact': 25,
                'name__exact': None,
                'name__iexact': 'abc',
                'name__contains': 'abc',
                'name__icontains': 'abc',
                'name__in': ['abc', 'bca', 'dce'],
                'name__startswith': 'abc',
                'name__istartswith': 'abc',
                'name__endswith': 'abc',
                'name__iendswith': 'abc',
                'id__range': [1, 2],
                'dt__date': _date,
                'dt__year': 2024,
                'dt__iso_year': 2025,
                'dt__month': 1,
                'dt__day': 2,
                'dt__week': 3,
                'dt__week_day': 4,
                'dt__iso_week_day': 5,
                'dt__quarter': 1,
                'dt__time': _time,
                'dt__hour': 2,
                'dt__minute': 3,
                'dt__second': 4,
                'id__isnull': True,
                'name__isnull': False,
                'name__regex': '^(b|c)',
                'other_name__iregex': '^(b|c)',
            },
            [
                str(MyModel.id == 25),
                str(MyModel.id == 25),
                str(MyModel.name.is_(None)),
                str(MyModel.name.ilike('abc')),
                str(MyModel.name.like(r'%abc%')),
                str(MyModel.name.ilike(r'%abc%')),
                str(MyModel.name.in_(['abc', 'bca', 'dce'])),
                str(MyModel.name.like(r'abc%')),
                str(MyModel.name.ilike(r'abc%')),
                str(MyModel.name.like(r'%abc')),
                str(MyModel.name.ilike(r'%abc')),
                str(MyModel.id.between(1, 2)),
                str(cast(MyModel.dt, Date) == _date),
                str(extract('year', MyModel.dt) == 2024),
                str(extract('isoyear', MyModel.dt) == 2025),
                str(extract('month', MyModel.dt) == 1),
                str(extract('day', MyModel.dt) == 2),
                str(extract('week', MyModel.dt) == 3),
                str(extract('dow', MyModel.dt) == 4),
                str(extract('isodow', MyModel.dt) == 5),
                str(extract('quarter', MyModel.dt) == 1),
                str(cast(MyModel.dt, Time) == _time),
                str(extract('hour', MyModel.dt) == 1),
                str(extract('minute', MyModel.dt) == 1),
                str(extract('second', MyModel.dt) == 1),
                str(MyModel.id.is_(None)),
                str(MyModel.name.is_not(None)),
                str(MyModel.name.regexp_match('^(b|c)')),
                str(func.lower(MyModel.other_name).regexp_match('^(b|c)')),
            ],
        ),
    ],
)
def test_converter(  # noqa
    converter_class: type[BaseFilterConverter],
    filters: Any,  # noqa
    expected_result: list[Any],
):
    converted_filters = converter_class.convert(MyModel, filters)
    if filters is not None:
        assert len(converted_filters) == len(filters)
    else:
        assert len(converted_filters) == 0
    for index, _filter in enumerate(converted_filters):
        assert str(_filter) == str(expected_result[index])


@pytest.mark.parametrize(
    ('converter_class', 'filters'),
    [
        (
            SimpleFilterConverter,
            {'wrong_field_name': 25},
        ),
        (
            AdvancedOperatorFilterConverter,
            {'field': 'wrong_field_name', 'value': 'abc'},
        ),
        (
            AdvancedOperatorFilterConverter,
            {'no_field_key': 'wrong_field_name'},
        ),
        (
            DjangoLikeFilterConverter,
            {'id__wrong_lookup': 25},
        ),
        (
            DjangoLikeFilterConverter,
            {'dt__hour__gt__abc': 2},  # NOTE: пока нет обработки вложенных фильтров.
        ),
        (
            DjangoLikeFilterConverter,
            {'wrong_field_name__gt': 2},
        ),
    ],
)
def test_filter_not_valid(
    converter_class: type[BaseFilterConverter],
    filters: Any,  # noqa
) -> None:
    with pytest.raises(FilterError):
        converter_class.convert(MyModel, filters)


def test_advanced_filter_never_situation() -> None:
    with pytest.raises(FilterError, match=''):
        AdvancedOperatorFilterConverter._convert_filter(MyModel, {'abc': 'abc'})  # type: ignore


def test_django_filter_never_situation() -> None:
    with pytest.raises(FilterError, match=''):
        DjangoLikeFilterConverter._convert_filter(  # type: ignore
            MyModel,
            {'id__hour__gt__abc': 'abc'},
        )
