from __future__ import annotations

import logging
from typing import Callable, Dict

logger = logging.getLogger(__name__)


def _tool_error(tool_name: str, error: Exception) -> str:
    return f"[TOOL ERROR — {tool_name}] {type(error).__name__}: {str(error)[:120]}"


def web_search(query: str) -> str:
    try:
        return f"[WEB SEARCH] Results for: '{query}'"
    except Exception as exc:
        return _tool_error("web_search", exc)


def scrape_url(url: str) -> str:
    try:
        return f"[SCRAPE] Content from {url}"
    except Exception as exc:
        return _tool_error("scrape_url", exc)


def knowledge_base_lookup(query: str) -> str:
    try:
        return f"[KB] Internal knowledge for: '{query}'"
    except Exception as exc:
        return _tool_error("knowledge_base_lookup", exc)


def get_expert_report(topic: str) -> str:
    try:
        return f"[EXPERT] Analysis on: '{topic}'"
    except Exception as exc:
        return _tool_error("get_expert_report", exc)


def get_market_data(ticker: str) -> str:
    try:
        return f"[MARKET] Data for {ticker}"
    except Exception as exc:
        return _tool_error("get_market_data", exc)


def get_earnings_report(company: str, quarter: str = "latest") -> str:
    try:
        return f"[EARNINGS] {company} {quarter}"
    except Exception as exc:
        return _tool_error("get_earnings_report", exc)


def financial_model(expression: str) -> str:
    try:
        return f"[CALC] Result of: {expression}"
    except Exception as exc:
        return _tool_error("financial_model", exc)


def search_case_law(query: str) -> str:
    try:
        return f"[CASES] Precedents for: '{query}'"
    except Exception as exc:
        return _tool_error("search_case_law", exc)


def lookup_statute(statute_id: str) -> str:
    try:
        return f"[STATUTE] {statute_id}: ..."
    except Exception as exc:
        return _tool_error("lookup_statute", exc)


def compliance_check(activity_description: str) -> str:
    try:
        return f"[COMPLIANCE] Analysis of: '{activity_description}'"
    except Exception as exc:
        return _tool_error("compliance_check", exc)


TOOL_REGISTRY: Dict[str, Callable[..., str]] = {
    "web_search": web_search,
    "scrape_url": scrape_url,
    "knowledge_base_lookup": knowledge_base_lookup,
    "get_expert_report": get_expert_report,
    "get_market_data": get_market_data,
    "get_earnings_report": get_earnings_report,
    "financial_model": financial_model,
    "search_case_law": search_case_law,
    "lookup_statute": lookup_statute,
    "compliance_check": compliance_check,
}
