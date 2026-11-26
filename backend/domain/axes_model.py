from sqlalchemy import Boolean, CheckConstraint, Column, Float, ForeignKey, Integer, JSON, String, Table

from core.db import metadata


axes = Table('axes', metadata,
    Column('code', String(64), primary_key=True),
    Column('segment', String(160), ForeignKey('segments.code'), nullable=False),
    Column('suggestion', String(160), nullable=False),
    Column('confidence', Float, nullable=False),
    Column('holdout', Float, nullable=False),
    Column('token', String(64), nullable=False, unique=True),
    # 借用模型与校准版次的来源留痕；同台织架原流程下 calibration 为空。
    Column('model_loom', String(160)),
    Column('source_loom', String(160)),
    Column('borrowed_from', String(160)),
    Column('calibration', String(64)),
    Column('calibration_code', String(64)),
    Column('calibration_version', String(64)),
    Column('calibration_id', String(64)),
    Column('calibration_revision', Integer),
    Column('transform', JSON),
    CheckConstraint('holdout between 0 and 1'),
    CheckConstraint('confidence between 0 and 1'),
)
