#!/usr/bin/env python3
"""
Berkholts Daily Stock Summary Emailer - URL VALIDATION VERSION
================================================================
Uses:
- yfinance: FREE accurate stock prices from Yahoo Finance  
- Claude API: For news analysis with VALIDATED URLs only
- URL validation: Checks ASX links exist before including them

Key fix: ASX URLs are verified before being included in email.
If Claude invents a fake URL, it gets caught and replaced with
a link to the company's announcement page instead.
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
# CONFIGURATION - 2 STOCKS FOR TESTING
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
# URL VALIDATION - Check if ASX PDF URLs actually exist
# ============================================================================

def validate_asx_url(url: str) -> bool:
    """
    Check if an ASX PDF URL actually exists by doing a HEAD request.
    Returns True if the URL returns 200, False otherwise.
    """
    if not url or 'asx.com.au' not in url:
        return False
    
    try:
        # Use HEAD request to check if file exists without downloading
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.head(url, headers=headers, timeout=10, allow_redirects=True)
        return response.status_code == 200
    except:
        return False


def validate_and_fix_urls_in_html(html: str, asx_code: str) -> str:
    """
    Find all ASX URLs in the HTML, validate them, and replace broken ones
    with a link to the company's announcement page.
    """
    # Pattern to find ASX announcement URLs
    asx_url_pattern = r'href="(https://[^"]*asx[^"]*\.pdf)"'
    
    # Fallback URL - the company's announcement page on ASX
    fallback_url = f"https://www.asx.com.au/markets/company/{asx_code}"
    
    def replace_if_invalid(match):
        url = match.group(1)
        if validate_asx_url(url):
            # URL is valid, keep it
            return match.group(0)
        else:
            # URL is invalid/fake, replace with fallback
            print(f"      ⚠️ Invalid URL detected: {url[:60]}...")
            print(f"         Replacing with company page: {fallback_url}")
            return f'href="{fallback_url}"'
    
    return re.sub(asx_url_pattern, replace_if_invalid, html)


# ============================================================================
# PRICE DATA - Using yfinance (FREE & ACCURATE)
# ============================================================================

def get_stock_price(ticker: str) -> dict:
    """Get ACCURATE stock price from Yahoo Finance."""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5d")
        
        if len(hist) < 2:
            return {"error": f"Not enough price history for {ticker}"}
        
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
# CLAUDE ANALYSIS - With strict URL requirements
# ============================================================================

def get_stock_analysis(client: anthropic.Anthropic, stock: dict) -> str:
    """
    Get comprehensive analysis from Claude with URLs.
    """
    
    prompt = f"""Research {stock['name']} (ASX: {stock['asx_code']}, Yahoo: {stock['ticker']}).

Provide these sections:

1. REASON FOR MOVE (Last 7 days)
   - Any material news explaining recent price movement
   - Include source URL if found
   - If no news, say "No material announcements in the past week"

2. LAST PRICE-SENSITIVE ANNOUNCEMENT
   Search for real ASX announcements using: site:announcements.asx.com.au {stock['asx_code']}
   - Date (exact)
   - Type (trading update/guidance/results/etc)
   - Summary WITH SPECIFIC NUMBERS
   - IMPORTANT: Only include a URL if you found it in search results
   - If you cannot find the actual URL, write "URL: See ASX website"

3. LAST EARNINGS REPORT
   - Date, Type
   - Revenue, NPAT, EPS, Dividend with % growth
   - URL if found, otherwise "URL: See ASX website"

4. INDUSTRY DYNAMICS ({stock['industry']} - 3 bullet points)
   - Market trends with dates and numbers
   - Each with source URL

5. COMPETITIVE DYNAMICS (2 bullet points about: {', '.join(stock['competitors'])})
   - Specific competitor news with dates
   - Each with source URL

CRITICAL RULES:
- NEVER invent or guess URLs - only use URLs you actually found in search results
- If you cannot find a real URL, write "URL: See ASX website" or "URL: Not found"
- Real ASX PDF URLs look like: https://announcements.asx.com.au/asxpdf/YYYYMMDD/pdf/XXXXX.pdf
- The XXXXX part is a real document ID like "06sr2bsh6yv802" - NEVER make these up
"""

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
        return f"Error: {str(e)}"


# ============================================================================
# HTML GENERATION
# ============================================================================

def generate_stock_html(client: anthropic.Anthropic, stock: dict, price_data: dict, analysis: str, stock_num: int) -> str:
    """Generate HTML for a single stock."""
    
    # Price HTML (from yfinance - ACCURATE)
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
    
    # Ask Claude to format analysis into HTML
    format_prompt = f"""Convert this analysis into HTML sections. Output ONLY HTML code.

STOCK: {stock['name']} ({stock['ticker']})

ANALYSIS DATA:
{analysis}

Generate these HTML sections (PRICE is already done, don't include it):

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">REASON FOR MOVE:</strong><br>
[content - if no material news, write "No material announcements in the past week"]
</p>

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">LAST PRICE-SENSITIVE ANNOUNCEMENT:</strong><br>
<strong>Date:</strong> [date]<br>
<strong>Type:</strong> [type]<br>
<strong>Summary:</strong> [summary with numbers]<br>
<strong>Source:</strong> <a href="[URL or https://www.asx.com.au/markets/company/{stock['asx_code']}]" style="color:#3498db;text-decoration:underline;">ASX Announcement</a>
</p>

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">LAST EARNINGS REPORT:</strong><br>
[date, type, metrics]<br>
<strong>Source:</strong> <a href="[URL or https://www.asx.com.au/markets/company/{stock['asx_code']}]" style="color:#3498db;text-decoration:underline;">ASX Announcement</a>
</p>

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">INDUSTRY DYNAMICS:</strong>
</p>
<ul style="margin:5px 0 15px 20px;line-height:1.8;">
<li>[point with <a href="URL" style="color:#3498db;text-decoration:underline;">Source</a>]</li>
<li>[point]</li>
<li>[point]</li>
</ul>

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">COMPETITIVE DYNAMICS:</strong>
</p>
<ul style="margin:5px 0 15px 20px;line-height:1.8;">
<li>[competitor point]</li>
<li>[competitor point]</li>
</ul>

RULES:
- All URLs must be in <a href> format
- If URL says "See ASX website" or "Not found", use: https://www.asx.com.au/markets/company/{stock['asx_code']}
- Output ONLY HTML, no explanations"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=3000,
            system="You are an HTML generator. Output ONLY valid HTML code. No explanations.",
            messages=[{"role": "user", "content": format_prompt}]
        )
        
        analysis_html = ""
        for block in response.content:
            if hasattr(block, 'text'):
                analysis_html += block.text
        
    except Exception as e:
        analysis_html = f"<p style='color:red;'>Analysis error: {str(e)}</p>"
    
    # Combine
    full_html = f'''
<h2 style="color:#34495e;margin-top:30px;border-bottom:2px solid #ecf0f1;padding-bottom:8px;">
{stock_num}. {stock['name']} ({stock['ticker']})
</h2>

{price_html}

{analysis_html}

<hr style="border:none;border-top:1px solid #ecf0f1;margin:30px 0;">
'''
    
    # VALIDATE AND FIX any broken ASX URLs
    print(f"      🔍 Validating ASX URLs...")
    full_html = validate_and_fix_urls_in_html(full_html, stock['asx_code'])
    
    return full_html


def wrap_in_email_template(content: str, today: str) -> str:
    """Wrap content in Outlook-compatible email template."""
    
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
<strong>Prices:</strong> Yahoo Finance (accurate) | <strong>Analysis:</strong> Claude AI (URLs validated)
</p>

</td></tr>
</table>
</td></tr>
</table>
</body>
</html>'''


def fix_urls_in_html(html: str) -> str:
    """Post-process HTML to fix angle bracket URLs."""
    
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
        else:
            text = 'Source'
        return f'<a href="{url}" style="color:#3498db;text-decoration:underline;">{text}</a>'
    
    return re.sub(pattern, replace_angle_url, html)


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
# MAIN
# ============================================================================

def main():
    """Main function."""
    
    print("=" * 70)
    print("🚀 Berkholts Daily Stock Summary Emailer")
    print("🔒 URL VALIDATION VERSION - Fake links will be caught!")
    print("   • Prices: yfinance (FREE, accurate)")
    print("   • Analysis: Claude API with web search")
    print("   • URLs: Validated before inclusion")
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
    print(f"📈 Stocks: {len(STOCKS)}")
    
    # Initialize Claude client
    client = anthropic.Anthropic(api_key=anthropic_key)
    
    # Calculate today's date
    today = datetime.now()
    today_str = today.strftime("%B %d, %Y")
    
    # Process each stock
    all_stock_html = ""
    
    for i, stock in enumerate(STOCKS, 1):
        print(f"\n{'=' * 70}")
        print(f"📊 STOCK {i}/{len(STOCKS)}: {stock['name']} ({stock['ticker']})")
        print("=" * 70)
        
        # 1. Get ACCURATE price from yfinance (FREE)
        print(f"   💰 Fetching price from Yahoo Finance...", end=" ")
        price_data = get_stock_price(stock['ticker'])
        if price_data.get('error'):
            print(f"⚠️ {price_data['error']}")
        else:
            print(f"✅ A${price_data['yesterday_close']:.2f} ({price_data['change_percent']:+.2f}%)")
        
        # 2. Get analysis from Claude
        print(f"   🔍 Getting analysis from Claude...")
        analysis = get_stock_analysis(client, stock)
        
        # 3. Generate HTML (includes URL validation)
        print(f"   🎨 Generating HTML...")
        stock_html = generate_stock_html(client, stock, price_data, analysis, i)
        all_stock_html += stock_html
        print(f"   ✅ Done!")
    
    # Assemble final email
    print(f"\n{'=' * 70}")
    print("📧 Assembling final email...")
    
    final_html = wrap_in_email_template(all_stock_html, today_str)
    final_html = fix_urls_in_html(final_html)
    print(f"📄 Total HTML: {len(final_html)} characters")
    
    # Send emails
    print(f"\n📤 Sending emails...")
    subject = f"Berkholts Stock Summaries - {today_str}"
    
    for recipient in recipients:
        try:
            print(f"   📤 {recipient}...", end=" ")
            send_email(final_html, recipient, smtp_email, smtp_password, subject)
            print("✅ Sent!")
        except Exception as e:
            print(f"❌ {str(e)}")
    
    print(f"\n{'=' * 70}")
    print("✅ ALL DONE!")
    print(f"⏰ Completed at: {datetime.now()}")
    print("=" * 70)


if __name__ == "__main__":
    main()
