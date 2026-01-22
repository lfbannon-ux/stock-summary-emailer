#!/usr/bin/env python3
"""
Berkholts Daily Stock Summary Emailer - Multi-Search Version
=============================================================
Uses multiple targeted searches per stock for higher accuracy.

Architecture:
- Separate API call for each data point
- Focused searches = better results
- Validates data before including
"""

import os
import sys
import smtplib
import re
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import anthropic
import json


# ============================================================================
# CONFIGURATION
# ============================================================================

STOCKS = [
    {
        "name": "AUB Group Limited",
        "ticker": "AUB.AX",
        "description": "Australian insurance broker",
        "industry": "insurance",
        "competitors": ["Steadfast Group (SDF.AX)", "PSC Insurance (PSI.AX)"]
    },
    {
        "name": "Mineral Resources Limited", 
        "ticker": "MIN.AX",
        "description": "Mining services and lithium producer",
        "industry": "mining",
        "competitors": ["Pilbara Minerals (PLS.AX)", "Fortescue Metals (FMG.AX)"]
    },
]

# Industry search terms (shared across stocks in same industry)
INDUSTRY_SEARCHES = {
    "insurance": "Australian insurance market premiums rates growth 2026 statistics",
    "mining": "Australian mining iron ore lithium prices production 2026",
}


# ============================================================================
# SEARCH FUNCTIONS
# ============================================================================

def search_and_extract(client: anthropic.Anthropic, query: str, instruction: str) -> str:
    """
    Perform a single focused search and extract specific information.
    
    Args:
        client: Anthropic client
        query: What to search for
        instruction: What to extract from results
    
    Returns:
        Extracted information as string
    """
    prompt = f"""Search for: {query}

Then from the search results, extract and report:
{instruction}

RULES:
1. Only report information you actually find in search results
2. Include the source URL for every fact
3. If you cannot find the information, say "NOT FOUND"
4. Be specific - include numbers, dates, percentages
5. Do not make up or estimate any data"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Extract text from response
        result = ""
        for block in response.content:
            if hasattr(block, 'text'):
                result += block.text
        
        return result.strip()
    
    except Exception as e:
        print(f"   ⚠️ Search error: {str(e)}")
        return "NOT FOUND"


def get_price_data(client: anthropic.Anthropic, ticker: str, company_name: str) -> dict:
    """Get stock price data from Yahoo Finance."""
    
    print(f"   📊 Searching price data...")
    
    query = f"{ticker} stock price Yahoo Finance historical"
    instruction = f"""Find the closing prices for {company_name} ({ticker}):

1. Yesterday's closing price (most recent trading day)
2. The day before yesterday's closing price

Report in this exact format:
YESTERDAY_CLOSE: [price]
PREVIOUS_CLOSE: [price]
SOURCE_URL: [Yahoo Finance URL]

Calculate the percentage change: ((yesterday - previous) / previous) * 100
CHANGE_PERCENT: [percentage]"""

    result = search_and_extract(client, query, instruction)
    
    return {"raw": result}


def get_last_announcement(client: anthropic.Anthropic, ticker: str, company_name: str) -> dict:
    """Get the last price-sensitive ASX announcement."""
    
    print(f"   📢 Searching last announcement...")
    
    query = f"site:asx.com.au {ticker} announcement 2025 2026"
    instruction = f"""Find the most recent PRICE-SENSITIVE announcement for {company_name} ({ticker}).

Look for: trading updates, guidance changes, earnings, acquisitions, material contracts.

Report in this exact format:
DATE: [exact date, e.g., December 1, 2025]
TYPE: [trading update/guidance/earnings/acquisition/etc]
SUMMARY: [2-3 sentences with SPECIFIC NUMBERS if any guidance was given, e.g., "FY26 NPAT guidance of $215-227M"]
URL: [direct link to ASX PDF or announcement page]"""

    result = search_and_extract(client, query, instruction)
    
    return {"raw": result}


def get_earnings_report(client: anthropic.Anthropic, ticker: str, company_name: str) -> dict:
    """Get the last earnings report details."""
    
    print(f"   💰 Searching earnings report...")
    
    query = f"{company_name} {ticker} annual results half year results FY25 FY26 revenue profit"
    instruction = f"""Find the most recent earnings report for {company_name} ({ticker}).

Report in this exact format:
DATE: [exact date of announcement]
TYPE: [Annual Results / Half-Year Results / Quarterly Update]
REVENUE: [amount and % growth, e.g., "$1.82B (+14% YoY)"]
NPAT: [amount and % growth, e.g., "$192M (+13% YoY)"]
EPS: [amount and % growth, e.g., "86.2c (+12%)"]
DIVIDEND: [amount, e.g., "62c fully franked"]
URL: [source link]"""

    result = search_and_extract(client, query, instruction)
    
    return {"raw": result}


def get_recent_news(client: anthropic.Anthropic, ticker: str, company_name: str, days: int = 7) -> dict:
    """Get any material news from the last week."""
    
    print(f"   📰 Searching recent news...")
    
    query = f"{company_name} {ticker} news announcement January 2026"
    instruction = f"""Find any material news or announcements for {company_name} ({ticker}) from the LAST 7 DAYS.

If there IS material news:
- Report each item with DATE, DESCRIPTION, and SOURCE URL

If there is NO material news from the last 7 days:
- Report: "NO_RECENT_NEWS"

Do not include old news. Only the last 7 days."""

    result = search_and_extract(client, query, instruction)
    
    return {"raw": result}


def get_industry_dynamics(client: anthropic.Anthropic, industry: str) -> dict:
    """Get industry-wide trends and data (shared across stocks in same industry)."""
    
    print(f"   🏭 Searching {industry} industry dynamics...")
    
    query = INDUSTRY_SEARCHES.get(industry, f"Australian {industry} industry trends 2026")
    instruction = f"""Find 3 DATA POINTS about the {industry} industry in Australia.

Focus on:
- Market size, growth rates, pricing trends
- Regulatory changes
- Industry-wide statistics

For EACH point, report:
DATE: [month/year]
FACT: [specific data with numbers, e.g., "Insurance premiums rose 8.5% to $47.2B"]
SOURCE: [publication name]
URL: [source link]

Do NOT include information about specific companies - only industry-wide trends."""

    result = search_and_extract(client, query, instruction)
    
    return {"raw": result}


def get_competitor_news(client: anthropic.Anthropic, competitors: list, industry: str) -> dict:
    """Get recent news about specific competitors."""
    
    print(f"   🏢 Searching competitor news...")
    
    competitor_str = ", ".join(competitors)
    query = f"{competitor_str} ASX announcement results January 2026"
    instruction = f"""Find recent news or announcements about these SPECIFIC competitors: {competitor_str}

For EACH competitor with news, report:
COMPETITOR: [company name and ticker]
DATE: [exact date]
NEWS: [specific announcement or result with numbers]
URL: [source link]

If no recent news for a competitor, skip them.
Only include news from the last 30 days."""

    result = search_and_extract(client, query, instruction)
    
    return {"raw": result}


# ============================================================================
# HTML GENERATION
# ============================================================================

def generate_html_for_stock(client: anthropic.Anthropic, stock: dict, data: dict, stock_num: int) -> str:
    """Generate HTML for a single stock using collected data."""
    
    prompt = f"""Convert this research data into HTML for an email. Output ONLY the HTML snippet.

STOCK: {stock['name']} ({stock['ticker']})
STOCK NUMBER: {stock_num}

RESEARCH DATA:
==============

PRICE DATA:
{data.get('price', {}).get('raw', 'NOT FOUND')}

RECENT NEWS (Last 7 days):
{data.get('news', {}).get('raw', 'NOT FOUND')}

LAST PRICE-SENSITIVE ANNOUNCEMENT:
{data.get('announcement', {}).get('raw', 'NOT FOUND')}

LAST EARNINGS REPORT:
{data.get('earnings', {}).get('raw', 'NOT FOUND')}

INDUSTRY DYNAMICS:
{data.get('industry', {}).get('raw', 'NOT FOUND')}

COMPETITOR NEWS:
{data.get('competitors', {}).get('raw', 'NOT FOUND')}

==============

Generate HTML using this EXACT structure:

<h2 style="color:#34495e;margin-top:30px;border-bottom:2px solid #ecf0f1;padding-bottom:8px;">
{stock_num}. {stock['name']} ({stock['ticker']})
</h2>

<p style="margin:10px 0;line-height:1.6;">
<strong style="color:#2980b9;">YESTERDAY:</strong> A$XX.XX | 
<strong style="color:#2980b9;">PREVIOUS DAY:</strong> A$XX.XX | 
<strong style="color:#2980b9;">CHANGE:</strong> <span style="color:[green if positive, red if negative];">[+/-X.XX%]</span>
</p>

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">REASON FOR MOVE:</strong><br>
[If recent news exists, describe it. If not, write "No material announcements in the past week"]
</p>

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">COMPANY DEVELOPMENTS (Past Week):</strong><br>
[List any developments or "No new developments this week"]
</p>

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">LAST PRICE-SENSITIVE ANNOUNCEMENT:</strong><br>
<strong>Date:</strong> [date]<br>
<strong>Type:</strong> [type]<br>
<strong>Summary:</strong> [summary WITH SPECIFIC NUMBERS]<br>
<strong>Source:</strong> <a href="[URL]" style="color:#3498db;text-decoration:underline;">ASX Announcement</a>
</p>

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">LAST EARNINGS REPORT:</strong><br>
<strong>Date:</strong> [date] | <strong>Type:</strong> [type]<br>
<strong>Revenue:</strong> [amount] | <strong>NPAT:</strong> [amount] | <strong>EPS:</strong> [amount] | <strong>Dividend:</strong> [amount]<br>
<strong>Source:</strong> <a href="[URL]" style="color:#3498db;text-decoration:underline;">ASX Announcement</a>
</p>

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">INDUSTRY DYNAMICS:</strong>
</p>
<ul style="margin:5px 0 15px 20px;line-height:1.8;">
<li>[Point 1 with <a href="URL" style="color:#3498db;text-decoration:underline;">Source</a>]</li>
<li>[Point 2 with <a href="URL" style="color:#3498db;text-decoration:underline;">Source</a>]</li>
<li>[Point 3 with <a href="URL" style="color:#3498db;text-decoration:underline;">Source</a>]</li>
</ul>

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">COMPETITIVE DYNAMICS:</strong>
</p>
<ul style="margin:5px 0 15px 20px;line-height:1.8;">
<li>[Competitor 1 news with <a href="URL" style="color:#3498db;text-decoration:underline;">Source</a>]</li>
<li>[Competitor 2 news with <a href="URL" style="color:#3498db;text-decoration:underline;">Source</a>]</li>
</ul>

<hr style="border:none;border-top:1px solid #ecf0f1;margin:30px 0;">

RULES:
1. Every URL must be in <a href="URL"> format
2. Use actual data from the research - do not make up numbers
3. If data says "NOT FOUND", write "Data not available" for that section
4. Green color for positive changes, red for negative
5. Output ONLY the HTML snippet - no explanations"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=3000,
            system="You are an HTML generator. Output ONLY valid HTML code. No explanations.",
            messages=[{"role": "user", "content": prompt}]
        )
        
        html = ""
        for block in response.content:
            if hasattr(block, 'text'):
                html += block.text
        
        return html.strip()
    
    except Exception as e:
        print(f"   ⚠️ HTML generation error: {str(e)}")
        return f"<h2>{stock['name']} - Error generating content</h2>"


def wrap_in_email_template(content: str, today: str) -> str:
    """Wrap stock content in full email HTML template."""
    
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family:Arial,Helvetica,sans-serif;margin:0;padding:0;background-color:#f4f4f4;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f4;">
<tr><td align="center" style="padding:20px;">
<table width="1000" cellpadding="20" cellspacing="0" style="background-color:#ffffff;border:1px solid #dddddd;">
<tr><td>

<h1 style="color:#2c3e50;border-bottom:3px solid #3498db;padding-bottom:10px;margin-top:0;">
Berkholts Stock Summaries - {today}
</h1>

{content}

<p style="color:#7f8c8d;font-size:12px;margin-top:30px;text-align:center;">
Generated by Berkholts Stock Summary System
</p>

</td></tr>
</table>
</td></tr>
</table>
</body>
</html>"""


def fix_urls_in_html(html: str) -> str:
    """Post-process HTML to fix any malformed URLs."""
    
    # Fix angle bracket URLs: <https://...> -> proper links
    pattern = r'<(https?://[^>]+)>'
    
    def replace_angle_url(match):
        url = match.group(1)
        if 'asx.com.au' in url:
            text = 'ASX Announcement'
        elif 'afr.com' in url:
            text = 'AFR'
        elif 'bloomberg.com' in url:
            text = 'Bloomberg'
        elif 'reuters.com' in url:
            text = 'Reuters'
        elif 'yahoo.com' in url:
            text = 'Yahoo Finance'
        else:
            text = 'Source'
        return f'<a href="{url}" style="color:#3498db;text-decoration:underline;">{text}</a>'
    
    html = re.sub(pattern, replace_angle_url, html)
    
    return html


# ============================================================================
# EMAIL SENDING
# ============================================================================

def send_email(html_content: str, recipient: str, smtp_email: str, smtp_password: str, subject: str):
    """Send HTML email via Gmail SMTP."""
    
    msg = MIMEText(html_content, 'html', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = smtp_email
    msg['To'] = recipient
    
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(smtp_email, smtp_password)
        server.sendmail(smtp_email, recipient, msg.as_string())


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    """Main function - orchestrates the multi-search process."""
    
    print("=" * 70)
    print("🚀 Berkholts Daily Stock Summary Emailer")
    print("📊 Multi-Search Version (Higher Accuracy)")
    print(f"⏰ Started at: {datetime.now()}")
    print("=" * 70)
    
    # Check environment variables
    print("\n📋 Checking environment variables...")
    
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
        print(f"\n❌ Missing: {', '.join(missing)}")
        sys.exit(1)
    
    print("✅ All environment variables found")
    
    recipients = [e.strip() for e in recipient_emails_str.split(',') if e.strip()]
    print(f"📧 Recipients: {', '.join(recipients)}")
    print(f"📈 Stocks to analyze: {len(STOCKS)}")
    
    # Initialize client
    client = anthropic.Anthropic(api_key=anthropic_key)
    
    # Calculate dates
    today = datetime.now()
    today_str = today.strftime("%B %d, %Y")
    
    # Cache for shared searches (industry dynamics)
    industry_cache = {}
    
    # Process each stock
    all_stock_html = ""
    
    for i, stock in enumerate(STOCKS, 1):
        print(f"\n{'=' * 70}")
        print(f"📊 STOCK {i}/{len(STOCKS)}: {stock['name']} ({stock['ticker']})")
        print("=" * 70)
        
        # Collect all data for this stock
        stock_data = {}
        
        # 1. Price data
        stock_data['price'] = get_price_data(client, stock['ticker'], stock['name'])
        
        # 2. Recent news (last 7 days)
        stock_data['news'] = get_recent_news(client, stock['ticker'], stock['name'])
        
        # 3. Last announcement
        stock_data['announcement'] = get_last_announcement(client, stock['ticker'], stock['name'])
        
        # 4. Last earnings
        stock_data['earnings'] = get_earnings_report(client, stock['ticker'], stock['name'])
        
        # 5. Industry dynamics (cached by industry)
        industry = stock['industry']
        if industry not in industry_cache:
            industry_cache[industry] = get_industry_dynamics(client, industry)
        stock_data['industry'] = industry_cache[industry]
        
        # 6. Competitor news
        stock_data['competitors'] = get_competitor_news(client, stock['competitors'], industry)
        
        # Generate HTML for this stock
        print(f"\n   🎨 Generating HTML...")
        stock_html = generate_html_for_stock(client, stock, stock_data, i)
        all_stock_html += stock_html
        
        print(f"   ✅ Complete!")
    
    # Wrap in email template
    print(f"\n{'=' * 70}")
    print("📧 Assembling final email...")
    print("=" * 70)
    
    final_html = wrap_in_email_template(all_stock_html, today_str)
    final_html = fix_urls_in_html(final_html)
    
    print(f"📄 Total HTML length: {len(final_html)} characters")
    
    # Send emails
    print(f"\n{'=' * 70}")
    print("📤 Sending emails...")
    print("=" * 70)
    
    subject = f"Berkholts Stock Summaries - {today_str}"
    
    for recipient in recipients:
        try:
            print(f"   📤 Sending to: {recipient}")
            send_email(final_html, recipient, smtp_email, smtp_password, subject)
            print(f"   ✅ Sent!")
        except Exception as e:
            print(f"   ❌ Failed: {str(e)}")
    
    print(f"\n{'=' * 70}")
    print("✅ ALL DONE!")
    print(f"⏰ Completed at: {datetime.now()}")
    print("=" * 70)


if __name__ == "__main__":
    main()
