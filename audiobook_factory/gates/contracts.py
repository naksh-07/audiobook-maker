#!/usr/bin/env python3
"""
Audiobook Factory - Quality Gate Contracts & Data Models.
Defines GateAuditError and AuditResult with dict-like compatibility.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict, model_validator


class GateAuditError(Exception):
    """Raised when an independent verification gate fails validation."""
    pass


class AuditResult(BaseModel):
    """
    Standardized Audit Result Contract for Quality Gates (Gates 0 - 6).
    Supports dictionary item access, serialization, and explicit failure lists.
    """
    model_config = ConfigDict(extra="ignore")

    gate: str = ""
    gate_name: Optional[str] = None
    status: str = "PASS"
    passed: bool = True
    details: Dict[str, Any] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _sync_before(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "passed" in data and "status" not in data:
                data["status"] = "PASS" if data["passed"] else "FAIL"
            elif "status" in data and "passed" not in data:
                data["passed"] = (data["status"] == "PASS")
            if "gate_name" in data and not data.get("gate"):
                data["gate"] = data["gate_name"]
            elif "gate" in data and not data.get("gate_name"):
                data["gate_name"] = data["gate"]
        return data

    @model_validator(mode="after")
    def _sync_after(self) -> AuditResult:
        if not self.passed and self.status == "PASS":
            self.status = "FAIL"
        elif self.status != "PASS" and self.passed:
            self.passed = False
        if not self.gate and self.gate_name:
            self.gate = self.gate_name
        elif not self.gate_name and self.gate:
            self.gate_name = self.gate
        return self

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()
