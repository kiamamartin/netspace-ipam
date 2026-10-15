"""Network inventory endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.inventory import NetworkCreate, NetworkDetail, NetworkRead, NetworkUpdate
from app.services import ipam_service

router = APIRouter()


@router.get("", summary="List networks")
def list_networks(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    q: str | None = Query(None, description="Search name, CIDR, site or description"),
    family: int | None = Query(None, description="4 or 6"),
    environment: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    site: str | None = Query(None),
    sort: str = Query("created_at"),
    order: str = Query("desc"),
) -> dict:
    return ipam_service.list_networks(
        db,
        page=page,
        page_size=page_size,
        q=q,
        family=family,
        environment=environment,
        status=status_filter,
        site=site,
        sort=sort,
        order=order,
    )


@router.post("", status_code=status.HTTP_201_CREATED, summary="Create a network")
def create_network(payload: NetworkCreate, db: Session = Depends(get_db)) -> NetworkRead:
    return ipam_service.create_network(db, payload.model_dump())


@router.get("/{network_id}", response_model=NetworkDetail, summary="Get a network")
def get_network(network_id: int, db: Session = Depends(get_db)) -> NetworkDetail:
    return ipam_service.network_detail(db, network_id)


@router.patch("/{network_id}", summary="Update a network")
def update_network(
    network_id: int, payload: NetworkUpdate, db: Session = Depends(get_db)
) -> NetworkRead:
    return ipam_service.update_network(db, network_id, payload.model_dump(exclude_unset=True))


@router.delete(
    "/{network_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a network",
)
def delete_network(network_id: int, db: Session = Depends(get_db)) -> Response:
    ipam_service.delete_network(db, network_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
