#!/usr/bin/env python3
"""
Berkholts Daily Stock Summary Emailer - TWO-STEP VERSION
==========================================================
Based on the 7:50pm version that actually worked.

The key insight: Claude needs to do research FIRST in one call,
then format the results into HTML in a SECOND call.

When we combine research + formatting in one prompt, Claude
either skips the research or produces generic filler.
"""

import os
import sys
import smtplib
import re
import requests
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import anthropic
import yfinance as yf


# ============================================================================
# CONFIGURATION
# ============================================================================

STOCKS = [
    {
        "name": "AUB Group Limited",
        "ticker": "AUB.AX",
        "asx_code": "AUB",
        "industry": "insurance",
        "competitors": ["Steadfast Group (SDF.AX)", "PSC Insurance (PSI.AX)"]
    },
    {
        "name": "Mineral Resources Limited",
        "ticker": "MIN.AX",
        "asx_code": "MIN",
        "industry": "mining",
        "competitors": ["Pilbara Minerals (PLS.AX)", "Fortescue Metals (FMG.AX)"]
    },
]


# ============================================================================
# PRICE DATA - yfinance (FREE & ACCURATE)
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
# STEP 1: RESEARCH - Claude searches and collects raw data
# ============================================================================

def research_stock(client: anthropic.Anthropic, stock: dict, today_str: str) -> str:
    """
    STEP 1: Research a stock using web search.
    This call ONLY does research - no HTML formatting.
    Returns raw research data as text.
    """
    
    prompt = f"""You are a financial research analyst. Today is {today_str}.

Research {stock['name']} (ASX: {stock['asx_code']}, Yahoo: {stock['ticker']}) and report your findings.

SEARCH AND REPORT ON:

1. RECENT NEWS (Last 7 days)
   Search: "{stock['name']} news January 2026"
   - Any material announcements or news?
   - Report with dates and source URLs
   - If nothing found, write "NO RECENT NEWS FOUND"

2. LAST ASX ANNOUNCEMENT
   Search: "site:asx.com.au {stock['asx_code']} announcement"
   Search: "{stock['name']} ASX announcement 2025"
   - Find the most recent price-sensitive announcement
   - Report: Date, Type, Summary with SPECIFIC NUMBERS
   - Include the actual URL if you find it
   - Real URLs look like: https://announcements.asx.com.au/asxpdf/YYYYMMDD/pdf/XXXXX.pdf

3. LAST EARNINGS RESULTS
   Search: "{stock['name']} annual results 2025" OR "{stock['name']} half year results"
   - Date of announcement
   - Revenue (with % growth)
   - NPAT/Profit (with % growth)
   - EPS
   - Dividend
   - Source URL

4. INDUSTRY NEWS ({stock['industry']} sector)
   Search: "Australian {stock['industry']} industry 2026 statistics"
   - Find 3 specific data points with numbers
   - Include dates and source URLs

5. COMPETITOR NEWS
   Search: "{stock['competitors'][0]} ASX announcement 2026"
   Search: "{stock['competitors'][1]} ASX results"
   - Find specific news about these named competitors
   - Include dates and source URLs

FORMAT YOUR RESPONSE AS RAW DATA:
==================================
STOCK: {stock['name']}

RECENT_NEWS:
[your findings or "NO RECENT NEWS FOUND"]

LAST_ANNOUNCEMENT:
Date: [date]
Type: [type]
Summary: [summary with numbers]
URL: [actual URL or "NOT FOUND"]

EARNINGS:
Date: [date]
Type: [Annual/Half-Year]
Revenue: [amount and growth]
NPAT: [amount and growth]
EPS: [amount]
Dividend: [amount]
URL: [URL or "NOT FOUND"]

INDUSTRY_DYNAMICS:
1. [date]: [fact with numbers] - Source: [name] URL: [url]
2. [date]: [fact with numbers] - Source: [name] URL: [url]
3. [date]: [fact with numbers] - Source: [name] URL: [url]

COMPETITOR_NEWS:
1. [competitor name]: [date] - [news] - URL: [url]
2. [competitor name]: [date] - [news] - URL: [url]
==================================

IMPORTANT: Use web search to find REAL information. Do not make up data."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )
        
        result = ""
        for block in response.content:
            if hasattr(block, 'text'):
                result += block.text
        
        return result
    
    except Exception as e:
        return f"RESEARCH ERROR: {str(e)}"


# ============================================================================
# STEP 2: FORMAT - Convert research into HTML
# ============================================================================

def format_to_html(client: anthropic.Anthropic, stock: dict, price_data: dict, research: str, stock_num: int) -> str:
    """
    STEP 2: Format the research data into HTML.
    This call ONLY formats - no web searching.
    """
    
    # Build price HTML (from yfinance - accurate)
    if price_data.get('error'):
        price_html = f'<p style="color:red;">Price unavailable: {price_data["error"]}</p>'
    else:
        change_color = "#27ae60" if price_data['change_percent'] >= 0 else "#e74c3c"
        change_sign = "+" if price_data['change_percent'] >= 0 else ""
        price_html = f'''<p style="margin:10px 0;line-height:1.6;">
<strong style="color:#2980b9;">YESTERDAY ({price_data['yesterday_date']}):</strong> A${price_data['yesterday_close']:.2f} | 
<strong style="color:#2980b9;">PREVIOUS ({price_data['previous_date']}):</strong> A${price_data['previous_close']:.2f} | 
<strong style="color:#2980b9;">CHANGE:</strong> <span style="color:{change_color};font-weight:bold;">{change_sign}{price_data['change_percent']:.2f}%</span>
</p>'''

    # Fallback URL for when no real URL is found
    fallback_url = f"https://www.asx.com.au/markets/company/{stock['asx_code']}"
    
    prompt = f"""Convert this research into HTML for an email. Output ONLY HTML code.

RESEARCH DATA:
{research}

FALLBACK URL (use when URL says "NOT FOUND"): {fallback_url}

Generate HTML using this EXACT structure:

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">REASON FOR MOVE:</strong><br>
[Use RECENT_NEWS section. If "NO RECENT NEWS FOUND", write "No material announcements in the past week"]
</p>

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">LAST PRICE-SENSITIVE ANNOUNCEMENT:</strong><br>
<strong>Date:</strong> [from LAST_ANNOUNCEMENT]<br>
<strong>Type:</strong> [from LAST_ANNOUNCEMENT]<br>
<strong>Summary:</strong> [from LAST_ANNOUNCEMENT - keep specific numbers]<br>
<strong>Source:</strong> <a href="[URL from research, or fallback URL]" style="color:#3498db;text-decoration:underline;">ASX Announcement</a>
</p>

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">LAST EARNINGS REPORT:</strong><br>
<strong>Date:</strong> [date] | <strong>Type:</strong> [type]<br>
<strong>Revenue:</strong> [revenue] | <strong>NPAT:</strong> [npat] | <strong>EPS:</strong> [eps] | <strong>Dividend:</strong> [div]<br>
<strong>Source:</strong> <a href="[URL or fallback]" style="color:#3498db;text-decoration:underline;">ASX Announcement</a>
</p>

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">INDUSTRY DYNAMICS:</strong>
</p>
<ul style="margin:5px 0 15px 20px;line-height:1.8;">
[3 list items from INDUSTRY_DYNAMICS, each with <a href="URL">Source</a>]
</ul>

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">COMPETITIVE DYNAMICS:</strong>
</p>
<ul style="margin:5px 0 15px 20px;line-height:1.8;">
[2 list items from COMPETITOR_NEWS, each with <a href="URL">Source</a>]
</ul>

RULES:
1. All URLs in <a href="URL"> format
2. Keep all specific numbers from the research
3. If data is missing, use the fallback URL
4. Output ONLY HTML - no explanations"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=3000,
            system="You are an HTML formatter. Convert the research data into clean HTML. Output ONLY HTML code, nothing else.",
            messages=[{"role": "user", "content": prompt}]
        )
        
        analysis_html = ""
        for block in response.content:
            if hasattr(block, 'text'):
                analysis_html += block.text
        
    except Exception as e:
        analysis_html = f"<p style='color:red;'>Formatting error: {str(e)}</p>"
    
    # Combine header + price + formatted analysis
    return f'''
<h2 style="color:#34495e;margin-top:30px;border-bottom:2px solid #ecf0f1;padding-bottom:8px;">
{stock_num}. {stock['name']} ({stock['ticker']})
</h2>

{price_html}

{analysis_html}

<hr style="border:none;border-top:1px solid #ecf0f1;margin:30px 0;">
'''


# ============================================================================
# URL VALIDATION
# ============================================================================

def validate_asx_url(url: str) -> bool:
    """Check if an ASX PDF URL exists."""
    if not url or 'asx.com.au' not in url or '.pdf' not in url:
        return False
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.head(url, headers=headers, timeout=10, allow_redirects=True)
        return response.status_code == 200
    except:
        return False


def validate_urls_in_html(html: str, asx_code: str) -> str:
    """Validate ASX PDF URLs and replace broken ones."""
    fallback = f"https://www.asx.com.au/markets/company/{asx_code}"
    
    pattern = r'href="(https://[^"]*\.pdf)"'
    
    def check_and_replace(match):
        url = match.group(1)
        if 'asx.com.au' in url and not validate_asx_url(url):
            print(f"      ⚠️ Broken URL: {url[:50]}... → Using fallback")
            return f'href="{fallback}"'
        return match.group(0)
    
    return re.sub(pattern, check_and_replace, html)


# ============================================================================
# EMAIL TEMPLATE
# ============================================================================

def wrap_in_template(content: str, today: str) -> str:
    """Wrap in Outlook-compatible HTML template."""
    return f'''<!DOCTYPE html>
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
Generated by Berkholts Stock Summary System<br>
Prices: Yahoo Finance | Analysis: Claude AI
</p>

</td></tr>
</table>
</td></tr>
</table>
</body>
</html>'''


def send_email(html: str, recipient: str, smtp_email: str, smtp_password: str, subject: str):
    """Send HTML email via Gmail SMTP."""
    msg = MIMEText(html, 'html', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = smtp_email
    msg['To'] = recipient
    
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(smtp_email, smtp_password)
        server.sendmail(smtp_email, recipient, msg.as_string())


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("=" * 70)
    print("🚀 Berkholts Daily Stock Summary Emailer")
    print("📊 TWO-STEP VERSION: Research first, then format")
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
    
    client = anthropic.Anthropic(api_key=anthropic_key)
    today_str = datetime.now().strftime("%B %d, %Y")
    
    all_html = ""
    
    for i, stock in enumerate(STOCKS, 1):
        print(f"\n{'=' * 70}")
        print(f"📊 STOCK {i}/{len(STOCKS)}: {stock['name']}")
        print("=" * 70)
        
        # Get price (yfinance - accurate)
        print("   💰 Getting price from Yahoo Finance...", end=" ")
        price = get_stock_price(stock['ticker'])
        if price.get('error'):
            print(f"⚠️ {price['error']}")
        else:
            print(f"✅ A${price['yesterday_close']:.2f} ({price['change_percent']:+.2f}%)")
        
        # STEP 1: Research
        print("   🔍 STEP 1: Researching (web search)...")
        research = research_stock(client, stock, today_str)
        print(f"      Research length: {len(research)} chars")
        
        # STEP 2: Format
        print("   🎨 STEP 2: Formatting to HTML...")
        stock_html = format_to_html(client, stock, price, research, i)
        
        # Validate URLs
        print("   🔗 Validating URLs...")
        stock_html = validate_urls_in_html(stock_html, stock['asx_code'])
        
        all_html += stock_html
        print("   ✅ Complete!")
    
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
