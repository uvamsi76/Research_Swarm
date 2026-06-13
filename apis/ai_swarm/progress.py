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
    def __init__(self, node: str, expected_tool_steps: int = 0) -> None:
        self.node = node
        self.expected_tool_steps = max(expected_tool_steps, 0)
        self.tools_executed = 0
        self.progress = 0
        self.tool_increment = 60.0 / self.expected_tool_steps if self.expected_tool_steps else 0.0

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

    def complete(self) -> None:
        self._emit(100, "completed")
