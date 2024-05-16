class NotSetType:
    """Class, that represents not set attributes."""

    def __bool__(self) -> bool:  # noqa: D105  # pragma: no coverage
        return False


NotSet = NotSetType()
