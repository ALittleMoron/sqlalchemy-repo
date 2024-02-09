""""""
import datetime
from typing import TYPE_CHECKING, Any, TypeVar

from sqlalchemy import Date, Time, cast, extract, false, func
from sqlalchemy.orm import QueryableAttribute

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.sql.elements import ColumnElement

    T = TypeVar('T')


# =================================================================
# |                       COMMON OPERATORS                        |
# =================================================================


def do_nothing(*args: Any, **kwargs: Any) -> None:  # noqa: ANN401
    """"""
    return None


def return_value(value: 'T') -> 'T':
    """"""
    return value


def is_(
    a: QueryableAttribute[Any],  # noqa: ANN401
    b: Any,  # noqa
) -> 'ColumnElement[bool]':
    """"""
    return a.is_(b)


def is_not(
    a: QueryableAttribute[Any],  # noqa: ANN401
    b: Any,  # noqa
) -> 'ColumnElement[bool]':
    """"""
    return a.is_not(b)


def between(
    a: QueryableAttribute[Any],  # noqa: ANN401
    b: tuple[Any, Any],
) -> 'ColumnElement[bool]':
    """ """
    if len(b) != 2:
        return false()
    return a.between(*b)


def contains(
    a: QueryableAttribute[Any],  # noqa: ANN401
    b: 'Sequence[Any]',
) -> 'ColumnElement[bool]':
    """"""
    return a.in_(b)


# =================================================================
# |                       DJANGO OPERATORS                        |
# =================================================================


def django_exact(
    a: QueryableAttribute[Any],  # noqa: ANN401
    b: Any,  # noqa: ANN401
) -> 'ColumnElement[bool]':
    """"""
    if b is None:
        return a.is_(None)
    return a == b


def django_iexact(
    a: QueryableAttribute[Any],  # noqa: ANN401
    b: Any,  # noqa
) -> 'ColumnElement[bool]':
    """"""
    if b is None:
        return a.is_(None)
    if isinstance(b, str):
        return a.ilike(b)
    return a == b


def django_contains(
    a: QueryableAttribute[Any],  # noqa: ANN401
    b: Any,  # noqa: ANN401
) -> 'ColumnElement[bool]':
    """"""
    if isinstance(b, str):
        b = f'%{b}%'
    return a.like(b)


def django_icontains(
    a: QueryableAttribute[Any],  # noqa: ANN401
    b: Any,  # noqa: ANN401
) -> 'ColumnElement[bool]':
    """"""
    if isinstance(b, str):
        b = f'%{b}%'
    return a.ilike(b)


def django_in(
    a: QueryableAttribute[Any],  # noqa: ANN401
    b: 'Sequence[Any]',
) -> 'ColumnElement[bool]':
    """"""
    return a.in_(b)


def django_startswith(
    a: QueryableAttribute[Any],  # noqa: ANN401
    b: Any,  # noqa: ANN401
) -> 'ColumnElement[bool]':
    """"""
    if isinstance(b, str):
        b = f'{b}%'
    return a.like(b)


def django_istartswith(
    a: QueryableAttribute[Any],  # noqa: ANN401
    b: Any,  # noqa: ANN401
) -> 'ColumnElement[bool]':
    """"""
    if isinstance(b, str):
        b = f'{b}%'
    return a.ilike(b)


def django_endswith(
    a: QueryableAttribute[Any],  # noqa: ANN401
    b: Any,  # noqa: ANN401
) -> 'ColumnElement[bool]':
    """"""
    if isinstance(b, str):
        b = f'%{b}'
    return a.like(b)


def django_iendswith(
    a: QueryableAttribute[Any],  # noqa: ANN401
    b: Any,  # noqa: ANN401
) -> 'ColumnElement[bool]':
    """"""
    if isinstance(b, str):
        b = f'%{b}'
    return a.ilike(b)


def django_range(
    a: QueryableAttribute[Any],  # noqa: ANN401
    b: tuple[Any, Any],
) -> 'ColumnElement[bool]':
    """"""
    return between(a, b)


def django_date(
    a: QueryableAttribute[Any],  # noqa: ANN401
    b: datetime.date,
) -> 'ColumnElement[bool]':
    """"""
    return cast(a, Date) == b


def django_year(
    a: QueryableAttribute[Any],  # noqa: ANN401
    b: int | str,
) -> 'ColumnElement[bool]':
    """"""
    return extract('year', a) == b


def django_iso_year(
    a: QueryableAttribute[Any],  # noqa: ANN401
    b: int | str,
) -> 'ColumnElement[bool]':
    """"""
    return extract('isoyear', a) == b


def django_month(
    a: QueryableAttribute[Any],  # noqa: ANN401
    b: int | str,
) -> 'ColumnElement[bool]':
    """"""
    return extract('month', a) == b


def django_day(
    a: QueryableAttribute[Any],  # noqa: ANN401
    b: int | str,
) -> 'ColumnElement[bool]':
    """"""
    return extract('day', a) == b


def django_week(
    a: QueryableAttribute[Any],  # noqa: ANN401
    b: int | str,
) -> 'ColumnElement[bool]':
    """"""
    return extract('week', a) == b


def django_week_day(
    a: QueryableAttribute[Any],  # noqa: ANN401
    b: int | str,
) -> 'ColumnElement[bool]':
    """"""
    return extract('dow', a) == b


def django_iso_week_day(
    a: QueryableAttribute[Any],  # noqa: ANN401
    b: int | str,
) -> 'ColumnElement[bool]':
    """"""
    return extract('isodow', a) == b


def django_quarter(
    a: QueryableAttribute[Any],  # noqa: ANN401
    b: int | str,
) -> 'ColumnElement[bool]':
    """"""
    return extract('quarter', a) == b


def django_time(
    a: QueryableAttribute[Any],  # noqa: ANN401
    b: datetime.time,
) -> 'ColumnElement[bool]':
    """"""
    return cast(a, Time) == b


def django_hour(
    a: QueryableAttribute[Any],  # noqa: ANN401
    b: int,
) -> 'ColumnElement[bool]':
    """"""
    return extract('hour', a) == b


def django_minute(
    a: QueryableAttribute[Any],  # noqa: ANN401
    b: int,
) -> 'ColumnElement[bool]':
    """"""
    return extract('minute', a) == b


def django_second(
    a: QueryableAttribute[Any],  # noqa: ANN401
    b: int,
) -> 'ColumnElement[bool]':
    """"""
    return extract('second', a) == b


def django_isnull(
    a: QueryableAttribute[Any],  # noqa: ANN401
    b: bool,  # noqa: FBT001
) -> 'ColumnElement[bool]':
    """"""
    return a.is_(None) if b else a.is_not(None)


def django_regex(
    a: QueryableAttribute[Any],  # noqa: ANN401
    b: str,
) -> 'ColumnElement[bool]':
    """"""
    return a.regexp_match(b)


def django_iregex(
    a: QueryableAttribute[Any],  # noqa: ANN401
    b: str,
) -> 'ColumnElement[bool]':
    """"""
    return func.lower(a).regexp_match(b.lower())
