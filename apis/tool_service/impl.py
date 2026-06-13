from __future__ import annotations

import logging
from functools import wraps
from typing import Callable, Dict

from tool_impl import get_company_data, funding_news_search, job_postings_analyzer

logger = logging.getLogger(__name__)


def log_tool(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        logger.info("Tool impl start: %s | args=%s | kwargs=%s", fn.__name__, args, kwargs)
        try:
            result = fn(*args, **kwargs)
            result_length = len(result) if isinstance(result, str) else "n/a"
            logger.info("Tool impl success: %s | result_length=%s", fn.__name__, result_length)
            return result
        except Exception as exc:
            logger.exception("Tool impl failed: %s", fn.__name__)
            return _tool_error(fn.__name__, exc)

    return wrapper


def _tool_error(tool_name: str, error: Exception) -> str:
    return f"[TOOL ERROR — {tool_name}] {type(error).__name__}: {str(error)[:120]}"


@log_tool
def web_search(query: str) -> str:
    try:
        return f"[WEB SEARCH] Results for: '{query}'"
    except Exception as exc:
        return _tool_error("web_search", exc)


@log_tool
def scrape_url(url: str) -> str:
    try:
        return f"[SCRAPE] Content from {url}"
    except Exception as exc:
        return _tool_error("scrape_url", exc)


@log_tool
def knowledge_base_lookup(query: str) -> str:
    try:
        return f"[KB] Internal knowledge for: '{query}'"
    except Exception as exc:
        return _tool_error("knowledge_base_lookup", exc)


@log_tool
def get_expert_report(topic: str) -> str:
    try:
        return f"[EXPERT] Analysis on: '{topic}'"
    except Exception as exc:
        return _tool_error("get_expert_report", exc)


@log_tool
def get_market_data(ticker: str) -> str:
    try:
        return f"[MARKET] Data for {ticker}"
    except Exception as exc:
        return _tool_error("get_market_data", exc)


@log_tool
def get_earnings_report(company: str, quarter: str = "latest") -> str:
    try:
        return f"[EARNINGS] {company} {quarter}"
    except Exception as exc:
        return _tool_error("get_earnings_report", exc)


@log_tool
def financial_model(expression: str) -> str:
    try:
        return f"[CALC] Result of: {expression}"
    except Exception as exc:
        return _tool_error("financial_model", exc)


@log_tool
def search_case_law(query: str) -> str:
    try:
        return f"[CASES] Precedents for: '{query}'"
    except Exception as exc:
        return _tool_error("search_case_law", exc)


@log_tool
def lookup_statute(statute_id: str) -> str:
    try:
        return f"[STATUTE] {statute_id}: ..."
    except Exception as exc:
        return _tool_error("lookup_statute", exc)


@log_tool
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

    "get_company_data" : get_company_data,
    "funding_news_search":funding_news_search,
    "job_postings_analyzer":job_postings_analyzer,
}

TOOL_REGISTRY2: Dict[str, Callable[..., str]] = {
    "get_company_data" : get_company_data,
    "funding_news_search":funding_news_search,
    "job_postings_analyzer":job_postings_analyzer,
    # "web_traffic_estimator":web_traffic_estimator
}
