from typing import Any, Annotated, Optional

from pydantic import BaseModel, ConfigDict, FiniteFloat, StringConstraints

Code = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]


class FitAxes(BaseModel):
    # 允许携带显式借用来源/校准版次；缺省时若该织架有启用校准则自动借用。
    model_config = ConfigDict(extra='allow', populate_by_name=True)
    segment: Code
    source_loom: Optional[str] = None
    model_loom: Optional[str] = None
    donor_loom: Optional[str] = None
    calibration: Optional[str] = None
    calibration_code: Optional[str] = None
    calibration_version: Optional[str] = None
    local: Optional[Any] = None


class RecordAxis(BaseModel):
    model_config = ConfigDict(extra='allow', populate_by_name=True)
    token: str
    code: Optional[str] = None
    axis: Optional[str] = None
