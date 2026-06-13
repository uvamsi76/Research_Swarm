from langchain_google_genai import ChatGoogleGenerativeAI
from firecrawl import FirecrawlApp
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from playwright.async_api import async_playwright
import asyncio
import time
import random
from ddgs import DDGS
from duckduckgo_search.exceptions import RatelimitException
import json
import re
from collections import Counter
from urllib.parse import urlparse
from dotenv import load_dotenv
from difflib import SequenceMatcher
import logging
import os
from langchain_openai import ChatOpenAI
from requests.exceptions import Timeout, ConnectionError

load_dotenv()

logger = logging.getLogger(__name__)

FIRECRAWL_KEY = os.getenv("FIRECRAWL_KEY")

# Per-worker rate limit tracking
# Each gunicorn worker tracks its own last_request_time and backoff
_last_llm_request_time = None
_llm_backoff_seconds = 0.1  # Start with minimal backoff

def llm_extract(prompt, max_retries: int = 4):
    """
    Extract data using LLM with rate limit handling for multi-worker deployment.
    
    Uses per-worker rate limiting (not cross-worker) suitable for gunicorn multi-process.
    Each worker tracks its own request timing and backs off independently.
    
    Args:
        prompt: The prompt to send to LLM
        max_retries: Maximum number of retry attempts (default: 4)
    
    Returns:
        Extracted response content
    
    Raises:
        Exception: If all retries exhausted or unrecoverable error occurs
    """
    global _last_llm_request_time, _llm_backoff_seconds
    
    logger.info("LLM extraction start | prompt_length=%s | max_retries=%s", len(prompt), max_retries)
    
    for attempt in range(max_retries):
        try:
            # Per-worker rate limiting: enforce minimum delay between requests
            # This is simple and avoids deadlocks in multi-process gunicorn
            if _last_llm_request_time is not None:
                time_since_last = time.time() - _last_llm_request_time
                if time_since_last < _llm_backoff_seconds:
                    wait_time = _llm_backoff_seconds - time_since_last
                    logger.debug("LLM rate limiting | worker_backoff=%.2fs | waiting %.2fs | attempt=%s/%s",
                               _llm_backoff_seconds, wait_time, attempt + 1, max_retries)
                    time.sleep(wait_time)
            
            logger.debug("LLM request attempt %s/%s | backoff=%.2fs | prompt_length=%s", 
                        attempt + 1, max_retries, _llm_backoff_seconds, len(prompt))
            
            llm = ChatOpenAI(
                model="google/gemma-4-E2B-it",
                temperature=1.0,
                api_key=os.getenv("LLM_API_KEY"),
                base_url=os.getenv("LLM_BASE_URL"),
                max_retries=0,  # Disable internal retries; we handle it here
                request_timeout=30,
            )
            
            logger.debug("LLM client initialized | invoking prompt | attempt=%s/%s", attempt + 1, max_retries)
            
            # Record request time BEFORE making call for proper rate limit tracking
            _last_llm_request_time = time.time()
            resp = llm.invoke(prompt)
            
            # Success: reset backoff
            _llm_backoff_seconds = 0.1
            logger.info("LLM response received | response_length=%s | attempt=%s/%s | backoff_reset", 
                       len(resp.content), attempt + 1, max_retries)
            return resp.content
        
        except (Timeout, ConnectionError) as exc:
            # Network-level errors - brief backoff
            wait_time = (2 ** attempt) + random.uniform(0, 1)
            logger.warning(
                "LLM network error on attempt %s/%s | error=%s | will retry in %.2f seconds",
                attempt + 1, max_retries, type(exc).__name__, wait_time
            )
            if attempt < max_retries - 1:
                time.sleep(wait_time)
            else:
                logger.exception("LLM network error exhausted retries | error=%s", type(exc).__name__)
                raise
        
        except Exception as exc:
            # Check if this is a rate limit error
            error_str = str(exc).lower()
            is_rate_limit = any(phrase in error_str for phrase in [
                "rate limit", "429", "too many requests", "quota exceeded", 
                "throttle", "ratelimit", "rate-limit", "too_many_requests"
            ])
            
            if is_rate_limit or "429" in str(getattr(exc, 'status_code', '')):
                # Exponential backoff for rate limits - increase delay for this worker
                old_backoff = _llm_backoff_seconds
                _llm_backoff_seconds = min(30, max(0.5, _llm_backoff_seconds * 2.5) + random.uniform(0.1, 0.5))
                wait_time = (2 ** attempt) * 2 + random.uniform(0, 2)
                
                logger.warning(
                    "LLM rate limit on attempt %s/%s | increased_backoff=%.2fs (was %.2fs) | will retry in %.2f seconds | error=%s",
                    attempt + 1, max_retries, _llm_backoff_seconds, old_backoff, wait_time, error_str[:100]
                )
                if attempt < max_retries - 1:
                    time.sleep(wait_time)
                else:
                    logger.exception("LLM rate limit exhausted retries after %s attempts", max_retries)
                    raise
            else:
                # Unrecoverable error - don't retry
                logger.exception("LLM unrecoverable error on attempt %s/%s | error=%s", 
                               attempt + 1, max_retries, type(exc).__name__)
                raise
    
    logger.error("LLM extraction exhausted all %s retries", max_retries)
    raise Exception("LLM extraction failed after all retry attempts")




def ddg_news_search(query: str, max_results: int = 10, retries: int = 3) -> list[dict]:
    logger.info("DDG news search start | query=%s | max_results=%s", query, max_results)
    for attempt in range(retries):
        try:
            logger.debug("DDG news search attempt %s/%s | query=%s", attempt + 1, retries, query)
            # Random delay to mimic human behavior
            time.sleep(random.uniform(2, 5))
            with DDGS() as ddgs:
                results = list(ddgs.news(query, max_results=max_results))
            logger.info("DDG news search success | query=%s | results=%s", query, len(results))
            return results
        except RatelimitException:
            wait = (attempt + 1) * 10
            logger.warning("DDG rate limited for query=%s | waiting %s seconds before retry %s/%s", query, wait, attempt + 1, retries)
            time.sleep(wait)
        except Exception as exc:
            logger.exception("DDG news search exception on attempt %s/%s | query=%s", attempt + 1, retries, query)
            return []
    logger.error("DDG news search exhausted retries | query=%s", query)
    return []



def ddg_search(query: str, max_results: int = 10) -> list[dict]:
    """
    Completely free. No API key. No rate limit issues for normal usage.
    Returns: title, url, body (snippet), published date
    """
    with DDGS() as ddgs:
        results = list(ddgs.text(
            query,
            max_results=max_results,
            safesearch='off'
        ))
    return results


def search_summarize(query: str, max_results: int = 20) -> list[dict]:
    logger.info("Search summarize start | query=%s | max_results=%s", query, max_results)
    try:
        results = ddg_news_search(query)
        logger.info("Search summarize: news search complete | results=%s | running LLM", len(results))
        prompt = f""" {results}
    This is the data retreived from searching something across internet. It might not be straight forward. 
    Your task is to summarize this without loosing any info what so ever."""
        response = llm_extract(prompt)
        logger.info("Search summarize complete | query=%s", query)
        return response
    except Exception as exc:
        logger.exception("Search summarize failed | query=%s", query)
        raise



async def scrape_url(url: str, wait_for: str = None) -> dict:
    """
    Handles JS-rendered pages. Free. No limits.
    wait_for: CSS selector to wait for before extracting
              e.g. ".reviews-container" for review pages
    """
    logger.info("Scrape URL async start | url=%s | wait_for=%s", url, wait_for)
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            logger.debug("Playwright browser launched")
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            logger.debug("Browser page created")
            
            try:
                logger.debug("Navigating to URL: %s", url)
                await page.goto(url, timeout=30000)
                
                if wait_for:
                    logger.debug("Waiting for selector: %s", wait_for)
                    await page.wait_for_selector(wait_for, timeout=10000)
                else:
                    logger.debug("Waiting for networkidle on URL: %s", url)
                    await page.wait_for_load_state("networkidle", timeout=15000)
                
                html = await page.content()
                logger.debug("HTML content retrieved | content_length=%s", len(html))
                
            except Exception as exc:
                logger.exception("Error during page navigation/content retrieval | url=%s", url)
                return {"url": url, "content": "", "error": str(exc), "text": None}
            finally:
                await browser.close()
                logger.debug("Browser closed")
        
        # Parse with BeautifulSoup
        logger.debug("Parsing HTML with BeautifulSoup | url=%s", url)
        soup = BeautifulSoup(html, 'lxml')
        
        # Remove noise
        for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
            tag.decompose()
        
        # Extract clean text
        text = soup.get_text(separator='\n', strip=True)
        logger.info("Scrape URL async complete | url=%s | text_length=%s", url, len(text[:8000]))
        
        return {
            "url": url,
            "title": soup.find('title').text if soup.find('title') else "",
            "text": text[:8000],   # cap at 8k chars for LLM context
            "html": str(soup)[:20000]
        }
    except Exception as exc:
        logger.exception("Scrape URL async failed | url=%s", url)
        raise

# Sync wrapper for use in LangGraph nodes
def scrape_url_sync(url: str, wait_for: str = None) -> dict:
    logger.info("Scrape URL sync start | url=%s", url)
    try:
        result = asyncio.run(scrape_url(url, wait_for))
        logger.info("Scrape URL sync complete | url=%s", url)
        return result
    except Exception as exc:
        logger.exception("Scrape URL sync failed | url=%s", url)
        raise



def scrape_simple(url: str) -> dict:
    """
    Fast scraper for non-JS pages — Crunchbase public, 
    company about pages, news articles
    """
    logger.info("Scrape simple start | url=%s", url)
    try:
        ua = UserAgent()
        headers = {
            "User-Agent": ua.random,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }
        logger.debug("Headers prepared with random user-agent")
        
        response = requests.get(url, headers=headers, timeout=15)
        logger.debug("HTTP request complete | url=%s | status=%s", url, response.status_code)
        
        soup = BeautifulSoup(response.text, 'lxml')
        logger.debug("HTML parsed with BeautifulSoup | url=%s", url)
        
        for tag in soup(['script', 'style', 'nav', 'footer']):
            tag.decompose()
        
        text = soup.get_text(separator='\n', strip=True)
        logger.info("Scrape simple complete | url=%s | text_length=%s", url, len(text[:8000]))
        
        return {
            "url": url,
            "status": response.status_code,
            "text": text[:8000]
        }
    except Exception as exc:
        logger.exception("Scrape simple failed | url=%s", url)
        return {"url": url, "text": "", "error": str(exc)}


def get_official_website(search_results, company_name):
    logger.debug("Getting official website | company=%s | results=%s", company_name, len(search_results))
    
    # 1. Define domains that are NEVER the official company site
    blacklist = [
        'wikipedia.org', 'linkedin.com', 'crunchbase.com', 
        'bloomberg.com', 'forbes.com', 'facebook.com', 
        'twitter.com', 'youtube.com', 'yahoo.com'
    ]
    
    # 2. Clean the company name (lowercase, remove spaces, drop 'inc'/'llc')
    clean_name = re.sub(r'[^a-z0-9]', '', company_name.lower().replace('inc', '').replace('llc', ''))
    logger.debug("Cleaned company name: %s", clean_name)

    for item in search_results:
        url = item['href']
        
        # Extract just the domain (e.g., 'www.apple.com' -> 'apple.com')
        domain = urlparse(url).netloc.lower()
        if domain.startswith('www.'):
            domain = domain[4:]

        # 3. Skip blacklisted directory/wiki sites immediately
        if any(bad_site in domain for bad_site in blacklist):
            logger.debug("Skipping blacklisted domain: %s", domain)
            continue

        # 4. Check if the cleaned company name is in the domain
        if clean_name in domain:
            logger.info("Official website found | company=%s | url=%s", company_name, url)
            return url
            
    # Fallback: If no exact match, return the first link that isn't blacklisted
    logger.debug("No exact match found, using fallback logic | company=%s", company_name)
    for item in search_results:
        domain = urlparse(item['href']).netloc.lower()
        if not any(bad_site in domain for bad_site in blacklist):
            logger.info("Official website found (fallback) | company=%s | url=%s", company_name, item['href'])
            return item['href']

    logger.warning("No official website found | company=%s", company_name)
    return None


def crunchbase_scraper(company_name: str) -> dict:
    """
    company_slug: 'openai' from crunchbase.com/organization/openai
    """
    logger.info("Crunchbase scraper start | company=%s", company_name)
    try:
        with DDGS() as ddgs:
            logger.debug("Searching Crunchbase for company: %s", company_name)
            results = list(ddgs.text(
                f"{company_name} site:crunchbase.com/organization",
                max_results=3
            ))
        
        logger.debug("Crunchbase search results: %s", len(results))
        cb_results = [r for r in results 
                      if 'crunchbase.com/organization' in r['href']]
        
        if not cb_results:
            logger.warning("No Crunchbase results found for company: %s", company_name)
            return {"found": False, "source": "crunchbase"}
        
        cb_url = cb_results[0]['href']
        logger.info("Crunchbase URL found | company=%s | url=%s", company_name, cb_url)
        
        app = FirecrawlApp(api_key=FIRECRAWL_KEY)
        logger.debug("FirecrawlApp initialized")
        
        result = app.scrape_url(cb_url)
        logger.debug("Crunchbase main page scraped | company=%s", company_name)

        funding_url = cb_url + "/funding_rounds"
        logger.debug("Scraping funding page: %s", funding_url)
        funding_result = app.scrape_url(funding_url)

        prompt = f"""
    Extract from this Crunchbase page:
    - Company description
    - Founded date
    - Headquarters
    - Employee count range
    - All funding rounds (date, amount, type, investors)
    - Total funding raised
    - Key executives/founders listed
    
    Return JSON alone without any text just pure JSON. 
    Content:
    {result.markdown[:4000]}
    
    Funding section:
    {funding_result.markdown[:2000]}
    """
        logger.debug("Invoking LLM to extract Crunchbase data for: %s", company_name)
        resp = llm_extract(prompt)
        logger.info("Crunchbase scraper complete | company=%s | data_length=%s", company_name, len(resp))
        return resp
    except Exception as exc:
        logger.exception("Crunchbase scraper failed | company=%s", company_name)
        return {"found": False, "source": "crunchbase", "error": str(exc)}



def comprehensive_news_search(company_name: str, topics: list[str], from_year: str, to_year: str) -> dict:
    """
    Searches multiple angles using DDG news search.
    Covers what Tavily was doing across multiple agents.
    """
    logger.info("Comprehensive news search start | company=%s | topics=%s | years=%s-%s", company_name, topics, from_year, to_year)
    results = {}
    
    search_map = {
        "funding0": f"{company_name} funding raised Series investment {from_year} {to_year}",
        "revenue": f"{company_name} revenue ARR growth annual",
        "legal": f"{company_name} lawsuit legal investigation penalty",
        "product": f"{company_name} product launch feature update",
        "leadership": f"{company_name} CEO founder executive hire",
        "competitors": f"{company_name} competitor vs alternative",
        "customers": f"{company_name} customer case study win deal",
        "layoffs": f"{company_name} layoffs fired employees cut",
        "funding1": f"{company_name} raises million Series",
        "funding2": f"{company_name} valuation investment",
        "funding3": f"{company_name} funding raised Series investment {from_year} {to_year}",
        "hiring_news": f"{company_name} \"hiring freeze\" OR \"expanding team\" OR \"adding jobs\"",
        "stealth_signals": f"{company_name} \"new division\" OR \"secret project\" OR \"R&D\" hiring"
    }
    
    # Only run the topics requested
    active_searches = {k: v for k, v in search_map.items() 
                       if k in topics}
    
    logger.debug("Active searches for %s: %s", company_name, list(active_searches.keys()))
    
    try:
        with DDGS() as ddgs:
            for topic, query in active_searches.items():
                try:
                    logger.debug("Searching topic=%s | company=%s", topic, company_name)
                    news_results = list(ddgs.news(query, max_results=5))
                    text_results = list(ddgs.text(query, max_results=5))
                    results[topic] = news_results + text_results
                    logger.debug("Topic search complete | topic=%s | results=%s", topic, len(results[topic]))
                except Exception as exc:
                    logger.exception("Topic search failed | topic=%s | company=%s", topic, company_name)
                    results[topic] = []
        
        prompt = f"""Extract from this scrapped info
    "funding info who all funded and how much,
    "revenue ",
    "legal issues they have dealt with and dealing with",
    "product detailed info about product",
    "leadership who is the leadership that steered and currently steering",
    "competitors who all are competetors of this company",
    "customers who all are the customers for the product",
    "hiring_news",
    "layoffs",
    "stealth_signals"
    Return JSON alone without any text just pure JSON.
    JSON should have the mentioned topics as key and value should be the info that you reasoned and Extracted entirely text but only values 
    Content:
    {results}
"""
        logger.debug("Invoking LLM for comprehensive news analysis | company=%s", company_name)
        response = llm_extract(prompt)
        logger.info("Comprehensive news search complete | company=%s", company_name)
        return response
    except Exception as exc:
        logger.exception("Comprehensive news search failed | company=%s", company_name)
        raise



def job_postings_analyzer_company(company_name: str, company_website: str, company_slug: str) -> dict:
    logger.info("Job postings analyzer company start | company=%s | website=%s | slug=%s", company_name, company_website, company_slug)
    
    try:
        # Step 1: Scrape their own careers page with Playwright (JS-heavy usually)
        careers_paths = ["/careers", "/jobs", "/about/careers", "/work-with-us"]
        careers_content = ""
        logger.debug("Step 1: Scraping careers page for %s", company_name)
        
        for path in careers_paths:
            careers_url = company_website + path
            logger.debug("Trying careers URL: %s", careers_url)
            result = scrape_url_sync(careers_url)
            if result.get('text') and len(result['text']) > 300:
                careers_content = result['text']
                logger.info("Found careers page content at: %s", careers_url)
                break
        
        if not careers_content:
            logger.warning("No careers page content found for: %s", company_name)
        
        # Step 2: DDG search for LinkedIn job postings (public, no auth)
        logger.debug("Step 2: Searching LinkedIn for job postings | company=%s", company_name)
        with DDGS() as ddgs:
            linkedin_jobs = list(ddgs.text(
                f"{company_name} jobs hiring site:linkedin.com/jobs",
                max_results=10
            ))
            logger.debug("LinkedIn jobs found: %s", len(linkedin_jobs))
            
            # Also search Indeed as a second source
            indeed_jobs = list(ddgs.text(
                f"{company_name} jobs site:indeed.com",
                max_results=5
            ))
            logger.debug("Indeed jobs found: %s", len(indeed_jobs))
        
        # Step 3: DDG news for hiring signals
        logger.debug("Step 3: Searching hiring news | company=%s", company_name)
        with DDGS() as ddgs:
            hiring_news = list(ddgs.news(
                f"{company_name} hiring expanding team 2024 2025",
                max_results=5
            ))
            logger.debug("Hiring news found: %s", len(hiring_news))
        
        # Step 4: LLM synthesizes everything
        logger.debug("Step 4: Running LLM synthesis for job postings | company=%s", company_name)
        prompt = f"""
    Analyze hiring signals for {company_name}:
    
    Careers page content:
    {careers_content[:2000]}
    
    LinkedIn job snippets:
    {json.dumps(linkedin_jobs, indent=2)[:2000]}
    
    Indeed snippets:
    {json.dumps(indeed_jobs, indent=2)[:1000]}
    
    Hiring news:
    {json.dumps(hiring_news, indent=2)[:1000]}
    
    Extract and infer:
    1. Total open roles (approximate)
    2. Roles by department (engineering / sales / marketing / ops / support)
    3. Seniority distribution (senior-heavy vs junior-heavy)
    4. Tech stack signals from job descriptions
    5. Hiring velocity: accelerating / stable / slowing / no postings
    6. Any stealth signals (hiring for product category not yet announced)
    7. Remote vs onsite split
    
    Return as JSON with a confidence level.
    """
        
        result = llm_extract(prompt)
        logger.info("Job postings analyzer company complete | company=%s", company_name)
        return result
    except Exception as exc:
        logger.exception("Job postings analyzer company failed | company=%s", company_name)
        raise


def job_postings_analyzer_ats(company_slug: str, ats_type: str = "greenhouse") -> dict:
    """
    Pulls and analyzes job data from Greenhouse or Lever.
    ats_type must be either 'greenhouse' or 'lever'.
    """
    logger.info("Job postings analyzer ATS start | company_slug=%s | ats_type=%s", company_slug, ats_type)
    
    if ats_type.lower() == "greenhouse":
        url = f"https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs?content=true"
    elif ats_type.lower() == "lever":
        url = f"https://api.lever.co/v0/postings/{company_slug}?mode=json"
    else:
        logger.warning("Unsupported ATS type: %s", ats_type)
        return {"error": "Unsupported ATS. Choose 'greenhouse' or 'lever'."}

    try:
        logger.debug("Fetching jobs from ATS | url=%s", url)
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            logger.error("ATS fetch failed | ats_type=%s | status=%s", ats_type, response.status_code)
            return {"error": f"Failed to fetch data. Status code: {response.status_code}. Make sure the slug is correct."}
        
        logger.debug("ATS response received | content_length=%s", len(response.text))
        jobs = response.json()
        
        # Greenhouse nests jobs under a 'jobs' key; Lever returns a flat list.
        if ats_type == "greenhouse":
            jobs = jobs.get("jobs", [])
            
        logger.debug("Jobs parsed from ATS | total_jobs=%s | ats_type=%s", len(jobs), ats_type)
            
    except Exception as exc:
        logger.exception("ATS fetch failed | company_slug=%s | ats_type=%s", company_slug, ats_type)
        return {"error": str(exc)}

    # Initialize tracking metrics
    metrics = {
        "total_roles": len(jobs),
        "remote_count": 0,
        "departments": Counter(),
        "seniority": {"Senior/Lead": 0, "Mid/Regular": 0, "Junior/Intern": 0},
        "tech_signals": Counter()
    }

    # Keywords to look for in job descriptions
    tech_keywords = ['python', 'react', 'aws', 'kubernetes', 'node.js', 'java', 'golang', 'sql', 'docker', 'typescript']
    logger.debug("Starting job analysis | total_jobs=%s", len(jobs))

    for idx, job in enumerate(jobs):
        # Extract fields based on ATS type
        if ats_type == "greenhouse":
            title = job.get("title", "").lower()
            dept_list = job.get("departments", [])
            dept = dept_list[0].get("name", "Uncategorized") if dept_list else "Uncategorized"
            location = job.get("location", {}).get("name", "").lower()
            html_content = job.get("content", "")
        else: # Lever
            title = job.get("text", "").lower()
            categories = job.get("categories", {})
            dept = categories.get("department") or categories.get("team") or "Uncategorized"
            location = categories.get("location", "").lower()
            html_content = job.get("descriptionPlain", "") # Lever usually provides plain text too

        # 1. Track Departments
        metrics["departments"][dept] += 1

        # 2. Track Remote vs Onsite
        if "remote" in location or "anywhere" in location:
            metrics["remote_count"] += 1

        # 3. Track Seniority (Basic keyword matching on titles)
        if any(w in title for w in ['senior', 'sr', 'lead', 'principal', 'staff', 'manager', 'director', 'head']):
            metrics["seniority"]["Senior/Lead"] += 1
        elif any(w in title for w in ['junior', 'jr', 'intern', 'associate']):
            metrics["seniority"]["Junior/Intern"] += 1
        else:
            metrics["seniority"]["Mid/Regular"] += 1

        # 4. Track Tech Stack (Only parse if it's likely an engineering role to reduce noise)
        if "engineer" in title or "developer" in title or "data" in title:
            # Strip HTML tags if any exist
            soup = BeautifulSoup(html_content, "html.parser")
            clean_text = soup.get_text().lower()
            
            for tech in tech_keywords:
                # Use regex to find exact word matches (so 'java' doesn't match 'javascript')
                if re.search(r'\b' + re.escape(tech) + r'\b', clean_text):
                    metrics["tech_signals"][tech] += 1

    logger.debug("Job analysis complete | total_roles=%s | remote_count=%s | departments=%s", 
                 metrics["total_roles"], metrics["remote_count"], dict(metrics["departments"].most_common(3)))

    prompt = f"""
    Analyze hiring signals for {company_slug}:
    
    {ats_type} content:
    Total Open Roles: {metrics["total_roles"]},
    Remote vs Onsite: 
        Remote: {metrics["remote_count"]},
        Onsite/Hybrid: {metrics["total_roles"] - metrics["remote_count"]},
    Seniority Distribution: {metrics["seniority"]},
    Top 5 Departments: {dict(metrics["departments"].most_common(5))},
    Top Tech Stack Signals: {dict(metrics["tech_signals"].most_common(5))}

    Extract and infer:
    1. Total open roles (approximate)
    2. Roles by department (engineering / sales / marketing / ops / support)
    3. Seniority distribution (senior-heavy vs junior-heavy)
    4. Tech stack signals from job descriptions
    5. Remote vs onsite split
    6. Any hiring velocity signals
    Return as JSON with a confidence level.
"""

    logger.debug("Running LLM synthesis | company_slug=%s | ats_type=%s", company_slug, ats_type)
    result = llm_extract(prompt)
    logger.info("Job postings analyzer ATS complete | company_slug=%s | ats_type=%s", company_slug, ats_type)
    return result




def get_company_details(company_name: str) -> dict:
    """
    Searches for a company's website and attempts to classify its business domain.
    """
    logger.info("Get company details start | company=%s", company_name)
    
    try:
        # 1. Generate slug
        slug = company_name.lower().strip()
        slug = re.sub(r'[^a-z0-9\s-]', '', slug)
        slug = re.sub(r'[\s-]+', '-', slug)
        logger.debug("Company slug generated: %s", slug)
        
        # 2. Define domain keyword maps
        domain_keywords = {
            "SaaS / Software": ["saas", "software as a service", "b2b software", "cloud software", "platform as a service", "enterprise software"],
            "FinTech": ["fintech", "financial technology", "payment processing", "banking app", "digital wallet", "lending platform"],
            "Financial Services": ["banking", "investment", "wealth management", "insurance", "hedge fund", "asset management", "credit union"],
            "E-Commerce": ["e-commerce", "ecommerce", "online retail", "marketplace", "direct-to-consumer", "dtc", "shopify"],
            "Healthcare / HealthTech": ["healthcare", "healthtech", "medical device", "biotech", "telemedicine", "pharmaceutical"],
            "Artificial Intelligence": ["artificial intelligence", "generative ai", "machine learning", "llm", "deep learning", "ai platform"]
        }
        
        logger.debug("Searching company details for: %s", company_name)
        with DDGS() as ddgs:
            # Look for official site and general descriptions
            search_query = f"{company_name} company profile industry overview description"
            search_results = list(ddgs.text(search_query, max_results=15, backend="duckduckgo"))
            logger.debug("Company search results: %s", len(search_results))
            
        if not search_results:
            logger.warning("No search results found for company: %s", company_name)
            return {"company_name": company_name, "domain": "Unknown", "company_slug": slug}
        
        # The first result usually contains the main website
        company_website = find_best_website(search_results, company_name)
        logger.debug("Best website found: %s", company_website)
        
        # Combine all result snippets into one block of text to scan for keywords
        combined_text = " ".join([result.get('body', '').lower() for result in search_results])
        
        # 3. Match text against domain categories
        detected_domains = []
        for domain, keywords in domain_keywords.items():
            for keyword in keywords:
                if re.search(r'\b' + re.escape(keyword) + r'\b', combined_text):
                    detected_domains.append(domain)
                    logger.debug("Domain detected: %s | company=%s", domain, company_name)
                    break # Move to next domain category if a keyword matches
        
        # Fallback if no specific keywords match
        final_domain = detected_domains[0] if detected_domains else "General Technology / Other"
        
        logger.info("Get company details complete | company=%s | domain=%s", company_name, final_domain)
        return {
            "company_name": company_name,
            "company_website": company_website,
            "company_slug": slug,
            "detected_domain": final_domain,
            "all_matching_signals": detected_domains
        }
            
    except Exception as exc:
        logger.exception("Get company details failed | company=%s", company_name)
        return {"error": str(exc)}

def find_best_website(search_results, company_name):
    logger.debug("Finding best website | company=%s | results=%s", company_name, len(search_results))
    
    blacklist = [
        'wikipedia.org', 'linkedin.com', 'crunchbase.com', 
        'bloomberg.com', 'forbes.com', 'facebook.com', 
        'twitter.com', 'youtube.com', 'yahoo.com', 'yelp.com'
    ]
    
    # Clean the name: lowercase, remove special characters, and common suffixes
    clean_name = re.sub(r'[^a-z0-9]', '', company_name.lower().replace('inc', '').replace('llc', '').replace('ltd', ''))
    
    best_link = None
    max_score = -float('inf')  # Start with lowest possible score

    for item in search_results:
        url = item['href']
        domain = urlparse(url).netloc.lower()
        if domain.startswith('www.'):
            domain = domain[4:]
            
        score = 0
        similarity_ratio = SequenceMatcher(None, clean_name, domain).ratio()
        score += int(similarity_ratio * 100)
        # 1. Heavily penalize social media, wikis, and directories
        if any(bad_site in domain for bad_site in blacklist):
            score -= 1000
            logger.debug("Blacklisted domain: %s | score=-1000", domain)
            
        # 3. Check if the domain at least contains the name
        elif clean_name in domain:
            score += 50
            logger.debug("Name match in domain: %s | score=+50", domain)
            
        # 4. Check if the name is just somewhere in the URL string
        elif clean_name in url.lower():
            score += 10
            logger.debug("Name match in URL: %s | score=+10", domain)

        # Update the max score and best link if this one is better
        if score > max_score:
            max_score = score
            best_link = url
            logger.debug("New best link found | domain=%s | score=%s", domain, score)
    
    logger.info("Best website selected | company=%s | url=%s | score=%s", company_name, best_link, max_score)
    return best_link

# def similarweb_free_scraper(domain: str) -> dict:
#     """
#     SimilarWeb shows public estimates on their site.
#     No API needed.
#     """
#     sw_url = f"https://www.similarweb.com/website/{domain}/"
#     result = scrape_url_sync(sw_url, wait_for=".engagement-list")
    
#     if not result['text']:
#         # Fallback: search for SimilarWeb data on this domain via DDG
#         with DDGS() as ddgs:
#             fallback = list(ddgs.text(
#                 f"site:similarweb.com {domain} traffic",
#                 max_results=2
#             ))
#         return {
#             "domain": domain,
#             "source": "snippet_only",
#             "snippet": fallback[0]['body'] if fallback else "Not found"
#         }
    
#     prompt = f"""
#     Extract from this SimilarWeb page:
#     - Monthly visits (approximate)
#     - Visit trend (growing/declining/stable)
#     - Top traffic sources (organic/paid/social/direct)
#     - Geographic breakdown (top countries)
#     - Bounce rate if available
#     - Pages per visit
    
#     Content: {result['text'][:3000]}
#     """
    
#     return llm_extract(prompt)


def revenueestimator(
    employee_count: int,
    funding_stage: str,
    web_traffic: int,
    industry: str,
    pricing_page_data: str
) -> dict:
    """
    Estimates ARR based on available signals.
    """
    logger.info("Revenue estimator start | employee_count=%s | funding_stage=%s | industry=%s | traffic=%s", 
                employee_count, funding_stage, industry, web_traffic)
    
    try:
        # Revenue benchmarks by stage (industry standard):
        # Seed: $0-$1M ARR
        # Series A: $1M-$5M ARR  
        # Series B: $5M-$20M ARR
        # Series C: $20M-$100M ARR
        
        # Revenue per employee by industry:
        # SaaS: ~$150K-$250K per employee
        # Services: ~$80K-$150K per employee
        
        prompt = f"""
    Given these signals about a {industry} company:
    - Employee count: {employee_count}
    - Funding stage: {funding_stage}
    - Monthly web traffic: {web_traffic}
    - Pricing info: {pricing_page_data}
    
    Using standard VC benchmarks (revenue per employee by stage,
    web traffic to revenue conversion estimates):
    
    Estimate ARR range and confidence level. 
    Show your reasoning step by step.
    Return JSON: {{ "range_low": number, "range_high": number, "confidence": string, "reasoning": string }}
    """
        
        logger.debug("Running LLM revenue estimation | industry=%s | funding_stage=%s", industry, funding_stage)
        result = llm_extract(prompt)
        logger.info("Revenue estimator complete | industry=%s | funding_stage=%s", industry, funding_stage)
        return result
    except Exception as exc:
        logger.exception("Revenue estimator failed | industry=%s | funding_stage=%s", industry, funding_stage)
        raise

