from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage

from .llm import LLMProvider
from .models import (
    AgentResult,
    AgentStatus,
    OrchestratorPlan,
    ParentState,
    SpecialistConfig,
    ValidationOutput,
)
from .progress import _current_node_progress
from . import tools

logger = logging.getLogger(__name__)


SPECIALIST_CONFIGS2: List[SpecialistConfig] = [
    SpecialistConfig(
        name="financial",
        task_key="financial_tasks",
        result_key="financial_result",
        system_prompt=(
            "You are a quantitative financial analyst. Complete EVERY assigned task. "
            "If any tool returns a [TOOL ERROR] message, note it clearly in your summary "
            "with the label '⚠️ Task incomplete:' and describe what could not be retrieved. "
            "Complete all other tasks normally."
        ),
        tool_names=["get_company_data", "funding_news_search", "job_postings_analyzer"] #, "web_traffic_estimator", "revenue_estimator"
    )
]





SPECIALIST_CONFIGS: List[SpecialistConfig] = [
    SpecialistConfig(
        name="web",
        task_key="web_tasks",
        result_key="web_result",
        system_prompt=(
            "You are a web research specialist. Complete EVERY assigned task. "
            "If any tool returns a [TOOL ERROR] message, note it clearly in your summary "
            "with the label '⚠️ Task incomplete:' and describe what could not be retrieved. "
            "Complete all other tasks normally."
        ),
        tool_names=["web_search", "scrape_url"],
    ),
    SpecialistConfig(
        name="domain",
        task_key="domain_tasks",
        result_key="domain_result",
        system_prompt=(
            "You are a domain knowledge specialist. Complete EVERY assigned task. "
            "If any tool returns a [TOOL ERROR] message, note it clearly in your summary "
            "with the label '⚠️ Task incomplete:' and describe what could not be retrieved. "
            "Complete all other tasks normally."
        ),
        tool_names=["knowledge_base_lookup", "get_expert_report"],
    ),
    SpecialistConfig(
        name="financial",
        task_key="financial_tasks",
        result_key="financial_result",
        system_prompt=(
            "You are a quantitative financial analyst. Complete EVERY assigned task. "
            "If any tool returns a [TOOL ERROR] message, note it clearly in your summary "
            "with the label '⚠️ Task incomplete:' and describe what could not be retrieved. "
            "Complete all other tasks normally."
        ),
        tool_names=["get_company_data", "funding_news_search", "job_postings_analyzer"],
    ),
    SpecialistConfig(
        name="legal",
        task_key="legal_tasks",
        result_key="legal_result",
        system_prompt=(
            "You are a legal research specialist. Complete EVERY assigned task. "
            "If any tool returns a [TOOL ERROR] message, note it clearly in your summary "
            "with the label '⚠️ Task incomplete:' and describe what could not be retrieved. "
            "Complete all other tasks normally."
        ),
        tool_names=["search_case_law", "lookup_statute", "compliance_check"],
    ),
]


class SpecialistAgent:
    def __init__(self, config: SpecialistConfig, llm: LLMProvider, tools: List[Callable[..., str]]) -> None:
        self.config = config
        self.llm = llm
        self.tools = tools

    def execute(self, state: ParentState) -> AgentResult:
        tasks = state.get(self.config.task_key, [])
        logger.info("Agent execution start: %s | tasks=%s", self.config.name, tasks)
        if not tasks:
            logger.info("Agent skipped: %s | no tasks assigned", self.config.name)
            return AgentResult(
                result_key=self.config.result_key,
                result="",
                status=AgentStatus.PENDING,
                failure=None,
            )

        prompt = self._build_prompt(state["query"], tasks)
        logger.debug("Agent prompt for %s: %s", self.config.name, prompt)
        return self._safe_invoke(prompt)

    def _build_prompt(self, query: str, tasks: List[str]) -> str:
        formatted_tasks = "\n".join(f"  {idx + 1}. {task}" for idx, task in enumerate(tasks))
        return (
            f"Original query: {query}\n\n"
            f"Your assigned tasks — complete ALL of them:\n"
            f"{formatted_tasks}\n\n"
            f"Use your tools for each. Label every result clearly."
        )

    def _safe_invoke(self, prompt: str) -> AgentResult:
        node_progress = _current_node_progress()
        try:
            logger.info("Agent %s invoking LLM", self.config.name)
            if node_progress is not None:
                node_progress.mark_llm_request()

            agent = create_agent(model=self.llm.model, tools=self.tools, system_prompt=self.config.system_prompt)
            output = agent.invoke({"messages": [HumanMessage(content=prompt)]})
            result_text = output["messages"][-1].content
            logger.info("Agent %s completed LLM invoke | output_length=%s", self.config.name, len(result_text))

            if node_progress is not None:
                node_progress.llm_response_received()

            if "⚠️ Task incomplete" in result_text or "[TOOL ERROR]" in result_text:
                logger.warning("Agent %s returned partial result due to tool issues", self.config.name)
                return AgentResult(
                    result_key=self.config.result_key,
                    result=result_text,
                    status=AgentStatus.PARTIAL,
                    failure=(
                        f"{self.config.name} — partial results: some tasks could not be completed "
                        f"(tool errors noted in output)"
                    ),
                )

            return AgentResult(
                result_key=self.config.result_key,
                result=result_text,
                status=AgentStatus.SUCCESS,
                failure=None,
            )
        except TimeoutError as exc:
            return self._failure_result(f"{self.config.name} — timed out ({exc})", AgentStatus.FAILED)
        except ConnectionError as exc:
            return self._failure_result(f"{self.config.name} — connection failed ({exc})", AgentStatus.FAILED)
        except Exception as exc:
            logger.exception("Agent %s crashed", self.config.name)
            return self._failure_result(
                f"{self.config.name} — unexpected error: {type(exc).__name__}: {str(exc)[:100]}",
                AgentStatus.FAILED,
            )

    def _failure_result(self, message: str, status: AgentStatus) -> AgentResult:
        return AgentResult(
            result_key=self.config.result_key,
            result="",
            status=status,
            failure=message,
        )


class SpecialistAgentFactory:
    @staticmethod
    def build(config: SpecialistConfig, llm: LLMProvider) -> SpecialistAgent:
        tools_list = [getattr(tools, tool_name) for tool_name in config.tool_names]
        return SpecialistAgent(config=config, llm=llm, tools=tools_list)


class Orchestrator:
    SYSTEM_PROMPT = """You are the planning orchestrator in a multi-agent research system.
Decompose the user query into specific, actionable task lists for up to four specialist agents:
  1. web_tasks  — current web information, news, public data
  2. domain_tasks         — internal knowledge base, expert-curated content
  3. financial_tasks      — market data, earnings, financial models
  4. legal_tasks          — case law, statutes, compliance checks

Rules: tasks must be concrete (not \"research X\" but \"find Q3 revenue for X\").
Leave a list empty if that domain is irrelevant. Aim for 2-5 tasks per agent.
CRITICAL INSTRUCTIONS:
You are an orchestrator breaking down a query. You MUST output valid JSON.
You are strictly FORBIDDEN from making up your own JSON keys. 
You must categorize tasks ONLY into the following exact keys:
- "reasoning"
- "web_tasks"
- "domain_tasks"
- "financial_tasks"
- "legal_tasks"

If there are no tasks for a category, return an empty array [].
Do not use names like "Web retrieval" or "Legal Assessment". Use the exact keys above.
"""

    def __init__(self, llm: LLMProvider, specialist_configs: List[SpecialistConfig]) -> None:
        self.llm = llm
        self.specialist_configs = specialist_configs

    def plan(self, query: str) -> dict[str, Any]:
        from .progress import CURRENT_NODE_PROGRESS, NodeProgress

        node_progress = NodeProgress("orchestrator")
        token = CURRENT_NODE_PROGRESS.set(node_progress)
        try:
            node_progress.start()
            logger.info("Orchestrator planning start for query: %s", query)
            node_progress.mark_llm_request()

            plan = self.llm.invoke_structured(
                [
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": query},
                ],
                OrchestratorPlan,
            )

            node_progress.llm_response_received()
            node_progress.complete()
        finally:
            CURRENT_NODE_PROGRESS.reset(token)

        statuses = {config.name: AgentStatus.PENDING for config in self.specialist_configs}
        self._log_plan(plan, statuses)
        logger.info(
            "Orchestrator plan complete | web=%s domain=%s financial=%s legal=%s",
            len(plan.web_tasks),
            len(plan.domain_tasks),
            len(plan.financial_tasks),
            len(plan.legal_tasks),
        )

        return {
            "orchestrator_plan": plan.reasoning,
            "web_tasks": plan.web_tasks,
            "domain_tasks": plan.domain_tasks,
            "financial_tasks": plan.financial_tasks,
            "legal_tasks": plan.legal_tasks,
            "agent_statuses": statuses,
            "agent_failures": [],
        }

    @staticmethod
    def _log_plan(plan: OrchestratorPlan, statuses: Dict[str, AgentStatus]) -> None:
        for config_name, status in statuses.items():
            tasks = getattr(plan, f"{config_name}_tasks")
            if tasks:
                logger.info("%s tasks (%s): %s", config_name.capitalize(), len(tasks), tasks)
            else:
                logger.info("%s: skipped (no tasks assigned)", config_name.capitalize())


class DevilAdvocate:
    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    def critique(self, state: ParentState) -> dict[str, str]:
        logger.info(
            "Devil's Advocate start | agent_statuses=%s | agent_failures=%s",
            state.get("agent_statuses", {}),
            state.get("agent_failures", []),
        )
        availability = self._build_availability_report(state)
        findings = self._assemble_findings(state)

        prompt = f"""ORIGINAL QUERY: {state['query']}

{availability}

SPECIALIST FINDINGS (only from agents that ran successfully or partially):
{findings}

Your critique MUST:
1. Explicitly address each FAILED or PARTIAL agent — what conclusions are impossible
   to draw confidently due to missing data?
2. Identify contradictions or gaps between the agents that DID respond
3. Challenge unsupported assumptions in the available findings
4. Flag where the missing data would have materially changed the analysis

Be specific. \"Legal data unavailable\" is not a critique — explain WHAT legal risk
cannot be assessed and WHY that matters for this query."""

        response = self.llm.invoke(
            [
                {"role": "system", "content": "You are the Devil's Advocate in a multi-expert pipeline."},
                {"role": "user", "content": prompt},
            ]
        )
        logger.info("Devil's Advocate complete | critique_length=%s", len(response.content))
        return {"devils_critique": response.content}

    def _build_availability_report(self, state: ParentState) -> str:
        failures = state.get("agent_failures", [])
        statuses = state.get("agent_statuses", {})

        lines = ["DATA AVAILABILITY:"]
        for key in ["web", "domain", "financial", "legal"]:
            status = statuses.get(key, AgentStatus.PENDING)
            if status == AgentStatus.PENDING:
                lines.append(f"  {key.capitalize():<12} ⏭️  skipped — not needed for this query")
            elif status == AgentStatus.SUCCESS:
                lines.append(f"  {key.capitalize():<12} ✅  complete")
            elif status == AgentStatus.PARTIAL:
                lines.append(f"  {key.capitalize():<12} ⚠️   partial — some tasks failed (see result for details)")
            elif status == AgentStatus.FAILED:
                lines.append(f"  {key.capitalize():<12} ❌  unavailable — data entirely missing")

        if failures:
            lines.append("\nFAILURE DETAILS:")
            for failure in failures:
                lines.append(f"  • {failure}")

        return "\n".join(lines)

    @staticmethod
    def _assemble_findings(state: ParentState) -> str:
        sections: List[str] = []
        for label, result_key in [
            ("Web Research", "web_result"),
            ("Domain Knowledge", "domain_result"),
            ("Financial", "financial_result"),
            ("Legal", "legal_result"),
        ]:
            value = state.get(result_key)
            if value:
                sections.append(f"── {label} ──\n{value}")

        return "\n\n".join(sections) if sections else "No findings available."


class Validator:
    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    def _build_availability_report(self, state: ParentState) -> str:
        failures = state.get("agent_failures", [])
        statuses = state.get("agent_statuses", {})

        lines = ["DATA AVAILABILITY:"]
        for key in ["web", "domain", "financial", "legal"]:
            status = statuses.get(key, AgentStatus.PENDING)
            if status == AgentStatus.PENDING:
                lines.append(f"  {key.capitalize():<12} ⏭️  skipped — not needed for this query")
            elif status == AgentStatus.SUCCESS:
                lines.append(f"  {key.capitalize():<12} ✅  complete")
            elif status == AgentStatus.PARTIAL:
                lines.append(f"  {key.capitalize():<12} ⚠️   partial — some tasks failed (see result for details)")
            elif status == AgentStatus.FAILED:
                lines.append(f"  {key.capitalize():<12} ❌  unavailable — data entirely missing")

        if failures:
            lines.append("\nFAILURE DETAILS:")
            for failure in failures:
                lines.append(f"  • {failure}")

        return "\n".join(lines)

    def validate(self, state: ParentState) -> dict[str, Any]:
        logger.info("Validator start | agent_statuses=%s | agent_failures=%s", state.get("agent_statuses", {}), state.get("agent_failures", []))
        availability = self._build_availability_report(state)
        failures = state.get("agent_failures", [])

        sections: List[str] = []
        for label, key in [
            ("Web", "web_result"),
            ("Domain", "domain_result"),
            ("Financial", "financial_result"),
            ("Legal", "legal_result"),
        ]:
            value = state.get(key)
            if value:
                sections.append(f"{label}: {value}")

        Sysytem_prompt="""CRITICAL JSON FORMATTING RULES:
1. You must output ONLY valid JSON. Do not include markdown code blocks (like ```json).
2. You must NEVER use unescaped double quotes inside your string values. 
3. If you need to quote a word inside a string, you must use single quotes (e.g., 'No') or properly escape them (e.g., \"No\").
"""
        prompt = f"""ORIGINAL QUERY: {state['query']}

{availability}

AVAILABLE RESEARCH:
{chr(10).join(sections) or 'None'}

DEVIL'S ADVOCATE CRITIQUE:
{state.get('devils_critique', 'N/A')}

Synthesize the final answer. For any failed or missing agent:
  - State clearly what is unknown: \"Legal risk assessment unavailable — {failures}\"
  - Adjust recommendations to acknowledge the gap
  - Set confidence to 'low' if a critical domain is missing for this query type
CRITICAL JSON INSTRUCTIONS:
You MUST output a completely flat JSON object. 
You are strictly FORBIDDEN from wrapping your response in nested keys like "synthesis", "output", or "result".
You must use exactly and ONLY these top-level keys:
- "final_answer"
- "confidence"
- "data_gaps"
- "is_valid"
"""

        result = self.llm.invoke_structured(
            [
                {"role": "system", "content": "You are the final synthesis and validation node.your Job is to validate all the data coming to you."+ Sysytem_prompt},
                {"role": "user", "content": prompt},
            ],
            ValidationOutput,
        )

        icon = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(result.confidence, "⚪")
        logger.info("Validator complete — confidence=%s | valid=%s | final_answer_length=%s", result.confidence, result.is_valid, len(result.final_answer))
        if result.data_gaps:
            for gap in result.data_gaps:
                logger.info("Data gap: %s", gap)

        return {
            "validated_answer": result.final_answer,
            "is_valid": result.is_valid,
            "confidence": result.confidence,
        }
