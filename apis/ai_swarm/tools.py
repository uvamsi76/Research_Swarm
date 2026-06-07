from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import requests
from langchain_core.tools import tool

from .progress import _current_node_progress, _emit_sse_event

logger = logging.getLogger(__name__)


class ToolServiceClient:
    def __init__(self, base_url: str, timeout_seconds: int = 10) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.timeout_seconds = timeout_seconds

    def call_tool(self, tool_name: str, *args: Any, **kwargs: Any) -> str:
        url = f"{self.base_url}/tool/{tool_name}"
        payload = {"args": list(args), "kwargs": kwargs}
        logger.info("Tool call start: %s | url=%s | args=%s | kwargs=%s", tool_name, url, args, kwargs)

        try:
            response = self.session.post(url, json=payload, timeout=self.timeout_seconds)
            response.raise_for_status()
            body = response.json()
            output = body.get("output", "")
            logger.info("Tool call success: %s | output_length=%s", tool_name, len(output))
            _emit_sse_event(
                {
                    "event": "tool",
                    "data": {
                        "tool_name": tool_name,
                        "status": "success",
                        "output_length": len(output),
                    },
                }
            )
            return output
        except requests.HTTPError as exc:
            logger.exception("Tool service HTTP error for %s", tool_name)
            _emit_sse_event(
                {
                    "event": "tool",
                    "data": {
                        "tool_name": tool_name,
                        "status": "failure",
                        "error": str(exc),
                    },
                }
            )
            return f"[TOOL ERROR — {tool_name}] HTTP error: {exc}"
        except requests.RequestException as exc:
            logger.exception("Tool service request failed for %s", tool_name)
            _emit_sse_event(
                {
                    "event": "tool",
                    "data": {
                        "tool_name": tool_name,
                        "status": "failure",
                        "error": str(exc),
                    },
                }
            )
            return f"[TOOL ERROR — {tool_name}] Request failed: {exc}"
        except ValueError as exc:
            logger.exception("Invalid tool service response for %s", tool_name)
            _emit_sse_event(
                {
                    "event": "tool",
                    "data": {
                        "tool_name": tool_name,
                        "status": "failure",
                        "error": str(exc),
                    },
                }
            )
            return f"[TOOL ERROR — {tool_name}] Invalid response: {exc}"


TOOL_SERVICE_URL = "http://swarm-toolservice-api.duckdns.org"

try:
    from os import getenv
    TOOL_SERVICE_URL = getenv("TOOL_SERVICE_URL", TOOL_SERVICE_URL)
except Exception:
    pass


tool_client = ToolServiceClient(TOOL_SERVICE_URL)


def _remote_tool_call(tool_name: str, *args: Any, **kwargs: Any) -> str:
    node_progress = _current_node_progress()
    if node_progress is not None:
        node_progress.tool_called(tool_name)
    return tool_client.call_tool(tool_name, *args, **kwargs)


@tool
def web_search(query: str) -> str:
    """Search the web for `query` using the remote tool service and return a text summary."""
    return _remote_tool_call("web_search", query)


@tool
def scrape_url(url: str) -> str:
    """Scrape the provided `url` and return its extracted text content."""
    return _remote_tool_call("scrape_url", url)


@tool
def knowledge_base_lookup(query: str) -> str:
    """Lookup `query` in the internal knowledge base and return relevant entries."""
    return _remote_tool_call("knowledge_base_lookup", query)


@tool
def get_expert_report(topic: str) -> str:
    """Request an expert report for `topic` from the remote tool service and return it."""
    return _remote_tool_call("get_expert_report", topic)


@tool
def get_market_data(ticker: str) -> str:
    """Fetch market data for `ticker` (e.g., price, volume) and return a summary."""
    return _remote_tool_call("get_market_data", ticker)


@tool
def get_earnings_report(company: str, quarter: str = "latest") -> str:
    """Retrieve the earnings report for `company` and `quarter` (defaults to 'latest')."""
    return _remote_tool_call("get_earnings_report", company, quarter=quarter)


@tool
def financial_model(expression: str) -> str:
    """Run or evaluate a financial model described by `expression` and return results."""
    return _remote_tool_call("financial_model", expression)


@tool
def search_case_law(query: str) -> str:
    """Search case law for `query` and return matching cases or summaries."""
    return _remote_tool_call("search_case_law", query)


@tool
def lookup_statute(statute_id: str) -> str:
    """Lookup statute text or summary for `statute_id` and return the result."""
    return _remote_tool_call("lookup_statute", statute_id)


@tool
def compliance_check(activity_description: str) -> str:
    """Perform a compliance check for `activity_description` and return findings."""
    return _remote_tool_call("compliance_check", activity_description)
