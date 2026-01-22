#!/usr/bin/env python3
"""
Berkholts Daily Stock Summary Emailer - EXPLICIT WEB SEARCH VERSION
=====================================================================
Key insight: Claude decides whether to use web search.
This version explicitly requests web search in the prompt.
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


def research_and_format_stock(client: anthropic.Anthropic, stock: dict, price_data: dict, stock_num: int, today_str: str) -> str:
    """
    Single API call that does both research AND formatting.
    Uses very explicit instructions to trigger web search.
    """
    
    # Build price HTML first (from yfinance - accurate)
    if price_data.get('error'):
        price_section = f"Price data unavailable: {price_data['error']}"
    else:
        change_color = "#27ae60" if price_data['change_percent'] >= 0 else "#e74c3c"
        change_sign = "+" if price_data['change_percent'] >= 0 else ""
        price_section = f"""YESTERDAY ({price_data['yesterday_date']}): A${price_data['yesterday_close']:.2f}
PREVIOUS ({price_data['previous_date']}): A${price_data['previous_close']:.2f}
CHANGE: {change_sign}{price_data['change_percent']:.2f}%"""

    fallback_url = f"https://www.asx.com.au/markets/company/{stock['asx_code']}"
    
    prompt = f"""I need you to research {stock['name']} (ASX: {stock['asx_code']}) using web search and then create an HTML email section.

IMPORTANT: You MUST use web search for this task. Search the web NOW.

STEP 1 - SEARCH THE WEB FOR EACH OF THESE:
Search 1: "{stock['name']} ASX announcement December 2025 January 2026"
Search 2: "{stock['name']} earnings results FY25 revenue profit"
Search 3: "Australian {stock['industry']} industry trends 2025 2026"
Search 4: "{stock['competitors'][0]} ASX announcement 2026"

STEP 2 - CREATE HTML OUTPUT:
After searching, create an HTML section with the information you found.

PRICE DATA (already provided - do not search for this):
{price_section}

Create HTML output with this exact structure:

<h2 style="color:#34495e;margin-top:30px;border-bottom:2px solid #ecf0f1;padding-bottom:8px;">
{stock_num}. {stock['name']} ({stock['ticker']})
</h2>

<p style="margin:10px 0;line-height:1.6;">
<strong style="color:#2980b9;">YESTERDAY ({price_data.get('yesterday_date', 'N/A')}):</strong> A${price_data.get('yesterday_close', 'N/A')} | 
<strong style="color:#2980b9;">PREVIOUS ({price_data.get('previous_date', 'N/A')}):</strong> A${price_data.get('previous_close', 'N/A')} | 
<strong style="color:#2980b9;">CHANGE:</strong> <span style="color:{change_color};">{change_sign}{price_data.get('change_percent', 0):.2f}%</span>
</p>

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">REASON FOR MOVE:</strong><br>
[What you found from Search 1 - any recent news. If nothing found, write "No material announcements in the past week"]
</p>

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">LAST PRICE-SENSITIVE ANNOUNCEMENT:</strong><br>
<strong>Date:</strong> [from search]<br>
<strong>Type:</strong> [from search]<br>
<strong>Summary:</strong> [from search - include numbers]<br>
<strong>Source:</strong> <a href="[URL from search or {fallback_url}]" style="color:#3498db;">ASX Announcement</a>
</p>

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">LAST EARNINGS REPORT:</strong><br>
[Date, revenue, profit, EPS, dividend from Search 2]<br>
<strong>Source:</strong> <a href="[URL or {fallback_url}]" style="color:#3498db;">ASX Announcement</a>
</p>

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">INDUSTRY DYNAMICS:</strong>
</p>
<ul style="margin:5px 0 15px 20px;line-height:1.8;">
<li>[Point 1 from Search 3 with <a href="URL" style="color:#3498db;">Source</a>]</li>
<li>[Point 2 with source]</li>
<li>[Point 3 with source]</li>
</ul>

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">COMPETITIVE DYNAMICS:</strong>
</p>
<ul style="margin:5px 0 15px 20px;line-height:1.8;">
<li>[Competitor news from Search 4 with <a href="URL" style="color:#3498db;">Source</a>]</li>
<li>[Another competitor point]</li>
</ul>

<hr style="border:none;border-top:1px solid #ecf0f1;margin:30px 0;">

Output ONLY the HTML code, nothing else. Use real URLs from your search results."""

    try:
        print(f"      Calling Claude API with web_search tool...")
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            tools=[{
                "type": "web_search_20250305", 
                "name": "web_search",
                "max_uses": 10  # Allow multiple searches
            }],
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Log what type of response we got
        print(f"      Response stop_reason: {response.stop_reason}")
        print(f"      Response content blocks: {len(response.content)}")
        
        # Extract the text content
        result = ""
        for block in response.content:
            block_type = getattr(block, 'type', 'unknown')
            print(f"      Block type: {block_type}")
            if hasattr(block, 'text'):
                result += block.text
        
        if not result:
            print("      ⚠️ No text content in response!")
            return f"<h2>{stock['name']} - No content generated</h2><hr>"
        
        return result
    
    except Exception as e:
        print(f"      ❌ API Error: {str(e)}")
        return f"<h2>{stock['name']} - Error: {str(e)}</h2><hr>"


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
Generated by Berkholts Stock Summary System<br>
Prices: Yahoo Finance | Analysis: Claude AI with Web Search
</p>

</td></tr>
</table>
</td></tr>
</table>
</body>
</html>'''


def send_email(html: str, recipient: str, smtp_email: str, smtp_password: str, subject: str):
    """Send email."""
    msg = MIMEText(html, 'html', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = smtp_email
    msg['To'] = recipient
    
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(smtp_email, smtp_password)
        server.sendmail(smtp_email, recipient, msg.as_string())


def main():
    print("=" * 70)
    print("🚀 Berkholts Stock Emailer - EXPLICIT WEB SEARCH VERSION")
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
        
        # Get price (yfinance)
        print("   💰 Getting price...", end=" ")
        price = get_stock_price(stock['ticker'])
        if price.get('error'):
            print(f"⚠️ {price['error']}")
        else:
            print(f"✅ A${price['yesterday_close']:.2f} ({price['change_percent']:+.2f}%)")
        
        # Research and format in one call
        print("   🔍 Researching and formatting...")
        stock_html = research_and_format_stock(client, stock, price, i, today_str)
        all_html += stock_html
        print("   ✅ Done!")
    
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
