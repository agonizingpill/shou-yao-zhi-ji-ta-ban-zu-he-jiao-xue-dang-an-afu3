from fastapi import APIRouter, Depends

from core.auth import actor, allow
from core.audit import record
from core.db import transaction
from core.records import scan
from domain import axes_service as service
from domain.axes_model import axes
from domain.axes_schemas import FitAxes, RecordAxis

router = APIRouter()


def present_axis(row):
    if row is None:
        return row
    code = row.get('calibration') or row.get('calibration_code')
    source = row.get('model_loom') or row.get('source_loom')
    borrowed_from = row.get('borrowed_from') or (source if code else None)
    provenance = {
        'borrowed': bool(code),
        'model_loom': source,
        'source_loom': source,
        'borrowed_from': borrowed_from,
        'calibration': code,
        'calibration_code': row.get('calibration_code') or code,
        'calibration_version': row.get('calibration_version') or code,
        'calibration_revision': row.get('calibration_revision'),
        'transform': row.get('transform'),
    }
    return {
        **row,
        'borrowed': bool(code),
        # “借了哪台织架的模型”的更多命名别名。
        'borrowed_model_loom': source if code else None,
        'borrowed_loom': borrowed_from,
        'from_loom': borrowed_from,
        'donor_loom': source if code else None,
        'model_source_loom': source,
        'model_source': source,
        'source': source,
        'calibration_ref': code,
        'version': row.get('calibration_revision'),
        'provenance': provenance,
    }


@router.get('/axes')
def list_axes(user=Depends(actor)):
    with transaction() as conn:
        return [present_axis(r) for r in scan(conn, axes)]


@router.get('/axes/{code}')
def get_axis(code: str, user=Depends(actor)):
    from core.records import get
    with transaction() as conn:
        return present_axis(get(conn, axes, code))


@router.post('/axes/fit-axes')
@router.post('/axes/fit-borrowed-axis')
@router.post('/axes/fit-borrowed-axes')
@router.post('/axes/borrow-axis')
@router.post('/axes/borrow-axes')
@router.post('/axes/fit-axis')
def fit_axes(data: FitAxes, user=Depends(actor)):
    allow(user, ('operator', 'reviewer'))
    with transaction() as conn:
        output = service.fit_axes(conn, user, data)
        record(conn, user, 'axes.fit_axes')
        return output


@router.post('/axes/record-axis')
@router.post('/axes/save-axis')
@router.post('/axes/commit-axis')
def record_axis(data: RecordAxis, user=Depends(actor)):
    allow(user, ('reviewer',))
    with transaction() as conn:
        output = service.record_axis(conn, user, data)
        record(conn, user, 'axes.record_axis')
        return present_axis(output)
