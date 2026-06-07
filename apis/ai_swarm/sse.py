from __future__ import annotations

import json
import logging
import queue
from typing import Any, Callable, Dict, Optional

from fastapi.responses import StreamingResponse

from .progress import LATEST_NODE_PROGRESS

logger = logging.getLogger(__name__)


def _format_sse(event_type: str, payload: dict[str, Any]) -> str:
    return f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"


def _build_stage_event(node: str, updates: dict[str, Any]) -> dict[str, Any]:
    progress = LATEST_NODE_PROGRESS.get(node)
    progress_source = "runtime" if progress is not None else "static"

    if progress is None:
        stage_progress = {
            "orchestrator": 10,
            "web_agent": 30,
            "domain_agent": 50,
            "financial_agent": 70,
            "legal_agent": 90,
            "devils_advocate": 95,
            "validator": 100,
        }
        progress = stage_progress.get(node, None)

    return {
        "stage": node,
        "progress": progress,
        "progress_source": progress_source,
        "updates": updates,
        "agent_statuses": updates.get("agent_statuses", {}),
    }


def _make_sse_queue_sink(queue_ref: queue.Queue[dict[str, Any]]) -> Callable[[dict[str, Any]], None]:
    tool_counts = {"total": 0, "success": 0, "failure": 0}

    def sink(payload: dict[str, Any]) -> None:
        if payload.get("event") == "tool":
            tool_counts["total"] += 1
            status = payload.get("data", {}).get("status")
            if status == "success":
                tool_counts["success"] += 1
            elif status == "failure":
                tool_counts["failure"] += 1

            payload = {
                "event": "tool",
                "data": {
                    **payload.get("data", {}),
                    "tool_counts": tool_counts.copy(),
                },
            }

        queue_ref.put(payload)

    return sink
