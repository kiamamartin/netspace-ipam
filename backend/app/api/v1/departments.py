"""Department endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.inventory import DepartmentCreate, DepartmentRead, DepartmentUpdate
from app.services import ipam_service

router = APIRouter()


@router.get("", summary="List departments")
def list_departments(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    q: str | None = Query(None),
) -> dict:
    return ipam_service.list_departments(db, page=page, page_size=page_size, q=q)


@router.post("", status_code=status.HTTP_201_CREATED, summary="Create a department")
def create_department(payload: DepartmentCreate, db: Session = Depends(get_db)) -> DepartmentRead:
    return ipam_service.create_department(db, payload.model_dump())


@router.get("/{department_id}", summary="Get a department")
def get_department(department_id: int, db: Session = Depends(get_db)) -> DepartmentRead:
    return ipam_service.get_department(db, department_id)


@router.patch("/{department_id}", summary="Update a department")
def update_department(
    department_id: int, payload: DepartmentUpdate, db: Session = Depends(get_db)
) -> DepartmentRead:
    return ipam_service.update_department(db, department_id, payload.model_dump(exclude_unset=True))


@router.delete(
    "/{department_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a department"
)
def delete_department(department_id: int, db: Session = Depends(get_db)) -> Response:
    ipam_service.delete_department(db, department_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
