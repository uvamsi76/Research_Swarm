from __future__ import annotations

import io
import logging
import queue
import threading
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .config import build_llm_provider_from_env
from .models import QueryRequest, QueryResponse, ParentState
from .pipeline import PipelineService
from .pdf_report import build_report_pdf
from .sse import _build_stage_event, _format_sse, _make_sse_queue_sink
from .progress import SSE_EVENT_SINK

logger = logging.getLogger(__name__)
app = FastAPI(title="LangGraph Pipeline Service", version="0.1.0")

# Allow cross-origin requests from the frontend (development convenience)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

llm_provider = build_llm_provider_from_env()
pipeline_service = PipelineService(llm_provider)

REPORT_CACHE: Dict[str, bytes] = {}
REPORT_CACHE_LOCK = threading.Lock()

AGENT_ID_MAP: dict[str, str] = {
    "orchestrator": "orchestrator",
    "web_agent": "web",
    "domain_agent": "domain",
    "financial_agent": "financial",
    "legal_agent": "legal",
    "devils_advocate": "devil",
    "validator": "validator",
}


def _build_agent_event(stage_data: dict[str, Any]) -> dict[str, Any]:
    node = stage_data.get("stage", "")
    agent_id = AGENT_ID_MAP.get(node, node)
    progress = int(stage_data.get("progress", 0) or 0)
    state = "done" if progress >= 100 else "active"
    updates = stage_data.get("updates", {}) or {}
    task = updates.get("task") or updates.get("detail") or updates.get("message") or f"{agent_id} in progress"

    return {
        "id": agent_id,
        "state": state,
        "task": task,
        "progress": progress,
    }


def _normalize_sse_event(item: dict[str, Any]) -> Optional[dict[str, Any]]:
    event_type = item.get("event")
    payload = item.get("data", {})

    if event_type == "stage":
        return {"event": "agent", "data": _build_agent_event(payload)}

    if event_type == "progress":
        stage_data = {
            "stage": payload.get("node", ""),
            "progress": payload.get("progress", 0),
            "updates": {"task": payload.get("detail")},
        }
        return {"event": "agent", "data": _build_agent_event(stage_data)}

    if event_type == "tool":
        # Keep tool events if useful, but they are usually supplementary.
        return item

    if event_type in {"status", "complete", "error", "finding", "metric", "topic", "confidence", "agent", "report"}:
        return item

    return None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "LangGraph Pipeline Service"}


def _stream_pipeline_response(query: str) -> StreamingResponse:
    if not query:
        raise HTTPException(status_code=400, detail="Query parameter is required for SSE streaming.")

    def event_generator():
        event_queue: queue.Queue[Optional[dict[str, Any]]] = queue.Queue()
        sink = _make_sse_queue_sink(event_queue)

        def worker() -> None:
            token = SSE_EVENT_SINK.set(sink)
            final_state: Optional[ParentState] = None
            try:
                event_queue.put({"event": "status", "data": {"status": "started", "query": query}})
                try:
                    initial_state = pipeline_service._make_initial_state(query)
                    for mode, payload in pipeline_service.graph.stream(
                        initial_state,
                        stream_mode=["updates", "values"],
                    ):
                        if mode == "updates":
                            node = next(iter(payload))
                            updates = payload[node]
                            event_queue.put({"event": "stage", "data": _build_stage_event(node, updates)})
                        elif mode == "values":
                            final_state = payload
                    if final_state is not None:
                        event_queue.put({"event": "status", "data": {"status": "done"}})
                        event_queue.put({"event": "agent", "data": {"id": "synthesis", "state": "active", "task": "Rendering final report PDF…", "progress": 80}})
                        event_queue.put({"event": "report", "data": {"status": "started", "query": query}})
                        try:
                            pdf_buffer = build_report_pdf(final_state)
                            pdf_bytes = pdf_buffer.getvalue()
                            with REPORT_CACHE_LOCK:
                                REPORT_CACHE[query] = pdf_bytes
                            event_queue.put({"event": "report", "data": {"status": "ready", "query": query}})
                            event_queue.put({"event": "agent", "data": {"id": "synthesis", "state": "done", "task": "Report ready — full PDF generated", "progress": 100}})
                        except Exception as exc:
                            logger.exception("PDF report generation failed")
                            event_queue.put({"event": "error", "data": {"message": f"PDF generation failed: {exc}"}})
                        event_queue.put({
                            "event": "complete",
                            "data": {
                                "query": query,
                                "agent_statuses": {name: status.value for name, status in final_state.get("agent_statuses", {}).items()},
                                "agent_failures": final_state.get("agent_failures", []),
                                "validated_answer": final_state.get("validated_answer", ""),
                                "confidence": final_state.get("confidence", "low"),
                                "is_valid": final_state.get("is_valid", False),
                            },
                        })
                    else:
                        event_queue.put({"event": "error", "data": {"message": "Pipeline completed without a final state."}})
                except Exception as exc:
                    logger.exception("SSE pipeline worker failed")
                    event_queue.put({"event": "error", "data": {"message": str(exc)}})
            finally:
                SSE_EVENT_SINK.reset(token)
                event_queue.put(None)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

        while True:
            item = event_queue.get()
            if item is None:
                break
            normalized = _normalize_sse_event(item)
            if normalized is None:
                continue
            yield _format_sse(normalized["event"], normalized["data"])

        thread.join(timeout=1)

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Access-Control-Allow-Origin": "*",
    }
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)


@app.get("/api/query/stream")
def stream_pipeline_get(query: str) -> StreamingResponse:
    return _stream_pipeline_response(query)


@app.post("/api/query/stream")
def stream_pipeline(request: QueryRequest) -> StreamingResponse:
    return _stream_pipeline_response(request.query)


@app.get("/api/report")
def get_report(query: str) -> StreamingResponse:
    if not query:
        raise HTTPException(status_code=400, detail="Query parameter is required for report retrieval.")

    with REPORT_CACHE_LOCK:
        pdf_bytes = REPORT_CACHE.get(query)

    if pdf_bytes is None:
        raise HTTPException(status_code=404, detail="Report not ready. Run the query stream first to generate the report.")

    buffer = io.BytesIO(pdf_bytes)
    buffer.seek(0)
    headers = {
        "Cache-Control": "no-cache",
        "Content-Disposition": "attachment; filename=researchswarm-report.pdf",
        "Access-Control-Allow-Origin": "*",
    }
    return StreamingResponse(buffer, media_type="application/pdf", headers=headers)


@app.post("/api/report")
def post_report(request: QueryRequest) -> StreamingResponse:
    return get_report(request.query)


@app.post("/api/query", response_model=QueryResponse)
def run_pipeline(request: QueryRequest) -> QueryResponse:
    logger.info("API request received: /api/query | query=%s", request.query)
    try:
        final_state = pipeline_service.run_query(request.query)
    except Exception as exc:
        logger.exception("Pipeline execution failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    response = QueryResponse(
        query=final_state["query"],
        orchestrator_plan=final_state["orchestrator_plan"],
        validated_answer=final_state["validated_answer"],
        is_valid=final_state["is_valid"],
        confidence=final_state.get("confidence", "low"),
        agent_statuses={name: status.value for name, status in final_state.get("agent_statuses", {}).items()},
        agent_failures=final_state.get("agent_failures", []),
        devils_critique=final_state.get("devils_critique", ""),
    )
    logger.info(
        "API response ready: /api/query | is_valid=%s | confidence=%s | agent_statuses=%s",
        response.is_valid,
        response.confidence,
        response.agent_statuses,
    )
    return response

