# |--------------| BASE |--------------|


class BaseSQLRepoError(Exception):
    """"""


# |--------------| MODELS |--------------|


class NoModelFieldError(Exception):
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
