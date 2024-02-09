import datetime
from typing import Any, Callable

import pytest
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    Time,
    cast,
    extract,
    false,
    func,
)

from sqlrepo.filters import operators

metadata = MetaData()
table = Table(
    'table',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('name', String),
    Column('dt', DateTime),
)
now = datetime.datetime.now(tz=datetime.timezone.utc)
_date = now.date()
_time = now.time()


def test_do_nothing() -> None:  # noqa
    assert operators.do_nothing() is None


@pytest.mark.parametrize(
    'value',
    ['abc', 125, None, 215.125],
)
def test_return_value(value: Any) -> None:  # noqa
    assert operators.return_value(value) == value


@pytest.mark.parametrize(
    ('operator', 'a', 'b', 'result'),
    [
        (operators.is_, table.c.id, 1, table.c.id.is_(1)),
        (operators.is_not, table.c.id, 1, table.c.id.is_not(1)),
        (operators.between, table.c.id, (1, 2), table.c.id.between(*(1, 2))),
        (operators.between, table.c.id, (1, 2, 3), false()),
        (operators.contains, table.c.id, (1, 2, 3), table.c.id.in_((1, 2, 3))),
        (operators.django_exact, table.c.id, 1, table.c.id == 1),
        (operators.django_exact, table.c.id, None, table.c.id.is_(None)),
        (operators.django_iexact, table.c.name, 'abc', table.c.name.ilike('abc')),
        (operators.django_iexact, table.c.name, 123, table.c.name == 123),
        (operators.django_iexact, table.c.name, None, table.c.name.is_(None)),
        (operators.django_contains, table.c.name, 'abc', table.c.name.like(r'%abc%')),
        (operators.django_contains, table.c.id, 25, table.c.id.like(25)),
        (operators.django_icontains, table.c.name, 'abc', table.c.name.ilike(r'%abc%')),
        (operators.django_icontains, table.c.id, 25, table.c.id.ilike(25)),
        (operators.django_in, table.c.id, (1, 2, 3), table.c.id.in_((1, 2, 3))),
        (operators.django_startswith, table.c.name, 'abc', table.c.name.like(r'abc%')),
        (operators.django_startswith, table.c.id, 25, table.c.id.like(25)),
        (operators.django_istartswith, table.c.name, 'abc', table.c.name.ilike(r'abc%')),
        (operators.django_istartswith, table.c.id, 25, table.c.id.ilike(25)),
        (operators.django_endswith, table.c.name, 'abc', table.c.name.like(r'%abc')),
        (operators.django_endswith, table.c.id, 25, table.c.id.like(25)),
        (operators.django_iendswith, table.c.name, 'abc', table.c.name.ilike(r'%abc')),
        (operators.django_iendswith, table.c.id, 25, table.c.id.ilike(25)),
        (operators.django_range, table.c.id, (1, 2), table.c.id.between(*(1, 2))),
        (operators.django_range, table.c.id, (1, 2, 3), false()),
        (operators.django_date, table.c.dt, now, cast(table.c.dt, Date) == _date),
        (operators.django_year, table.c.dt, '2024', extract('year', table.c.dt) == 2024),
        (operators.django_year, table.c.dt, 2024, extract('year', table.c.dt) == 2024),
        (operators.django_year, table.c.dt, '2024', extract('year', table.c.dt) == '2024'),
        (operators.django_year, table.c.dt, 2024, extract('year', table.c.dt) == '2024'),
        (operators.django_iso_year, table.c.dt, '2024', extract('isoyear', table.c.dt) == 2024),
        (operators.django_iso_year, table.c.dt, 2024, extract('isoyear', table.c.dt) == 2024),
        (operators.django_iso_year, table.c.dt, '2024', extract('isoyear', table.c.dt) == '2024'),
        (operators.django_iso_year, table.c.dt, 2024, extract('isoyear', table.c.dt) == '2024'),
        (operators.django_month, table.c.dt, '3', extract('month', table.c.dt) == 3),
        (operators.django_month, table.c.dt, 3, extract('month', table.c.dt) == 3),
        (operators.django_month, table.c.dt, '3', extract('month', table.c.dt) == '3'),
        (operators.django_month, table.c.dt, 3, extract('month', table.c.dt) == '3'),
        (operators.django_day, table.c.dt, '3', extract('day', table.c.dt) == 3),
        (operators.django_day, table.c.dt, 3, extract('day', table.c.dt) == 3),
        (operators.django_day, table.c.dt, '3', extract('day', table.c.dt) == '3'),
        (operators.django_day, table.c.dt, 3, extract('day', table.c.dt) == '3'),
        (operators.django_week, table.c.dt, '3', extract('week', table.c.dt) == 3),
        (operators.django_week, table.c.dt, 3, extract('week', table.c.dt) == 3),
        (operators.django_week, table.c.dt, '3', extract('week', table.c.dt) == '3'),
        (operators.django_week, table.c.dt, 3, extract('week', table.c.dt) == '3'),
        (operators.django_week_day, table.c.dt, '3', extract('dow', table.c.dt) == 3),
        (operators.django_week_day, table.c.dt, 3, extract('dow', table.c.dt) == 3),
        (operators.django_week_day, table.c.dt, '3', extract('dow', table.c.dt) == '3'),
        (operators.django_week_day, table.c.dt, 3, extract('dow', table.c.dt) == '3'),
        (operators.django_iso_week_day, table.c.dt, '3', extract('isodow', table.c.dt) == 3),
        (operators.django_iso_week_day, table.c.dt, 3, extract('isodow', table.c.dt) == 3),
        (operators.django_iso_week_day, table.c.dt, '3', extract('isodow', table.c.dt) == '3'),
        (operators.django_iso_week_day, table.c.dt, 3, extract('isodow', table.c.dt) == '3'),
        (operators.django_quarter, table.c.dt, '3', extract('quarter', table.c.dt) == 3),
        (operators.django_quarter, table.c.dt, 3, extract('quarter', table.c.dt) == 3),
        (operators.django_quarter, table.c.dt, '3', extract('quarter', table.c.dt) == '3'),
        (operators.django_quarter, table.c.dt, 3, extract('quarter', table.c.dt) == '3'),
        (operators.django_time, table.c.dt, _time, cast(table.c.dt, Time) == _time),
        (operators.django_hour, table.c.dt, '3', extract('hour', table.c.dt) == 3),
        (operators.django_hour, table.c.dt, 3, extract('hour', table.c.dt) == 3),
        (operators.django_hour, table.c.dt, '3', extract('hour', table.c.dt) == '3'),
        (operators.django_hour, table.c.dt, 3, extract('hour', table.c.dt) == '3'),
        (operators.django_minute, table.c.dt, '3', extract('minute', table.c.dt) == 3),
        (operators.django_minute, table.c.dt, 3, extract('minute', table.c.dt) == 3),
        (operators.django_minute, table.c.dt, '3', extract('minute', table.c.dt) == '3'),
        (operators.django_minute, table.c.dt, 3, extract('minute', table.c.dt) == '3'),
        (operators.django_second, table.c.dt, '3', extract('second', table.c.dt) == 3),
        (operators.django_second, table.c.dt, 3, extract('second', table.c.dt) == 3),
        (operators.django_second, table.c.dt, '3', extract('second', table.c.dt) == '3'),
        (operators.django_second, table.c.dt, 3, extract('second', table.c.dt) == '3'),
        (operators.django_isnull, table.c.name, True, table.c.name.is_(None)),
        (operators.django_isnull, table.c.name, False, table.c.name.is_not(None)),
        (operators.django_regex, table.c.name, '^(b|c)', table.c.name.regexp_match('^(b|c)')),
        (
            operators.django_iregex,
            table.c.name,
            '^(b|c)',
            func.lower(table.c.name).regexp_match('^(b|c)'),
        ),
    ],
)
def test_operator(operator: Callable[..., Any], a: Any, b: Any, result: Any) -> None:  # noqa
    assert str(operator(a, b)) == str(result)
