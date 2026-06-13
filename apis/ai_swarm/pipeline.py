from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional
import time

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from .agents import DevilAdvocate, Orchestrator, SpecialistAgentFactory, SPECIALIST_CONFIGS, Validator
from .models import ParentState, AgentStatus
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
        # Collector node: all specialists edge here to ensure synchronization
        # Multiple edges → single node → LangGraph waits for all sources before invoking
        builder.add_node("specialists_collector", self.collect_specialist_results)
        # Join node that verifies all specialists completed
        builder.add_node("specialists_done", self.wait_for_specialists)
        builder.add_node("devils_advocate", self.run_devils_advocate)
        builder.add_node("validator", self.run_validator)

        builder.add_edge(START, "orchestrator")
        builder.add_conditional_edges("orchestrator", self.fan_out)

        # All specialists edge to collector node - this is the synchronization point
        # LangGraph waits for all specialist edges before invoking the collector
        for specialist in self.specialists:
            builder.add_edge(f"{specialist.config.name}_agent", "specialists_collector")

        # Collector → join node → devils_advocate
        builder.add_edge("specialists_collector", "specialists_done")
        builder.add_edge("specialists_done", "devils_advocate")

        builder.add_edge("devils_advocate", "validator")
        builder.add_edge("validator", END)
        return builder.compile()

    def run_orchestrator(self, state: ParentState) -> dict[str, Any]:
        logger.info("Orchestrator node invoked")
        return self.orchestrator.plan(state["query"])

    def _make_specialist_node(self, specialist: Any) -> Callable[[ParentState], dict[str, Any]]:
        def node(state: ParentState) -> dict[str, Any]:
            node_name = f"{specialist.config.name}_agent"
            num_tasks = len(state.get(specialist.config.task_key, []))
            current_statuses = state.get("agent_statuses", {})
            
            logger.info(
                "Specialist node starting: %s | tasks=%s | available_tools=%s",
                node_name,
                num_tasks,
                len(specialist.tools),
            )
            
            # Handle empty task case - skip processing but still complete successfully
            if not num_tasks:
                logger.info("Specialist %s has no tasks | returning SUCCESS", specialist.config.name)
                state_update = {
                    f"{specialist.config.name}_result": "",
                    "agent_failures": [],
                    "agent_statuses": {specialist.config.name: AgentStatus.SUCCESS},
                }
                logger.info(
                    "Specialist %s state update (no tasks): %s",
                    specialist.config.name,
                    state_update.get("agent_statuses", {}),
                )
                return state_update
            
            # Process specialist with tasks
            # Estimate expected tool calls: approximately 1-2 tools per task
            estimated_tool_calls = max(1, num_tasks * 2)
            node_progress = NodeProgress(node_name, expected_tool_steps=estimated_tool_calls)
            token = CURRENT_NODE_PROGRESS.set(node_progress)
            try:
                node_progress.start()
                result = specialist.execute(state)
                
                # Mark progress based on result status
                if result.status.value == "success":
                    node_progress.complete()
                    logger.info("Specialist %s marked complete | status=SUCCESS", specialist.config.name)
                elif result.status.value == "partial":
                    node_progress.mark_partial()
                    logger.warning("Specialist %s marked partial | status=PARTIAL", specialist.config.name)
                else:  # failed
                    node_progress.mark_partial()
                    logger.error("Specialist %s marked partial due to failure | status=FAILED", specialist.config.name)
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
                num_tasks,
                result.failure,
            )
            
            # Build state update - only this specialist's status, not all
            state_update = result.to_state_update(current_statuses)
            logger.info(
                "Specialist node state update: %s | status=%s",
                specialist.config.name,
                state_update.get("agent_statuses", {}).get(specialist.config.name),
            )
            
            return state_update

        return node

    def fan_out(self, state: ParentState) -> List[Send]:
        """Dispatch work to ALL specialists to ensure join node is reached.
        
        Dispatches to all specialists regardless of task count.
        Specialists with tasks will process them; those without will no-op.
        All specialists edge to the join node, guaranteeing it runs.
        """
        sends: List[Send] = []
        
        # Always dispatch to all specialists
        for specialist in self.specialists:
            sends.append(Send(f"{specialist.config.name}_agent", state))
        
        dispatch_names = [f"{s.config.name}_agent" for s in self.specialists]
        logger.info("Fan-out dispatching to all specialists: %s", dispatch_names)
        
        return sends

    def run_devils_advocate(self, state: ParentState) -> dict[str, str]:
        return self.devil.critique(state)

    def collect_specialist_results(self, state: ParentState) -> dict[str, Any]:
        """Collector node: synchronization point that waits for all specialists.
        
        In LangGraph, when multiple nodes have edges to a single node, that node 
        is invoked only once with all updates merged. This collector acts as the 
        synchronization point - all specialists edge here, ensuring they all 
        complete before proceeding to the join node.
        """
        statuses = state.get("agent_statuses", {})
        logger.info(
            "Collector: all specialists reported | statuses=%s",
            statuses,
        )
        
        # Just pass through the merged state from all specialists
        return {
            "agent_statuses": statuses,
            "agent_failures": state.get("agent_failures", []),
        }

    def wait_for_specialists(self, state: ParentState) -> dict[str, Any]:
        """Join node: final verification before proceeding to critique/validation.
        
        By the time this node runs, all specialists have completed and their updates
        have been merged by the collector node. This node just verifies and logs.
        """
        statuses = state.get("agent_statuses", {})
        failures = state.get("agent_failures", [])
        
        logger.info(
            "Join node: all specialists complete | verified statuses=%s | failures=%s",
            statuses,
            failures,
        )
        
        # Log summary
        for name in ["web", "domain", "financial", "legal"]:
            status = statuses.get(name, "not_dispatched")
            if status != "not_dispatched":
                logger.info("  ✓ %s: %s", name, status.value if hasattr(status, 'value') else status)
        
        # Pass through to downstream nodes
        return {
            "agent_statuses": statuses,
            "agent_failures": failures,
        }

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
