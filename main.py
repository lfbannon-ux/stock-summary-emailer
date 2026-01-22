#!/usr/bin/env python3
"""
Berkholts Daily Stock Summary Emailer
=====================================
Generates and emails daily stock summaries using Claude API and Gmail SMTP.

Key Features:
- Two-step generation (research then format)
- Yahoo Finance for price data
- Separate Industry and Competitive sections
- Working hyperlinks only
- Outlook-compatible HTML
"""

import os
import sys
import smtplib
import re
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import anthropic


# Configuration
STOCKS = [
    ("AUB Group Limited", "AUB.AX", "Australian insurance broker"),
    ("Mineral Resources Limited", "MIN.AX", "Mining services and lithium producer"),
]


def get_research_prompt(stocks: list, today: str, yesterday: str, day_before: str) -> str:
    """Generate the research prompt for Step 1."""
    
    stock_list = "\n".join([f"- {name} ({ticker}) - {desc}" for name, ticker, desc in stocks])
    
    return f"""You are a financial research analyst. Today is {today}.

Research these Australian stocks and provide FACTUAL data only:

{stock_list}

For EACH stock, find and report:

═══════════════════════════════════════════════════════════════════════════════
STOCK: [Company Name] ([Ticker])
═══════════════════════════════════════════════════════════════════════════════

1. PRICE DATA
   Search: "[ticker] stock price Yahoo Finance"
   Report:
   - Yesterday's close ({yesterday}): A$XX.XX
   - Previous day's close ({day_before}): A$XX.XX  
   - Change: X.XX% (calculate: ((yesterday - previous) / previous) * 100)
   
   ⚠️ Use ACTUAL prices from Yahoo Finance. Do not estimate.

2. REASON FOR MOVE (Last 7 days only: {day_before} to {today})
   Search: "[company name] ASX announcement" and "[company name] news"
   - If material news exists: Describe it with date and source URL
   - If no news: Write "No material announcements in the past week"
   
3. COMPANY DEVELOPMENTS (Last 7 days only)
   - List any new developments with dates and source URLs
   - If none: Write "No new developments this week"

4. LAST PRICE-SENSITIVE ANNOUNCEMENT
   Search: "site:asx.com.au [ticker] announcement"
   Report:
   - Date: [exact date]
   - Type: [trading update/guidance/results/etc]
   - Summary: Include SPECIFIC NUMBERS if guidance was given
     (e.g., "FY26 NPAT guidance of $215-227M, revenue growth 8-10%")
   - URL: [direct ASX PDF link]

5. LAST EARNINGS REPORT
   Search: "[company name] annual results" or "[company name] half year results"
   Report:
   - Date: [exact date]
   - Type: [Annual/Half-Year/Quarterly]
   - Key metrics:
     * Revenue: $XXM (X% growth)
     * NPAT/Profit: $XXM (X% growth)
     * EPS: $X.XX (X% growth)
     * Dividend: X cents per share
   - URL: [source link]

6. INDUSTRY DYNAMICS (3 points) - MARKET/SECTOR TRENDS ONLY
   ⚠️ This section is about the INDUSTRY, not specific competitors
   Search: "[industry] market trends Australia 2026"
   Find 3 data points about:
   - Market size, growth rates, pricing trends
   - Regulatory changes affecting the sector
   - Industry-wide statistics
   
   Format each point as:
   - [Date]: [Fact with numbers] - [Source Name](URL)
   
   Examples:
   - "Jan 2026: Australian insurance premiums rose 8.5% to $47B - AFR(url)"
   - "Dec 2025: Mining sector capex increased 12% YoY - Bloomberg(url)"

7. COMPETITIVE DYNAMICS (2 points) - SPECIFIC COMPETITOR NEWS ONLY
   ⚠️ This section is about NAMED COMPETITORS, not general industry
   Search: "[main competitors of company] results announcement 2025 2026"
   Find 2 specific competitor updates:
   - Name the competitor explicitly
   - Include their specific results or news
   
   Format each point as:
   - [Date]: [Competitor Name] - [specific news] - [Source Name](URL)
   
   Examples:
   - "Jan 15, 2026: Steadfast Group reported 11% profit growth to $89M - ASX(url)"
   - "Dec 2025: QBE Insurance expanded into cyber market - Reuters(url)"
   
   If no competitor news: Write "No material competitor developments to report"

═══════════════════════════════════════════════════════════════════════════════

CRITICAL RULES:
1. Every fact MUST have a real, working URL from your search results
2. Do NOT make up URLs - only use URLs you actually found
3. Do NOT estimate prices - use actual Yahoo Finance data
4. Keep Industry (market trends) and Competitive (named competitors) SEPARATE
5. If you cannot verify something, say "Data not verified" rather than guess

Now research both stocks and provide the data."""


def get_html_prompt(research_data: str, today: str) -> str:
    """Generate the HTML formatting prompt for Step 2."""
    
    return f"""Convert this research into a clean HTML email. Output ONLY HTML code.

RESEARCH DATA:
{research_data}

HTML REQUIREMENTS:

1. Start with this exact structure:
<!DOCTYPE html>
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

2. Title:
<h1 style="color:#2c3e50;border-bottom:3px solid #3498db;padding-bottom:10px;margin-top:0;">
Berkholts Stock Summaries - {today}
</h1>

3. For each stock use this structure:

<h2 style="color:#34495e;margin-top:30px;border-bottom:2px solid #ecf0f1;padding-bottom:8px;">
1. Company Name (TICKER)
</h2>

<p style="margin:10px 0;line-height:1.6;">
<strong style="color:#2980b9;">PRICE:</strong> A$XX.XX | 
<strong>YESTERDAY:</strong> A$XX.XX | 
<strong>CHANGE:</strong> <span style="color:green;">+X.XX%</span> or <span style="color:red;">-X.XX%</span>
</p>

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">REASON FOR MOVE:</strong><br>
[Content with <a href="URL" style="color:#3498db;text-decoration:underline;">Source Name</a>]
</p>

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">COMPANY DEVELOPMENTS:</strong><br>
[Content or "No new developments this week"]
</p>

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">LAST PRICE-SENSITIVE ANNOUNCEMENT:</strong><br>
Date: [date]<br>
Type: [type]<br>
Summary: [summary with specific numbers]<br>
Source: <a href="URL" style="color:#3498db;text-decoration:underline;">ASX Announcement</a>
</p>

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">LAST EARNINGS REPORT:</strong><br>
Date: [date] | Type: [type]<br>
Revenue: $XXM (X% growth) | NPAT: $XXM (X% growth) | EPS: $X.XX | Dividend: Xc<br>
Source: <a href="URL" style="color:#3498db;text-decoration:underline;">ASX Announcement</a>
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

4. End with:
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>

CRITICAL:
- INDUSTRY DYNAMICS and COMPETITIVE DYNAMICS must be TWO SEPARATE sections
- Every URL must be in <a href="URL"> format - NO raw URLs
- Use colors: green for positive changes, red for negative
- Output ONLY HTML - no explanations before or after"""


def fix_urls_in_html(html: str) -> str:
    """Post-process HTML to fix any malformed URLs."""
    
    # Fix angle bracket URLs: <https://...> -> proper links
    pattern = r'<(https?://[^>]+)>'
    
    def replace_angle_url(match):
        url = match.group(1)
        # Determine link text based on domain
        if 'asx.com.au' in url:
            text = 'ASX Announcement'
        elif 'afr.com' in url:
            text = 'AFR'
        elif 'bloomberg.com' in url:
            text = 'Bloomberg'
        elif 'reuters.com' in url:
            text = 'Reuters'
        elif 'yahoo.com' in url or 'finance.yahoo' in url:
            text = 'Yahoo Finance'
        elif 'wsj.com' in url:
            text = 'WSJ'
        elif 'ft.com' in url:
            text = 'Financial Times'
        else:
            text = 'Source'
        return f'<a href="{url}" style="color:#3498db;text-decoration:underline;">{text}</a>'
    
    html = re.sub(pattern, replace_angle_url, html)
    
    # Fix bare URLs not in anchor tags
    bare_url_pattern = r'(?<!["\'>])(https?://[^\s<>"\']+)(?![^<]*</a>)'
    
    def replace_bare_url(match):
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
    
    html = re.sub(bare_url_pattern, replace_bare_url, html)
    
    return html


def extract_html(content: str) -> str:
    """Extract HTML from Claude's response, removing any preamble."""
    
    # Try to find HTML starting point
    html_starts = ['<!DOCTYPE html>', '<!doctype html>', '<html>', '<HTML>']
    
    for start in html_starts:
        idx = content.lower().find(start.lower())
        if idx != -1:
            content = content[idx:]
            break
    
    # Try to find HTML ending point
    html_ends = ['</html>', '</HTML>']
    
    for end in html_ends:
        idx = content.lower().rfind(end.lower())
        if idx != -1:
            content = content[:idx + len(end)]
            break
    
    # If no proper HTML structure, wrap content
    if not content.strip().lower().startswith('<!doctype') and not content.strip().lower().startswith('<html'):
        content = f"""<!DOCTYPE html>
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
{content}
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>"""
    
    return content


def send_email(html_content: str, recipient: str, smtp_email: str, smtp_password: str, subject: str):
    """Send HTML email via Gmail SMTP."""
    
    msg = MIMEText(html_content, 'html', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = smtp_email
    msg['To'] = recipient
    msg['Content-Type'] = 'text/html; charset=utf-8'
    
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(smtp_email, smtp_password)
        server.sendmail(smtp_email, recipient, msg.as_string())


def main():
    """Main function to generate and send daily stock summary."""
    
    print("=" * 70)
    print("🚀 Berkholts Daily Stock Summary Emailer")
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
        print(f"\n❌ Missing environment variables: {', '.join(missing)}")
        sys.exit(1)
    
    print("✅ All environment variables found")
    
    recipients = [e.strip() for e in recipient_emails_str.split(',') if e.strip()]
    print(f"📧 Recipients: {', '.join(recipients)}")
    
    # Calculate dates
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    day_before = today - timedelta(days=2)
    
    today_str = today.strftime("%B %d, %Y")
    yesterday_str = yesterday.strftime("%B %d, %Y")
    day_before_str = day_before.strftime("%B %d, %Y")
    
    # Initialize Claude client
    client = anthropic.Anthropic(api_key=anthropic_key)
    
    # STEP 1: Research
    print("\n" + "=" * 70)
    print("📊 STEP 1: Researching stocks with Claude...")
    print("⏱️  This will take 2-3 minutes...")
    print("=" * 70)
    
    try:
        research_prompt = get_research_prompt(STOCKS, today_str, yesterday_str, day_before_str)
        
        research_response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=16000,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": research_prompt}]
        )
        
        # Extract research text
        research_data = ""
        for block in research_response.content:
            if hasattr(block, 'text'):
                research_data += block.text
        
        print("✅ Research complete!")
        print(f"📄 Research length: {len(research_data)} characters")
        
    except Exception as e:
        print(f"\n❌ Research error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # STEP 2: Format as HTML
    print("\n" + "=" * 70)
    print("🎨 STEP 2: Converting to HTML email format...")
    print("=" * 70)
    
    try:
        html_prompt = get_html_prompt(research_data, today_str)
        
        html_response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            system="You are an HTML email generator. Output ONLY valid HTML code. No explanations, no preamble, no text outside HTML tags. Start with <!DOCTYPE html> and end with </html>.",
            messages=[{"role": "user", "content": html_prompt}]
        )
        
        # Extract HTML
        html_content = ""
        for block in html_response.content:
            if hasattr(block, 'text'):
                html_content += block.text
        
        # Clean up the HTML
        html_content = extract_html(html_content)
        html_content = fix_urls_in_html(html_content)
        
        print("✅ HTML generated!")
        print(f"📄 HTML length: {len(html_content)} characters")
        
    except Exception as e:
        print(f"\n❌ HTML generation error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # STEP 3: Send emails
    print("\n" + "=" * 70)
    print("📧 STEP 3: Sending emails...")
    print("=" * 70)
    
    subject = f"Berkholts Stock Summaries - {today_str}"
    
    for recipient in recipients:
        try:
            print(f"📤 Sending to: {recipient}")
            send_email(html_content, recipient, smtp_email, smtp_password, subject)
            print(f"   ✅ Sent successfully!")
        except Exception as e:
            print(f"   ❌ Failed: {str(e)}")
    
    print("\n" + "=" * 70)
    print("✅ ALL DONE!")
    print(f"⏰ Completed at: {datetime.now()}")
    print("=" * 70)


if __name__ == "__main__":
    main()
