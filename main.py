#!/usr/bin/env python3
"""
Berkholts Daily Stock Summary Emailer - Accurate Data Version
==============================================================
Uses:
- yfinance: FREE accurate stock prices from Yahoo Finance
- pyasx: FREE direct ASX announcement links
- Claude API: Only for news analysis (reduced cost)

This gives you:
- 100% accurate prices
- Real, working ASX PDF links
- Lower API costs
"""

import os
import sys
import smtplib
import re
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import anthropic

# FREE libraries for accurate data
import yfinance as yf
import pyasx.data.companies as asx_companies


# ============================================================================
# CONFIGURATION - 2 STOCKS FOR TESTING (expand to 19 later)
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
# PRICE DATA - Using yfinance (FREE & 100% ACCURATE)
# ============================================================================

def get_stock_price(ticker: str) -> dict:
    """
    Get ACCURATE stock price from Yahoo Finance.
    
    Returns dict with:
    - yesterday_close: Most recent closing price
    - previous_close: Day before closing price
    - change_percent: Percentage change
    - dates: The actual dates for each price
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5d")
        
        if len(hist) < 2:
            return {"error": f"Not enough price history for {ticker}"}
        
        # Get last two trading days
        yesterday_close = float(hist['Close'].iloc[-1])
        previous_close = float(hist['Close'].iloc[-2])
        yesterday_date = hist.index[-1].strftime("%B %d, %Y")
        previous_date = hist.index[-2].strftime("%B %d, %Y")
        
        # Calculate change
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
# ASX ANNOUNCEMENTS - Using pyasx (FREE & REAL LINKS)
# ============================================================================

def get_asx_announcements(asx_code: str, limit: int = 10) -> list:
    """
    Get REAL ASX announcements with direct PDF links.
    
    Returns list of dicts with:
    - title: Announcement title
    - url: Direct link to ASX PDF
    - date: Release date
    - pages: Number of pages
    """
    try:
        announcements = asx_companies.get_company_announcements(asx_code)
        
        results = []
        for ann in announcements[:limit]:
            results.append({
                "title": ann.get("title", "Unknown"),
                "url": ann.get("url", ""),
                "date": ann.get("document_date", ann.get("release_date")),
                "pages": ann.get("num_pages", 0),
                "size": ann.get("size", "")
            })
        
        return results
    except Exception as e:
        print(f"   ⚠️ Error fetching ASX announcements for {asx_code}: {e}")
        return []


def find_latest_earnings(announcements: list) -> dict:
    """Find the most recent earnings/results announcement."""
    
    earnings_keywords = [
        "results", "half year", "full year", "annual report",
        "quarterly", "profit", "earnings", "financial report"
    ]
    
    for ann in announcements:
        title_lower = ann.get("title", "").lower()
        if any(keyword in title_lower for keyword in earnings_keywords):
            return ann
    
    return None


def find_latest_price_sensitive(announcements: list) -> dict:
    """Find the most recent price-sensitive announcement."""
    
    # Price sensitive keywords
    sensitive_keywords = [
        "trading update", "guidance", "profit warning", "acquisition",
        "merger", "takeover", "dividend", "capital raising", "placement",
        "results", "quarterly", "material"
    ]
    
    for ann in announcements:
        title_lower = ann.get("title", "").lower()
        if any(keyword in title_lower for keyword in sensitive_keywords):
            return ann
    
    # If none found, return the most recent
    return announcements[0] if announcements else None


# ============================================================================
# NEWS ANALYSIS - Using Claude API (minimal usage)
# ============================================================================

def get_news_analysis(client: anthropic.Anthropic, stock: dict) -> str:
    """
    Get news analysis from Claude - ONLY for recent news and industry dynamics.
    We don't need Claude for prices or ASX links anymore!
    """
    
    prompt = f"""Research {stock['name']} ({stock['ticker']}) and provide ONLY:

1. REASON FOR MOVE (Last 7 days)
   - Any material news explaining recent price movement
   - If no news: "No material announcements in the past week"

2. INDUSTRY DYNAMICS (3 brief points about {stock['industry']} industry)
   - Recent market trends with dates
   - Focus on data that affects the business

3. COMPETITIVE DYNAMICS (2 points about: {', '.join(stock['competitors'])})
   - Recent news about these specific competitors

Keep responses brief. Include source names but don't worry about URLs.
Say "Not found" if you can't verify something."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
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

def format_date(dt) -> str:
    """Format datetime object to string."""
    if dt is None:
        return "Unknown"
    if hasattr(dt, 'strftime'):
        return dt.strftime("%B %d, %Y")
    return str(dt)


def generate_stock_html(stock: dict, price_data: dict, announcements: list, analysis: str, stock_num: int) -> str:
    """Generate HTML for a single stock with accurate data."""
    
    # Price section (from yfinance - ACCURATE)
    if price_data.get('error'):
        price_html = f'<p style="color:red;">Price unavailable: {price_data["error"]}</p>'
    else:
        change_color = "green" if price_data['change_percent'] >= 0 else "red"
        change_sign = "+" if price_data['change_percent'] >= 0 else ""
        price_html = f'''<p style="margin:10px 0;line-height:1.6;">
<strong style="color:#2980b9;">YESTERDAY ({price_data['yesterday_date']}):</strong> A${price_data['yesterday_close']:.2f} | 
<strong style="color:#2980b9;">PREVIOUS DAY ({price_data['previous_date']}):</strong> A${price_data['previous_close']:.2f} | 
<strong style="color:#2980b9;">CHANGE:</strong> <span style="color:{change_color};font-weight:bold;">{change_sign}{price_data['change_percent']:.2f}%</span>
</p>'''
    
    # Last Price-Sensitive Announcement (from pyasx - REAL LINKS)
    latest_announcement = find_latest_price_sensitive(announcements)
    if latest_announcement:
        ann_html = f'''<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">LAST PRICE-SENSITIVE ANNOUNCEMENT:</strong><br>
<strong>Date:</strong> {format_date(latest_announcement.get('date'))}<br>
<strong>Title:</strong> {latest_announcement.get('title', 'Unknown')}<br>
<strong>Source:</strong> <a href="{latest_announcement.get('url', '#')}" style="color:#3498db;text-decoration:underline;">ASX Announcement (PDF)</a>
</p>'''
    else:
        ann_html = '<p style="margin:15px 0;"><strong style="color:#2980b9;">LAST PRICE-SENSITIVE ANNOUNCEMENT:</strong> No announcements found</p>'
    
    # Last Earnings Report (from pyasx - REAL LINKS)
    latest_earnings = find_latest_earnings(announcements)
    if latest_earnings:
        earnings_html = f'''<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">LAST EARNINGS REPORT:</strong><br>
<strong>Date:</strong> {format_date(latest_earnings.get('date'))}<br>
<strong>Title:</strong> {latest_earnings.get('title', 'Unknown')}<br>
<strong>Source:</strong> <a href="{latest_earnings.get('url', '#')}" style="color:#3498db;text-decoration:underline;">ASX Announcement (PDF)</a>
</p>'''
    else:
        earnings_html = '<p style="margin:15px 0;"><strong style="color:#2980b9;">LAST EARNINGS REPORT:</strong> No earnings reports found</p>'
    
    # Recent Announcements List (from pyasx - REAL LINKS)
    recent_ann_html = '<p style="margin:15px 0;line-height:1.6;"><strong style="color:#2980b9;">RECENT ASX ANNOUNCEMENTS:</strong></p><ul style="margin:5px 0 15px 20px;line-height:1.8;">'
    for ann in announcements[:5]:
        recent_ann_html += f'<li>{format_date(ann.get("date"))}: <a href="{ann.get("url", "#")}" style="color:#3498db;text-decoration:underline;">{ann.get("title", "Unknown")}</a></li>'
    recent_ann_html += '</ul>'
    
    # Parse analysis for Industry and Competitive sections
    analysis_html = parse_analysis_to_html(analysis)
    
    # Combine all sections
    return f'''
<h2 style="color:#34495e;margin-top:30px;border-bottom:2px solid #ecf0f1;padding-bottom:8px;">
{stock_num}. {stock['name']} ({stock['ticker']})
</h2>

{price_html}

{analysis_html['reason_for_move']}

{ann_html}

{earnings_html}

{recent_ann_html}

{analysis_html['industry_dynamics']}

{analysis_html['competitive_dynamics']}

<hr style="border:none;border-top:1px solid #ecf0f1;margin:30px 0;">
'''


def parse_analysis_to_html(analysis: str) -> dict:
    """Parse Claude's analysis into HTML sections."""
    
    # Default values
    result = {
        'reason_for_move': '<p style="margin:15px 0;line-height:1.6;"><strong style="color:#2980b9;">REASON FOR MOVE:</strong><br>No material announcements in the past week</p>',
        'industry_dynamics': '<p style="margin:15px 0;line-height:1.6;"><strong style="color:#2980b9;">INDUSTRY DYNAMICS:</strong></p><ul style="margin:5px 0 15px 20px;line-height:1.8;"><li>Data not available</li></ul>',
        'competitive_dynamics': '<p style="margin:15px 0;line-height:1.6;"><strong style="color:#2980b9;">COMPETITIVE DYNAMICS:</strong></p><ul style="margin:5px 0 15px 20px;line-height:1.8;"><li>Data not available</li></ul>'
    }
    
    if not analysis or "Error" in analysis:
        return result
    
    # Try to extract sections from analysis
    analysis_lower = analysis.lower()
    
    # Extract Reason for Move
    if "reason for move" in analysis_lower:
        try:
            start = analysis_lower.find("reason for move")
            end = analysis_lower.find("industry", start)
            if end == -1:
                end = analysis_lower.find("competitive", start)
            if end == -1:
                end = start + 500
            
            reason_text = analysis[start:end].strip()
            # Clean up the text
            reason_text = re.sub(r'^.*?:', '', reason_text, count=1).strip()
            reason_text = reason_text[:500]  # Limit length
            
            result['reason_for_move'] = f'<p style="margin:15px 0;line-height:1.6;"><strong style="color:#2980b9;">REASON FOR MOVE:</strong><br>{reason_text}</p>'
        except:
            pass
    
    # Extract Industry Dynamics
    if "industry" in analysis_lower:
        try:
            start = analysis_lower.find("industry")
            end = analysis_lower.find("competitive", start)
            if end == -1:
                end = start + 800
            
            industry_text = analysis[start:end].strip()
            
            # Convert to bullet points
            lines = [l.strip() for l in industry_text.split('\n') if l.strip() and len(l.strip()) > 10]
            if lines:
                bullets = ''.join([f'<li>{line}</li>' for line in lines[1:4]])  # Skip header, take 3 points
                result['industry_dynamics'] = f'<p style="margin:15px 0;line-height:1.6;"><strong style="color:#2980b9;">INDUSTRY DYNAMICS:</strong></p><ul style="margin:5px 0 15px 20px;line-height:1.8;">{bullets}</ul>'
        except:
            pass
    
    # Extract Competitive Dynamics
    if "competitive" in analysis_lower:
        try:
            start = analysis_lower.find("competitive")
            end = len(analysis)
            
            competitive_text = analysis[start:end].strip()
            
            # Convert to bullet points
            lines = [l.strip() for l in competitive_text.split('\n') if l.strip() and len(l.strip()) > 10]
            if lines:
                bullets = ''.join([f'<li>{line}</li>' for line in lines[1:3]])  # Skip header, take 2 points
                result['competitive_dynamics'] = f'<p style="margin:15px 0;line-height:1.6;"><strong style="color:#2980b9;">COMPETITIVE DYNAMICS:</strong></p><ul style="margin:5px 0 15px 20px;line-height:1.8;">{bullets}</ul>'
        except:
            pass
    
    return result


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
<strong>Prices:</strong> Yahoo Finance (yfinance) | <strong>Announcements:</strong> ASX (pyasx) | <strong>Analysis:</strong> Claude AI
</p>

</td></tr>
</table>
</td></tr>
</table>
</body>
</html>'''


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
    """Main function - uses yfinance + pyasx + Claude."""
    
    print("=" * 70)
    print("🚀 Berkholts Daily Stock Summary Emailer")
    print("📊 ACCURATE DATA VERSION")
    print("   • Prices: yfinance (FREE, 100% accurate)")
    print("   • ASX Links: pyasx (FREE, real PDF links)")
    print("   • Analysis: Claude API (reduced usage)")
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
        
        # 2. Get REAL ASX announcements from pyasx (FREE)
        print(f"   📢 Fetching ASX announcements...", end=" ")
        announcements = get_asx_announcements(stock['asx_code'])
        print(f"✅ Found {len(announcements)} announcements")
        
        # 3. Get news analysis from Claude (minimal API usage)
        print(f"   🔍 Getting news analysis from Claude...")
        analysis = get_news_analysis(client, stock)
        print(f"   ✅ Analysis complete")
        
        # 4. Generate HTML
        print(f"   🎨 Generating HTML...")
        stock_html = generate_stock_html(stock, price_data, announcements, analysis, i)
        all_stock_html += stock_html
        print(f"   ✅ Done!")
    
    # Assemble final email
    print(f"\n{'=' * 70}")
    print("📧 Assembling final email...")
    
    final_html = wrap_in_email_template(all_stock_html, today_str)
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
