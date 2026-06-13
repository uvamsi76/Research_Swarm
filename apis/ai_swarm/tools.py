from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import requests
from langchain_core.tools import tool

from .progress import _current_node_progress, _emit_sse_event

logger = logging.getLogger(__name__)


class ToolServiceClient:
    def __init__(self, base_url: str, timeout_seconds: int = 60) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.timeout_seconds = timeout_seconds

    def call_tool(self, tool_name: str, *args: Any, **kwargs: Any) -> str:
        url = f"{self.base_url}/tool/{tool_name}"
        payload = {"args": list(args), "kwargs": kwargs}
        logger.info("Tool service endpoint called: %s | url=%s | args=%s | kwargs=%s", tool_name, url, args, kwargs)

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


# TOOL_SERVICE_URL = "http://swarm-toolservice-api.duckdns.org"
TOOL_SERVICE_URL = "http://127.0.0.1:3000"

try:
    from os import getenv
    TOOL_SERVICE_URL = getenv("TOOL_SERVICE_URL", TOOL_SERVICE_URL)
except Exception:
    pass


tool_client = ToolServiceClient(TOOL_SERVICE_URL)


def _remote_tool_call(tool_name: str, *args: Any, **kwargs: Any) -> str:
    logger.info("Remote tool service call requested: %s | args=%s", tool_name, args)
    node_progress = _current_node_progress()
    
    # Check tool call limits before making the call
    if node_progress is not None:
        can_call, error_msg = node_progress.check_tool_limit(tool_name)
        if not can_call:
            logger.warning("Tool call rejected due to limit | tool=%s | message=%s", tool_name, error_msg)
            return error_msg
        
        # Increment counter and proceed
        node_progress.increment_tool_call(tool_name)
        node_progress.tool_called(tool_name)
    
    result = tool_client.call_tool(tool_name, *args, **kwargs)
    logger.info("Tool call completed: %s | output_length=%s", tool_name, len(result) if isinstance(result, str) else 0)
    return result


@tool
def web_search(query: str) -> str:
    """Search the web for `query` using the remote tool service and return a text summary."""
    return _remote_tool_call("web_search", query)


@tool
def search_across_internet(query: str) -> str:
    """Search the internet regarding `query` to get more information that is not obtained using the remote tool service"""
    return _remote_tool_call("search_across_internet", query)


@tool
def get_company_data(query: str) -> str:
    """Get comprehensive info regarding details of the company including 
    - Company description
    - Founded date
    - Headquarters
    - Employee count range
    - All funding rounds (date, amount, type, investors)
    - Total funding raised
    - Key executives/founders listed 
    using the remote tool service"""
    return _remote_tool_call("get_company_data", query)

@tool
def funding_news_search(query: str) -> str:
    """Get Comprehensive info regarding news which include 
    funding info who all funded and how much,
    revenue ,
    leadership who is the leadership that steered and currently steering,
    competitors who all are competetors of this company,
    customers who all are the customers for the product,
    hiring_news,
    layoffs,
    stealth_signals
    using the remote tool service"""
    return _remote_tool_call("funding_news_search", query)


@tool
def job_postings_analyzer(query: str) -> str:
    """ Get Comprehensive info regarding job postings made by the company which include 
    1. Total open roles (approximate)
    2. Roles by department (engineering / sales / marketing / ops / support)
    3. Seniority distribution (senior-heavy vs junior-heavy)
    4. Tech stack signals from job descriptions
    5. Hiring velocity: accelerating / stable / slowing / no postings
    6. Any stealth signals (hiring for product category not yet announced)
    7. Remote vs onsite split
    using the remote tool service
    """
    return _remote_tool_call("job_postings_analyzer", query)


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
