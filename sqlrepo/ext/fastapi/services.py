import importlib
import warnings
from inspect import isclass
from typing import TYPE_CHECKING, Any, ForwardRef, Generic, TypeVar, get_args

from fastapi import Depends, HTTPException, Request, status
from pydantic import BaseModel, TypeAdapter
from sqlalchemy.orm.decl_api import DeclarativeBase
from verbose_http_exceptions import BaseVerboseHTTPException

from sqlrepo.ext.fastapi.helpers import NotSet, NotSetType
from sqlrepo.ext.fastapi.pagination import PaginatedResult, PaginationMeta
from sqlrepo.ext.fastapi.stubs import _get_session_stub  # type: ignore[reportPrivateUsage]

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm.session import Session


TModel = TypeVar("TModel", bound=DeclarativeBase)
TDetailSchema = TypeVar("TDetailSchema", bound=BaseModel)
VListSchema = TypeVar("VListSchema", bound=BaseModel)


def resolve_type(
    cls: type["BaseService[TModel, TDetailSchema, VListSchema]"],
    value: Any,  # noqa: ANN401
) -> Any | None:  # noqa: ANN401
    """Resolve given generic type of BaseService to real type."""
    if isinstance(value, ForwardRef):
        try:
            module = vars(cls).get("__module__")
            if not module:  # pragma: no coverage
                msg = (
                    f"No attribute __module__ in {cls}. Can't import global context for "
                    "ForwardRef resolving."
                )
                raise TypeError(msg)  # noqa: TRY301
            detail_schema_globals = vars(importlib.import_module(module))
            return eval(  # noqa: S307
                value.__forward_arg__,
                detail_schema_globals,
            )
        except (ImportError, TypeError, AttributeError, NameError) as exc:
            msg = (
                "Can't evaluate ForwardRef of generic type. "
                "Don't use type in generic with quotes. "
                f"Original exception: {exc!s}"
            )
            warnings.warn(msg, ServiceClassIncorrectUseWarning, stacklevel=2)
            return None
    elif isinstance(value, TypeVar):
        msg = "GenericType was not passed for pydantic BaseModel subclass."
        warnings.warn(msg, ServiceClassIncorrectUseWarning, stacklevel=2)
        return None
    elif not issubclass(value, BaseModel):
        msg = "Passed GenericType is not pydantic BaseModel subclass."
        warnings.warn(msg, ServiceClassIncorrectUseWarning, stacklevel=2)
        return None
    return value


class ServiceClassIncorrectUseWarning(Warning):
    """Service class incorrect use warning."""


class BaseService(Generic[TModel, TDetailSchema, VListSchema]):
    """Base service class."""

    __inheritance_check_model_class__: bool = True

    def __init_subclass__(cls) -> None:  # noqa: D105
        super().__init_subclass__()
        if not isinstance(
            cls.detail_schema,
            NotSetType,
        ) and not isinstance(
            cls.list_schema,
            NotSetType,
        ):
            return
        if cls.__inheritance_check_model_class__ is False:
            cls.__inheritance_check_model_class__ = True
            return
        try:
            # PEP-560: https://peps.python.org/pep-0560/
            # NOTE: this code is needed for getting type from generic: Generic[int] -> int type
            # get_args get params from __orig_bases__, that contains Generic passed types.
            _, detail_schema_type, list_schema_type, *_ = get_args(cls.__orig_bases__[0])  # type: ignore[reportAttributeAccessIssue]
        except (AttributeError, IndexError, TypeError) as exc:
            msg = (
                f"Error during getting information about Generic types for {cls.__name__}. "
                f"Original exception: {exc!s}"
            )
            warnings.warn(msg, ServiceClassIncorrectUseWarning, stacklevel=2)
            return
        if (
            isinstance(getattr(cls, "detail_schema", NotSet), NotSetType)
            and (detail_schema_type := resolve_type(cls, detail_schema_type)) is not None
        ):
            cls.detail_schema = detail_schema_type
        if (
            isinstance(getattr(cls, "list_schema", NotSet), NotSetType)
            and (list_schema_type := resolve_type(cls, list_schema_type)) is not None
        ):
            cls.list_schema = list_schema_type

    detail_schema: "type[TDetailSchema] | NotSetType" = NotSet
    list_schema: "type[VListSchema]| NotSetType" = NotSet
    not_found_message: "str | NotSetType" = NotSet
    not_found_exception: "Exception | type[Exception] | NotSetType " = NotSet

    def _resolve_entity_not_found(self) -> None:
        message = "Entity not found."
        if not isinstance(self.not_found_message, NotSetType):
            message = self.not_found_message
        if isinstance(self.not_found_exception, NotSetType):
            msg = "not_found_exception must be set, if you use resolve_entity in your code."
            raise AttributeError(msg)  # noqa: TRY004
        if not isclass(self.not_found_exception):
            raise self.not_found_exception
        if issubclass(self.not_found_exception, HTTPException):
            raise self.not_found_exception(
                detail=message,
                status_code=status.HTTP_404_NOT_FOUND,
            )
        if issubclass(self.not_found_exception, BaseVerboseHTTPException):
            message = self.not_found_exception.message or message
            raise self.not_found_exception(
                message=message,
                status_code=status.HTTP_404_NOT_FOUND,
            )
        raise self.not_found_exception(message)

    def resolve_entity(self, entity: "TModel | None") -> "TDetailSchema":
        """Resolve given SQLAlchemy entity and return pydantic schema."""
        if entity is None:
            self._resolve_entity_not_found()
        if isinstance(self.detail_schema, NotSetType):
            msg = "detail_schema must be set, if you use resolve_entity in your code."
            raise AttributeError(msg)  # noqa: TRY004
        return self.detail_schema.model_validate(entity, from_attributes=True)

    def resolve_entity_list(self, entities: "Sequence[TModel]") -> "list[VListSchema]":
        """Resolve given SQLAlchemy entity and return pydantic schema."""
        if isinstance(self.list_schema, NotSetType):
            msg = "list_schema must be set, if you use resolve_entity in your code."
            raise AttributeError(msg)  # noqa: TRY004
        return TypeAdapter(list[self.list_schema]).validate_python(entities, from_attributes=True)

    def paginate_result(
        self,
        entities: "Sequence[TModel]",
        meta: PaginationMeta,
    ) -> PaginatedResult["VListSchema"]:
        """Resolve list if entities and put them into pagination."""
        return PaginatedResult(
            meta=meta,
            data=self.resolve_entity_list(entities=entities),
        )


class BaseAsyncService(BaseService[TModel, TDetailSchema, VListSchema]):
    """Base service with async interface."""

    __inheritance_check_model_class__: bool = False

    def init_repositories(self, session: "AsyncSession") -> None:
        """Init repositories.

        Define your own method for it and specify your own methods for working with repositories.
        """
        raise NotImplementedError

    def __init__(
        self,
        request: "Request",
        session: "AsyncSession" = Depends(_get_session_stub),
    ) -> None:  # pragma: no coverage
        self.session = session
        self.request = request
        self.init_repositories(session)


class BaseSyncService(BaseService[TModel, TDetailSchema, VListSchema]):
    """Base service with async interface."""

    __inheritance_check_model_class__: bool = False

    def init_repositories(self, session: "Session") -> None:
        """Init repositories.

        Define your own method for it and specify your own methods for working with repositories.
        """
        raise NotImplementedError

    def __init__(
        self,
        request: Request,
        session: "Session" = Depends(_get_session_stub),
    ) -> None:  # pragma: no coverage
        self.session = session
        self.request = request
        self.init_repositories(session)
