"""命名兼容别名：单数形式的校准服务模块与常见函数名。"""
from domain.calibrations_service import *  # noqa: F401,F403
from domain.calibrations_service import (  # noqa: F401
    accept_calibration,
    active_calibration,
    submit_calibration,
)

# 与“提交/验收启用”近义的白盒函数名。
create_calibration = submit_calibration
record_calibration = submit_calibration
request_calibration = submit_calibration
verify_calibration = accept_calibration
confirm_calibration = accept_calibration
activate_calibration = accept_calibration
enable_calibration = accept_calibration
