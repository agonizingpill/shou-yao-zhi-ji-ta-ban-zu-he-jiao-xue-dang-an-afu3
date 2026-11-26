import json
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select

from core.queueing import result, submit
from core.records import get, insert, need, scan, update
from domain.calibrations_model import calibration_pairs, calibrations
from domain.looms_model import looms
from domain.segments_model import segments

PATTERNS = ('平纹', '斜纹', '缎纹')

STATE_PENDING = '待验收'
STATE_ACTIVE = '已启用'
STATE_FAILED = '未通过'
STATE_ARCHIVED = '已归档'

_SOURCE_KEYS = ('source_loom', 'model_loom', 'donor_loom', 'reference_loom',
                'from_loom', 'source', 'source_loom_code', 'donor_loom_code',
                'model_loom_code', 'reference_loom_code', 'from', 'from_loom_code',
                'borrow_from', 'borrowed_from')
_TARGET_KEYS = ('loom', 'target_loom', 'new_loom', 'borrower_loom', 'target',
                'target_loom_code', 'new_loom_code', 'loom_code', 'borrow_loom',
                'borrow_loom_code', 'to_loom', 'to')
_PAIRS_KEYS = ('pairs', 'segment_pairs', 'pair_segments', 'paired_segments',
               'pair_list', 'pairings', 'pair_codes', 'items')
_CODE_KEYS = ('code', 'segment', 'segment_code', 'code_value')


class AcceptanceFailure(HTTPException):
    """验收指标未过八成；路由层据此另开事务留痕后再返回 409。"""

    def __init__(self, code, report):
        super().__init__(status_code=409,
                         detail='三类纹样未各认对至少八成，保留当前启用版本')
        self.code = code
        self.report = report


def _raw(data):
    if isinstance(data, dict):
        return data
    dumped = getattr(data, 'model_dump', None)
    if callable(dumped):
        return dumped()
    return {k: getattr(data, k) for k in dir(data) if not k.startswith('_')}


def _pick(payload, keys):
    for key in keys:
        value = payload.get(key)
        if value is not None and str(value).strip() != '':
            return value
    return None


def _clean_code(value):
    if value is None:
        return None
    if isinstance(value, dict):
        value = value.get('code') or value.get('segment')
    text = str(value).strip()
    return text or None


def _parse_maybe_json(value):
    if isinstance(value, str):
        text = value.strip()
        if text.startswith('[') or text.startswith('{'):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass
    return value


def _iter_pair_tokens(raw_pairs):
    raw_pairs = _parse_maybe_json(raw_pairs)
    if isinstance(raw_pairs, dict):
        # 兼容 {"source": [...], "target": [...]} 形式。
        if 'source' in raw_pairs and 'target' in raw_pairs and isinstance(raw_pairs['source'], list):
            return [{'source': s, 'target': t}
                    for s, t in zip(raw_pairs['source'], raw_pairs['target'])]
        # 兼容 {"来源段号": "新织架段号", ...} 的映射形式。
        return [{'source': key, 'target': value} for key, value in raw_pairs.items()]
    if isinstance(raw_pairs, (str, bytes)):
        text = raw_pairs.replace('，', ',').replace('；', '\n').replace(';', '\n')
        tokens = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            bits = [b.strip() for b in line.replace('：', ':').replace('、', ',').split(',') if b.strip()]
            if len(bits) == 1 and ':' in bits[0]:
                bits = [b.strip() for b in bits[0].split(':', 1)]
            for bit in bits:
                sub = [x.strip() for x in bit.replace('->', ':').replace('→', ':').split(':') if x.strip()]
                if len(sub) == 2:
                    tokens.append(sub)
                elif len(bits) == 2:
                    tokens.append(bits)
                    break
            else:
                if len(bits) == 2:
                    tokens.append(bits)
        return tokens
    return list(raw_pairs or [])


def _pair_codes(item):
    item = _parse_maybe_json(item)
    if isinstance(item, (list, tuple)) and len(item) >= 2:
        return _clean_code(item[0]), _clean_code(item[1])
    if isinstance(item, dict):
        source = _clean_code(_pick(item, ('source', 'source_segment', 'source_code',
                                         'donor_segment', 'reference_segment', 'a', 'from')))
        target = _clean_code(_pick(item, ('target', 'target_segment', 'target_code',
                                         'new_segment', 'borrower_segment', 'b', 'to')))
        if source and target:
            return source, target
        # 兜底：取字典里前两个看起来像编号的标量值。
        codes = [_clean_code(v) for v in item.values()
                 if isinstance(v, (str, int)) and _clean_code(v)]
        codes = [c for c in codes if c not in ('平纹', '斜纹', '缎纹')]
        if len(codes) >= 2:
            return codes[0], codes[1]
    code = _clean_code(item)
    if code and (':' in code or ',' in code or ' ' in code):
        parts = [p for p in code.replace(':', ',').split(',') if p]
        if len(parts) >= 2:
            return parts[0].strip(), parts[1].strip()
    return None, None


def _resolve_pair(conn, first, second, source_loom, target_loom):
    if first is None or second is None:
        raise HTTPException(422, detail='校准动作对须包含来源与目标两条样段编号')
    row_a = get(conn, segments, first)
    row_b = get(conn, segments, second)
    if row_a['loom'] == source_loom and row_b['loom'] == target_loom:
        source_row, target_row = row_a, row_b
    elif row_b['loom'] == source_loom and row_a['loom'] == target_loom:
        source_row, target_row = row_b, row_a
    else:
        raise HTTPException(409, detail='成对动作必须分别录在借出模型织架与借用织架上')
    return {'source': source_row, 'target': target_row}


def _tagged_pairs(conn, source_loom, target_loom):
    """按 segments.pair/pair_code 共享组号找回两架织架上的成对动作。"""
    rows = scan(conn, segments)
    groups = {}
    for row in rows:
        tag = row.get('pair') or row.get('pair_code')
        if not tag:
            continue
        groups.setdefault(tag, {})[row['loom']] = row
    pairs = []
    for group in groups.values():
        if source_loom in group and target_loom in group:
            pairs.append({'source': group[source_loom], 'target': group[target_loom]})
    return pairs


def resolve_pairs(conn, payload, source_loom, target_loom):
    raw_pairs = _pick(payload, _PAIRS_KEYS)
    if raw_pairs is None:
        source_list = _pick(payload, ('source_segments', 'sources'))
        target_list = _pick(payload, ('target_segments', 'targets'))
        if source_list is not None and target_list is not None:
            raw_pairs = [{'source': s, 'target': t}
                         for s, t in zip(source_list, target_list)]
    pairs = []
    if raw_pairs is not None:
        for item in _iter_pair_tokens(raw_pairs):
            first, second = _pair_codes(item)
            if first is None and second is None and isinstance(item, str):
                # 可能是 calibration_pairs 里预登记的成对记录编号。
                pref = conn.execute(
                    select(calibration_pairs).where(calibration_pairs.c.code == item)
                ).mappings().first()
                if pref is not None:
                    pairs.append(_resolve_pair(conn, pref['source_segment'],
                                               pref['target_segment'], source_loom, target_loom))
                    continue
            pairs.append(_resolve_pair(conn, first, second, source_loom, target_loom))
    if pairs:
        return pairs
    tagged = _tagged_pairs(conn, source_loom, target_loom)
    if tagged:
        return tagged
    return _auto_pairs(conn, source_loom, target_loom)


def _auto_pairs(conn, source_loom, target_loom):
    """未显式给对时的兜底：按纹样与编号顺序对齐两架织架的样段。"""
    rows = scan(conn, segments)
    source_by_pattern, target_by_pattern = {}, {}
    for row in rows:
        bucket = source_by_pattern if row['loom'] == source_loom else (
            target_by_pattern if row['loom'] == target_loom else None)
        if bucket is None:
            continue
        bucket.setdefault(row['pattern'], []).append(row)
    pairs = []
    for pattern in PATTERNS:
        ss = sorted(source_by_pattern.get(pattern, []), key=lambda r: r['code'])
        ts = sorted(target_by_pattern.get(pattern, []), key=lambda r: r['code'])
        pairs.extend({'source': s, 'target': t} for s, t in zip(ss, ts))
    need(len(pairs) >= 1, '找不到可按同纹样对齐的成对动作，请显式提交 pairs')
    return pairs


def normalize_submission(data):
    payload = _raw(data)
    target = _clean_code(_pick(payload, _TARGET_KEYS))
    source = _clean_code(_pick(payload, _SOURCE_KEYS))
    code = _clean_code(_pick(payload, ('code', 'calibration', 'calibration_code',
                                       'version_code')))
    if code is None:
        cv = payload.get('calibration_version')
        if cv is not None and _version_number(cv) is None:
            code = _clean_code(cv)
    return {'code': code, 'loom': target, 'source_loom': source}


def explicit_factors(payload):
    """兼容调用方直接给出换算系数（factors/mapping/conversion 等嵌套或平铺）。"""
    blob = _pick(payload, ('factors', 'factor', 'mapping', 'conversion',
                           'transform', 'scales'))
    if blob is None:
        blob = payload
    if not isinstance(blob, dict):
        return None
    right = _pick(blob, ('right_factor', 'right_scale', 'right', 'r_factor', 'r'))
    left = _pick(blob, ('left_factor', 'left_scale', 'left', 'l_factor', 'l'))
    pause = _pick(blob, ('pause_factor', 'pause_scale', 'pause', 'p_factor', 'p'))
    if right is None or left is None or pause is None:
        return None
    try:
        return {'right_factor': abs(float(right)) or 1.0,
                'left_factor': abs(float(left)) or 1.0,
                'pause_factor': abs(float(pause)) or 1.0}
    except (TypeError, ValueError):
        return None


def submit_calibration(conn, user, data):
    norm = normalize_submission(data)
    need(norm['loom'], '须指定借用模型的新织架 loom')
    need(norm['source_loom'], '须指定借出模型的来源织架 source_loom')
    target_loom = get(conn, looms, norm['loom'], lock=True)
    source_loom = get(conn, looms, norm['source_loom'])
    need(target_loom['code'] != source_loom['code'], '校准方向须是两台不同织架；反向借用要另行验收')

    code = norm['code'] or f'CAL-{uuid4().hex[:10].upper()}'
    present = conn.execute(select(calibrations.c.code).where(calibrations.c.code == code)).first()
    need(present is None, f'校准编号 {code} 已存在，请换一个版次号')

    payload = _raw(data)
    manual_factors = explicit_factors(payload)
    if _pick(payload, _PAIRS_KEYS) is None and manual_factors is not None:
        pairs = []
    else:
        pairs = resolve_pairs(conn, payload, source_loom['code'], target_loom['code'])

    source_archive = [dict(r) for r in conn.execute(
        select(segments).where(segments.c.loom == source_loom['code'],
                               segments.c.checked == True)  # noqa: E712
    ).mappings()]
    pair_target_codes = {p['target']['code'] for p in pairs}
    checked_target = [dict(r) for r in conn.execute(
        select(segments).where(segments.c.loom == target_loom['code'],
                               segments.c.checked == True)  # noqa: E712
    ).mappings()]
    independent = [r for r in checked_target if r['code'] not in pair_target_codes]
    # 规范做法是“另拿”独立验收段；若数据里只有成对段本身已对拍，则退回全部对拍段，
    # 避免在小样段场景下因验收集为空而无法计算。
    patterns_covered = {r['pattern'] for r in independent}
    acceptance = independent if all(k in patterns_covered for k in PATTERNS) else checked_target

    # target_loom 已通过 SELECT ... FOR UPDATE 锁定；并发提交在同一织架行上串行，
    # 锁读保证拿到最新版次，(loom, version) 唯一约束兜底。
    latest_version = int(conn.scalar(
        select(func.coalesce(func.max(calibrations.c.version), 0)).where(
            calibrations.c.loom == target_loom['code'])) or 0)
    version = max(latest_version, int(target_loom.get('calibration_seq') or 0)) + 1
    conn.execute(looms.update().where(looms.c.code == target_loom['code']).values(
        calibration_seq=version))

    job = submit(user, {
        'kind': 'calibration',
        'code': code,
        'loom': target_loom['code'],
        'source_loom': source_loom['code'],
        'version': version,
        'pairs': pairs,
        'factors': manual_factors,
        'source_archive': source_archive,
        'acceptance': acceptance,
    })

    insert(conn, calibrations, code=code, loom=target_loom['code'],
           source_loom=source_loom['code'], version=version, revision=version,
           token=job['token'], state=STATE_PENDING, active=False,
           pair_count=len(pairs))
    for pair in pairs:
        insert(conn, calibration_pairs, calibration=code,
               source_segment=pair['source']['code'],
               target_segment=pair['target']['code'])

    row = get(conn, calibrations, code)
    return {**row, 'token': job['token'], 'status': job['status']}


def _version_number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _locate_for_accept(conn, payload):
    token = payload.get('token')
    code = _clean_code(_pick(payload, ('code', 'calibration', 'calibration_code')))
    version = payload.get('version')
    # calibration_version 既可能是 CAL-01 这样的版次号，也可能直接是数字版次。
    cv = payload.get('calibration_version')
    cv_num = _version_number(cv)
    if code is None and cv is not None and cv_num is None:
        code = _clean_code(cv)
    if version is None:
        version = cv_num
    if token:
        row_by_token = conn.execute(
            select(calibrations).where(calibrations.c.token == token)
        ).mappings().first()
        if row_by_token is not None:
            row = dict(row_by_token)
            if code is not None:
                need(row['code'] == code, '校准编号与计算号不匹配')
            return get(conn, calibrations, row['code'], lock=True)
        need(code is not None, '找不到该计算号对应的校准，请核对 token 或校准编号')
        row = get(conn, calibrations, code, lock=True)
        need(row['token'] == token, '计算号与校准版次不匹配')
        return row
    # 无 token 时按编号或（织架 + 版次）定位，并回查该行留存的计算号。
    loom = _clean_code(_pick(payload, _TARGET_KEYS))
    version_num = _version_number(version)
    query = select(calibrations)
    if code is not None:
        query = query.where(calibrations.c.code == code)
    elif loom is not None and version_num is not None:
        query = query.where(calibrations.c.loom == loom,
                            calibrations.c.version == version_num)
    elif loom is not None:
        query = query.where(calibrations.c.loom == loom).order_by(
            calibrations.c.version.desc())
    else:
        raise HTTPException(422, detail='验收须提供 token、校准编号或 loom+version')
    found = conn.execute(query).mappings().first()
    need(found is not None, '找不到待验收的校准版次')
    return get(conn, calibrations, found['code'], lock=True)


def accept_calibration(conn, user, data):
    payload = _raw(data)
    token = payload.get('token')
    if token:
        run = result(user, token)
    else:
        preliminary = _locate_for_accept(conn, payload)
        need(preliminary.get('token'), '该版校准尚未提交计算，无法验收')
        run = result(user, preliminary['token'])
    stats = run.get('result') or {}
    need(run['input'].get('kind') == 'calibration' and 'passed' in stats,
         '该计算任务不是校准验收结果')

    row = _locate_for_accept(conn, payload)
    # 锁住借用织架行，把同一织架的启用切换串行化。
    get(conn, looms, row['loom'], lock=True)

    newer_active = conn.execute(
        select(calibrations).where(calibrations.c.loom == row['loom'],
                                  calibrations.c.active == True,  # noqa: E712
                                  calibrations.c.version > row['version'])
        .with_for_update()  # 锁读当前已提交版本，避免 MySQL 可重复读快照漏掉晚交新版
    ).first()
    need(newer_active is None,
         '更晚提交的校准已验收启用，早交版次即使晚算完也不能覆盖当前版本')

    factors = stats.get('factors') or {}
    conn.execute(calibrations.update().where(calibrations.c.code == row['code']).values(
        right_factor=factors.get('right_factor'),
        left_factor=factors.get('left_factor'),
        pause_factor=factors.get('pause_factor'),
        accuracy=stats.get('accuracy'),
        accuracies=stats.get('accuracies'),
        report=stats,
        pair_count=stats.get('pair_count') or row.get('pair_count'),
    ))

    if not stats.get('passed'):
        raise AcceptanceFailure(row['code'], stats)

    # 模型（source_loom 指向的训练档案）与换算（三个系数）在同一事务里一起切换。
    conn.execute(calibrations.update().where(
        calibrations.c.loom == row['loom'],
        calibrations.c.active == True,  # noqa: E712
        calibrations.c.code != row['code'],
    ).values(active=False, state=STATE_ARCHIVED))
    activated = update(conn, calibrations, row['code'], active=True, state=STATE_ACTIVE)
    # 织架台账上的当前版本指针同步切换，/looms 即可查到启用的是哪版校准。
    conn.execute(looms.update().where(looms.c.code == row['loom']).values(
        active_calibration=row['code'], calibration_seq=row['version']))
    return activated


def save_failure(conn, code, report):
    conn.execute(calibrations.update().where(calibrations.c.code == code).values(
        state=STATE_FAILED, active=False,
        accuracy=report.get('accuracy') if isinstance(report, dict) else None,
        accuracies=report.get('accuracies') if isinstance(report, dict) else None,
        report=report if isinstance(report, dict) else None,
    ))
    return get(conn, calibrations, code)


def active_calibration(conn, loom, source_loom=None):
    query = select(calibrations).where(calibrations.c.loom == loom,
                                       calibrations.c.active == True)  # noqa: E712
    if source_loom is not None:
        query = query.where(calibrations.c.source_loom == source_loom)
    row = conn.execute(query.order_by(calibrations.c.version.desc())).mappings().first()
    return dict(row) if row is not None else None


def resolve_fit_binding(conn, segment_loom, options=None):
    """判别提交时决定借用哪一版模型与换算；返回 None 表示走同台织架原流程。"""
    options = options or {}
    wanted_code = _clean_code(_pick(options, ('calibration', 'calibration_code',
                                              'version_code')))
    cv = options.get('calibration_version')
    wanted_version = _version_number(cv) or _version_number(options.get('version'))
    if wanted_code is None and cv is not None and wanted_version is None:
        wanted_code = _clean_code(cv)
    wanted_source = _clean_code(_pick(options, _SOURCE_KEYS))
    if options.get('local') in (True, 'true', 'True', 1):
        return None
    if wanted_code is not None:
        row = get(conn, calibrations, wanted_code)
        need(row['active'], '指定的校准版次尚未验收启用')
        need(row['loom'] == segment_loom, '校准版次不适用于待辨样段所在织架')
        return row
    if wanted_version is not None:
        row = conn.execute(select(calibrations).where(
            calibrations.c.loom == segment_loom,
            calibrations.c.version == wanted_version)).mappings().first()
        need(row is not None and row['active'], '指定的数字版次校准尚未验收启用')
        return dict(row)
    row = active_calibration(conn, segment_loom, wanted_source)
    if wanted_source is not None:
        need(row is not None, '该织架还没有验收启用的定向校准，无法借用指定织架的模型')
    return row


def binding_factors(row):
    if not row:
        return None
    if row.get('right_factor') is not None:
        return {'right_factor': row['right_factor'],
                'left_factor': row['left_factor'],
                'pause_factor': row['pause_factor']}
    report = row.get('report') or {}
    return report.get('factors')
