from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, JsonValue


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Record(Model):
    resource_type: str
    record_id: str
    fields: dict[str, JsonValue]
    version: int = Field(ge=1)


class Permission(Model):
    id: str
    sentence: str
    resource_type: str
    record_id: str
    set_fields: dict[str, JsonValue]
    preserve_fields: dict[str, JsonValue]
    forbidden_operations: list[str]
    version: int = Field(ge=1)


class Proposal(Model):
    permission_id: str | None = None
    resource_type: str
    record_id: str
    operation: str = "update"
    fields: dict[str, JsonValue]
    version: int = Field(ge=1)
    channel: Literal["click", "enter", "http"] = "http"
    origin: Literal["manual", "agent", "fault_injection"] = "manual"


class Decision(Model):
    verdict: Literal["allow", "reject", "pause"]
    code: str
    reason: str
