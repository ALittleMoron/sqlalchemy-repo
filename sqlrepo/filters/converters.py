import enum
import operator as builtin_operator
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any, Callable, final

from abstractcp import Abstract, abstract_class_property
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql.elements import ColumnElement

from sqlrepo.exc import FilterError
from sqlrepo.filters import operators as custom_operator
from sqlrepo.filters.guards import is_dict_simple_filter_dict
from sqlrepo.utils import get_sqlalchemy_attribute, get_valid_field_names

IsValid = bool
Message = str
FilterDict = dict[str, Any]
SQLAlchemyFilter = ColumnElement[bool]
LookupMapping = dict[enum.Enum | str, Callable[[Any, Any], SQLAlchemyFilter]]


class BaseFilterConverter(ABC, Abstract):
    """Base class for filter converters."""

    lookup_mapping: LookupMapping = abstract_class_property(LookupMapping)

    @classmethod
    @abstractmethod
    def _is_filter_valid(
        cls,
        model: type[DeclarativeBase],
        filter_: FilterDict,
    ) -> tuple[IsValid, Message]:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def _convert_filter(
        cls,
        model: type[DeclarativeBase],
        filter_: FilterDict,
    ) -> Sequence[SQLAlchemyFilter]:
        raise NotImplementedError

    @classmethod
    @final
    def convert(
        cls,
        model: type[DeclarativeBase],
        filters: FilterDict
        | ColumnElement[bool]
        | Sequence[FilterDict | ColumnElement[bool]]
        | None = None,
    ) -> Sequence[SQLAlchemyFilter]:
        """Convert input dict or list of dicts to SQLAlchemy filter."""
        result: Sequence[SQLAlchemyFilter] = []
        if filters is None:
            return result
        if not isinstance(filters, Sequence):
            filters = [filters]
        for filter_ in filters:
            if isinstance(filter_, ColumnElement):
                result.append(filter_)
                continue
            is_valid, message = cls._is_filter_valid(model, filter_)
            if not is_valid:
                msg = f'Filter with data {filter_} is not valid: {message}'
                raise FilterError(msg)
            result.extend(cls._convert_filter(model, filter_))
        return result


class SimpleFilterConverter(BaseFilterConverter):
    """Simple filter converter, that works with pairs ``"field"-"value"``.

    ...
    """

    lookup_mapping = {}  # no needs for it.

    @classmethod
    def _is_filter_valid(
        cls,
        model: type[DeclarativeBase],
        filter_: FilterDict,
    ) -> tuple[IsValid, Message]:
        for field_name in filter_:
            if field_name not in get_valid_field_names(model):
                return False, f'Model or select statement {model} has no field "{field_name}".'
        return True, ''

    @classmethod
    def _convert_filter(
        cls,
        model: type[DeclarativeBase],
        filter_: FilterDict,
    ) -> Sequence[SQLAlchemyFilter]:
        operator_func = builtin_operator.eq
        sqlalchemy_filters: Sequence[SQLAlchemyFilter] = []
        for field_name, value in filter_.items():
            sqlalchemy_field = get_sqlalchemy_attribute(model, field_name)
            sqlalchemy_filters.append(operator_func(sqlalchemy_field, value))
        return sqlalchemy_filters


class AdvancedOperatorFilterConverter(BaseFilterConverter):
    lookup_mapping = {
        '==': builtin_operator.eq,
        '>': builtin_operator.gt,
        '<': builtin_operator.lt,
        '>=': builtin_operator.ge,
        '<=': builtin_operator.le,
        'is': custom_operator.is_,
        'is_not': custom_operator.is_not,
        'between': custom_operator.between,
        'contains': custom_operator.contains,
        # TODO: добавить валидацию значений.
        # Например, для between, чтобы передавать строго 2 значения, иначе FilterError.
    }

    @classmethod
    def _is_filter_valid(
        cls,
        model: type[DeclarativeBase],
        filter_: FilterDict,
    ) -> tuple[IsValid, Message]:
        if not is_dict_simple_filter_dict(filter_):
            return False, 'filter dict is not subtype of OperatorFilterDict.'
        field = filter_['field']
        if field not in get_valid_field_names(model):
            return False, f'Model or select statement {model} has no field "{field}".'
        return True, ''

    @classmethod
    def _convert_filter(
        cls,
        model: type[DeclarativeBase],
        filter_: FilterDict,
    ) -> Sequence[SQLAlchemyFilter]:
        if not is_dict_simple_filter_dict(filter_):
            msg = "Never situation. Don't use _convert_filter method directly!"
            raise FilterError(msg)
        operator_str = filter_['operator'] if 'operator' in filter_ else '=='
        operator_func = cls.lookup_mapping[operator_str]
        sqlalchemy_field = get_sqlalchemy_attribute(model, filter_['field'])
        return [operator_func(sqlalchemy_field, filter_['value'])]


class DjangoLikeFilterConverter(BaseFilterConverter):
    lookup_mapping = {
        'exact': custom_operator.django_exact,
        'iexact': custom_operator.django_iexact,
        'contains': custom_operator.django_contains,
        'icontains': custom_operator.django_icontains,
        'in': custom_operator.contains,
        'gt': builtin_operator.gt,
        'gte': builtin_operator.ge,
        'lt': builtin_operator.lt,
        'lte': builtin_operator.le,
        'startswith': custom_operator.django_startswith,
        'istartswith': custom_operator.django_istartswith,
        'endswith': custom_operator.django_endswith,
        'iendswith': custom_operator.django_iendswith,
        'range': custom_operator.django_range,
        'date': custom_operator.django_date,
        'year': custom_operator.django_year,
        'iso_year': custom_operator.django_iso_year,
        'month': custom_operator.django_month,
        'day': custom_operator.django_day,
        'week': custom_operator.django_week,
        'week_day': custom_operator.django_week_day,
        'iso_week_day': custom_operator.django_iso_week_day,
        'quarter': custom_operator.django_quarter,
        'time': custom_operator.django_time,
        'hour': custom_operator.django_hour,
        'minute': custom_operator.django_minute,
        'second': custom_operator.django_second,
        'isnull': custom_operator.django_isnull,
        'regex': custom_operator.django_regex,
        'iregex': custom_operator.django_iregex,
        # TODO: добавить sub-lookups, по типу year__gre, time__range и т.д.
        # NOTE: можно добавить параметр suboperator, который по умолчанию будет ==.
        #       и далее можно переиспользовать эти все функции.
        # NOTE: либо можно доработать _convert_filter для разделения нескольких частей фильтра.
    }

    @classmethod
    def _is_filter_valid(
        cls,
        model: type[DeclarativeBase],
        filter_: FilterDict,
    ) -> tuple[IsValid, Message]:
        for field in filter_:
            field_parts = field.split('__')
            if len(field_parts) == 1:
                field_name = field_parts[0]
                lookup = 'exact'
            elif len(field_parts) == 2:
                field_name, lookup = field_parts
            else:
                return (
                    False,
                    (
                        "DjangoLikeFilterConverter can't use nested filters or "
                        "related model filters yet."
                    ),
                )
            if field_name not in get_valid_field_names(model):
                return False, f'Model or select statement {model} has no field "{field_name}".'
            if lookup not in cls.lookup_mapping:
                all_lookup_mapping = list(cls.lookup_mapping.keys())
                message = f'Unexpected lookup "{lookup}".' f'Valid lookups: {all_lookup_mapping}.'
                return False, message
        return True, ''

    @classmethod
    def _convert_filter(
        cls,
        model: type[DeclarativeBase],
        filter_: FilterDict,
    ) -> Sequence[SQLAlchemyFilter]:
        sqlalchemy_filters: Sequence[SQLAlchemyFilter] = []
        for field, value in filter_.items():
            field_parts = field.split('__')
            # TODO: добавить возможность фильтровать по связанным сущностям.
            if len(field_parts) == 1:
                field_name = field_parts[0]
                lookup = 'exact'
            elif len(field_parts) == 2:
                field_name, lookup = field_parts
            else:
                msg = "Never situation. Don't use _convert_filter method directly!"
                raise FilterError(msg)
            operator_func = cls.lookup_mapping[lookup]
            sqlalchemy_field = get_sqlalchemy_attribute(model, field_name)
            sqlalchemy_filters.append(operator_func(sqlalchemy_field, value))
        return sqlalchemy_filters
