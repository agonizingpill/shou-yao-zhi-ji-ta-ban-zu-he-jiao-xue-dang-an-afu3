from sqlalchemy import Boolean, CheckConstraint, Column, Float, ForeignKey, Integer, JSON, String, Table

from core.db import metadata


segments = Table('segments', metadata,
    Column('code', String(64), primary_key=True),
    Column('loom', String(160), ForeignKey('looms.code'), nullable=False),
    Column('pattern', String(160), nullable=False),
    Column('right_rate', Float, nullable=False),
    Column('left_rate', Float, nullable=False),
    Column('pause', Float, nullable=False),
    Column('checked', Boolean, nullable=False),
    # 成对动作的共享组号（同一 pair/pair_code 在两架织架上各有一条）。
    Column('pair', String(64)),
    Column('pair_code', String(64)),
    CheckConstraint('right_rate >= 0'),
    CheckConstraint('left_rate >= 0'),
    CheckConstraint('pause >= 0'),
)
