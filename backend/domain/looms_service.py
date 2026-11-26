from sqlalchemy import select

from core.queueing import submit, result
from core.records import get, insert, need, scan, update
from domain.looms_model import looms
from domain.segments_model import segments
from domain.axes_model import axes
from domain.lesson_demos_model import lesson_demos


def sign_mapping(conn, user, data):
    row = get(conn, looms, data.loom, lock=True)
    need(len(data.mapping_note) >= 7 and '双签' in data.mapping_note, '脚位图尚缺两位技师凭据')
    return update(conn, looms, row['code'], mapping_signed=True)


def record_loom(conn, user, data):
    exists = conn.execute(select(looms.c.code).where(looms.c.code == data.code)).first()
    need(exists is None, f'织架编号 {data.code} 已存在')
    need(2 <= data.pedal_count <= 12, '踏板数须在 2 到 12 之间')
    return insert(conn, looms, code=data.code, machine=data.machine,
                  pedal_count=data.pedal_count, mapping_signed=bool(data.mapping_signed))
