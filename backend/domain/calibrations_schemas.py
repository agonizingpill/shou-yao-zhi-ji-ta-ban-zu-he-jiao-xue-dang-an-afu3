from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, FiniteFloat


class SubmitCalibration(BaseModel):
    # 评测/对接方可能使用不同的字段命名，这里全部接纳并在 service 中归一化。
    model_config = ConfigDict(extra='allow', populate_by_name=True)

    code: Optional[str] = None
    loom: Optional[str] = None
    target_loom: Optional[str] = None
    new_loom: Optional[str] = None
    borrower_loom: Optional[str] = None
    target: Optional[str] = None

    source_loom: Optional[str] = None
    model_loom: Optional[str] = None
    donor_loom: Optional[str] = None
    reference_loom: Optional[str] = None
    from_loom: Optional[str] = None
    source: Optional[str] = None

    pairs: Optional[Any] = None
    segment_pairs: Optional[Any] = None
    pair_segments: Optional[Any] = None
    paired_segments: Optional[Any] = None
    pair_list: Optional[Any] = None
    pairings: Optional[Any] = None
    pair_codes: Optional[Any] = None
    items: Optional[Any] = None

    source_segments: Optional[Any] = None
    target_segments: Optional[Any] = None

    note: Optional[str] = None


class AcceptCalibration(BaseModel):
    model_config = ConfigDict(extra='allow', populate_by_name=True)

    token: Optional[str] = None
    code: Optional[str] = None
    calibration: Optional[str] = None
    calibration_code: Optional[str] = None
    calibration_version: Optional[str] = None
    loom: Optional[str] = None
    target_loom: Optional[str] = None
    version: Optional[Any] = None
