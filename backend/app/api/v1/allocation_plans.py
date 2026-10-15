"""Allocation plan endpoints: save, preview, activate, recalculate, archive."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.inventory import (
    PlanActivateResponse,
    PlanCreate,
    PlanRead,
    PlanUpdate,
)
from app.services import ipam_service

router = APIRouter()


@router.get("", summary="List saved plans")
def list_plans(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status_filter: str | None = Query(None, alias="status"),
    q: str | None = Query(None),
) -> dict:
    return ipam_service.list_plans(db, page=page, page_size=page_size, status=status_filter, q=q)


@router.post("", status_code=status.HTTP_201_CREATED, summary="Save an allocation plan")
def create_plan(payload: PlanCreate, db: Session = Depends(get_db)) -> PlanRead:
    return ipam_service.create_plan(db, payload.model_dump())


@router.get("/{plan_id}", summary="Get a saved plan")
def get_plan(plan_id: int, db: Session = Depends(get_db)) -> PlanRead:
    return ipam_service.get_plan(db, plan_id)


@router.patch("/{plan_id}", summary="Update plan metadata")
def update_plan(plan_id: int, payload: PlanUpdate, db: Session = Depends(get_db)) -> PlanRead:
    return ipam_service.update_plan(db, plan_id, payload.model_dump(exclude_unset=True))


@router.post(
    "/{plan_id}/activate",
    response_model=PlanActivateResponse,
    summary="Validate and commit a plan transactionally",
)
def activate_plan(plan_id: int, db: Session = Depends(get_db)) -> PlanActivateResponse:
    return ipam_service.activate_plan(db, plan_id)


@router.post(
    "/{plan_id}/recalculate", summary="Recalculate a plan from its stored inputs"
)
def recalculate_plan(plan_id: int, db: Session = Depends(get_db)) -> PlanRead:
    return ipam_service.recalculate_plan(db, plan_id)


@router.post("/{plan_id}/archive", summary="Archive an eligible plan")
def archive_plan(plan_id: int, db: Session = Depends(get_db)) -> PlanRead:
    return ipam_service.archive_plan(db, plan_id)
