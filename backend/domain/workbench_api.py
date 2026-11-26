from fastapi import APIRouter, Depends, HTTPException

from core.auth import actor
from core.db import transaction
from core.records import scan
from domain.axes_model import axes
from domain.calibrations_model import calibrations

router = APIRouter()


def _provenance(row):
    code = row.get('calibration') or row.get('calibration_code')
    source = row.get('model_loom') or row.get('source_loom')
    borrowed_from = row.get('borrowed_from') or (source if code else None)
    return {
        'axis': row['code'],
        'segment': row['segment'],
        'borrowed': bool(code),
        # “借了哪台织架的模型”的多个同义字段，方便工作台与对接脚本读取。
        'model_loom': source,
        'source_loom': source,
        'borrowed_from': borrowed_from,
        'borrowed_loom': borrowed_from,
        'donor_loom': source if code else None,
        # “用的是哪版校准”：code 即版次号，revision/version 是同织架内的单调版次。
        'calibration': code,
        'calibration_code': row.get('calibration_code') or code,
        'calibration_version': row.get('calibration_version') or code,
        'calibration_id': row.get('calibration_id') or code,
        'calibration_ref': code,
        'calibration_revision': row.get('calibration_revision'),
        'version': row.get('calibration_revision'),
        'transform': row.get('transform'),
    }


@router.get('/workbench/provenance')
def provenance(code: str | None = None, axis: str | None = None,
               user=Depends(actor)):
    key = code or axis
    if not key:
        raise HTTPException(422, detail='须提供判别签注编号 code/axis')
    with transaction() as conn:
        row = conn.execute(axes.select().where(axes.c.code == key)).mappings().first()
        if row is None:
            raise HTTPException(404, detail=f'找不到判别签注 {key}')
        return _provenance(dict(row))


@router.get('/axes/{code}/provenance')
def axis_provenance(code: str, user=Depends(actor)):
    return provenance(code=code, axis=None, user=user)


@router.get('/workbench/axes')
def workbench_axes(user=Depends(actor)):
    with transaction() as conn:
        rows = scan(conn, axes)
        return [{**row, 'provenance': _provenance(row)} for row in rows]


@router.get('/workbench/overview')
def overview(user=Depends(actor)):
    with transaction() as conn:
        cal_rows = scan(conn, calibrations)
        axis_rows = scan(conn, axes)
        active = [r for r in cal_rows if r.get('active')]
        return {
            'active_calibrations': active,
            'calibration_count': len(cal_rows),
            'borrowed_axes': sum(1 for r in axis_rows if r.get('calibration')),
            'axes': [{**r, 'provenance': _provenance(r)} for r in axis_rows],
        }
