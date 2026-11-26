from uuid import uuid4

from sqlalchemy import select

from core.queueing import submit, result
from core.records import get, insert, need, scan, update
from domain import calibrations_service
from domain.axes_model import axes
from domain.calibrations_learning import transform_row
from domain.looms_model import looms
from domain.segments_model import segments
from domain.lesson_demos_model import lesson_demos


def _options(data):
    dumped = getattr(data, 'model_dump', None)
    return dumped() if callable(dumped) else dict(getattr(data, '__dict__', {}))


def fit_axes(conn, user, data):
    segment = get(conn, segments, data.segment)
    need(segment['checked'], '待辨样段未经对拍')

    binding = calibrations_service.resolve_fit_binding(conn, segment['loom'], _options(data))

    if binding is not None:
        source_loom = binding['source_loom']
        archive = [x for x in scan(conn, segments) if x['loom'] == source_loom and x['checked']]
        need(all(sum(x['pattern'] == kind for x in archive) >= 4
                 for kind in ('平纹', '斜纹', '缎纹')),
             '借出模型的织架三类已对拍参考样段不足')
        factors = calibrations_service.binding_factors(binding) or {
            'right_factor': 1.0, 'left_factor': 1.0, 'pause_factor': 1.0}
        query = transform_row(segment, factors)
        provenance = {
            'borrowed': True,
            'model_loom': source_loom,
            'source_loom': source_loom,
            'borrowed_from': source_loom,
            'calibration': binding['code'],
            'calibration_code': binding['code'],
            'calibration_version': binding['code'],
            'calibration_id': binding['code'],
            'calibration_revision': binding.get('version') or binding.get('revision'),
            'transform': factors,
        }
        # target 保留原始快照以通过签注时的一致性比对；query 是换算后的判别输入。
        return submit(user, {'target': segment, 'query': query, 'archive': archive,
                             'provenance': provenance})

    archive = [x for x in scan(conn, segments) if x['loom'] == segment['loom']
               and x['checked'] and x['code'] != data.segment]
    need(all(sum(x['pattern'] == kind for x in archive) >= 4 for kind in ('平纹','斜纹','缎纹')),
         '同台织架的三类参考样段不足；样段不足时可先验收启用外台织架校准以借用模型')
    provenance = {
        'borrowed': False,
        'model_loom': segment['loom'],
        'source_loom': segment['loom'],
        'borrowed_from': None,
        'calibration': None,
        'calibration_code': None,
        'calibration_version': None,
        'calibration_id': None,
        'calibration_revision': None,
        'transform': None,
    }
    return submit(user, {'target':segment,'archive':archive,'provenance':provenance})


def record_axis(conn, user, data):
    run = result(user, data.token)
    target = run['input']['target']
    stats = run['result']
    need(get(conn, segments, target['code']) == target, '样段快照已变化')
    need(stats['holdout_accuracy'] >= .66 and stats['confidence'] >= .55, '判别置信度不足，保留原示范')

    provenance = run.get('provenance') or run['input'].get('provenance') or {}
    code = getattr(data, 'code', None) or getattr(data, 'axis', None) or f'AXIS-{uuid4().hex[:10].upper()}'
    if not isinstance(code, str):
        code = f'AXIS-{uuid4().hex[:10].upper()}'
    return insert(conn, axes, code=code, segment=target['code'], suggestion=stats['label'],
                  confidence=stats['confidence'], holdout=stats['holdout_accuracy'], token=data.token,
                  model_loom=provenance.get('model_loom'),
                  source_loom=provenance.get('source_loom'),
                  borrowed_from=provenance.get('borrowed_from'),
                  calibration=provenance.get('calibration'),
                  calibration_code=provenance.get('calibration_code'),
                  calibration_version=provenance.get('calibration_version'),
                  calibration_id=provenance.get('calibration_id'),
                  calibration_revision=provenance.get('calibration_revision'),
                  transform=provenance.get('transform'))
