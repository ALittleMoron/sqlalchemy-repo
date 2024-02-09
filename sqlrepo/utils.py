"""Модуль утилит."""

import datetime
import types
import zoneinfo
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Callable, TypeVar

from sqlalchemy import Delete, Insert, Select, Update, inspect
from sqlalchemy.ext.hybrid import HybridExtensionType
from sqlalchemy.orm import joinedload

from sqlrepo.logging import logger

if TYPE_CHECKING:
    from sqlalchemy.orm import DeclarativeBase, Mapper, QueryableAttribute
    from sqlalchemy.orm.base import InspectionAttr
    from sqlalchemy.orm.clsregistry import _ClsRegistryType  # type: ignore
    from sqlalchemy.orm.strategy_options import _AbstractLoad  # type: ignore

    T = TypeVar('T', bound=Select[Any])

Statement = (
    Select[tuple['DeclarativeBase']]
    | Update['DeclarativeBase']
    | Delete['DeclarativeBase']
    | Insert['DeclarativeBase']
)


def get_utc_now() -> datetime.datetime:
    """Get current UTC datetime.

    Returns
    -------
        datetime: current datetime with UTC timezone.
    """
    return datetime.datetime.now(zoneinfo.ZoneInfo('UTC'))


def get_sqlalchemy_field(
    model: type["DeclarativeBase"],
    field_name: str,
) -> "QueryableAttribute[Any]":
    """Get sqlalchemy field (column) object from given model.

    Args
    ----
    model : type[DeclarativeBase]
        SQLAlchemy declarative model.
    field_name : str
        name of field to find in model.

    Returns
    -------
    QueryableAttribute[Any]
        any attribute from model, that can be used in queries.
    """
    # TODO: добавить проверку на существование.
    sqlalchemy_field = getattr(model, field_name)
    if isinstance(sqlalchemy_field, types.MethodType):
        sqlalchemy_field = sqlalchemy_field()
    return sqlalchemy_field


def get_model_classes_from_statement(stmt: Statement) -> Sequence[type['DeclarativeBase']]:
    """Get sqlalchemy model classes from given statement.

    Args
    ----
    stmt : Statement
        SQLAlchemy statement (select, update, delete, insert).

    Returns
    -------
    Sequence['DeclarativeBase']
        sequence of model classes.
    """
    if isinstance(stmt, Select):
        # select_from_objs = []
        # if stmt._from_obj:
        return [col_desc['entity'] for col_desc in stmt.column_descriptions]
    return [stmt.entity_description['entity']]


def get_registry_class(model: type['DeclarativeBase']) -> '_ClsRegistryType':
    """Get sqlalchemy registry class from any model.

    Args
    ----
    model : type[DeclarativeBase]
        SQLAlchemy declarative model.

    Returns
    -------
    _ClsRegistryType
        SQLAlchemy registry of all models and other specific objects.
    """
    return model.registry._class_registry  # type: ignore


def get_model_class_by_name(
    registry: '_ClsRegistryType',
    name: str,
) -> type['DeclarativeBase'] | None:
    """Return the model class matching `name` in the given `registry`.

    Args
    ----
    registry : _ClsRegistryType
        SQLAlchemy registry of all models and other specific objects.
    name : str
        name of model to find in registry.

    Returns
    -------
    type['DeclarativeBase'] | None
        Optional model class.
    """
    for cls in registry.values():
        if getattr(cls, '__name__', None) == name:
            return cls  # type: ignore


def get_valid_model_class_names(registry: '_ClsRegistryType') -> set[str]:
    """Get sqlalchemy model names as strings from given registry.

    Args
    ----
    registry : _ClsRegistryType
        SQLAlchemy registry of all models and other specific objects.

    Returns
    -------
    set[str]
        set of model names as strings.
    """
    return set(
        filter(
            None,
            (getattr(ele, '__name__', None) for ele in registry.values()),
        ),
    )


def get_valid_relationships_names(model: type['DeclarativeBase']) -> set[str]:
    """Get sqlalchemy relationship names as strings from given model.

    Args
    ----
    model : type[DeclarativeBase]
        SQLAlchemy declarative model.

    Returns
    -------
    set[str]
        set of model relationships as strings.
    """
    return set(inspect(model).relationships.keys())


def get_valid_field_names(model: type["DeclarativeBase"]) -> set[str]:
    """Get sqlalchemy field names as strings from given model.

    It includes hybrid properties and hybrid methods, because they can be used in queries.

    Args
    ----
    model : type[DeclarativeBase]
        SQLAlchemy declarative model.

    Returns
    -------
    set[str]
        set of model fields as strings.
    """
    inspect_mapper: 'Mapper[Any]' = inspect(model)  # type: ignore
    columns = inspect_mapper.columns
    orm_descriptors = inspect_mapper.all_orm_descriptors

    column_names = columns.keys()
    hybrid_names = [
        key
        for key, item in orm_descriptors.items()
        if is_hybrid_property(item) or is_hybrid_method(item)
    ]

    return set(column_names) | set(hybrid_names)


def is_hybrid_property(orm_descriptor: "InspectionAttr") -> bool:
    """Check, if given field inspected object is hybrid property or not.

    Args
    ----
    orm_descriptor: InspectionAttr
        SQLAlchemy field inspected object.

    Returns
    -------
    bool
        is field a hybrid property or not?
    """
    return orm_descriptor.extension_type == HybridExtensionType.HYBRID_PROPERTY


def is_hybrid_method(orm_descriptor: "InspectionAttr") -> bool:
    """Check, if given field inspected object is hybrid method or not.

    Args
    ----
    orm_descriptor: InspectionAttr
        SQLAlchemy field inspected object.

    Returns
    -------
    bool
        is field a hybrid method or not?
    """
    return orm_descriptor.extension_type == HybridExtensionType.HYBRID_METHOD


def apply_loads(
    stmt: "T",
    *relationship_names: str,
    load_strategy: Callable[[Any], '_AbstractLoad'] = joinedload,
) -> "T":
    """Apply loads from string.

    String joins should represent relations, not model classes.

    Args
    ----
    stmt : TypeVar (Statement)
        select statement instance.
    *relationship_names : str
        any relationship names of model.
    load_strategy : Callable
        any callable object, that will return Load object.

    Returns
    -------
    stmt : TypeVar (Statement)
        select statement instance with applied joins.
    """
    model_classes = get_model_classes_from_statement(stmt)
    loaders: list['_AbstractLoad'] = []
    for relationship_ in relationship_names:
        sqlalchemy_relationship = None
        for model_ in model_classes:
            if relationship_ in get_valid_relationships_names(model_):
                sqlalchemy_relationship = get_sqlalchemy_field(model_, relationship_)
        if not sqlalchemy_relationship:
            # TODO: убрать continue. сделать выкидывание ошибки со списком возможных relationship.
            continue
        load = load_strategy(sqlalchemy_relationship)
        loaders.append(load)
    stmt = stmt.options(*loaders)
    return stmt


def apply_joins(
    stmt: "T",
    *relationship_names: str,
    left_outer_join: bool = False,
    full_join: bool = False,
) -> "T":
    """Apply joins from string.

    String joins should represent relations, not model classes.

    Args
    ----
    stmt : TypeVar (Statement)
        select statement instance.
    *relationship_names : str
        any relationship names of model.
    left_outer_join : bool (False)
        use LEFT OUTER JOIN.
    full_join : bool (False)
        use FULL JOIN.

    Returns
    -------
    stmt : TypeVar (Statement)
        select statement instance with applied joins.
    """
    model_classes = get_model_classes_from_statement(stmt)
    for relationship_ in relationship_names:
        sqlalchemy_relationship = None
        # TODO: добавить поиск по названию модели (joins=('ModelName'))
        for model_ in model_classes:
            if relationship_ in get_valid_relationships_names(model_):
                sqlalchemy_relationship = get_sqlalchemy_field(model_, relationship_)
        if not sqlalchemy_relationship:
            msg = (
                f'SQLAlchemy relationship "{relationship_}" was not found in {model_classes}. '
                'Maybe you passed incorrect relationship name or passed model name.'
            )
            logger.warning(msg)
            # TODO: убрать continue. сделать выкидывание ошибки со списком возможных relationship.
            continue
        stmt = stmt.join(  # type: ignore
            sqlalchemy_relationship,
            isouter=left_outer_join,
            full=full_join,
        )
    return stmt
