from sqlalchemy import (Boolean, CheckConstraint, Column, Float, ForeignKey,
                        Integer, JSON, String, Table, UniqueConstraint)

from core.db import metadata


# 一架新织架可以按方向借用另一架织架的判别模型；
# 每份校准都是一个有版次的换算+模型组合，验收通过后原子启用。
calibrations = Table('calibrations', metadata,
    Column('code', String(64), primary_key=True),
    Column('loom', String(160), ForeignKey('looms.code'), nullable=False, index=True),
    Column('source_loom', String(160), ForeignKey('looms.code'), nullable=False),
    # 同一借用方向（目标织架）内单调递增的提交版次，用于晚到写入的围栏判断。
    Column('version', Integer, nullable=False),
    Column('revision', Integer, nullable=False),
    Column('token', String(64), unique=True),
    Column('state', String(32), nullable=False, default='待验收'),
    Column('active', Boolean, nullable=False, default=False),
    # 目标织架读数 -> 来源织架模型坐标的乘法换算系数。
    Column('right_factor', Float),
    Column('left_factor', Float),
    Column('pause_factor', Float),
    Column('accuracy', Float),
    Column('accuracies', JSON),
    Column('pair_count', Integer),
    Column('report', JSON),
    UniqueConstraint('loom', 'version', name='uq_calibrations_loom_version'),
    CheckConstraint('version >= 1'),
)


# 成对动作的留痕：同一组踏板动作在来源织架与借用织架上各录一条。
calibration_pairs = Table('calibration_pairs', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('code', String(64), unique=True),
    Column('calibration', String(64), ForeignKey('calibrations.code'), index=True),
    Column('source_segment', String(64), ForeignKey('segments.code'), nullable=False),
    Column('target_segment', String(64), ForeignKey('segments.code'), nullable=False),
)
