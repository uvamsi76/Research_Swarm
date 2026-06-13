from __future__ import annotations

import logging
from contextvars import ContextVar
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

SSE_EVENT_SINK: ContextVar[Optional[Callable[[dict[str, Any]], None]]] = ContextVar("SSE_EVENT_SINK", default=None)
CURRENT_NODE_PROGRESS: ContextVar[Optional["NodeProgress"]] = ContextVar("CURRENT_NODE_PROGRESS", default=None)
LATEST_NODE_PROGRESS: Dict[str, int] = {}


def _emit_sse_event(event_payload: dict[str, Any]) -> None:
    sink = SSE_EVENT_SINK.get()
    if sink is not None:
        try:
            sink(event_payload)
        except Exception:
            logger.exception("Failed to emit SSE event")


def _current_node_progress() -> Optional["NodeProgress"]:
    return CURRENT_NODE_PROGRESS.get()


class NodeProgress:
    MAX_TOOL_CALLS_PER_TOOL = 3  # Maximum calls per individual tool
    MAX_TOTAL_TOOL_CALLS = 15    # Maximum total tool calls per agent
    
    def __init__(self, node: str, expected_tool_steps: int = 0) -> None:
        self.node = node
        self.expected_tool_steps = max(expected_tool_steps, 0)
        self.tools_executed = 0
        self.progress = 0
        self.tool_increment = 60.0 / self.expected_tool_steps if self.expected_tool_steps else 0.0
        self.tool_call_counts: Dict[str, int] = {}  # Track calls per tool
        self.tool_limit_exceeded = False

    def _emit(self, progress: int, detail: Optional[str] = None) -> None:
        self.progress = max(self.progress, min(100, progress))

        try:
            LATEST_NODE_PROGRESS[self.node] = int(self.progress)
        except Exception:
            pass

        logger.debug(
            "Progress update: node=%s progress=%s detail=%s tools_executed=%s expected_tool_steps=%s",
            self.node,
            self.progress,
            detail,
            self.tools_executed,
            self.expected_tool_steps,
        )

        _emit_sse_event(
            {
                "event": "progress",
                "data": {
                    "node": self.node,
                    "progress": self.progress,
                    "detail": detail,
                    "tools_executed": self.tools_executed,
                    "expected_tool_steps": self.expected_tool_steps,
                },
            }
        )

    def start(self) -> None:
        self._emit(0, "starting")

    def mark_llm_request(self) -> None:
        self._emit(10, "sent llm request")

    def tool_called(self, tool_name: str) -> None:
        self.tools_executed += 1
        if self.tool_increment:
            target = min(75, int(self.progress + self.tool_increment))
        else:
            target = min(75, self.progress + 10)
        self._emit(target, f"tool executed: {tool_name}")

    def llm_response_received(self) -> None:
        self._emit(max(self.progress, 75), "llm response received")
    
    def mark_partial(self) -> None:
        """Mark the agent as having partial/incomplete results."""
        self._emit(75, "partial - some tasks incomplete")

    def complete(self) -> None:
        self._emit(100, "completed")

    def check_tool_limit(self, tool_name: str) -> tuple[bool, Optional[str]]:
        """
        Check if tool can be called. Returns (can_call, error_message).
        
        Enforces:
        - Max 3 calls per individual tool
        - Max 15 total tool calls per agent
        """
        # Check total tool call limit
        total_calls = sum(self.tool_call_counts.values())
        if total_calls >= self.MAX_TOTAL_TOOL_CALLS:
            msg = (
                f"[TOOL LIMIT EXCEEDED] Agent has reached maximum tool calls ({self.MAX_TOTAL_TOOL_CALLS}). "
                f"Please wrap up your response with the findings you have collected so far."
            )
            logger.warning("Tool limit exceeded for node=%s | total_calls=%s | tool=%s", 
                          self.node, total_calls, tool_name)
            self.tool_limit_exceeded = True
            return False, msg

        # Check per-tool limit
        tool_count = self.tool_call_counts.get(tool_name, 0)
        if tool_count >= self.MAX_TOOL_CALLS_PER_TOOL:
            msg = (
                f"[TOOL LIMIT EXCEEDED] Tool '{tool_name}' has been called {tool_count} times "
                f"(max: {self.MAX_TOOL_CALLS_PER_TOOL}). Please use a different tool or wrap up."
            )
            logger.warning("Per-tool limit exceeded for node=%s | tool=%s | count=%s", 
                          self.node, tool_name, tool_count)
            return False, msg

        return True, None

    def increment_tool_call(self, tool_name: str) -> None:
        """Track a tool call."""
        self.tool_call_counts[tool_name] = self.tool_call_counts.get(tool_name, 0) + 1
        total_calls = sum(self.tool_call_counts.values())
        logger.info(
            "Tool call tracked | node=%s | tool=%s | tool_count=%s | total_calls=%s/%s",
            self.node,
            tool_name,
            self.tool_call_counts[tool_name],
            total_calls,
            self.MAX_TOTAL_TOOL_CALLS,
        )
