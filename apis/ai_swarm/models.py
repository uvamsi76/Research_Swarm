from __future__ import annotations

import operator
from enum import Enum
from typing import Any, Annotated, Dict, List, Optional, TypedDict

from pydantic import BaseModel, Field


class AgentStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class ParentState(TypedDict):
    query: str

    orchestrator_plan: str
    web_tasks: List[str]
    domain_tasks: List[str]
    financial_tasks: List[str]
    legal_tasks: List[str]

    web_result: str
    domain_result: str
    financial_result: str
    legal_result: str

    agent_failures: Annotated[List[str], operator.add]
    agent_statuses: Annotated[Dict[str, AgentStatus], operator.or_]

    devils_critique: str
    validated_answer: str
    confidence: str
    is_valid: bool


class OrchestratorPlan(BaseModel):
    reasoning: Optional[str] = Field(default=None,description="How you decomposed this query.")
    web_tasks: List[str] = Field(default_factory=list)
    domain_tasks: List[str] = Field(default_factory=list)
    financial_tasks: List[str] = Field(default_factory=list)
    legal_tasks: List[str] = Field(default_factory=list)

class ValidationOutput(BaseModel):
    final_answer: str = Field(
        description=(
            "The synthesized answer. Where data was unavailable, state the gap "
            "explicitly: 'Legal assessment unavailable — recommend consulting counsel.'"
        )
    )
    confidence: str = Field(
        description=(
            "Reflects data completeness: high = all relevant agents succeeded; "
            "medium = minor gaps or partial failures; "
            "low = one or more critical agents failed"
        )
    )
    data_gaps: List[str] = Field(
        description="Explicit list of information that could not be retrieved and why it matters.",
        default_factory=list,
    )
    is_valid: bool = Field(
        description=(
            "False if a critical agent failed and the answer cannot be trusted without it. "
            "True if partial gaps are acceptable for this query."
        )
    )


class SpecialistConfig(BaseModel):
    name: str
    task_key: str
    result_key: str
    system_prompt: str
    tool_names: List[str]


class AgentResult(BaseModel):
    result_key: str
    result: str
    status: AgentStatus
    failure: Optional[str]

    def to_state_update(self, current_statuses: Dict[str, AgentStatus]) -> dict[str, Any]:
        return {
            self.result_key: self.result,
            "agent_failures": [self.failure] if self.failure else [],
            "agent_statuses": {**current_statuses, self.result_key.replace("_result", ""): self.status},
        }


class QueryRequest(BaseModel):
    query: str = Field(..., description="A natural language research query for the multi-agent pipeline.")


class QueryResponse(BaseModel):
    query: str
    orchestrator_plan: str
    validated_answer: str
    is_valid: bool
    confidence: str
    agent_statuses: Dict[str, str]
    agent_failures: List[str]
    devils_critique: Optional[str] = None
