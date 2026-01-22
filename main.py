#!/usr/bin/env python3
"""
Berkholts Daily Stock Summary Emailer - ROBUST VERSION
========================================================
Uses:
- yfinance: FREE accurate stock prices from Yahoo Finance
- Multiple ASX endpoints: Try different APIs with fallback for announcements
- Claude API: For news analysis, industry dynamics, competitor analysis

Key improvements:
- Multiple ASX URL formats tried in sequence
- Proper error handling and fallback for announcements
- Full content sections: prices, news, announcements, industry, competitors
"""

import os
import sys
import smtplib
import re
import requests
import json
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import anthropic

# FREE library for accurate stock prices
import yfinance as yf


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
# ASX ANNOUNCEMENTS - Multiple endpoints with fallback
# ============================================================================

# Different headers to try (some endpoints are picky)
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.asx.com.au",
    "Referer": "https://www.asx.com.au/"
}


def try_markitdigital_api(asx_code: str, limit: int = 10) -> list:
    """
    Try the MarkitDigital API (used by ASX website internally).
    URL format: https://asx.api.markitdigital.com/asx-research/1.0/companies/{code}/announcements
    """
    try:
        url = f"https://asx.api.markitdigital.com/asx-research/1.0/companies/{asx_code.lower()}/announcements?count={limit}&market_sensitive=false"
        response = requests.get(url, headers=BROWSER_HEADERS, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            results = []
            for ann in data.get("data", [])[:limit]:
                doc_key = ann.get("documentKey", "")
                if doc_key:
                    # Build the CDN URL for the PDF
                    pdf_url = f"https://cdn-api.markitdigital.com/apiman-gateway/ASX/asx-research/1.0/file/{doc_key}"
                else:
                    pdf_url = ""
                
                results.append({
                    "title": ann.get("header", ann.get("headline", "Unknown")),
                    "url": pdf_url,
                    "date": ann.get("documentDate", ann.get("releaseDate", "")),
                    "is_price_sensitive": ann.get("priceSensitive", ann.get("marketSensitive", False)),
                })
            return results
        else:
            print(f"      MarkitDigital returned {response.status_code}")
    except Exception as e:
        print(f"      MarkitDigital error: {e}")
    return []


def try_asx_v2_api(asx_code: str, limit: int = 10) -> list:
    """
    Try the ASX v2 statistics API.
    This is an older endpoint that sometimes works.
    """
    try:
        url = f"https://www.asx.com.au/asx/1/company/{asx_code}/announcements?count={limit}"
        response = requests.get(url, headers=BROWSER_HEADERS, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            results = []
            for ann in data.get("data", [])[:limit]:
                pdf_url = ann.get("url", "")
                # Convert old URL format to new announcements.asx.com.au format
                if pdf_url and "www.asx.com.au/asxpdf" in pdf_url:
                    pdf_url = pdf_url.replace("www.asx.com.au/asxpdf", "announcements.asx.com.au/asxpdf")
                
                results.append({
                    "title": ann.get("header", "Unknown"),
                    "url": pdf_url,
                    "date": ann.get("document_date", ""),
                    "is_price_sensitive": ann.get("price_sensitive", False),
                })
            return results
        else:
            print(f"      ASX v2 API returned {response.status_code}")
    except Exception as e:
        print(f"      ASX v2 API error: {e}")
    return []


def get_asx_announcements(asx_code: str, limit: int = 10) -> list:
    """
    Get ASX announcements by trying multiple endpoints in sequence.
    Returns list of announcements with working PDF links.
    """
    print(f"      Trying MarkitDigital API...", end=" ")
    results = try_markitdigital_api(asx_code, limit)
    if results:
        print(f"✓ Got {len(results)}")
        return results
    
    print(f"\n      Trying ASX v2 API...", end=" ")
    results = try_asx_v2_api(asx_code, limit)
    if results:
        print(f"✓ Got {len(results)}")
        return results
    
    print("✗ All APIs failed")
    return []


def find_latest_earnings(announcements: list) -> dict:
    """Find the most recent earnings/results announcement."""
    earnings_keywords = [
        "results", "half year", "full year", "annual report",
        "quarterly", "profit", "earnings", "financial report", "4e", "4d"
    ]
    
    for ann in announcements:
        title_lower = ann.get("title", "").lower()
        if any(keyword in title_lower for keyword in earnings_keywords):
            return ann
    return None


def find_latest_price_sensitive(announcements: list) -> dict:
    """Find the most recent price-sensitive announcement."""
    # First try explicitly price-sensitive
    for ann in announcements:
        if ann.get("is_price_sensitive"):
            return ann
    
    # Fall back to keyword matching
    sensitive_keywords = [
        "trading update", "guidance", "profit warning", "acquisition",
        "merger", "takeover", "dividend", "capital raising", "placement",
        "results", "quarterly", "material", "scheme"
    ]
    
    for ann in announcements:
        title_lower = ann.get("title", "").lower()
        if any(keyword in title_lower for keyword in sensitive_keywords):
            return ann
    
    # Return most recent if nothing else
    return announcements[0] if announcements else None


# ============================================================================
# CLAUDE API - For news analysis, industry dynamics, competitor analysis
# ============================================================================

def get_full_analysis(client: anthropic.Anthropic, stock: dict, has_announcements: bool) -> dict:
    """
    Get comprehensive analysis from Claude including:
    - Reason for recent price move
    - Industry dynamics (3 points)
    - Competitive dynamics (2 points)
    - Recent announcements (if API failed to get them)
    """
    
    announcement_section = ""
    if not has_announcements:
        announcement_section = """
5. RECENT ASX ANNOUNCEMENTS (API couldn't fetch them, please find via web search)
   - Find the 3 most recent announcements from the ASX for this company
   - For each: provide title, date, and if possible the direct PDF link
   - Look on asx.com.au or announcements.asx.com.au
"""
    
    prompt = f"""Analyze {stock['name']} (ASX: {stock['asx_code']}, Yahoo: {stock['ticker']}).

Provide EXACTLY these sections with SPECIFIC DATA (not vague summaries):

1. REASON FOR MOVE (Last 7 days)
   - What news/events explain recent share price movement?
   - Include specific dates and numbers if available
   - If no material news, say "No material announcements in the past week"

2. INDUSTRY DYNAMICS ({stock['industry']} industry)
   Provide exactly 3 bullet points about recent industry trends:
   - Include specific data points, percentages, or figures where possible
   - Focus on Australian market conditions
   - Include dates for any news/data

3. COMPETITIVE DYNAMICS
   Provide exactly 2 bullet points about these specific competitors: {', '.join(stock['competitors'])}
   - Recent news about these named companies only
   - Include specific dates and details
{announcement_section}
IMPORTANT RULES:
- Use web search to find current information
- Include source names (e.g., "per AFR", "per company announcement")
- Say "Not found" if you cannot verify something - do NOT make up data
- Keep each section concise but specific
"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=3000,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Extract text from response
        full_text = ""
        for block in response.content:
            if hasattr(block, 'text'):
                full_text += block.text
        
        # Parse into sections
        return parse_analysis(full_text)
        
    except Exception as e:
        print(f"      Claude API error: {e}")
        return {
            "reason_for_move": "Analysis unavailable",
            "industry_dynamics": ["Data unavailable"],
            "competitive_dynamics": ["Data unavailable"],
            "announcements_from_search": []
        }


def parse_analysis(text: str) -> dict:
    """Parse Claude's analysis into structured sections."""
    result = {
        "reason_for_move": "No material announcements in the past week",
        "industry_dynamics": [],
        "competitive_dynamics": [],
        "announcements_from_search": []
    }
    
    if not text:
        return result
    
    text_lower = text.lower()
    
    # Extract Reason for Move
    try:
        if "reason for move" in text_lower:
            start = text_lower.find("reason for move")
            # Find end - next section header
            end = len(text)
            for marker in ["industry dynamics", "2.", "competitive"]:
                pos = text_lower.find(marker, start + 20)
                if pos != -1 and pos < end:
                    end = pos
            
            section = text[start:end].strip()
            # Remove the header
            lines = section.split('\n')
            content_lines = [l.strip() for l in lines[1:] if l.strip() and len(l.strip()) > 5]
            if content_lines:
                result["reason_for_move"] = ' '.join(content_lines[:3])[:500]
    except:
        pass
    
    # Extract Industry Dynamics
    try:
        if "industry dynamics" in text_lower:
            start = text_lower.find("industry dynamics")
            end = len(text)
            for marker in ["competitive dynamics", "3.", "recent asx"]:
                pos = text_lower.find(marker, start + 20)
                if pos != -1 and pos < end:
                    end = pos
            
            section = text[start:end]
            # Find bullet points or numbered items
            lines = section.split('\n')
            bullets = []
            for line in lines:
                line = line.strip()
                if line and (line.startswith('-') or line.startswith('•') or line.startswith('*') or (len(line) > 2 and line[0].isdigit() and line[1] in '.)')):
                    # Clean the line
                    clean = re.sub(r'^[-•*\d.)\s]+', '', line).strip()
                    if len(clean) > 10:
                        bullets.append(clean)
            
            result["industry_dynamics"] = bullets[:3] if bullets else ["Data not available"]
    except:
        pass
    
    # Extract Competitive Dynamics  
    try:
        if "competitive dynamics" in text_lower:
            start = text_lower.find("competitive dynamics")
            end = len(text)
            for marker in ["recent asx", "5.", "important"]:
                pos = text_lower.find(marker, start + 20)
                if pos != -1 and pos < end:
                    end = pos
            
            section = text[start:end]
            lines = section.split('\n')
            bullets = []
            for line in lines:
                line = line.strip()
                if line and (line.startswith('-') or line.startswith('•') or line.startswith('*') or (len(line) > 2 and line[0].isdigit() and line[1] in '.)')):
                    clean = re.sub(r'^[-•*\d.)\s]+', '', line).strip()
                    if len(clean) > 10:
                        bullets.append(clean)
            
            result["competitive_dynamics"] = bullets[:2] if bullets else ["Data not available"]
    except:
        pass
    
    return result


# ============================================================================
# HTML GENERATION
# ============================================================================

def format_date(date_str) -> str:
    """Format date string to readable format."""
    if not date_str:
        return "Unknown"
    
    try:
        if "T" in str(date_str):
            dt = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
            return dt.strftime("%B %d, %Y")
        dt = datetime.strptime(str(date_str)[:10], "%Y-%m-%d")
        return dt.strftime("%B %d, %Y")
    except:
        return str(date_str)


def generate_stock_html(stock: dict, price_data: dict, announcements: list, analysis: dict, stock_num: int) -> str:
    """Generate HTML for a single stock."""
    
    # Price section (from yfinance - ACCURATE)
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
    
    # Reason for Move
    reason_html = f'''<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">REASON FOR MOVE:</strong><br>
{analysis.get('reason_for_move', 'No material announcements in the past week')}
</p>'''
    
    # Last Price-Sensitive Announcement
    latest_ann = find_latest_price_sensitive(announcements)
    if latest_ann and latest_ann.get('url'):
        ann_html = f'''<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">LAST PRICE-SENSITIVE ANNOUNCEMENT:</strong><br>
<strong>Date:</strong> {format_date(latest_ann.get('date'))}<br>
<strong>Title:</strong> {latest_ann.get('title', 'Unknown')}<br>
<strong>Link:</strong> <a href="{latest_ann.get('url')}" style="color:#3498db;">View PDF on ASX</a>
</p>'''
    else:
        ann_html = '<p style="margin:15px 0;"><strong style="color:#2980b9;">LAST PRICE-SENSITIVE ANNOUNCEMENT:</strong> Not available via API</p>'
    
    # Last Earnings Report
    latest_earnings = find_latest_earnings(announcements)
    if latest_earnings and latest_earnings.get('url'):
        earnings_html = f'''<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">LAST EARNINGS REPORT:</strong><br>
<strong>Date:</strong> {format_date(latest_earnings.get('date'))}<br>
<strong>Title:</strong> {latest_earnings.get('title', 'Unknown')}<br>
<strong>Link:</strong> <a href="{latest_earnings.get('url')}" style="color:#3498db;">View PDF on ASX</a>
</p>'''
    else:
        earnings_html = '<p style="margin:15px 0;"><strong style="color:#2980b9;">LAST EARNINGS REPORT:</strong> Not available via API</p>'
    
    # Recent Announcements List
    if announcements:
        ann_list = '<p style="margin:15px 0;"><strong style="color:#2980b9;">RECENT ASX ANNOUNCEMENTS:</strong></p><ul style="margin:5px 0 15px 20px;line-height:1.8;">'
        for ann in announcements[:5]:
            title = ann.get('title', 'Unknown')
            url = ann.get('url', '')
            date = format_date(ann.get('date', ''))
            if url:
                ann_list += f'<li>{date}: <a href="{url}" style="color:#3498db;">{title}</a></li>'
            else:
                ann_list += f'<li>{date}: {title}</li>'
        ann_list += '</ul>'
    else:
        ann_list = '<p style="margin:15px 0;"><strong style="color:#2980b9;">RECENT ASX ANNOUNCEMENTS:</strong> Unable to fetch from API</p>'
    
    # Industry Dynamics
    industry_items = analysis.get('industry_dynamics', ['Data not available'])
    industry_bullets = ''.join([f'<li>{item}</li>' for item in industry_items])
    industry_html = f'''<p style="margin:15px 0;"><strong style="color:#2980b9;">INDUSTRY DYNAMICS ({stock['industry'].upper()}):</strong></p>
<ul style="margin:5px 0 15px 20px;line-height:1.8;">{industry_bullets}</ul>'''
    
    # Competitive Dynamics
    comp_items = analysis.get('competitive_dynamics', ['Data not available'])
    comp_bullets = ''.join([f'<li>{item}</li>' for item in comp_items])
    comp_html = f'''<p style="margin:15px 0;"><strong style="color:#2980b9;">COMPETITIVE DYNAMICS:</strong></p>
<ul style="margin:5px 0 15px 20px;line-height:1.8;">{comp_bullets}</ul>'''
    
    # Combine all sections
    return f'''
<h2 style="color:#34495e;margin-top:30px;border-bottom:2px solid #ecf0f1;padding-bottom:8px;">
{stock_num}. {stock['name']} ({stock['ticker']})
</h2>

{price_html}
{reason_html}
{ann_html}
{earnings_html}
{ann_list}
{industry_html}
{comp_html}

<hr style="border:none;border-top:1px solid #ecf0f1;margin:30px 0;">
'''


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
<strong>Prices:</strong> Yahoo Finance (accurate) | <strong>Announcements:</strong> ASX APIs | <strong>Analysis:</strong> Claude AI
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
    """Main function."""
    
    print("=" * 70)
    print("🚀 Berkholts Daily Stock Summary Emailer")
    print("📊 ROBUST VERSION - Multiple ASX endpoints + Full Analysis")
    print("   • Prices: yfinance (FREE, 100% accurate)")
    print("   • Announcements: Multiple ASX APIs with fallback")
    print("   • Analysis: Claude API (news, industry, competitors)")
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
        
        # 2. Get ASX announcements (try multiple endpoints)
        print(f"   📢 Fetching ASX announcements...")
        announcements = get_asx_announcements(stock['asx_code'])
        
        # 3. Get full analysis from Claude
        print(f"   🔍 Getting analysis from Claude...")
        analysis = get_full_analysis(client, stock, has_announcements=len(announcements) > 0)
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
