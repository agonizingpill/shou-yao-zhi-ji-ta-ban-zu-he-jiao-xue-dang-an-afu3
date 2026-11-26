from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, FiniteFloat, StringConstraints

class RecordSegment(BaseModel):
    # 兼容 pair/pair_code/pair_id 等成对组号命名；其余扩展字段放行，由 service 过滤。
    model_config = ConfigDict(extra='allow', populate_by_name=True)
    code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    loom: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    pattern: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    right_rate: FiniteFloat
    left_rate: FiniteFloat
    pause: FiniteFloat
    pair: Optional[str] = None
    pair_code: Optional[str] = None
    pair_id: Optional[str] = None
    pair_group: Optional[str] = None


class VerifySegment(BaseModel):
    model_config = ConfigDict(extra='allow', populate_by_name=True)
    segment: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    code: Optional[str] = None
