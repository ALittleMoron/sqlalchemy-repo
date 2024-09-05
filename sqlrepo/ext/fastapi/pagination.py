from typing import Annotated, Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class BaseSchema(BaseModel):
    """Base schema for pagination."""

    model_config = ConfigDict(from_attributes=True)


class PaginationMeta(BaseSchema):
    """Metadata of pagination result."""

    all_records_count: int
    filtered_records_count: int
    per_page: int
    current_page: int
    all_pages_count: int
    filtered_pages_count: int
    prev_page: int | None = None
    next_page: int | None = None

    @classmethod
    def create(  # noqa: D102
        cls,
        *,
        pagination: "AbstractBasePagination",
        all_records_count: int,
        filtered_records_count: int | None = None,
    ) -> "PaginationMeta":
        if filtered_records_count is None:  # pragma: no coverage
            filtered_records_count = all_records_count
        current_page = pagination.current_page
        per_page = pagination.per_page
        all_pages_count = all_records_count // per_page
        filtered_pages_count = filtered_records_count // per_page
        prev_page = current_page - 1 if (current_page - 1) > 0 else None
        next_page = current_page + 1 if (current_page + 1) <= filtered_pages_count else None
        return cls(
            all_records_count=all_records_count,
            filtered_records_count=filtered_records_count,
            per_page=per_page,
            current_page=current_page,
            all_pages_count=all_pages_count,
            filtered_pages_count=filtered_pages_count,
            prev_page=prev_page,
            next_page=next_page,
        )


class PaginatedResult(BaseSchema, Generic[T]):
    """Pagination result."""

    meta: PaginationMeta
    data: list[T]


class AbstractBasePagination:
    """Abstract base pagination depends."""

    limit: int
    offset: int
    per_page: int
    current_page: int

    def __init__(self) -> None:  # pragma: no coverage
        raise NotImplementedError


class LimitOffsetPagination(AbstractBasePagination):
    """Limit-Offset pagination depends."""

    def __init__(
        self,
        limit: Annotated[
            int,
            Query(
                ge=1,
                le=100,
                description="SQL limit.",
                examples=[1, 50, 100],
            ),
        ] = 50,
        offset: Annotated[
            int,
            Query(
                ge=0,
                description="SQL offset.",
                examples=[0, 10, 1000],
            ),
        ] = 0,
    ) -> None:
        self.limit = limit
        self.offset = offset
        self.per_page = limit
        self.current_page = (offset // limit) + 1


class PageSizePagination(AbstractBasePagination):
    """Page-Size pagination depends."""

    def __init__(
        self,
        per_page: Annotated[
            int,
            Query(
                ge=1,
                le=100,
                description="Count of items in paginated result.",
                examples=[1, 50, 100],
            ),
        ] = 50,
        page: Annotated[
            int,
            Query(
                ge=1,
                description="Number of current page.",
                examples=[0, 10, 1000],
            ),
        ] = 1,
    ) -> None:
        self.per_page = per_page
        self.current_page = page
        self.limit = per_page
        self.offset = (page - 1) * per_page
