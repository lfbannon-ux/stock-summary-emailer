#!/usr/bin/env python3
"""
Berkholts Daily Stock Summary Emailer - V5 IMPROVED
====================================================
Key improvements from V3:
1. Enhanced industry research with source hierarchy (trade pubs → tier-one news)
2. Explicit exclusion of aggregators (IBISWorld, Mordor Intelligence)
3. Supply chain context in industry analysis
4. Stricter 2-week timeframe for competitor news with date verification
5. Includes unlisted competitors in competitive analysis
6. Better handling of date uncertainty in sources
"""

import os
import sys
import smtplib
import json
import re
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from pathlib import Path
import anthropic
import yfinance as yf


# Cache settings
CACHE_DIR = Path("/home/claude/cache")  # Railway persistent storage - adjust path as needed
EARNINGS_CACHE_DAYS = 30  # How long to cache earnings data


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
        "competitors": ["Steadfast Group (SDF.AX)", "PSC Insurance (PSI.AX)", "Gallagher Australia (unlisted)", "Marsh McLennan (unlisted local ops)"],
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
        "competitors": ["Pilbara Minerals (PLS.AX)", "Fortescue Metals (FMG.AX)", "IGO Limited (IGO.AX)", "Liontown Resources (LTR.AX)"],
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
        "competitors": ["Netwealth Group (NWL.AX)", "Praemium Limited (PPS.AX)", "Mason Stevens (unlisted)", "AMP Platforms (AMP.AX)"],
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
        "competitors": ["ANZ Group (ANZ.AX)", "Commonwealth Bank (CBA.AX)", "Morgan Stanley (global)", "Goldman Sachs (global)"],
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
        "competitors": ["Goodman Group (GMG.AX)", "Dexus (DXS.AX)", "GPT Group (GPT.AX)", "Centuria Capital (CNI.AX)"],
        "asx_url": "https://www.asx.com.au/markets/company/CHC"
    },
]


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


def call_claude_with_search(client: anthropic.Anthropic, prompt: str, max_searches: int = 5) -> str:
    """
    Call Claude API with web search tool enabled.
    Returns the text response. Always returns a string, never None.
    """
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
        
        # Extract text from response
        result = ""
        for block in response.content:
            if hasattr(block, 'text') and block.text is not None:
                result += block.text
        
        return result.strip() if result else "NO_RESPONSE"
        
    except Exception as e:
        return f"ERROR: {str(e)}"


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
    """
    Load data from cache if it exists and is not expired.
    Returns None if cache miss or expired.
    """
    cache_path = get_cache_path(asx_code, cache_type)
    
    if not cache_path.exists():
        return None
    
    try:
        with open(cache_path, 'r') as f:
            cached = json.load(f)
        
        # Check if cache is expired
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


def research_announcements(client: anthropic.Anthropic, stock: dict) -> dict:
    """
    Research the company's recent ASX announcements.
    Returns structured data about announcements.
    """
    prompt = f"""Search the web for recent ASX announcements from {stock['name']} (ASX: {stock['asx_code']}).

Search for: "{stock['asx_code']} ASX announcement 2025 2026"
Also search: "{stock['name']} announcement investor"

After searching, provide the following in JSON format only (no other text):
{{
    "last_announcement": {{
        "date": "the date or 'Not found'",
        "title": "title of the announcement or 'Not found'",
        "summary": "1-2 sentence summary with specific numbers if available, or 'Not found'",
        "source_url": "actual URL from search results, or null if not found"
    }},
    "price_sensitive_news": {{
        "found": true or false,
        "description": "what news might explain recent price moves, or 'No material news found in last 3 days'",
        "source_url": "URL or null"
    }}
}}

IMPORTANT RULES:
- Only include information you actually found in search results
- If you can't find something, say "Not found" - do NOT make up dates or details
- For URLs, only use real URLs from your search results - do NOT invent URLs
- If no announcement source URL is found, use null (the system will use the ASX company page instead)
"""
    
    result = call_claude_with_search(client, prompt, max_searches=3)
    
    # Try to parse JSON from response
    try:
        # Find JSON in the response (might be wrapped in markdown)
        json_match = re.search(r'\{[\s\S]*\}', result)
        if json_match:
            data = json.loads(json_match.group())
            return data
    except (json.JSONDecodeError, AttributeError):
        pass
    
    # Return fallback structure
    return {
        "last_announcement": {
            "date": "Not found",
            "title": "Not found",
            "summary": "Unable to retrieve announcement data",
            "source_url": None
        },
        "price_sensitive_news": {
            "found": False,
            "description": "No material news found in last 3 days",
            "source_url": None
        }
    }


def research_earnings(client: anthropic.Anthropic, stock: dict, use_cache: bool = True) -> dict:
    """
    Research the company's last earnings report.
    Uses caching since earnings only update every 6 months.
    """
    asx_code = stock['asx_code']
    
    # Try to load from cache first
    if use_cache:
        cached = load_from_cache(asx_code, 'earnings', EARNINGS_CACHE_DAYS)
        if cached:
            return cached
    
    prompt = f"""Search the web for {stock['name']} (ASX: {stock['asx_code']}) earnings results and financial reports.

Search for: "{stock['asx_code']} earnings results FY2025 revenue profit"
Also search: "{stock['name']} half year results annual report"

After searching, provide the following in JSON format only (no other text):
{{
    "report_type": "Annual/Half-Year/Quarterly or 'Not found'",
    "report_date": "date of the report or 'Not found'",
    "period": "e.g., 'FY2025' or 'H1 FY2025' or 'Not found'",
    "revenue": "revenue figure with currency or 'Not found'",
    "npat": "net profit after tax or 'Not found'",
    "ebitda": "EBITDA if available or 'Not found'",
    "eps": "earnings per share or 'Not found'",
    "dividend": "dividend info or 'Not found'",
    "guidance": "any forward guidance mentioned or 'None mentioned'",
    "source_url": "URL from search results or null"
}}

IMPORTANT: Only report numbers you actually found. Do NOT make up financial figures.
"""
    
    result = call_claude_with_search(client, prompt, max_searches=3)
    
    earnings_data = None
    try:
        json_match = re.search(r'\{[\s\S]*\}', result)
        if json_match:
            earnings_data = json.loads(json_match.group())
    except (json.JSONDecodeError, AttributeError):
        pass
    
    if not earnings_data:
        earnings_data = {
            "report_type": "Not found",
            "report_date": "Not found",
            "period": "Not found",
            "revenue": "Not found",
            "npat": "Not found",
            "ebitda": "Not found",
            "eps": "Not found",
            "dividend": "Not found",
            "guidance": "None mentioned",
            "source_url": None
        }
    
    # Save to cache (even if partial data, better than re-fetching)
    if earnings_data.get('report_type') != 'Not found':
        save_to_cache(asx_code, 'earnings', earnings_data)
    
    return earnings_data


def research_industry(client: anthropic.Anthropic, stock: dict) -> dict:
    """
    Research industry dynamics with authoritative sources.
    V5: Enhanced with source hierarchy, supply chain context, and aggregator exclusion.
    """
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
        }},
        {{
            "fact": "Another specific data point or development",
            "source_name": "Source name",
            "source_url": "URL or null",
            "publication_date": "Date or 'Date not verified'",
            "relevance": "Relevance to the company"
        }},
        {{
            "fact": "Third data point",
            "source_name": "Source name",
            "source_url": "URL or null",
            "publication_date": "Date or 'Date not verified'",
            "relevance": "Relevance to the company"
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
    
    result = call_claude_with_search(client, prompt, max_searches=4)
    
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
    Research competitor news and announcements.
    V5: Enhanced with strict 2-week timeframe, includes unlisted competitors, date verification.
    """
    competitors_str = ", ".join(stock['competitors'])
    
    # Separate listed vs unlisted for search strategy
    listed_comps = [c for c in stock['competitors'] if '.AX)' in c]
    unlisted_comps = [c for c in stock['competitors'] if '.AX)' not in c]
    
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

Search for: "{listed_comps[0] if listed_comps else stock['competitors'][0]} announcement 2025 2026"
Also search for other competitors as needed.

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
    
    result = call_claude_with_search(client, prompt, max_searches=4)
    
    try:
        json_match = re.search(r'\{[\s\S]*\}', result)
        if json_match:
            data = json.loads(json_match.group())
            return data
    except (json.JSONDecodeError, AttributeError):
        pass
    
    return {
        "competitor_news": [],
        "no_recent_news": True,
        "no_recent_news_note": "Unable to retrieve competitor data"
    }


def format_stock_html(stock: dict, price_data: dict, announcements: dict, earnings: dict, 
                      industry: dict, competitors: dict, stock_num: int) -> str:
    """
    Format all researched data into HTML.
    V5: Updated to handle new field names and structures.
    """
    
    # Ensure all inputs are dicts (not None)
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
        earnings_html = "Earnings data not found in recent search"
    else:
        earnings_html = "<br>".join(earnings_parts)
    
    # Industry dynamics - V5 updated format
    ind_points = industry.get('data_points') or []
    if ind_points:
        ind_items = []
        for point in ind_points:
            if point is None:
                continue
            fact = point.get('fact') or ''
            if not fact or fact == 'N/A':
                continue
            
            # Build source attribution
            source_name = point.get('source_name') or point.get('source')  # Handle both V3 and V5 format
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
            
            # Add relevance if meaningful
            relevance = point.get('relevance')
            if relevance and relevance != 'N/A' and len(relevance) > 10:
                item += f'<br><em style="color:#7f8c8d;font-size:0.9em;">→ {relevance}</em>'
            
            ind_items.append(f'<li>{item}</li>')
        industry_html = "\n".join(ind_items) if ind_items else "<li>No specific industry data found from authoritative sources</li>"
    else:
        industry_html = "<li>No specific industry data found from authoritative sources</li>"
    
    # Competitor dynamics - V5 updated format
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
            
            # Add source with date
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
            if implications:
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
<strong>Source:</strong> <a href="{ann_url}" style="color:#3498db;">ASX Company Page</a>
</p>

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">LAST EARNINGS REPORT:</strong><br>
{earnings_html}<br>
<strong>Source:</strong> <a href="{earn_url}" style="color:#3498db;">ASX Company Page</a>
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
Generated by Berkholts Stock Summary System V5<br>
Prices: Yahoo Finance | Research: Claude AI with Web Search<br>
Sources: Trade publications, AFR, WSJ, SMH, The Australian, company announcements<br>
Note: ASX Company Page links provided for verification. Click to view official announcements.
</p>

</td></tr>
</table>
</td></tr>
</table>
</body>
</html>'''


def send_email(html: str, recipient: str, smtp_email: str, smtp_password: str, subject: str):
    """Send email with detailed logging."""
    msg = MIMEText(html, 'html', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = smtp_email
    msg['To'] = recipient
    
    # Add headers to improve deliverability
    msg['Reply-To'] = smtp_email
    msg['X-Priority'] = '3'  # Normal priority
    
    try:
        print(f"      Connecting to smtp.gmail.com:465...")
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            print(f"      Connected. Logging in as {smtp_email}...")
            server.login(smtp_email, smtp_password)
            print(f"      Logged in. Sending to {recipient}...")
            result = server.sendmail(smtp_email, recipient, msg.as_string())
            if result:
                # result is a dict of failed recipients
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


def main():
    print("=" * 70)
    print("🚀 Berkholts Stock Emailer - V5 (Enhanced Source Quality + Caching)")
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
    print(f"📧 Recipients: {', '.join(recipients)}")
    
    # Initialize cache
    ensure_cache_dir()
    print(f"💾 Cache directory: {CACHE_DIR}")
    print(f"   Earnings cache duration: {EARNINGS_CACHE_DAYS} days")
    
    client = anthropic.Anthropic(api_key=anthropic_key)
    today_str = datetime.now().strftime("%B %d, %Y")
    
    all_html = ""
    cache_hits = 0
    api_calls_saved = 0
    
    for i, stock in enumerate(STOCKS, 1):
        print(f"\n{'=' * 70}")
        print(f"📊 STOCK {i}/{len(STOCKS)}: {stock['name']}")
        print("=" * 70)
        
        # Step 1: Get price (yfinance - always accurate)
        print("   💰 Getting price...", end=" ")
        price = get_stock_price(stock['ticker'])
        if price.get('error'):
            print(f"⚠️ {price['error']}")
        else:
            print(f"✅ A${price['yesterday_close']:.2f} ({price['change_percent']:+.2f}%)")
        
        # Step 2: Research announcements (separate API call)
        print("   📢 Researching announcements...", end=" ")
        announcements = research_announcements(client, stock)
        ann_status = "✅" if announcements.get('last_announcement', {}).get('date') != 'Not found' else "⚠️"
        print(ann_status)
        
        # Step 3: Research earnings (with caching)
        print("   💹 Researching earnings...", end=" ")
        # Check if we'll hit cache (for stats)
        cached_earnings = load_from_cache(stock['asx_code'], 'earnings', EARNINGS_CACHE_DAYS)
        if cached_earnings:
            cache_hits += 1
            api_calls_saved += 1
            earnings = cached_earnings
            print(f"✅ (cached)")
        else:
            earnings = research_earnings(client, stock, use_cache=False)  # Already checked cache
            earn_status = "✅" if earnings.get('report_type') != 'Not found' else "⚠️"
            print(earn_status)
        
        # Step 4: Research industry (separate API call - V5 enhanced)
        print("   🏭 Researching industry (V5 enhanced)...", end=" ")
        industry = research_industry(client, stock)
        ind_status = "✅" if len(industry.get('data_points', [])) > 0 else "⚠️"
        print(ind_status)
        
        # Step 5: Research competitors (separate API call - V5 enhanced)
        print("   🏁 Researching competitors (V5 enhanced)...", end=" ")
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
    print(f"💾 Cache stats: {cache_hits} hits, {api_calls_saved} API calls saved")
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
