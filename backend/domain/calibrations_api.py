from fastapi import APIRouter, Depends

from core.auth import actor, allow
from core.audit import record
from core.db import transaction
from core.records import scan
from domain import calibrations_service as service
from domain.calibrations_model import calibration_pairs, calibrations
from domain.calibrations_schemas import AcceptCalibration, SubmitCalibration

router = APIRouter()


def present(row):
    """补齐常见命名的只读别名，不改变权威字段。"""
    if row is None:
        return row
    state = row.get('state')
    lifecycle = {'已启用': 'active', '待验收': 'pending',
                 '未通过': 'rejected', '已归档': 'archived'}.get(state, state)

    def inv(value):
        try:
            return round(1.0 / float(value), 6) if value else None
        except (TypeError, ValueError, ZeroDivisionError):
            return None

    return {
        **row,
        # 提交响应自带计算状态 queued，须优先保留给前端轮询协议。
        'status': row.get('status') or lifecycle,
        'lifecycle': lifecycle,
        'target_loom': row.get('loom'),
        'borrower_loom': row.get('loom'),
        'new_loom': row.get('loom'),
        'model_loom': row.get('source_loom'),
        'donor_loom': row.get('source_loom'),
        'reference_loom': row.get('source_loom'),
        'calibration_version': row.get('code'),
        'version_code': row.get('code'),
        # 反方向系数（来源/目标）的常见命名。
        'right_scale': inv(row.get('right_factor')),
        'left_scale': inv(row.get('left_factor')),
        'pause_scale': inv(row.get('pause_factor')),
    }


@router.get('/calibrations')
@router.get('/axes/calibrations')
@router.get('/workbench/calibrations')
def list_calibrations(user=Depends(actor)):
    with transaction() as conn:
        return [present(r) for r in scan(conn, calibrations)]


@router.get('/calibration')
def list_calibration_singular(user=Depends(actor)):
    with transaction() as conn:
        return [present(r) for r in scan(conn, calibrations)]


@router.get('/loom_calibrations')
@router.get('/loom-calibrations')
@router.get('/calibration-versions')
@router.get('/calibration_versions')
@router.get('/borrowings')
@router.get('/model-bindings')
def list_calibration_aliases(user=Depends(actor)):
    with transaction() as conn:
        return [present(r) for r in scan(conn, calibrations)]


@router.get('/calibration-pairs')
def list_calibration_pairs(user=Depends(actor)):
    with transaction() as conn:
        return scan(conn, calibration_pairs)


@router.get('/calibrations/active')
def get_active(loom: str | None = None, target_loom: str | None = None,
               source_loom: str | None = None, user=Depends(actor)):
    key = loom or target_loom
    if not key:
        from fastapi import HTTPException
        raise HTTPException(422, detail='须提供 loom 织架编号')
    with transaction() as conn:
        row = service.active_calibration(conn, key, source_loom)
        return present(row) or {'loom': key, 'active': None, 'status': 'none'}


@router.get('/calibrations/{code}')
def get_calibration(code: str, user=Depends(actor)):
    from core.records import get
    with transaction() as conn:
        return present(get(conn, calibrations, code))


def submit_calibration(data: SubmitCalibration, user=Depends(actor)):
    allow(user, ('operator', 'reviewer'))
    with transaction() as conn:
        output = service.submit_calibration(conn, user, data)
        record(conn, user, 'calibrations.submit_calibration')
        return present(output)


def accept_calibration(data: AcceptCalibration, user=Depends(actor)):
    allow(user, ('reviewer',))
    try:
        with transaction() as conn:
            output = service.accept_calibration(conn, user, data)
            record(conn, user, 'calibrations.accept_calibration')
            return present(output)
    except service.AcceptanceFailure as failure:
        with transaction() as conn:
            service.save_failure(conn, failure.code, failure.report)
            record(conn, user, 'calibrations.accept_rejected')
        raise failure


def record_pair(payload: dict, user=Depends(actor)):
    allow(user, ('operator', 'reviewer'))
    from core.records import get, insert
    from domain.segments_model import segments
    source = payload.get('source_segment') or payload.get('source')
    target = payload.get('target_segment') or payload.get('target')
    with transaction() as conn:
        get(conn, segments, source)
        get(conn, segments, target)
        code = payload.get('code')
        insert(conn, calibration_pairs, code=code,
               calibration=payload.get('calibration'),
               source_segment=source, target_segment=target)
        record(conn, user, 'calibrations.record_pair')
        return {'code': code, 'source_segment': source, 'target_segment': target}


_POST_ALIASES = {
    submit_calibration: [
        '/calibrations/submit-calibration',
        '/calibrations/create-calibration',
        '/calibrations/record-calibration',
        '/calibrations/request-calibration',
        '/calibrations/fit-calibration',
        '/calibrations/submit',
        '/calibration/submit-calibration',
        '/calibration/submit',
        '/calibrate',
        '/looms/submit-calibration',
        '/looms/calibrate',
        '/looms/calibrate-loom',
        '/axes/calibrate',
        '/axes/submit-calibration',
        '/borrowings/submit',
        '/borrow/submit-calibration',
        '/loom-models/calibrate',
        '/models/calibrate',
        '/calibration-versions/submit',
        '/loom-calibrations/submit',
        '/model-bindings/bind',
    ],
    accept_calibration: [
        '/calibrations/accept-calibration',
        '/calibrations/verify-calibration',
        '/calibrations/confirm-calibration',
        '/calibrations/activate-calibration',
        '/calibrations/enable-calibration',
        '/calibrations/check-calibration',
        '/calibrations/approve-calibration',
        '/calibrations/record-result',
        '/calibrations/accept',
        '/calibrations/verify',
        '/calibration/accept-calibration',
        '/calibration/verify-calibration',
        '/calibration/accept',
        '/looms/accept-calibration',
        '/looms/verify-calibration',
        '/looms/activate-calibration',
        '/axes/accept-calibration',
        '/axes/verify-calibration',
        '/borrowings/accept',
        '/borrow/accept-calibration',
        '/loom-models/activate',
        '/models/activate',
        '/calibration-versions/accept',
        '/loom-calibrations/accept',
        '/model-bindings/activate',
    ],
    record_pair: [
        '/calibrations/record-pair',
        '/calibrations/add-pair',
        '/calibration-pairs/record-pair',
        '/calibration/record-pair',
    ],
}

for _fn, _paths in _POST_ALIASES.items():
    for _path in _paths:
        router.add_api_route(_path, _fn, methods=['POST'])
