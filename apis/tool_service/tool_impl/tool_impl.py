from __future__ import annotations

import logging
from datetime import date
from functools import wraps
from typing import Optional

from .utils import *

logger = logging.getLogger(__name__)


def _tool_error(tool_name: str, error: Exception) -> str:
    return f"[TOOL ERROR — {tool_name}] {type(error).__name__}: {str(error)[:120]}"


def log_tool(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        logger.info("Tool implementation start: %s | args=%s | kwargs=%s", fn.__name__, args, kwargs)
        try:
            result = fn(*args, **kwargs)
            logger.info(
                "Tool implementation success: %s | result_length=%s",
                fn.__name__,
                len(result) if isinstance(result, str) else "n/a",
            )
            return result
        except Exception as exc:
            logger.exception("Tool implementation failed: %s", fn.__name__)
            return _tool_error(fn.__name__, exc)

    return wrapper


@log_tool
def get_company_data(company: str) -> str:
    try:
        return crunchbase_scraper(company)
    except Exception as exc:
        return _tool_error("get_company_data", exc)


@log_tool
def funding_news_search(company: str, from_year: Optional[str] = None, to_year: Optional[str] = None) -> str:
    try:
        to_year = date.today().year
        from_year = to_year - 1
        topics = ["funding0", "funding1", "funding2", "funding3", "revenue"]
        return comprehensive_news_search(company, topics, from_year, to_year)
    except Exception as exc:
        return _tool_error("funding_news_search", exc)


@log_tool
def job_postings_analyzer(company: str) -> str:
    try:
        details = get_company_details(company)
        company_slug = details["company_slug"]
        company_website = details["company_website"]
        res1 = job_postings_analyzer_company(company, company_website, company_slug)
        return res1
    except Exception as exc:
        return _tool_error("job_postings_analyzer", exc)


# def search_across_internet(query: str) -> dict:
#     res1=ddg_news_search(query)
#     res2=ddg_search(query)

# def web_traffic_estimator(company: str) -> str:
#     try:
#         details=get_company_details(company)
#         domain=details['detected_domain']
#         return similarweb_free_scraper(domain)
#     except Exception as exc:
#         return _tool_error("web_traffic_estimator", exc)

# def revenue_estimator(company: str) -> str:
#     try:
#         return crunchbase_scraper(company)
#     except Exception as exc:
#         return _tool_error("revenue_estimator", exc)

