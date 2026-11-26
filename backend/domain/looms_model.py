from sqlalchemy import Boolean, CheckConstraint, Column, Float, ForeignKey, Integer, JSON, String, Table

from core.db import metadata


looms = Table('looms', metadata,
    Column('code', String(64), primary_key=True),
    Column('machine', String(160), nullable=False),
    Column('pedal_count', Integer, nullable=False),
    Column('mapping_signed', Boolean, nullable=False),
    # 同一织架校准提交的单调序号（原子自增，保证并发提交版次不重号）。
    Column('calibration_seq', Integer),
    # 当前启用的“模型来源 + 换算”组合（calibrations.code），与校准行在同一事务切换。
    Column('active_calibration', String(64)),
    CheckConstraint('pedal_count between 2 and 12'),
)
