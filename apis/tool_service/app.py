from __future__ import annotations

import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .impl import TOOL_REGISTRY
from .models import ToolRequest, ToolResponse

logger = logging.getLogger(__name__)
app = FastAPI(title="LangGraph Tool Service", version="0.1.0")

# Allow cross-origin requests from the frontend (development convenience)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "LangGraph Tool Service"}


@app.get("/tools")
def list_tools() -> dict[str, list[str]]:
    return {"tools": sorted(TOOL_REGISTRY)}


@app.post("/tool/{tool_name}", response_model=ToolResponse)
def invoke_tool(tool_name: str, request: ToolRequest) -> ToolResponse:
    if tool_name not in TOOL_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' is not available.")

    tool_callable = TOOL_REGISTRY[tool_name]
    try:
        output = tool_callable(*request.args, **request.kwargs)
    except TypeError as exc:
        logger.exception("Invalid arguments for tool %s", tool_name)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Tool %s execution failed", tool_name)
        output = f"[TOOL ERROR — {tool_name}] {type(exc).__name__}: {str(exc)[:120]}"

    return ToolResponse(output=output)
