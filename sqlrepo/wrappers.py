from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from dev_utils.core.exc import BaseDevError
from sqlalchemy.exc import SQLAlchemyError

from sqlrepo.exc import BaseSQLRepoError, QueryError, RepositoryError

if TYPE_CHECKING:
    from collections.abc import Generator


@contextmanager
def wrap_any_exception_manager() -> "Generator[None, None, Any]":
    """Context manager wrapper to prevent sqlalchemy or any other exceptions to be thrown.

    replace with such pattern:

        1) if there is SQLAlchemyError, throw QueryError, because its error in query executing.

        2) if there is error from python-dev-utils (BaseDevError), throw RepositoryError.

        3) if there is possible python errors (no all. Only specific), throw BaseSQLRepoError.
    """
    try:
        yield
    except SQLAlchemyError as exc:
        raise QueryError from exc
    except BaseDevError as exc:
        raise RepositoryError from exc
    except (AttributeError, TypeError, ValueError) as exc:
        raise BaseSQLRepoError from exc
