from collections.abc import Mapping
from functools import partial
from types import TracebackType
from typing import Any, Literal, Protocol, TypeAlias, TypeVar, overload

_T_contra = TypeVar("_T_contra", contravariant=True)
_SysExcInfoType: TypeAlias = (
    tuple[type[BaseException], BaseException, TracebackType | None] | tuple[None, None, None]
)
_ExcInfoType: TypeAlias = bool | _SysExcInfoType | BaseException


class SupportsWrite(Protocol[_T_contra]):  # noqa: D101
    def write(self, s: _T_contra, /) -> object: ...  # noqa: D102  pragma: no cover


class SupportsFlush(Protocol):  # noqa: D101
    def flush(self) -> object: ...  # noqa: D102  pragma: no cover


class _SupportsWriteAndFlush(SupportsWrite[_T_contra], SupportsFlush, Protocol[_T_contra]): ...


class _PrintProtocol(Protocol):
    @overload
    @staticmethod
    def __call__(  # NOTE: print 1
        *values: object,
        sep: str | None = " ",
        end: str | None = "\n",
        file: "SupportsWrite[str] | None" = None,
        flush: Literal[False] = False,
    ) -> None: ...

    @overload
    @staticmethod
    def __call__(  # NOTE: print 2
        *values: object,
        sep: str | None = " ",
        end: str | None = "\n",
        file: "_SupportsWriteAndFlush[str] | None" = None,
        flush: bool,
    ) -> None: ...

    @staticmethod
    def __call__(*args: Any, **kwargs: Any) -> None: ...  # pragma: no cover


class _PythonLogProtocol(Protocol):
    @staticmethod
    def __call__(
        msg: object,
        *args: object,
        exc_info: _ExcInfoType | None = None,
        stack_info: bool = False,
        stacklevel: int = 1,
        extra: Mapping[str, object] | None = None,
    ) -> None: ...


class _StructLogProtocol(Protocol):
    @staticmethod
    def __call__(
        event: str | None = None,
        *args: Any,  # noqa: ANN401
        **kw: Any,  # noqa: ANN401
    ) -> Any: ...  # noqa: ANN401


class _WarnProtocol(Protocol):
    @overload
    @staticmethod
    def __call__(
        message: str,
        category: type[Warning] | None = None,
        stacklevel: int = 1,
        source: Any | None = None,  # noqa: ANN401
        *,
        skip_file_prefixes: tuple[str, ...] = (),
    ) -> None: ...

    @overload
    @staticmethod
    def __call__(
        message: Warning,
        category: Any = None,  # noqa: ANN401
        stacklevel: int = 1,
        source: Any | None = None,  # noqa: ANN401
        *,
        skip_file_prefixes: tuple[str, ...] = (),
    ) -> None: ...


LogFunctionProtocol: TypeAlias = (
    _PrintProtocol | _PythonLogProtocol | _StructLogProtocol | _WarnProtocol | partial[None]
)
"""Type alias for log function protocols."""
