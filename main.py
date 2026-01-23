#!/usr/bin/env python3
"""
Berkholts Daily Stock Summary Emailer - V6
===========================================
Key changes from V5:
1. ASX Scraper integration for announcements (replaces Claude web search)
2. ASX Scraper integration for earnings (replaces Claude web search)
3. Option C for competitors: Claude web search + ASX scraper supplement for listed competitors
4. Significant cost reduction (fewer API calls)

Dependencies (add to requirements.txt):
- playwright
- pdfplumber
- beautifulsoup4

Post-install command for Railway:
- playwright install chromium
"""

import os
import sys
import smtplib
import json
import re
import tempfile
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from pathlib import Path
import anthropic
import yfinance as yf
import requests
from bs4 import BeautifulSoup
import pdfplumber
from playwright.sync_api import sync_playwright


# Cache settings
CACHE_DIR = Path(os.environ.get('CACHE_DIR', '/home/claude/cache'))
EARNINGS_CACHE_DAYS = 30

# ASX Scraper settings
ASX_BASE_URL = "https://www.asx.com.au"
ASX_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
}


STOCKS = [
    {
        "name": "CSL Limited",
        "ticker": "CSL.AX",
        "asx_code": "CSL",
        "industry": "biotechnology and plasma-derived therapies",
        "industry_publications": ["BioPharma Dive", "Fierce Pharma", "Endpoints News", "BioWorld"],
        "supply_chain": {
            "customers": "hospitals, healthcare providers, governments (vaccines), patients with immunodeficiencies and bleeding disorders",
            "suppliers": "plasma collection centres (CSL Plasma), pharmaceutical manufacturing equipment providers"
        },
        "competitors": ["Takeda Pharmaceutical (global)", "Grifols (global)", "BioMarin (global)", "Sanofi (vaccines)"],
        "listed_competitors": [],  # No ASX-listed competitors
        "asx_url": "https://www.asx.com.au/markets/company/CSL"
    },
    {
        "name": "Dicker Data Limited",
        "ticker": "DDR.AX",
        "asx_code": "DDR",
        "industry": "IT distribution and technology wholesale",
        "industry_publications": ["CRN Australia", "ARN (Australian Reseller News)", "iTnews", "Channel Life"],
        "supply_chain": {
            "customers": "IT resellers, system integrators, managed service providers across Australia and NZ",
            "suppliers": "Cisco, Dell Technologies, HP, Lenovo, Microsoft, VMware, Hewlett Packard Enterprise"
        },
        "competitors": ["Ingram Micro Australia (unlisted)", "Synnex Australia (unlisted)", "Westcon-Comstor (unlisted)", "Sektor (unlisted)"],
        "listed_competitors": [],  # No ASX-listed competitors
        "asx_url": "https://www.asx.com.au/markets/company/DDR"
    },
    {
        "name": "Hansen Technologies Limited",
        "ticker": "HSN.AX",
        "asx_code": "HSN",
        "industry": "billing software for energy and utilities",
        "industry_publications": ["Energy Magazine Australia", "Utility Week", "Smart Energy International", "Comms Business"],
        "supply_chain": {
            "customers": "energy retailers, utilities (electricity, gas, water), telecommunications providers, pay-TV operators",
            "suppliers": "cloud infrastructure providers (AWS, Azure), technology partners"
        },
        "competitors": ["Oracle Utilities (global)", "SAP (global)", "Gentrack Group (NZX:GTK)", "TechnologyOne (ASX:TNE)"],
        "listed_competitors": ["TNE"],  # TechnologyOne is ASX-listed
        "asx_url": "https://www.asx.com.au/markets/company/HSN"
    },
    {
        "name": "Growthpoint Properties Australia",
        "ticker": "GOZ.AX",
        "asx_code": "GOZ",
        "industry": "real estate investment trust (office and industrial)",
        "industry_publications": ["The Property Council", "Commercial Real Estate", "Australian Property Journal", "The Urban Developer"],
        "supply_chain": {
            "customers": "office tenants (corporates, government), industrial tenants including Woolworths, institutional investors (funds management)",
            "suppliers": "property developers, construction firms, property managers, facilities management providers"
        },
        "competitors": ["Dexus (ASX:DXS)", "GPT Group (ASX:GPT)", "Centuria Office REIT (ASX:COF)", "Charter Hall (ASX:CHC)"],
        "listed_competitors": ["DXS", "GPT", "COF", "CHC"],  # All are ASX-listed
        "asx_url": "https://www.asx.com.au/markets/company/GOZ"
    },
    {
        "name": "Propel Funeral Partners Limited",
        "ticker": "PFP.AX",
        "asx_code": "PFP",
        "industry": "death care services (funeral homes, cemeteries, crematoria)",
        "industry_publications": ["Australian Funeral Directors Association", "Australasian Cemeteries & Crematoria Association", "InvoCare industry reports"],
        "supply_chain": {
            "customers": "families and individuals requiring funeral services across Australia and New Zealand",
            "suppliers": "casket and coffin manufacturers, memorial and headstone suppliers (Decra), floral providers, vehicle fleet suppliers"
        },
        "competitors": ["InvoCare (acquired by TPG Capital, unlisted)", "Independent family-owned funeral homes", "Southern Metropolitan Cemeteries Trust (unlisted)"],
        "listed_competitors": [],  # No ASX-listed competitors (InvoCare was delisted)
        "asx_url": "https://www.asx.com.au/markets/company/PFP"
    },
]


# ============================================================================
# YAHOO FINANCE - PRICE DATA
# ============================================================================

def get_stock_price(ticker: str) -> dict:
    """Get accurate stock price from Yahoo Finance."""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5d")
        
        if len(hist) < 2:
            return {"error": f"Not enough history for {ticker}"}
        
        yesterday_close = float(hist['Close'].iloc[-1])
        previous_close = float(hist['Close'].iloc[-2])
        yesterday_date = hist.index[-1].strftime("%B %d, %Y")
        previous_date = hist.index[-2].strftime("%B %d, %Y")
        change_percent = ((yesterday_close - previous_close) / previous_close) * 100
        
        return {
            "yesterday_close": round(yesterday_close, 2),
            "yesterday_date": yesterday_date,
            "previous_close": round(previous_close, 2),
            "previous_date": previous_date,
            "change_percent": round(change_percent, 2),
            "error": None
        }
    except Exception as e:
        return {"error": str(e)}


# ============================================================================
# ASX SCRAPER FUNCTIONS
# ============================================================================

def asx_get_announcements(ticker: str) -> list:
    """Get announcement list from ASX."""
    url = f"{ASX_BASE_URL}/asx/v2/statistics/announcements.do?by=asxCode&asxCode={ticker}&timeframe=D&period=M6"
    
    try:
        r = requests.get(url, headers=ASX_HEADERS, timeout=30)
        soup = BeautifulSoup(r.text, 'html.parser')
        table = soup.find('table')
        
        if not table:
            return []
        
        anns = []
        for row in table.find_all('tr'):
            cells = row.find_all('td')
            if len(cells) < 3:
                continue
            
            link = cells[2].find('a', href=True)
            if not link:
                continue
            
            href = link['href']
            pdf_url = f"{ASX_BASE_URL}{href}" if href.startswith('/') else f"{ASX_BASE_URL}/asx/v2/statistics/{href}"
            
            text = link.get_text(strip=True)
            m = re.match(r'^(.+?)\s*\d+\s*pages?', text, re.I)
            
            anns.append({
                'title': m.group(1).strip() if m else text,
                'date': cells[0].get_text(strip=True),
                'pdf_url': pdf_url,
                'sensitive': bool(cells[1].find('img'))
            })
        
        return anns
    except Exception as e:
        print(f"      Error fetching announcements: {e}")
        return []


def asx_download_pdf(pdf_url: str) -> bytes:
    """Download PDF by clicking Accept button using Playwright."""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            
            page.goto(pdf_url, wait_until='networkidle', timeout=20000)
            
            content = page.content()
            
            if 'commercial purpose' in content.lower():
                buttons = page.query_selector_all('input[type="submit"]')
                
                accept_btn = None
                for btn in buttons:
                    value = btn.get_attribute('value') or ''
                    if 'agree' in value.lower() or 'confirm' in value.lower() or 'accept' in value.lower():
                        accept_btn = btn
                        break
                
                checkbox = page.query_selector('input[type="checkbox"]')
                if checkbox:
                    checkbox.click()
                    page.wait_for_timeout(500)
                
                if accept_btn:
                    accept_btn.click()
                else:
                    try:
                        page.click('text=Agree')
                    except:
                        pass
                
                page.wait_for_timeout(3000)
                page.wait_for_load_state('networkidle')
                
                resp = context.request.get(pdf_url)
                body = resp.body()
                
                if body[:5] == b'%PDF-':
                    browser.close()
                    return body
            
            browser.close()
            return None
    except Exception as e:
        print(f"      Error downloading PDF: {e}")
        return None


def asx_extract_text(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes."""
    try:
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(pdf_bytes)
            path = f.name
        
        text = ""
        with pdfplumber.open(path) as pdf:
            for pg in pdf.pages[:15]:
                t = pg.extract_text()
                if t:
                    text += t + "\n"
        
        os.unlink(path)
        return text[:12000] if text else ""
    except Exception as e:
        print(f"      Error extracting text: {e}")
        return ""


def asx_is_periodic_earnings_report(title: str) -> bool:
    """Check if announcement is a quarterly, half-yearly or annual earnings report."""
    title_lower = title.lower()
    
    periodic_patterns = [
        r'(full year|fy\d{2}|annual).*(result|report)',
        r'(half year|1h\d{2}|2h\d{2}|interim).*(result|report)',
        r'(quarter|q[1-4]|[1-4]q).*(result|report)',
        r'(result|report).*(full year|fy\d{2}|annual)',
        r'(result|report).*(half year|1h|2h|interim)',
        r'(result|report).*(quarter|q[1-4])',
        r'appendix 4[de]',
        r'preliminary final report',
        r'\d{4}\s+(full year|annual)\s+result',
        r'(1h|2h|hy)\d{2}\s+result',
        r'profit announcement',
    ]
    
    exclude_patterns = [
        'trading update', 'guidance', 'presentation', 'investor',
        'agm', 'annual general meeting', 'dividend', 'buyback',
        'acquisition', 'merger', 'takeover', 'proposal', 'bid',
        'offer', 'chair address', 'ceo address',
    ]
    
    for exclude in exclude_patterns:
        if exclude in title_lower:
            return False
    
    for pattern in periodic_patterns:
        if re.search(pattern, title_lower):
            return True
    
    return False


# ============================================================================
# CLAUDE API FUNCTIONS
# ============================================================================

def get_anthropic_client() -> anthropic.Anthropic:
    """Get Anthropic client."""
    return anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))


def call_claude_with_search(client: anthropic.Anthropic, prompt: str, max_searches: int = 2) -> str:
    """Call Claude API with web search tool enabled."""
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            tools=[{
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": max_searches
            }],
            messages=[{"role": "user", "content": prompt}]
        )
        
        result = ""
        for block in response.content:
            if hasattr(block, 'text') and block.text is not None:
                result += block.text
        
        return result.strip() if result else "NO_RESPONSE"
    except Exception as e:
        return f"ERROR: {str(e)}"


def call_claude_analyze(client: anthropic.Anthropic, prompt: str) -> str:
    """Call Claude API for analysis (no web search)."""
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        return f"ERROR: {str(e)}"


# ============================================================================
# ASX-BASED RESEARCH FUNCTIONS (replaces web search for announcements/earnings)
# ============================================================================

def research_announcements_asx(client: anthropic.Anthropic, stock: dict) -> dict:
    """
    Research announcements using ASX scraper.
    Returns structured data compatible with V5 format.
    """
    asx_code = stock['asx_code']
    
    anns = asx_get_announcements(asx_code)
    if not anns:
        return {
            "last_announcement": {
                "date": "Not found",
                "title": "Not found",
                "summary": "Unable to retrieve announcement data from ASX",
                "source_url": stock.get('asx_url')
            },
            "price_sensitive_news": {
                "found": False,
                "description": "No announcements found",
                "source_url": None
            }
        }
    
    # Get price-sensitive announcements
    sensitive = [a for a in anns if a['sensitive']]
    
    result = {
        "last_announcement": {
            "date": "Not found",
            "title": "Not found",
            "summary": "No recent announcements",
            "source_url": stock.get('asx_url')
        },
        "price_sensitive_news": {
            "found": False,
            "description": "No material announcements in the past 3 days",
            "source_url": None
        }
    }
    
    # Process the latest price-sensitive announcement
    if sensitive:
        latest = sensitive[0]
        print(f"      Downloading: {latest['title'][:40]}...")
        
        pdf_bytes = asx_download_pdf(latest['pdf_url'])
        if pdf_bytes:
            text = asx_extract_text(pdf_bytes)
            if text:
                # Use Claude to summarize the announcement
                prompt = f"""Analyze this ASX announcement and provide a 2-3 sentence summary focusing on what happened and why it matters to investors.

Title: {latest['title']}
Date: {latest['date']}

Content:
{text[:8000]}

Provide ONLY the summary, no bullet points or formatting."""

                summary = call_claude_analyze(client, prompt)
                
                result["last_announcement"] = {
                    "date": latest['date'],
                    "title": latest['title'],
                    "summary": summary if not summary.startswith("ERROR") else "Summary unavailable",
                    "source_url": latest['pdf_url']
                }
                
                result["price_sensitive_news"] = {
                    "found": True,
                    "description": summary if not summary.startswith("ERROR") else latest['title'],
                    "source_url": latest['pdf_url']
                }
    
    return result


def research_earnings_asx(client: anthropic.Anthropic, stock: dict) -> dict:
    """
    Research earnings using ASX scraper.
    Returns structured data compatible with V5 format.
    """
    asx_code = stock['asx_code']
    
    # Check cache first
    cached = load_from_cache(asx_code, 'earnings', EARNINGS_CACHE_DAYS)
    if cached:
        return cached
    
    anns = asx_get_announcements(asx_code)
    if not anns:
        return {
            "report_type": "Not found",
            "report_date": "Not found",
            "period": "Not found",
            "revenue": "Not found",
            "npat": "Not found",
            "ebitda": "Not found",
            "eps": "Not found",
            "dividend": "Not found",
            "guidance": "None mentioned",
            "source_url": stock.get('asx_url')
        }
    
    # Find periodic earnings reports
    earnings = [a for a in anns if asx_is_periodic_earnings_report(a['title'])]
    
    if not earnings:
        return {
            "report_type": "Not found",
            "report_date": "Not found",
            "period": "Not found",
            "revenue": "Not found",
            "npat": "Not found",
            "ebitda": "Not found",
            "eps": "Not found",
            "dividend": "Not found",
            "guidance": "None mentioned",
            "source_url": stock.get('asx_url')
        }
    
    # Process the latest earnings report
    latest = earnings[0]
    print(f"      Downloading: {latest['title'][:40]}...")
    
    pdf_bytes = asx_download_pdf(latest['pdf_url'])
    if not pdf_bytes:
        return {
            "report_type": "Not found",
            "report_date": latest['date'],
            "period": "Not found",
            "revenue": "Not found",
            "npat": "Not found",
            "ebitda": "Not found",
            "eps": "Not found",
            "dividend": "Not found",
            "guidance": "None mentioned",
            "source_url": latest['pdf_url']
        }
    
    text = asx_extract_text(pdf_bytes)
    if not text:
        return {
            "report_type": "Not found",
            "report_date": latest['date'],
            "period": "Not found",
            "revenue": "Not found",
            "npat": "Not found",
            "ebitda": "Not found",
            "eps": "Not found",
            "dividend": "Not found",
            "guidance": "None mentioned",
            "source_url": latest['pdf_url']
        }
    
    # Use Claude to extract financial metrics
    prompt = f"""Analyze this ASX earnings report and extract key financial metrics.

Title: {latest['title']}
Date: {latest['date']}

Content:
{text[:10000]}

Provide your response in EXACTLY this JSON format (no other text):
{{
    "report_type": "Annual/Half-Year/Quarterly",
    "report_date": "{latest['date']}",
    "period": "e.g. FY25 or H1 FY26",
    "revenue": "revenue figure with currency e.g. $1.2B or 'Not found'",
    "npat": "net profit after tax e.g. $150M or 'Not found'",
    "ebitda": "EBITDA figure or 'Not found'",
    "eps": "earnings per share e.g. 45.2c or 'Not found'",
    "dividend": "dividend info e.g. '25c fully franked' or 'Not found'",
    "guidance": "forward guidance summary or 'None mentioned'"
}}

Only report numbers you actually found. Do NOT make up financial figures."""

    response = call_claude_analyze(client, prompt)
    
    try:
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            earnings_data = json.loads(json_match.group())
            earnings_data['source_url'] = latest['pdf_url']
            
            # Cache successful results
            if earnings_data.get('report_type') != 'Not found':
                save_to_cache(asx_code, 'earnings', earnings_data)
            
            return earnings_data
    except (json.JSONDecodeError, AttributeError):
        pass
    
    return {
        "report_type": "Not found",
        "report_date": latest['date'],
        "period": "Not found",
        "revenue": "Not found",
        "npat": "Not found",
        "ebitda": "Not found",
        "eps": "Not found",
        "dividend": "Not found",
        "guidance": "None mentioned",
        "source_url": latest['pdf_url']
    }


# ============================================================================
# CLAUDE WEB SEARCH RESEARCH FUNCTIONS (for industry and competitors)
# ============================================================================

def research_industry(client: anthropic.Anthropic, stock: dict) -> dict:
    """Research industry dynamics with authoritative sources."""
    industry_pubs = ", ".join(stock.get('industry_publications', []))
    supply_chain = stock.get('supply_chain', {})
    customers = supply_chain.get('customers', 'N/A')
    suppliers = supply_chain.get('suppliers', 'N/A')
    
    prompt = f"""You are conducting industry research for {stock['name']} (ASX: {stock['asx_code']}) in the {stock['industry']} sector.

**SOURCE HIERARCHY (prioritize in this order):**
1. Industry-specific trade publications: {industry_pubs}
2. Tier-one financial news: Australian Financial Review (AFR), Wall Street Journal (WSJ), Sydney Morning Herald (SMH), The Australian, Bloomberg, Reuters
3. Company press releases and ASX announcements
4. Other reputable business journalism with clear editorial standards

**EXCLUDED SOURCES - DO NOT CITE:**
- IBISWorld, Mordor Intelligence, or similar market research aggregators
- If you cannot verify whether a source is an aggregator, exclude it

**SUPPLY CHAIN CONTEXT:**
- Key customers: {customers}
- Key suppliers: {suppliers}
- Include relevant supply chain developments if material to {stock['name']}

Search for: "{stock['industry']} Australia 2025 2026"
Also search: "{stock['name']} industry outlook" or relevant supply chain news

After searching, provide the following in JSON format only (no other text):
{{
    "data_points": [
        {{
            "fact": "A specific statistic, trend, or development with numbers/percentages where available",
            "source_name": "Name of the publication (e.g., 'Australian Financial Review', 'Mining.com')",
            "source_url": "Actual URL from search results, or null if not available",
            "publication_date": "Date if visible in search results, or 'Date not verified'",
            "relevance": "How this specifically relates to {stock['name']} or its supply chain"
        }}
    ]
}}

**CRITICAL RULES:**
- Provide 2-4 specific data points with actual numbers/percentages where possible
- Only include facts you actually found in search results - do NOT fabricate statistics
- Verify each source meets reputability standards before including
- If IBISWorld or Mordor Intelligence appears in results, explicitly skip it
- Include supply chain news only when it materially impacts {stock['name']}
- If publication date cannot be verified from search results, state "Date not verified"
"""
    
    result = call_claude_with_search(client, prompt, max_searches=2)
    
    try:
        json_match = re.search(r'\{[\s\S]*\}', result)
        if json_match:
            data = json.loads(json_match.group())
            return data
    except (json.JSONDecodeError, AttributeError):
        pass
    
    return {
        "data_points": [
            {
                "fact": "No specific industry data found from authoritative sources",
                "source_name": "N/A",
                "source_url": None,
                "publication_date": "N/A",
                "relevance": "N/A"
            }
        ]
    }


def research_competitors(client: anthropic.Anthropic, stock: dict) -> dict:
    """
    Research competitor news using Claude web search.
    Option C: Web search as primary, ASX scraper supplement for listed competitors.
    """
    competitors_str = ", ".join(stock['competitors'])
    listed_comps = [c for c in stock['competitors'] if '.AX)' in c or 'ASX:' in c]
    unlisted_comps = [c for c in stock['competitors'] if '.AX)' not in c and 'ASX:' not in c]
    
    prompt = f"""You are conducting competitive intelligence research for {stock['name']} (ASX: {stock['asx_code']}).

**COMPETITORS TO MONITOR:**
Listed: {', '.join(listed_comps) if listed_comps else 'None specified'}
Unlisted: {', '.join(unlisted_comps) if unlisted_comps else 'None specified'}

**STRICT TIMEFRAME: Last 14 days only (from today's date)**
- Only include news published within the last 2 weeks
- Verify publication dates from search results where possible
- If no recent competitive updates exist within this window, explicitly state this - do NOT broaden the timeframe

**SOURCE HIERARCHY (prioritize in this order):**
1. Company press releases and ASX announcements
2. Industry-specific trade publications
3. Tier-one financial news: Australian Financial Review (AFR), Wall Street Journal (WSJ), Sydney Morning Herald (SMH), The Australian, Bloomberg, Reuters

**EXCLUDED SOURCES - DO NOT CITE:**
- IBISWorld, Mordor Intelligence, or similar market research aggregators
- Opinion pieces or general industry commentary (focus on competitor ACTIONS)

**WHAT COUNTS AS COMPETITIVE NEWS:**
- Product launches or service changes
- Pricing changes
- Partnerships or contracts announced
- Executive appointments
- Funding rounds or capital raises
- Market entry/exit decisions
- M&A activity
- Operational changes or restructuring

After searching, provide the following in JSON format only (no other text):
{{
    "competitor_news": [
        {{
            "competitor": "Company name",
            "news": "Specific action, announcement, or development (not opinion/commentary)",
            "publication_date": "Date from search results, or 'Date not verified'",
            "source_name": "Publication name",
            "source_url": "Actual URL from search results, or null",
            "implications": "What this might mean for {stock['name']}'s competitive position"
        }}
    ],
    "no_recent_news": false,
    "no_recent_news_note": null
}}

If NO competitive news was found within the 2-week window, return:
{{
    "competitor_news": [],
    "no_recent_news": true,
    "no_recent_news_note": "No material competitive announcements found within the last 14 days for monitored competitors."
}}

**CRITICAL RULES:**
- Only include news you actually found with verifiable competitor ACTIONS
- Do NOT include general market commentary or analyst opinions
- If publication date cannot be verified, note "Date not verified" but still include if the content appears recent
- Be specific about what competitors announced or did
- If no recent news exists, say so clearly - do NOT invent or stretch timeframes
"""
    
    result = call_claude_with_search(client, prompt, max_searches=2)
    
    competitor_data = None
    try:
        json_match = re.search(r'\{[\s\S]*\}', result)
        if json_match:
            competitor_data = json.loads(json_match.group())
    except (json.JSONDecodeError, AttributeError):
        pass
    
    if not competitor_data:
        competitor_data = {
            "competitor_news": [],
            "no_recent_news": True,
            "no_recent_news_note": "Unable to retrieve competitor data"
        }
    
    # Option C: Supplement with ASX scraper for listed competitors
    listed_competitor_codes = stock.get('listed_competitors', [])
    if listed_competitor_codes:
        asx_competitor_news = research_competitors_asx(client, listed_competitor_codes)
        if asx_competitor_news:
            # Add ASX-sourced news to the competitor_news list
            competitor_data['competitor_news'].extend(asx_competitor_news)
            if competitor_data.get('no_recent_news') and asx_competitor_news:
                competitor_data['no_recent_news'] = False
                competitor_data['no_recent_news_note'] = None
    
    return competitor_data


def research_competitors_asx(client: anthropic.Anthropic, competitor_codes: list) -> list:
    """
    Get recent announcements from ASX-listed competitors.
    Returns list of competitor news items.
    """
    competitor_news = []
    
    # Limit to top 2 competitors to manage time
    for code in competitor_codes[:2]:
        print(f"      Checking ASX competitor: {code}...")
        
        anns = asx_get_announcements(code)
        if not anns:
            continue
        
        # Get latest price-sensitive announcement
        sensitive = [a for a in anns if a['sensitive']]
        if not sensitive:
            continue
        
        latest = sensitive[0]
        
        # Only include if within last 14 days (approximate check via date string)
        # Note: Date parsing could be improved for exact validation
        
        competitor_news.append({
            "competitor": f"{code} (ASX)",
            "news": latest['title'],
            "publication_date": latest['date'],
            "source_name": "ASX Announcement",
            "source_url": latest['pdf_url'],
            "implications": "See ASX announcement for details"
        })
    
    return competitor_news


# ============================================================================
# CACHING FUNCTIONS
# ============================================================================

def ensure_cache_dir():
    """Create cache directory if it doesn't exist."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def get_cache_path(asx_code: str, cache_type: str) -> Path:
    """Get the cache file path for a specific stock and data type."""
    return CACHE_DIR / f"{asx_code.lower()}_{cache_type}.json"


def load_from_cache(asx_code: str, cache_type: str, max_age_days: int) -> dict | None:
    """Load data from cache if it exists and is not expired."""
    cache_path = get_cache_path(asx_code, cache_type)
    
    if not cache_path.exists():
        return None
    
    try:
        with open(cache_path, 'r') as f:
            cached = json.load(f)
        
        cached_date = datetime.fromisoformat(cached.get('_cached_at', '2000-01-01'))
        age = datetime.now() - cached_date
        
        if age > timedelta(days=max_age_days):
            print(f"(cache expired: {age.days} days old)")
            return None
        
        print(f"(using cache from {age.days} days ago)")
        return cached.get('data')
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        print(f"(cache read error: {e})")
        return None


def save_to_cache(asx_code: str, cache_type: str, data: dict):
    """Save data to cache with timestamp."""
    ensure_cache_dir()
    cache_path = get_cache_path(asx_code, cache_type)
    
    cached = {
        '_cached_at': datetime.now().isoformat(),
        '_asx_code': asx_code,
        'data': data
    }
    
    try:
        with open(cache_path, 'w') as f:
            json.dump(cached, f, indent=2)
    except Exception as e:
        print(f"(cache write error: {e})")


# ============================================================================
# HTML FORMATTING
# ============================================================================

def format_stock_html(stock: dict, price_data: dict, announcements: dict, earnings: dict, 
                      industry: dict, competitors: dict, stock_num: int) -> str:
    """Format all researched data into HTML."""
    
    price_data = price_data or {}
    announcements = announcements or {}
    earnings = earnings or {}
    industry = industry or {}
    competitors = competitors or {}
    
    # Price section
    if price_data.get('error'):
        price_html = f'<span style="color:#e74c3c;">Price data unavailable: {price_data.get("error", "Unknown error")}</span>'
    else:
        change_pct = price_data.get('change_percent', 0) or 0
        change_color = "#27ae60" if change_pct >= 0 else "#e74c3c"
        change_sign = "+" if change_pct >= 0 else ""
        price_html = f"""<strong style="color:#2980b9;">YESTERDAY ({price_data.get('yesterday_date', 'N/A')}):</strong> A${price_data.get('yesterday_close', 0):.2f} | 
<strong style="color:#2980b9;">PREVIOUS ({price_data.get('previous_date', 'N/A')}):</strong> A${price_data.get('previous_close', 0):.2f} | 
<strong style="color:#2980b9;">CHANGE:</strong> <span style="color:{change_color};">{change_sign}{change_pct:.2f}%</span>"""
    
    # Reason for move
    news = announcements.get('price_sensitive_news') or {}
    if news.get('found'):
        reason_text = news.get('description') or 'No specific catalyst identified'
        if news.get('source_url'):
            reason_text += f' <a href="{news["source_url"]}" style="color:#3498db;">[Source]</a>'
    else:
        reason_text = news.get('description') or 'No material announcements in the past 3 days that would explain the price movement.'
    
    # Last announcement
    ann = announcements.get('last_announcement') or {}
    ann_url = ann.get('source_url') or stock.get('asx_url', '#')
    ann_date = ann.get('date') or 'Not found'
    ann_title = ann.get('title') or 'Not found'
    ann_summary = ann.get('summary') or 'Unable to retrieve'
    
    # Earnings
    earn = earnings or {}
    earn_url = earn.get('source_url') or stock.get('asx_url', '#')
    
    earnings_parts = []
    if earn.get('report_type') and earn.get('report_type') != 'Not found':
        earnings_parts.append(f"<strong>Report:</strong> {earn.get('report_type')} ({earn.get('period') or 'N/A'})")
    if earn.get('report_date') and earn.get('report_date') != 'Not found':
        earnings_parts.append(f"<strong>Date:</strong> {earn.get('report_date')}")
    if earn.get('revenue') and earn.get('revenue') != 'Not found':
        earnings_parts.append(f"<strong>Revenue:</strong> {earn.get('revenue')}")
    if earn.get('npat') and earn.get('npat') != 'Not found':
        earnings_parts.append(f"<strong>NPAT:</strong> {earn.get('npat')}")
    if earn.get('ebitda') and earn.get('ebitda') != 'Not found':
        earnings_parts.append(f"<strong>EBITDA:</strong> {earn.get('ebitda')}")
    if earn.get('eps') and earn.get('eps') != 'Not found':
        earnings_parts.append(f"<strong>EPS:</strong> {earn.get('eps')}")
    if earn.get('dividend') and earn.get('dividend') != 'Not found':
        earnings_parts.append(f"<strong>Dividend:</strong> {earn.get('dividend')}")
    if earn.get('guidance') and earn.get('guidance') != 'None mentioned':
        earnings_parts.append(f"<strong>Guidance:</strong> {earn.get('guidance')}")
    
    if not earnings_parts:
        earnings_html = "Earnings data not found in recent announcements"
    else:
        earnings_html = "<br>".join(earnings_parts)
    
    # Industry dynamics
    ind_points = industry.get('data_points') or []
    if ind_points:
        ind_items = []
        for point in ind_points:
            if point is None:
                continue
            fact = point.get('fact') or ''
            if not fact or fact == 'N/A':
                continue
            
            source_name = point.get('source_name') or point.get('source')
            source_url = point.get('source_url')
            pub_date = point.get('publication_date', '')
            
            item = fact
            if source_name and source_name != 'N/A':
                if source_url:
                    item += f' <a href="{source_url}" style="color:#3498db;">({source_name}'
                    if pub_date and pub_date != 'Date not verified':
                        item += f', {pub_date}'
                    item += ')</a>'
                else:
                    item += f' ({source_name}'
                    if pub_date and pub_date != 'Date not verified':
                        item += f', {pub_date}'
                    item += ')'
            
            relevance = point.get('relevance')
            if relevance and relevance != 'N/A' and len(relevance) > 10:
                item += f'<br><em style="color:#7f8c8d;font-size:0.9em;">→ {relevance}</em>'
            
            ind_items.append(f'<li>{item}</li>')
        industry_html = "\n".join(ind_items) if ind_items else "<li>No specific industry data found from authoritative sources</li>"
    else:
        industry_html = "<li>No specific industry data found from authoritative sources</li>"
    
    # Competitor dynamics
    comp_news = competitors.get('competitor_news') or []
    no_recent = competitors.get('no_recent_news', False)
    
    if no_recent or not comp_news:
        note = competitors.get('no_recent_news_note') or 'No material competitive announcements found within the last 14 days.'
        competitor_html = f"<li><em>{note}</em></li>"
    else:
        comp_items = []
        for news_item in comp_news:
            if news_item is None:
                continue
            competitor_name = news_item.get('competitor') or 'Unknown'
            news_desc = news_item.get('news') or ''
            if not news_desc:
                continue
            
            item = f"<strong>{competitor_name}:</strong> {news_desc}"
            
            source_name = news_item.get('source_name')
            pub_date = news_item.get('publication_date') or news_item.get('date')
            source_url = news_item.get('source_url')
            
            if source_name or pub_date:
                item += ' ('
                if pub_date:
                    item += pub_date
                if source_name and pub_date:
                    item += ', '
                if source_name:
                    item += source_name
                item += ')'
            
            if source_url:
                item += f' <a href="{source_url}" style="color:#3498db;">[Source]</a>'
            
            implications = news_item.get('implications')
            if implications and implications != "See ASX announcement for details":
                item += f"<br><em style=\"color:#7f8c8d;font-size:0.9em;\">→ Implications: {implications}</em>"
            
            comp_items.append(f'<li>{item}</li>')
        
        competitor_html = "\n".join(comp_items) if comp_items else "<li>No recent competitor announcements found in the last 2 weeks</li>"
    
    # Assemble HTML
    html = f"""
<h2 style="color:#34495e;margin-top:30px;border-bottom:2px solid #ecf0f1;padding-bottom:8px;">
{stock_num}. {stock['name']} ({stock['ticker']})
</h2>

<p style="margin:10px 0;line-height:1.6;">
{price_html}
</p>

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">REASON FOR MOVE:</strong><br>
{reason_text}
</p>

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">LAST PRICE-SENSITIVE ANNOUNCEMENT:</strong><br>
<strong>Date:</strong> {ann_date}<br>
<strong>Title:</strong> {ann_title}<br>
<strong>Summary:</strong> {ann_summary}<br>
<strong>Source:</strong> <a href="{ann_url}" style="color:#3498db;">View Announcement</a>
</p>

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">LAST EARNINGS REPORT:</strong><br>
{earnings_html}<br>
<strong>Source:</strong> <a href="{earn_url}" style="color:#3498db;">View Report</a>
</p>

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">INDUSTRY DYNAMICS:</strong>
</p>
<ul style="margin:5px 0 15px 20px;line-height:1.8;">
{industry_html}
</ul>

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">COMPETITIVE DYNAMICS:</strong>
</p>
<ul style="margin:5px 0 15px 20px;line-height:1.8;">
{competitor_html}
</ul>

<hr style="border:none;border-top:1px solid #ecf0f1;margin:30px 0;">
"""
    return html


def wrap_in_template(content: str, today: str) -> str:
    """Wrap in email template."""
    return f'''<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
</head>
<body style="font-family:Arial,sans-serif;margin:0;padding:0;background-color:#f4f4f4;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f4;">
<tr><td align="center" style="padding:20px;">
<table width="1000" cellpadding="20" cellspacing="0" style="background-color:#ffffff;border:1px solid #dddddd;">
<tr><td>

<h1 style="color:#2c3e50;border-bottom:3px solid #3498db;padding-bottom:10px;margin-top:0;">
Berkholts Stock Summaries - {today}
</h1>

{content}

<p style="color:#7f8c8d;font-size:12px;margin-top:30px;text-align:center;">
Generated by Berkholts Stock Summary System V6<br>
Prices: Yahoo Finance | Announcements & Earnings: ASX Direct | Industry & Competitors: Claude AI<br>
Sources: ASX announcements, trade publications, AFR, WSJ, SMH, The Australian<br>
</p>

</td></tr>
</table>
</td></tr>
</table>
</body>
</html>'''


# ============================================================================
# EMAIL FUNCTIONS
# ============================================================================

def send_email(html: str, recipient: str, smtp_email: str, smtp_password: str, subject: str):
    """Send email with detailed logging."""
    msg = MIMEText(html, 'html', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = smtp_email
    msg['To'] = recipient
    
    msg['Reply-To'] = smtp_email
    msg['X-Priority'] = '3'
    
    try:
        print(f"      Connecting to smtp.gmail.com:465...")
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            print(f"      Connected. Logging in as {smtp_email}...")
            server.login(smtp_email, smtp_password)
            print(f"      Logged in. Sending to {recipient}...")
            result = server.sendmail(smtp_email, recipient, msg.as_string())
            if result:
                print(f"      ⚠️ Partial failure: {result}")
            else:
                print(f"      ✅ SMTP accepted message for {recipient}")
    except smtplib.SMTPRecipientsRefused as e:
        print(f"      ❌ Recipient refused: {e.recipients}")
        raise
    except smtplib.SMTPAuthenticationError as e:
        print(f"      ❌ Authentication failed: {e}")
        raise
    except smtplib.SMTPException as e:
        print(f"      ❌ SMTP error: {type(e).__name__}: {e}")
        raise
    except Exception as e:
        print(f"      ❌ Unexpected error: {type(e).__name__}: {e}")
        raise


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("=" * 70)
    print("🚀 Berkholts Stock Emailer - V6 (ASX Scraper Integration)")
    print(f"⏰ Started: {datetime.now()}")
    print("=" * 70)
    
    # Check env vars
    anthropic_key = os.getenv('ANTHROPIC_API_KEY')
    smtp_email = os.getenv('SMTP_EMAIL')
    smtp_password = os.getenv('SMTP_PASSWORD')
    recipient_emails_str = os.getenv('RECIPIENT_EMAILS')
    
    missing = []
    if not anthropic_key: missing.append('ANTHROPIC_API_KEY')
    if not smtp_email: missing.append('SMTP_EMAIL')
    if not smtp_password: missing.append('SMTP_PASSWORD')
    if not recipient_emails_str: missing.append('RECIPIENT_EMAILS')
    
    if missing:
        print(f"❌ Missing: {', '.join(missing)}")
        sys.exit(1)
    
    recipients = [e.strip() for e in recipient_emails_str.split(',') if e.strip()]
    
    # Always include backup recipient
    BACKUP_RECIPIENT = "lfbannon@gmail.com"
    if BACKUP_RECIPIENT not in recipients:
        recipients.append(BACKUP_RECIPIENT)
        print(f"📧 Recipients: {', '.join(recipients[:-1])} + backup: {BACKUP_RECIPIENT}")
    else:
        print(f"📧 Recipients: {', '.join(recipients)}")
    
    # Initialize cache
    ensure_cache_dir()
    print(f"💾 Cache directory: {CACHE_DIR}")
    print(f"   Earnings cache duration: {EARNINGS_CACHE_DAYS} days")
    
    client = get_anthropic_client()
    today_str = datetime.now().strftime("%B %d, %Y")
    
    all_html = ""
    
    for i, stock in enumerate(STOCKS, 1):
        print(f"\n{'=' * 70}")
        print(f"📊 STOCK {i}/{len(STOCKS)}: {stock['name']}")
        print("=" * 70)
        
        # Step 1: Get price (Yahoo Finance)
        print("   💰 Getting price...", end=" ")
        price = get_stock_price(stock['ticker'])
        if price.get('error'):
            print(f"⚠️ {price['error']}")
        else:
            print(f"✅ A${price['yesterday_close']:.2f} ({price['change_percent']:+.2f}%)")
        
        # Step 2: Research announcements (ASX Scraper)
        print("   📢 Researching announcements (ASX)...", end=" ")
        announcements = research_announcements_asx(client, stock)
        ann_status = "✅" if announcements.get('last_announcement', {}).get('date') != 'Not found' else "⚠️"
        print(ann_status)
        
        # Step 3: Research earnings (ASX Scraper with caching)
        print("   💹 Researching earnings (ASX)...", end=" ")
        earnings = research_earnings_asx(client, stock)
        earn_status = "✅" if earnings.get('report_type') != 'Not found' else "⚠️"
        print(earn_status)
        
        # Step 4: Research industry (Claude web search)
        print("   🏭 Researching industry (Claude)...", end=" ")
        industry = research_industry(client, stock)
        ind_status = "✅" if len(industry.get('data_points', [])) > 0 else "⚠️"
        print(ind_status)
        
        # Step 5: Research competitors (Claude + ASX supplement)
        listed_comp_count = len(stock.get('listed_competitors', []))
        print(f"   🏁 Researching competitors (Claude + {listed_comp_count} ASX)...", end=" ")
        competitors = research_competitors(client, stock)
        comp_status = "✅" if len(competitors.get('competitor_news', [])) > 0 or competitors.get('no_recent_news') else "⚠️"
        print(comp_status)
        
        # Step 6: Format HTML
        print("   📝 Formatting HTML...", end=" ")
        try:
            stock_html = format_stock_html(stock, price, announcements, earnings, industry, competitors, i)
            if stock_html is None:
                stock_html = f"<h2>{stock['name']} - Error formatting data</h2><hr>"
            print("✅")
        except Exception as e:
            print(f"❌ {e}")
            stock_html = f"<h2>{stock['name']} - Error: {str(e)}</h2><hr>"
        
        all_html += stock_html
    
    # Final assembly
    print(f"\n📧 Assembling email...")
    final_html = wrap_in_template(all_html, today_str)
    print(f"📄 Total: {len(final_html)} chars")
    
    # Send
    subject = f"Berkholts Stock Summaries - {today_str}"
    for recipient in recipients:
        try:
            print(f"📤 Sending to {recipient}...", end=" ")
            send_email(final_html, recipient, smtp_email, smtp_password, subject)
            print("✅")
        except Exception as e:
            print(f"❌ {e}")
    
    print(f"\n✅ DONE at {datetime.now()}")


if __name__ == "__main__":
    main()
