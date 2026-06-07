from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class ToolRequest(BaseModel):
    args: List[Any] = Field(default_factory=list)
    kwargs: Dict[str, Any] = Field(default_factory=dict)


class ToolResponse(BaseModel):
    output: str
