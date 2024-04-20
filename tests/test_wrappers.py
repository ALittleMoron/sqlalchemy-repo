import pytest
from dev_utils.core.exc import (
    BaseDevError,
    NoDeclarativeModelError,
    NoModelAttributeError,
    NoModelRelationshipError,
    ProfilingError,
)
from sqlalchemy.exc import SQLAlchemyError

from sqlrepo.exc import BaseSQLRepoError, QueryError, RepositoryError
from sqlrepo.wrappers import wrap_any_exception_manager


@pytest.mark.parametrize(
    ("wrap_error", "output_error"),
    [
        (BaseDevError, RepositoryError),
        (NoDeclarativeModelError, RepositoryError),
        (NoModelAttributeError, RepositoryError),
        (NoModelRelationshipError, RepositoryError),
        (ProfilingError, RepositoryError),
        (SQLAlchemyError, QueryError),
        (AttributeError, BaseSQLRepoError),
        (TypeError, BaseSQLRepoError),
        (ValueError, BaseSQLRepoError),
    ],
)
def test_wrap_work(wrap_error: type[Exception], output_error: type[Exception]) -> None:
    error_message = "some error message."
    with pytest.raises(output_error), wrap_any_exception_manager():
        raise wrap_error(error_message)
