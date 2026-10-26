"""Version 1 API routes."""

from fastapi import APIRouter

from app.api.v1 import (
    allocation_plans,
    auth,
    calculator,
    dashboard,
    departments,
    ip_addresses,
    networks,
    reports,
    subnets,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(calculator.router, prefix="/calculator", tags=["calculator"])
api_router.include_router(networks.router, prefix="/networks", tags=["networks"])
api_router.include_router(subnets.router, prefix="/subnets", tags=["subnets"])
api_router.include_router(ip_addresses.router, prefix="/ip-addresses", tags=["ip-addresses"])
api_router.include_router(departments.router, prefix="/departments", tags=["departments"])
api_router.include_router(allocation_plans.router, prefix="/allocation-plans", tags=["allocation-plans"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(dashboard.router, prefix="", tags=["dashboard"])

__all__ = ["api_router", "auth"]
