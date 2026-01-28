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
        "name": "AUB Group Limited",
        "ticker": "AUB.AX",
        "asx_code": "AUB",
        "industry": "insurance broking",
        "industry_publications": ["Insurance News Australia", "Insurance Business Australia", "Australasian Underwriting"],
        "supply_chain": {
            "customers": "SME businesses, corporate clients requiring insurance placement",
            "suppliers": "underwriters including Lloyd's syndicates, QBE, Allianz"
        },
        "competitors": ["Steadfast Group (ASX:SDF)", "PSC Insurance (ASX:PSI)", "Gallagher Australia (unlisted)", "Marsh McLennan (unlisted)"],
        "listed_competitors": ["SDF", "PSI"],
        "asx_url": "https://www.asx.com.au/markets/company/AUB"
    },
    {
        "name": "Mineral Resources Limited",
        "ticker": "MIN.AX",
        "asx_code": "MIN",
        "industry": "mining services and lithium production",
        "industry_publications": ["Mining.com", "Australian Mining", "Mining Weekly", "Fastmarkets"],
        "supply_chain": {
            "customers": "lithium buyers including battery manufacturers, iron ore offtakers",
            "suppliers": "mining equipment providers, crushing/processing contractors"
        },
        "competitors": ["Pilbara Minerals (ASX:PLS)", "Fortescue Metals (ASX:FMG)", "IGO Limited (ASX:IGO)", "Liontown Resources (ASX:LTR)"],
        "listed_competitors": ["PLS", "FMG", "IGO"],
        "asx_url": "https://www.asx.com.au/markets/company/MIN"
    },
    {
        "name": "HUB24 Limited",
        "ticker": "HUB.AX",
        "asx_code": "HUB",
        "industry": "wealth management platforms",
        "industry_publications": ["Financial Standard", "Professional Planner", "Money Management", "Morningstar Australia"],
        "supply_chain": {
            "customers": "financial advisers, stockbrokers, accountants, self-directed investors",
            "suppliers": "custody providers, fund managers, technology vendors"
        },
        "competitors": ["Netwealth Group (ASX:NWL)", "Praemium Limited (ASX:PPS)", "Mason Stevens (unlisted)", "AMP Platforms (ASX:AMP)"],
        "listed_competitors": ["NWL", "PPS"],
        "asx_url": "https://www.asx.com.au/markets/company/HUB"
    },
    {
        "name": "Macquarie Group Limited",
        "ticker": "MQG.AX",
        "asx_code": "MQG",
        "industry": "investment banking and asset management",
        "industry_publications": ["Infrastructure Investor", "Private Equity International", "Bloomberg Markets", "Reuters Finance"],
        "supply_chain": {
            "customers": "institutional investors, infrastructure funds, corporate clients, retail banking customers",
            "suppliers": "global capital markets, institutional co-investors"
        },
        "competitors": ["ANZ Group (ASX:ANZ)", "Commonwealth Bank (ASX:CBA)", "Morgan Stanley (global)", "Goldman Sachs (global)"],
        "listed_competitors": ["ANZ", "CBA"],
        "asx_url": "https://www.asx.com.au/markets/company/MQG"
    },
    {
        "name": "Charter Hall Group",
        "ticker": "CHC.AX",
        "asx_code": "CHC",
        "industry": "real estate investment and funds management",
        "industry_publications": ["The Property Council", "Commercial Real Estate", "Australian Property Journal", "PERE News"],
        "supply_chain": {
            "customers": "institutional investors, superannuation funds, wholesale investors, tenants",
            "suppliers": "property developers, construction firms, property managers"
        },
        "competitors": ["Goodman Group (ASX:GMG)", "Dexus (ASX:DXS)", "GPT Group (ASX:GPT)", "Centuria Capital (ASX:CNI)"],
        "listed_competitors": ["GMG", "DXS", "GPT"],
        "asx_url": "https://www.asx.com.au/markets/company/CHC"
    },
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
        "listed_competitors": [],
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
        "listed_competitors": [],
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
        "listed_competitors": ["TNE"],
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
        "listed_competitors": ["DXS", "GPT", "COF", "CHC"],
        "asx_url": "https://www.asx.com.au/markets/company/GOZ"
    },
    {
        "name": "Propel Funeral Partners Limited",
        "ticker": "PFP.AX",
        "asx_code": "PFP",
        "industry": "death care services (funeral homes, cemeteries, crematoria)",
        "industry_publications": ["Australian Funeral Directors Association", "Australasian Cemeteries & Crematoria Association"],
        "supply_chain": {
            "customers": "families and individuals requiring funeral services across Australia and New Zealand",
            "suppliers": "casket and coffin manufacturers, memorial and headstone suppliers (Decra), floral providers, vehicle fleet suppliers"
        },
        "competitors": ["InvoCare (acquired by TPG Capital, unlisted)", "Independent family-owned funeral homes", "Southern Metropolitan Cemeteries Trust (unlisted)"],
        "listed_competitors": [],
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

def parse_asx_date(date_str: str) -> datetime:
    """Parse ASX date string which may include time. Returns datetime or None."""
    if not date_str:
        return None
    
    # Clean up the date string - remove time portion if present
    # ASX dates can be "26/08/2025" or "26/08/20257:38 am" or "29/01/2026 8:12 am"
    date_str = date_str.strip()
    
    # Try to extract just the date part (DD/MM/YYYY)
    date_match = re.match(r'(\d{1,2}/\d{1,2}/\d{4})', date_str)
    if date_match:
        date_part = date_match.group(1)
        try:
            return datetime.strptime(date_part, "%d/%m/%Y")
        except ValueError:
            pass
    
    # Try other formats
    for fmt in ["%d/%m/%Y", "%d %b %Y", "%Y-%m-%d", "%d/%m/%Y %H:%M %p", "%d/%m/%Y%H:%M %p"]:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    return None


def format_asx_date(date_str: str) -> str:
    """Format ASX date string to clean format without time."""
    parsed = parse_asx_date(date_str)
    if parsed:
        return parsed.strftime("%d %b %Y")  # e.g., "26 Aug 2025"
    return date_str  # Return original if parsing fails


def research_new_information(client: anthropic.Anthropic, stock: dict) -> dict:
    """
    Research NEW information about the company in the last 7 days.
    MUST capture ALL ASX announcements from last 7 days - no filtering.
    Returns structured data for the "New Information" section.
    """
    asx_code = stock['asx_code']
    today = datetime.now()
    seven_days_ago = today - timedelta(days=7)
    
    result = {
        "has_new_info": False,
        "items": [],  # List of new information items
        "no_news_message": "No new information in the last 7 days."
    }
    
    # Step 1: Get ALL ASX announcements from last 7 days - NO FILTERING
    anns = asx_get_announcements(asx_code)
    recent_anns = []
    
    for ann in anns:
        ann_date = parse_asx_date(ann['date'])
        if ann_date and ann_date >= seven_days_ago:
            recent_anns.append(ann)
        elif not ann_date:
            # If date parsing fails but it's in the first few announcements, include it
            if len(recent_anns) < 5 and anns.index(ann) < 5:
                recent_anns.append(ann)
    
    # Add ALL recent ASX announcements to result (prioritize price-sensitive)
    # Sort: price-sensitive first, then by date
    recent_anns.sort(key=lambda x: (not x.get('sensitive', False), x.get('date', '')))
    
    for ann in recent_anns[:5]:  # Max 5 recent announcements
        # Mark price-sensitive announcements
        ann_type = "ASX Announcement (Price Sensitive)" if ann.get('sensitive') else "ASX Announcement"
        
        result["items"].append({
            "type": ann_type,
            "title": ann['title'],
            "date": format_asx_date(ann['date']),
            "summary": None,
            "source_url": ann['pdf_url'],
            "is_new": True,
            "price_sensitive": ann.get('sensitive', False)
        })
        result["has_new_info"] = True
    
    # Step 2: Search for recent news from reputable sources (skip if we have plenty of ASX news)
    if len(result["items"]) < 3:
        news_prompt = f"""Search for news about {stock['name']} (ASX: {stock['asx_code']}) published in the LAST 7 DAYS ONLY.

**ONLY include news from these sources:**
- Australian Financial Review (AFR)
- Sydney Morning Herald (SMH)
- The Australian
- Bloomberg
- Reuters

**STRICT RULES:**
- ONLY include articles published within the last 7 days
- If you cannot verify the publication date is within 7 days, DO NOT include it
- Focus on material news: earnings updates, contracts, acquisitions, management changes, guidance
- Ignore opinion pieces, analyst commentary, or general market news

After searching, provide JSON only:
{{
    "news_items": [
        {{
            "title": "Headline of the article",
            "source_name": "Publication name",
            "source_url": "URL or null",
            "publication_date": "Date (must be within last 7 days)",
            "summary": "1 sentence summary of what's new"
        }}
    ],
    "no_recent_news": true/false
}}

If no news from the last 7 days is found, return: {{"news_items": [], "no_recent_news": true}}
"""
        
        search_result = call_claude_with_search(client, news_prompt, max_searches=1)
        
        try:
            json_match = re.search(r'\{[\s\S]*\}', search_result)
            if json_match:
                news_data = json.loads(json_match.group())
                for item in news_data.get('news_items', []):
                    result["items"].append({
                        "type": "News",
                        "title": item.get('title'),
                        "date": item.get('publication_date'),
                        "summary": item.get('summary'),
                        "source_name": item.get('source_name'),
                        "source_url": item.get('source_url'),
                        "is_new": True,
                        "price_sensitive": False
                    })
                    result["has_new_info"] = True
        except (json.JSONDecodeError, AttributeError):
            pass
    
    return result


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


def research_market_update(client: anthropic.Anthropic, stock: dict) -> dict:
    """
    Research the LAST MARKET UPDATE - the most recent price-sensitive ASX announcement
    containing fundamental information that impacts the stock price.
    
    This includes: quarterly updates, guidance changes, trading updates, annual/half-year results,
    capital raises, acquisitions, or any other price-sensitive material.
    """
    asx_code = stock['asx_code']
    
    # Check cache first (cache for 7 days since market updates are more frequent)
    cached = load_from_cache(asx_code, 'market_update', 7)
    if cached:
        return cached
    
    anns = asx_get_announcements(asx_code)
    if not anns:
        return {
            "update_type": "Not found",
            "update_date": "Not found",
            "title": "Not found",
            "key_financials": "Not found",
            "guidance": "None mentioned",
            "source_url": stock.get('asx_url')
        }
    
    # Get the most recent PRICE-SENSITIVE announcement (ASX marks these clearly)
    sensitive = [a for a in anns if a.get('sensitive')]
    
    if not sensitive:
        return {
            "update_type": "Not found",
            "update_date": "Not found",
            "title": "No recent price-sensitive announcements",
            "key_financials": "Not found",
            "guidance": "None mentioned",
            "source_url": stock.get('asx_url')
        }
    
    # Use the MOST RECENT price-sensitive announcement
    latest = sensitive[0]
    print(f"      Downloading: {latest['title'][:50]}...")
    
    pdf_bytes = asx_download_pdf(latest['pdf_url'])
    if not pdf_bytes:
        return {
            "update_type": "Announcement",
            "update_date": format_asx_date(latest['date']),
            "title": latest['title'],
            "key_financials": "Unable to download PDF",
            "guidance": "None mentioned",
            "source_url": latest['pdf_url']
        }
    
    text = asx_extract_text(pdf_bytes)
    if not text:
        return {
            "update_type": "Announcement",
            "update_date": format_asx_date(latest['date']),
            "title": latest['title'],
            "key_financials": "Unable to extract text from PDF",
            "guidance": "None mentioned",
            "source_url": latest['pdf_url']
        }
    
    # Use Claude to extract key information from any type of market update
    prompt = f"""Analyze this ASX price-sensitive announcement and extract the key information that would impact the stock price.

Title: {latest['title']}
Date: {latest['date']}

Content:
{text[:10000]}

This could be ANY type of market update: quarterly results, half-year/annual results, trading update, guidance change, capital raising, acquisition, or other material announcement.

Provide your response in EXACTLY this JSON format (no other text):
{{
    "update_type": "Type of update (e.g., 'Annual Results FY25', 'Quarterly Update Q2 FY26', 'Trading Update', 'Capital Raising', 'Guidance Upgrade', 'Acquisition Announcement', etc.)",
    "key_financials": "The MOST IMPORTANT financial metrics or numbers from this announcement. For results: include Revenue, NPAT, EPS, Dividend if available. For trading updates: include any metrics mentioned. For capital raises: include size and terms. For guidance: include the specific numbers. Format as a concise string with key metrics separated by ' | '. Example: 'NPAT: $180M (+31%) | EPS: 171.75c | Dividend: 66c fully franked'. If no financials, describe the key material information.",
    "guidance": "Any forward-looking guidance, outlook, or forecasts mentioned. Include specific numbers if provided. If none, return 'None mentioned'."
}}

**RULES:**
- Extract the ACTUAL numbers from the document
- Focus on the most material information that would move the stock price
- Be specific with numbers - include percentages, currency amounts, comparisons to prior periods
- If this is a capital raising, include the size, price, and discount
- If this is an acquisition, include the target and price"""

    response = call_claude_analyze(client, prompt)
    
    try:
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            update_data = json.loads(json_match.group())
            result = {
                "update_type": update_data.get('update_type', 'Announcement'),
                "update_date": format_asx_date(latest['date']),
                "title": latest['title'],
                "key_financials": update_data.get('key_financials', 'Not found'),
                "guidance": update_data.get('guidance', 'None mentioned'),
                "source_url": latest['pdf_url']
            }
            
            # Cache successful results
            if result.get('key_financials') != 'Not found':
                save_to_cache(asx_code, 'market_update', result)
            
            return result
    except (json.JSONDecodeError, AttributeError):
        pass
    
    return {
        "update_type": "Announcement",
        "update_date": format_asx_date(latest['date']),
        "title": latest['title'],
        "key_financials": "Unable to extract - see source",
        "guidance": "None mentioned",
        "source_url": latest['pdf_url']
    }


# Keep the old function name as alias for backwards compatibility during transition
def research_earnings_asx(client: anthropic.Anthropic, stock: dict) -> dict:
    """Deprecated - use research_market_update instead."""
    return research_market_update(client, stock)


# ============================================================================
# CLAUDE WEB SEARCH RESEARCH FUNCTIONS (for industry and competitors)
# ============================================================================

def research_industry(client: anthropic.Anthropic, stock: dict) -> dict:
    """Research industry dynamics with authoritative sources. Max 2 months old, flag items from last 7 days as NEW."""
    industry_pubs = ", ".join(stock.get('industry_publications', []))
    supply_chain = stock.get('supply_chain', {})
    customers = supply_chain.get('customers', 'N/A')
    suppliers = supply_chain.get('suppliers', 'N/A')
    
    prompt = f"""You are conducting industry research for {stock['name']} (ASX: {stock['asx_code']}) in the {stock['industry']} sector.

**STRICT DATE REQUIREMENTS:**
- ONLY include information published within the LAST 2 MONTHS (60 days)
- For each item, you MUST verify and include the publication date
- If you cannot verify the date is within 2 months, DO NOT include it
- Mark items published in the LAST 7 DAYS with "is_new": true

**SOURCE HIERARCHY (prioritize in this order):**
1. Industry-specific trade publications: {industry_pubs}
2. Tier-one financial news: Australian Financial Review (AFR), Wall Street Journal (WSJ), Sydney Morning Herald (SMH), The Australian, Bloomberg, Reuters
3. Company press releases and ASX announcements
4. Other reputable business journalism with clear editorial standards

**EXCLUDED SOURCES - DO NOT CITE:**
- IBISWorld, Mordor Intelligence, or similar market research aggregators
- Any article older than 2 months
- If you cannot verify whether a source is an aggregator, exclude it

**SUPPLY CHAIN CONTEXT:**
- Key customers: {customers}
- Key suppliers: {suppliers}
- Include relevant supply chain developments if material to {stock['name']}

Search for: "{stock['industry']} Australia 2025 2026"

After searching, provide the following in JSON format only (no other text):
{{
    "data_points": [
        {{
            "fact": "A specific statistic, trend, or development with numbers/percentages where available",
            "source_name": "Name of the publication (e.g., 'Australian Financial Review')",
            "source_url": "Actual URL from search results, or null if not available",
            "publication_date": "REQUIRED - exact date from the article (e.g., 'January 15, 2026')",
            "is_new": true/false,
            "relevance": "How this specifically relates to {stock['name']} or its supply chain"
        }}
    ]
}}

**CRITICAL RULES:**
- Provide 2-4 specific data points with actual numbers/percentages where possible
- EVERY item must have a verified publication_date within the last 2 months
- Set "is_new": true if published within the last 7 days, otherwise false
- Only include facts you actually found in search results - do NOT fabricate statistics
- If no recent industry news exists within 2 months, return empty data_points array
"""
    
    result = call_claude_with_search(client, prompt, max_searches=2)
    
    try:
        json_match = re.search(r'\{[\s\S]*\}', result)
        if json_match:
            data = json.loads(json_match.group())
            
            # POST-PROCESS: Filter out items older than 2 months
            if 'data_points' in data:
                filtered_points = []
                two_months_ago = datetime.now() - timedelta(days=60)
                
                for point in data['data_points']:
                    if point is None:
                        continue
                    pub_date_str = point.get('publication_date', '')
                    
                    # Try to parse the date and validate it's within 2 months
                    is_valid = False
                    for fmt in ["%B %d, %Y", "%d %B %Y", "%B %Y", "%d/%m/%Y", "%Y-%m-%d", 
                                "%b %d, %Y", "%d %b %Y", "%b %Y"]:
                        try:
                            pub_date = datetime.strptime(pub_date_str, fmt)
                            if pub_date >= two_months_ago:
                                is_valid = True
                                # Also check if it's within last 7 days for [NEW] tag
                                seven_days_ago = datetime.now() - timedelta(days=7)
                                point['is_new'] = pub_date >= seven_days_ago
                            break
                        except ValueError:
                            continue
                    
                    # If we couldn't parse the date, check for year indicators
                    if not is_valid and pub_date_str:
                        # Reject if contains old years
                        if any(yr in pub_date_str for yr in ['2024', '2023', '2022', '2021', '2020']):
                            continue
                        # Accept if contains recent months
                        if '2026' in pub_date_str or '2025' in pub_date_str:
                            # Check for months that are definitely > 2 months old
                            if any(m in pub_date_str.lower() for m in ['january 2025', 'february 2025', 'march 2025', 
                                                                         'april 2025', 'may 2025', 'june 2025',
                                                                         'july 2025', 'august 2025', 'september 2025',
                                                                         'october 2025']):
                                continue  # Skip old 2025 dates
                            is_valid = True
                    
                    if is_valid:
                        filtered_points.append(point)
                
                data['data_points'] = filtered_points
            
            return data
    except (json.JSONDecodeError, AttributeError):
        pass
    
    return {
        "data_points": []
    }


def research_competitors(client: anthropic.Anthropic, stock: dict) -> dict:
    """
    Research competitor news using Claude web search.
    Max 2 months old, flag items from last 7 days as NEW.
    Option C: Web search as primary, ASX scraper supplement for listed competitors.
    """
    competitors_str = ", ".join(stock['competitors'])
    listed_comps = [c for c in stock['competitors'] if '.AX)' in c or 'ASX:' in c]
    unlisted_comps = [c for c in stock['competitors'] if '.AX)' not in c and 'ASX:' not in c]
    
    prompt = f"""You are conducting competitive intelligence research for {stock['name']} (ASX: {stock['asx_code']}).

**COMPETITORS TO MONITOR:**
Listed: {', '.join(listed_comps) if listed_comps else 'None specified'}
Unlisted: {', '.join(unlisted_comps) if unlisted_comps else 'None specified'}

**STRICT DATE REQUIREMENTS:**
- ONLY include news published within the LAST 2 MONTHS (60 days)
- For each item, you MUST verify and include the publication date
- If you cannot verify the date is within 2 months, DO NOT include it
- Mark items published in the LAST 7 DAYS with "is_new": true

**SOURCE HIERARCHY (prioritize in this order):**
1. Company press releases and ASX announcements
2. Industry-specific trade publications
3. Tier-one financial news: Australian Financial Review (AFR), Wall Street Journal (WSJ), Sydney Morning Herald (SMH), The Australian, Bloomberg, Reuters

**EXCLUDED SOURCES - DO NOT CITE:**
- IBISWorld, Mordor Intelligence, or similar market research aggregators
- Opinion pieces or general industry commentary (focus on competitor ACTIONS)
- Any article older than 2 months

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
            "publication_date": "REQUIRED - exact date from the article (e.g., 'January 15, 2026')",
            "is_new": true/false,
            "source_name": "Publication name",
            "source_url": "Actual URL from search results, or null",
            "implications": "What this might mean for {stock['name']}'s competitive position"
        }}
    ],
    "no_recent_news": false,
    "no_recent_news_note": null
}}

If NO competitive news was found within the 2-month window, return:
{{
    "competitor_news": [],
    "no_recent_news": true,
    "no_recent_news_note": "No material competitive announcements found within the last 2 months for monitored competitors."
}}

**CRITICAL RULES:**
- EVERY item must have a verified publication_date within the last 2 months
- Set "is_new": true if published within the last 7 days, otherwise false
- Only include news you actually found with verifiable competitor ACTIONS
- Do NOT include general market commentary or analyst opinions
- Be specific about what competitors announced or did
- If no recent news exists within 2 months, return empty competitor_news array
"""
    
    result = call_claude_with_search(client, prompt, max_searches=2)
    
    competitor_data = None
    try:
        json_match = re.search(r'\{[\s\S]*\}', result)
        if json_match:
            competitor_data = json.loads(json_match.group())
            
            # POST-PROCESS: Filter out items older than 2 months
            if 'competitor_news' in competitor_data:
                filtered_news = []
                two_months_ago = datetime.now() - timedelta(days=60)
                
                for item in competitor_data['competitor_news']:
                    if item is None:
                        continue
                    pub_date_str = item.get('publication_date', '')
                    
                    # Try to parse the date and validate it's within 2 months
                    is_valid = False
                    for fmt in ["%B %d, %Y", "%d %B %Y", "%B %Y", "%d/%m/%Y", "%Y-%m-%d", 
                                "%b %d, %Y", "%d %b %Y", "%b %Y"]:
                        try:
                            pub_date = datetime.strptime(pub_date_str, fmt)
                            if pub_date >= two_months_ago:
                                is_valid = True
                                # Also check if it's within last 7 days for [NEW] tag
                                seven_days_ago = datetime.now() - timedelta(days=7)
                                item['is_new'] = pub_date >= seven_days_ago
                            break
                        except ValueError:
                            continue
                    
                    # If we couldn't parse the date, check for year indicators
                    if not is_valid and pub_date_str:
                        # Reject if contains old years
                        if any(yr in pub_date_str for yr in ['2024', '2023', '2022', '2021', '2020']):
                            continue
                        # Accept if contains recent months
                        if '2026' in pub_date_str or '2025' in pub_date_str:
                            # Check for months that are definitely > 2 months old
                            if any(m in pub_date_str.lower() for m in ['january 2025', 'february 2025', 'march 2025', 
                                                                         'april 2025', 'may 2025', 'june 2025',
                                                                         'july 2025', 'august 2025', 'september 2025',
                                                                         'october 2025']):
                                continue  # Skip old 2025 dates
                            is_valid = True
                    
                    if is_valid:
                        filtered_news.append(item)
                
                competitor_data['competitor_news'] = filtered_news
                
                # Update no_recent_news flag if all items were filtered out
                if not filtered_news:
                    competitor_data['no_recent_news'] = True
                    competitor_data['no_recent_news_note'] = "No material competitive announcements found within the last 2 months."
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

def format_stock_html(stock: dict, price_data: dict, new_info: dict, market_update: dict, 
                      industry: dict, competitors: dict, stock_num: int) -> str:
    """Format all researched data into HTML."""
    
    price_data = price_data or {}
    new_info = new_info or {}
    market_update = market_update or {}
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
    
    # NEW INFORMATION section - ALL ASX announcements from last 7 days
    if new_info.get('has_new_info') and new_info.get('items'):
        new_info_items = []
        for item in new_info['items']:
            # Highlight price-sensitive announcements
            if item.get('price_sensitive'):
                item_html = f"<strong style=\"color:#e74c3c;\">⚡ {item.get('type', 'News')}:</strong> {item.get('title', 'Untitled')}"
            else:
                item_html = f"<strong>{item.get('type', 'News')}:</strong> {item.get('title', 'Untitled')}"
            if item.get('date'):
                item_html += f" ({item['date']})"
            if item.get('source_url'):
                item_html += f' <a href="{item["source_url"]}" style="color:#3498db;">[Source]</a>'
            if item.get('summary'):
                item_html += f"<br><em style=\"color:#7f8c8d;font-size:0.9em;\">{item['summary']}</em>"
            new_info_items.append(f"<li>{item_html}</li>")
        new_info_html = "\n".join(new_info_items)
    else:
        new_info_html = "<li><em>No new information in the last 7 days.</em></li>"
    
    # LAST MARKET UPDATE section (replaces old Earnings section)
    update_url = market_update.get('source_url') or stock.get('asx_url', '#')
    
    if market_update.get('update_type') and market_update.get('update_type') != 'Not found':
        market_update_html = f"""<strong>Type:</strong> {market_update.get('update_type')}<br>
<strong>Date:</strong> {market_update.get('update_date', 'Not found')}<br>
<strong>Key Financials:</strong> {market_update.get('key_financials', 'Not found')}<br>
<strong>Guidance:</strong> {market_update.get('guidance', 'None mentioned')}"""
    else:
        market_update_html = "No recent price-sensitive market update found."
    
    # Industry dynamics - with [NEW] tag for items from last 7 days
    ind_points = industry.get('data_points') or []
    if ind_points:
        ind_items = []
        for point in ind_points:
            if point is None:
                continue
            fact = point.get('fact') or ''
            if not fact or fact == 'N/A':
                continue
            
            # Add [NEW] tag if published in last 7 days
            is_new = point.get('is_new', False)
            new_tag = '<span style="color:#e74c3c;font-weight:bold;">[NEW]</span> ' if is_new else ''
            
            source_name = point.get('source_name') or point.get('source')
            source_url = point.get('source_url')
            pub_date = point.get('publication_date', '')
            
            item = f"{new_tag}{fact}"
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
        industry_html = "\n".join(ind_items) if ind_items else "<li>No industry news from the last 2 months.</li>"
    else:
        industry_html = "<li>No industry news from the last 2 months.</li>"
    
    # Competitor dynamics - with [NEW] tag for items from last 7 days
    comp_news = competitors.get('competitor_news') or []
    no_recent = competitors.get('no_recent_news', False)
    
    if no_recent or not comp_news:
        note = competitors.get('no_recent_news_note') or 'No material competitive announcements found within the last 2 months.'
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
            
            # Add [NEW] tag if published in last 7 days
            is_new = news_item.get('is_new', False)
            new_tag = '<span style="color:#e74c3c;font-weight:bold;">[NEW]</span> ' if is_new else ''
            
            item = f"{new_tag}<strong>{competitor_name}:</strong> {news_desc}"
            
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
        
        competitor_html = "\n".join(comp_items) if comp_items else "<li>No competitor news from the last 2 months.</li>"
    
    # Assemble HTML
    html = f"""
<h2 style="color:#34495e;margin-top:30px;border-bottom:2px solid #ecf0f1;padding-bottom:8px;">
{stock_num}. {stock['name']} ({stock['ticker']})
</h2>

<p style="margin:10px 0;line-height:1.6;">
{price_html}
</p>

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">NEW INFORMATION (Last 7 Days):</strong>
</p>
<ul style="margin:5px 0 15px 20px;line-height:1.8;">
{new_info_html}
</ul>

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">LAST MARKET UPDATE:</strong><br>
{market_update_html}<br>
<strong>Source:</strong> <a href="{update_url}" style="color:#3498db;">View Announcement</a>
</p>

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">INDUSTRY DYNAMICS (Last 2 Months):</strong>
</p>
<ul style="margin:5px 0 15px 20px;line-height:1.8;">
{industry_html}
</ul>

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">COMPETITIVE DYNAMICS (Last 2 Months):</strong>
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
        
        # Step 2: Research NEW INFORMATION (last 7 days - ALL ASX announcements)
        print("   📰 Researching new information (last 7 days)...", end=" ")
        new_info = research_new_information(client, stock)
        new_info_count = len(new_info.get('items', []))
        new_info_status = f"✅ ({new_info_count} items)" if new_info.get('has_new_info') else "⚠️ (none)"
        print(new_info_status)
        
        # Step 3: Research LAST MARKET UPDATE (most recent price-sensitive announcement)
        print("   💹 Researching last market update (ASX)...", end=" ")
        market_update = research_market_update(client, stock)
        update_status = "✅" if market_update.get('update_type') != 'Not found' else "⚠️"
        print(update_status)
        
        # Step 4: Research industry (Claude web search - last 2 months)
        print("   🏭 Researching industry (last 2 months)...", end=" ")
        industry = research_industry(client, stock)
        ind_status = "✅" if len(industry.get('data_points', [])) > 0 else "⚠️"
        print(ind_status)
        
        # Step 5: Research competitors (Claude + ASX supplement - last 2 months)
        listed_comp_count = len(stock.get('listed_competitors', []))
        print(f"   🏁 Researching competitors (last 2 months, +{listed_comp_count} ASX)...", end=" ")
        competitors = research_competitors(client, stock)
        comp_status = "✅" if len(competitors.get('competitor_news', [])) > 0 or competitors.get('no_recent_news') else "⚠️"
        print(comp_status)
        
        # Step 6: Format HTML
        print("   📝 Formatting HTML...", end=" ")
        try:
            stock_html = format_stock_html(stock, price, new_info, market_update, industry, competitors, i)
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
