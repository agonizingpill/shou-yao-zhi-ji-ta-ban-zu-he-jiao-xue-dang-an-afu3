"""极简向前迁移：metadata.create_all 不会给旧表补列，这里只补可空列。"""
import logging

from sqlalchemy import inspect, text

from core import db

log = logging.getLogger('uvicorn.error')

# 表名 -> {列名: 列 DDL 类型片段}
_ADDED_COLUMNS = {
    'axes': {
        'model_loom': 'VARCHAR(160)',
        'source_loom': 'VARCHAR(160)',
        'borrowed_from': 'VARCHAR(160)',
        'calibration': 'VARCHAR(64)',
        'calibration_code': 'VARCHAR(64)',
        'calibration_version': 'VARCHAR(64)',
        'calibration_id': 'VARCHAR(64)',
        'calibration_revision': 'INTEGER',
        'transform': 'JSON',
    },
    'segments': {
        'pair': 'VARCHAR(64)',
        'pair_code': 'VARCHAR(64)',
    },
    'looms': {
        'calibration_seq': 'INTEGER',
        'active_calibration': 'VARCHAR(64)',
    },
}


def upgrade():
    engine = db.engine
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, columns in _ADDED_COLUMNS.items():
            if table not in existing_tables:
                continue  # 新库由 create_all 直接建出全列
            present = {col['name'] for col in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name in present:
                    continue
                try:
                    conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {ddl}'))
                    log.info('migrate: added %s.%s', table, name)
                except Exception:
                    log.exception('migrate: failed adding %s.%s', table, name)
                    raise
