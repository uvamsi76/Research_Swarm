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
import os
load_dotenv()

FIRECRAWL_KEY=os.getenv("FIRECRAWL_KEY")
def llm_extract(prompt):
    llm= ChatGoogleGenerativeAI(
            model='gemini-2.5-flash',
            temperature=1.0,
            api_key= os.getenv("Google_api_key"),
            max_retries=2,
        )
    resp=llm.invoke(prompt)
    return resp.content


def ddg_news_search(query: str, max_results: int = 10, retries: int = 3) -> list[dict]:
    for attempt in range(retries):
        try:
            # Random delay to mimic human behavior
            time.sleep(random.uniform(2, 5))
            with DDGS() as ddgs:
                results = list(ddgs.news(query, max_results=max_results))
            return results
        except RatelimitException:
            wait = (attempt + 1) * 10 
            print(f"Rate limited. Waiting {wait}s before retry {attempt+1}/{retries}...")
            time.sleep(wait)
        except Exception as e:
            return []
    print("All retries exhausted.")
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

async def scrape_url(url: str, wait_for: str = None) -> dict:
    """
    Handles JS-rendered pages. Free. No limits.
    wait_for: CSS selector to wait for before extracting
              e.g. ".reviews-container" for review pages
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            await page.goto(url, timeout=30000)
            
            if wait_for:
                await page.wait_for_selector(wait_for, timeout=10000)
            else:
                await page.wait_for_load_state("networkidle", timeout=15000)
            
            html = await page.content()
            
        except Exception as e:
            return {"url": url, "content": "", "error": str(e),"text":None}
        finally:
            await browser.close()
    
    # Parse with BeautifulSoup
    soup = BeautifulSoup(html, 'lxml')
    
    # Remove noise
    for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
        tag.decompose()
    
    # Extract clean text
    text = soup.get_text(separator='\n', strip=True)
    
    return {
        "url": url,
        "title": soup.find('title').text if soup.find('title') else "",
        "text": text[:8000],   # cap at 8k chars for LLM context
        "html": str(soup)[:20000]
    }

# Sync wrapper for use in LangGraph nodes
def scrape_url_sync(url: str, wait_for: str = None) -> dict:
    return asyncio.run(scrape_url(url, wait_for))

def scrape_simple(url: str) -> dict:
    """
    Fast scraper for non-JS pages — Crunchbase public, 
    company about pages, news articles
    """
    ua = UserAgent()
    headers = {
        "User-Agent": ua.random,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'lxml')
        
        for tag in soup(['script', 'style', 'nav', 'footer']):
            tag.decompose()
        
        return {
            "url": url,
            "status": response.status_code,
            "text": soup.get_text(separator='\n', strip=True)[:8000]
        }
    except Exception as e:
        return {"url": url, "text": "", "error": str(e)}

def get_official_website(search_results, company_name):
    # 1. Define domains that are NEVER the official company site
    blacklist = [
        'wikipedia.org', 'linkedin.com', 'crunchbase.com', 
        'bloomberg.com', 'forbes.com', 'facebook.com', 
        'twitter.com', 'youtube.com', 'yahoo.com'
    ]
    
    # 2. Clean the company name (lowercase, remove spaces, drop 'inc'/'llc')
    clean_name = re.sub(r'[^a-z0-9]', '', company_name.lower().replace('inc', '').replace('llc', ''))

    for item in search_results:
        url = item['href']
        
        # Extract just the domain (e.g., 'www.apple.com' -> 'apple.com')
        domain = urlparse(url).netloc.lower()
        if domain.startswith('www.'):
            domain = domain[4:]

        # 3. Skip blacklisted directory/wiki sites immediately
        if any(bad_site in domain for bad_site in blacklist):
            continue

        # 4. Check if the cleaned company name is in the domain
        if clean_name in domain:
            return url
            
    # Fallback: If no exact match, return the first link that isn't blacklisted
    for item in search_results:
        domain = urlparse(item['href']).netloc.lower()
        if not any(bad_site in domain for bad_site in blacklist):
            return item['href']

    return None

def crunchbase_scraper(company_name: str) -> dict:
    """
    company_slug: 'openai' from crunchbase.com/organization/openai
    """
    with DDGS() as ddgs:
        results = list(ddgs.text(
            f"{company_name} site:crunchbase.com/organization",
            max_results=3
        ))
    
    cb_results = [r for r in results 
                  if 'crunchbase.com/organization' in r['href']]
    
    if not cb_results:
        return {"found": False, "source": "crunchbase"}
    
    cb_url = cb_results[0]['href']
    app = FirecrawlApp(api_key=FIRECRAWL_KEY)
    
    result = app.scrape_url(cb_url)

    funding_url = cb_url + "/funding_rounds"
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
    resp = llm_extract(prompt)
    print(resp)
    return resp


def comprehensive_news_search(company_name: str, topics: list[str],from_year : str,to_year: str) -> dict:
    """
    Searches multiple angles using DDG news search.
    Covers what Tavily was doing across multiple agents.
    """
    results = {}
    
    search_map = {
        "funding0":      f"{company_name} funding raised Series investment {from_year} {to_year}",
        "revenue":      f"{company_name} revenue ARR growth annual",
        "legal":        f"{company_name} lawsuit legal investigation penalty",
        "product":      f"{company_name} product launch feature update",
        "leadership":   f"{company_name} CEO founder executive hire",
        "competitors":  f"{company_name} competitor vs alternative",
        "customers":    f"{company_name} customer case study win deal",
        "layoffs":      f"{company_name} layoffs fired employees cut",
        "funding1":     f"{company_name} raises million Series",
        "funding2":     f"{company_name} valuation investment",
        "funding3":     f"{company_name} funding raised Series investment {from_year} {to_year}",
        "hiring_news": f"{company_name} \"hiring freeze\" OR \"expanding team\" OR \"adding jobs\"",
        "stealth_signals": f"{company_name} \"new division\" OR \"secret project\" OR \"R&D\" hiring"
    }
    
    # Only run the topics requested
    active_searches = {k: v for k, v in search_map.items() 
                       if k in topics}
    
    with DDGS() as ddgs:
        for topic, query in active_searches.items():
            try:
                news_results = list(ddgs.news(query, max_results=5))
                text_results = list(ddgs.text(query, max_results=5))
                results[topic] = news_results + text_results
            except Exception as e:
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
    return llm_extract(prompt)

def job_postings_analyzer_company(company_name: str, company_website:str,company_slug:str) -> dict:
    
    # Step 1: Scrape their own careers page with Playwright (JS-heavy usually)
    careers_paths = ["/careers", "/jobs", "/about/careers", "/work-with-us"]
    careers_content = ""
    print("running job_postings_analyzer_company")
    for path in careers_paths:
        result = scrape_url_sync(company_website + path)
        if result['text'] and len(result['text']) > 300:
            careers_content = result['text']
            break
    
    # Step 2: DDG search for LinkedIn job postings (public, no auth)
    with DDGS() as ddgs:
        linkedin_jobs = list(ddgs.text(
            f"{company_name} jobs hiring site:linkedin.com/jobs",
            max_results=10
        ))
        
        # Also search Indeed as a second source
        indeed_jobs = list(ddgs.text(
            f"{company_name} jobs site:indeed.com",
            max_results=5
        ))
    
    # Step 3: DDG news for hiring signals
    with DDGS() as ddgs:
        hiring_news = list(ddgs.news(
            f"{company_name} hiring expanding team 2024 2025",
            max_results=5
        ))
    
    # Step 4: LLM synthesizes everything
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
    
    return llm_extract(prompt)

def job_postings_analyzer_ats(company_slug: str, ats_type: str = "greenhouse") -> dict:
    """
    Pulls and analyzes job data from Greenhouse or Lever.
    ats_type must be either 'greenhouse' or 'lever'.
    """
    if ats_type.lower() == "greenhouse":
        url = f"https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs?content=true"
    elif ats_type.lower() == "lever":
        url = f"https://api.lever.co/v0/postings/{company_slug}?mode=json"
    else:
        return {"error": "Unsupported ATS. Choose 'greenhouse' or 'lever'."}

    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return {"error": f"Failed to fetch data. Status code: {response.status_code}. Make sure the slug is correct."}
        
        jobs = response.json()
        
        # Greenhouse nests jobs under a 'jobs' key; Lever returns a flat list.
        if ats_type == "greenhouse":
            jobs = jobs.get("jobs", [])
            
    except Exception as e:
        return {"error": str(e)}

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

    for job in jobs:
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

    prompt = f"""
    Analyze hiring signals for {company_slug}:
    
    {ats_type} content:
    Total Open Roles": metrics["total_roles"],
        Remote vs Onsite": 
            "Remote": {metrics["remote_count"]},
            "Onsite/Hybrid": {metrics["total_roles"] - metrics["remote_count"]}
        ,
        "Seniority Distribution": {metrics["seniority"]},
        "Top 5 Departments": {dict(metrics["departments"].most_common(5))},
        "Top Tech Stack Signals": {dict(metrics["tech_signals"].most_common(5))}

        Extract and infer:
        1. Total open roles (approximate)
        2. Roles by department (engineering / sales / marketing / ops / support)
        3. Seniority distribution (senior-heavy vs junior-heavy)
        4. Tech stack signals from job descriptions
        5. Remote vs onsite split
        6. layoffs fired employees cut
        Return as JSON with a confidence level.
"""

    # Format the final output
    return llm_extract(prompt)


def get_company_details(company_name: str) -> dict:
    """
    Searches for a company's website and attempts to classify its business domain.
    """
    print(f"Searching for: {company_name}...")
    
    # 1. Generate slug
    slug = company_name.lower().strip()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s-]+', '-', slug)
    
    # 2. Define domain keyword maps
    domain_keywords = {
        "SaaS / Software": ["saas", "software as a service", "b2b software", "cloud software", "platform as a service", "enterprise software"],
        "FinTech": ["fintech", "financial technology", "payment processing", "banking app", "digital wallet", "lending platform"],
        "Financial Services": ["banking", "investment", "wealth management", "insurance", "hedge fund", "asset management", "credit union"],
        "E-Commerce": ["e-commerce", "ecommerce", "online retail", "marketplace", "direct-to-consumer", "dtc", "shopify"],
        "Healthcare / HealthTech": ["healthcare", "healthtech", "medical device", "biotech", "telemedicine", "pharmaceutical"],
        "Artificial Intelligence": ["artificial intelligence", "generative ai", "machine learning", "llm", "deep learning", "ai platform"]
    }
    
    try:
        with DDGS() as ddgs:
            # Look for official site and general descriptions
            search_query = f"{company_name} company profile industry overview description"
            search_results = list(ddgs.text(search_query, max_results=15,backend="duckduckgo"))
            
        if not search_results:
            return {"company_name": company_name, "domain": "Unknown", "company_slug": slug}
        # The first result usually contains the main website
        company_website = find_best_website(search_results,company_name)
        
        # Combine all result snippets into one block of text to scan for keywords
        combined_text = " ".join([result.get('body', '').lower() for result in search_results])
        
        # 3. Match text against domain categories
        detected_domains = []
        for domain, keywords in domain_keywords.items():
            for keyword in keywords:
                if re.search(r'\b' + re.escape(keyword) + r'\b', combined_text):
                    detected_domains.append(domain)
                    break # Move to next domain category if a keyword matches
        
        # Fallback if no specific keywords match
        final_domain = detected_domains[0] if detected_domains else "General Technology / Other"
        
        return {
            "company_name": company_name,
            "company_website": company_website,
            "company_slug": slug,
            "detected_domain": final_domain,
            "all_matching_signals": detected_domains
        }
            
    except Exception as e:
        return {"error": str(e)}
def find_best_website(search_results, company_name):
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
            
        # 3. Check if the domain at least contains the name
        elif clean_name in domain:
            score += 50
            
        # 4. Check if the name is just somewhere in the URL string
        elif clean_name in url.lower():
            score += 10

        # Update the max score and best link if this one is better
        if score > max_score:
            max_score = score
            best_link = url
    # Return the highest scoring link (returns None if the list was empty)
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
    Return: {{ range_low, range_high, confidence, reasoning }}z
    """
# add reasoning call here before sending out

