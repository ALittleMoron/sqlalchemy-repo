# |--------------| BASE |--------------|


class BaseSQLRepoError(Exception):
    """"""


# |--------------| REPOSITORIES |--------------|


class RepositoryError(BaseSQLRepoError):
    """"""


class RepositoryAttributeError(RepositoryError):
    """"""


# |--------------| FILTERS |--------------|


class FilterError(BaseSQLRepoError):
    """"""


# |--------------| QUERIES |--------------|


class QueryError(BaseSQLRepoError):
    """"""
