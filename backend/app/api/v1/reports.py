"""Reporting endpoints: real downloadable CSV / XLSX / PDF files."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services import report_service

router = APIRouter()


def _attachment(filename: str, media_type: str, content: bytes) -> Response:
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/networks/{network_id}/csv", summary="Download a network report as CSV")
def network_csv(network_id: int, db: Session = Depends(get_db)) -> Response:
    data = report_service.network_report_data(db, network_id)
    csv_text = report_service.render_csv(data)
    return _attachment(f"network-{network_id}-report.csv", "text/csv; charset=utf-8", csv_text.encode("utf-8"))


@router.get("/networks/{network_id}/xlsx", summary="Download a network report as Excel")
def network_xlsx(network_id: int, db: Session = Depends(get_db)) -> Response:
    data = report_service.network_report_data(db, network_id)
    content = report_service.render_xlsx(data)
    return _attachment(
        f"network-{network_id}-report.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        content,
    )


@router.get("/networks/{network_id}/pdf", summary="Download a network report as PDF")
def network_pdf(network_id: int, db: Session = Depends(get_db)) -> Response:
    data = report_service.network_report_data(db, network_id)
    content = report_service.render_pdf(data)
    return _attachment(f"network-{network_id}-report.pdf", "application/pdf", content)


@router.get("/allocation-plans/{plan_id}/csv", summary="Download a plan as CSV")
def plan_csv(plan_id: int, db: Session = Depends(get_db)) -> Response:
    data = report_service.plan_report_data(db, plan_id)
    csv_text = report_service.render_csv(data)
    return _attachment(f"allocation-plan-{plan_id}.csv", "text/csv; charset=utf-8", csv_text.encode("utf-8"))


@router.get("/allocation-plans/{plan_id}/xlsx", summary="Download a plan as Excel")
def plan_xlsx(plan_id: int, db: Session = Depends(get_db)) -> Response:
    data = report_service.plan_report_data(db, plan_id)
    content = report_service.render_xlsx(data)
    return _attachment(
        f"allocation-plan-{plan_id}.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        content,
    )


@router.get("/allocation-plans/{plan_id}/pdf", summary="Download a plan as PDF")
def plan_pdf(plan_id: int, db: Session = Depends(get_db)) -> Response:
    data = report_service.plan_report_data(db, plan_id)
    content = report_service.render_pdf(data)
    return _attachment(f"allocation-plan-{plan_id}.pdf", "application/pdf", content)
