"""Exceptions for sqlrepo project."""

# |--------------| BASE |--------------|


class BaseSQLRepoError(Exception):
    """Base sqlrepo error."""


# |--------------| REPOSITORIES |--------------|


class RepositoryError(BaseSQLRepoError):
    """Base repository error."""


class RepositoryAttributeError(RepositoryError):
    """Repository error about incorrect attribute."""


# |--------------| QUERIES |--------------|


class QueryError(BaseSQLRepoError):
    """Base query error."""


# |--------------| Unit of work |--------------|


class UnitOfWorkError(BaseSQLRepoError):
    """Base unit of work error."""


class NonContextManagerUOWUsageError(UnitOfWorkError):
    """Error, caused by incorrect usage of unit of work.

    There is only one use case - via context manager. Other use-cases are not valid.
    """
