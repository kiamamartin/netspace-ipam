"""Shared schema primitives."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


class ErrorDetail(BaseModel):
    field: str | None = None
    message: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[dict] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    """Consistent error payload returned by every failing endpoint."""

    error: ErrorBody


class MessageResponse(BaseModel):
    message: str


class PaginationQuery:
    """Reusable pagination query parameters."""

    def __init__(self, page: int = 1, page_size: int = 50) -> None:
        self.page = max(page, 1)
        self.page_size = max(min(page_size, 200), 1)
