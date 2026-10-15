"""Pydantic schemas for requests and responses."""

from app.schemas.calculator import (
    AllocationPolicyInput,
    SplitRequest,
    SubnetCalcRequest,
    SummarizeRequest,
    ValidateRequest,
    ValidateResponse,
    VLSMDepartment,
    VLSMRequest,
)
from app.schemas.common import ErrorBody, ErrorResponse, MessageResponse, Page

__all__ = [
    "AllocationPolicyInput",
    "ErrorBody",
    "ErrorResponse",
    "MessageResponse",
    "Page",
    "SplitRequest",
    "SubnetCalcRequest",
    "SummarizeRequest",
    "ValidateRequest",
    "ValidateResponse",
    "VLSMDepartment",
    "VLSMRequest",
]
