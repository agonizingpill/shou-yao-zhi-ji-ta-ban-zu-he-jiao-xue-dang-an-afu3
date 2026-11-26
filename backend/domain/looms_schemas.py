from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, FiniteFloat, StringConstraints

class SignMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")
    loom: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    mapping_note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]


class RecordLoom(BaseModel):
    model_config = ConfigDict(extra='allow', populate_by_name=True)
    code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
    machine: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    pedal_count: int = 4
    mapping_signed: bool = False
