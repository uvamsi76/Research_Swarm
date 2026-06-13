from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from .agents import DevilAdvocate, Orchestrator, SpecialistAgentFactory, SPECIALIST_CONFIGS, Validator
from .models import ParentState
from .progress import CURRENT_NODE_PROGRESS, NodeProgress

logger = logging.getLogger(__name__)


class MultiAgentPipeline:
    def __init__(self, llm_provider: Any) -> None:
        self.llm_provider = llm_provider
        self.orchestrator = Orchestrator(llm_provider, SPECIALIST_CONFIGS)
        self.specialists = [SpecialistAgentFactory.build(config, llm_provider) for config in SPECIALIST_CONFIGS]
        self.devil = DevilAdvocate(llm_provider)
        self.validator = Validator(llm_provider)

    def build_graph(self) -> Any:
        builder = StateGraph(ParentState)

        builder.add_node("orchestrator", self.run_orchestrator)
        for specialist in self.specialists:
            builder.add_node(f"{specialist.config.name}_agent", self._make_specialist_node(specialist))
        builder.add_node("devils_advocate", self.run_devils_advocate)
        builder.add_node("validator", self.run_validator)

        builder.add_edge(START, "orchestrator")
        builder.add_conditional_edges("orchestrator", self.fan_out)

        for specialist in self.specialists:
            builder.add_edge(f"{specialist.config.name}_agent", "devils_advocate")

        builder.add_edge("devils_advocate", "validator")
        builder.add_edge("validator", END)
        return builder.compile()

    def run_orchestrator(self, state: ParentState) -> dict[str, Any]:
        logger.info("Orchestrator node invoked")
        return self.orchestrator.plan(state["query"])

    def _make_specialist_node(self, specialist: Any) -> Callable[[ParentState], dict[str, Any]]:
        def node(state: ParentState) -> dict[str, Any]:
            node_name = f"{specialist.config.name}_agent"
            logger.info(
                "Specialist node starting: %s | tasks=%s",
                node_name,
                len(state.get(specialist.config.task_key, [])),
            )
            node_progress = NodeProgress(node_name, expected_tool_steps=len(specialist.tools))
            token = CURRENT_NODE_PROGRESS.set(node_progress)
            try:
                node_progress.start()
                result = specialist.execute(state)
                node_progress.complete()
            finally:
                CURRENT_NODE_PROGRESS.reset(token)

            logger.info(
                "Specialist node completed: %s | status=%s | failure=%s",
                node_name,
                result.status.value,
                result.failure,
            )

            self._log_agent(
                specialist.config.name,
                result.status,
                len(state.get(specialist.config.task_key, [])),
                result.failure,
            )
            logger.info(
                "State leaving specialist node: %s | status=%s | failure=%s",
                specialist.config.name,
                result.status.value,
                result.failure,
            )
            return result.to_state_update(state.get("agent_statuses", {}))

        return node

    def fan_out(self, state: ParentState) -> List[Send]:
        sends: List[Send] = []
        for specialist in self.specialists:
            if state.get(specialist.config.task_key):
                sends.append(Send(f"{specialist.config.name}_agent", state))
        if sends:
            send_names = [
                getattr(send, "target", None)
                or getattr(send, "node", None)
                or getattr(send, "name", None)
                or repr(send)
                for send in sends
            ]
            logger.info("Fan-out dispatching to agents: %s", send_names)
        else:
            logger.info("Fan-out skipped specialists: no tasks assigned, sending directly to Devil's Advocate")
        return sends or [Send("devils_advocate", state)]

    def run_devils_advocate(self, state: ParentState) -> dict[str, str]:
        return self.devil.critique(state)

    def run_validator(self, state: ParentState) -> dict[str, Any]:
        return self.validator.validate(state)

    @staticmethod
    def _log_agent(name: str, status: Any, n_tasks: int, failure: Optional[str]) -> None:
        icon = {"success": "✅", "partial": "⚠️ ", "failed": "❌"}.get(status.value, "?")
        logger.info("%s agent — %s (%s)", name.capitalize(), status.value, n_tasks)
        if failure:
            logger.info("   %s", failure)


class PipelineService:
    def __init__(self, llm_provider: Any) -> None:
        self.pipeline = MultiAgentPipeline(llm_provider)
        self.graph = self.pipeline.build_graph()

    def run_query(self, query: str) -> ParentState:
        logger.info("Pipeline run started for query: %s", query)
        initial_state = self._make_initial_state(query)

        final_state = self.graph.invoke(initial_state)
        logger.info(
            "Pipeline run complete for query: %s | final_statuses=%s | is_valid=%s | confidence=%s",
            query,
            final_state.get("agent_statuses", {}),
            final_state.get("is_valid", False),
            final_state.get("confidence", "low"),
        )
        return final_state

    @staticmethod
    def _make_initial_state(query: str) -> ParentState:
        return {
            "query": query,
            "orchestrator_plan": "",
            "web_tasks": [],
            "domain_tasks": [],
            "financial_tasks": [],
            "legal_tasks": [],
            "web_result": "",
            "domain_result": "",
            "financial_result": "",
            "legal_result": "",
            "agent_failures": [],
            "agent_statuses": {},
            "devils_critique": "",
            "validated_answer": "",
            "confidence": "low",
            "is_valid": False,
        }
