#!/usr/bin/env python3
import os
import sys
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import anthropic

def main():
    """Generate and send daily stock summary"""
    
    print("=" * 60)
    print(f"🚀 Berkholts Daily Stock Summary")
    print(f"📊 2 Companies - STRICT DATA VERIFICATION")
    print(f"⏰ {datetime.now()}")
    print("=" * 60)
    
    # Environment variables
    anthropic_key = os.getenv('ANTHROPIC_API_KEY')
    smtp_email = os.getenv('SMTP_EMAIL')
    smtp_password = os.getenv('SMTP_PASSWORD')
    recipient_emails_str = os.getenv('RECIPIENT_EMAILS')
    
    if not all([anthropic_key, smtp_email, smtp_password, recipient_emails_str]):
        print("❌ Missing environment variables!")
        sys.exit(1)
    
    recipient_emails = [e.strip() for e in recipient_emails_str.split(',') if e.strip()]
    
    client = anthropic.Anthropic(api_key=anthropic_key)
    today = datetime.now().strftime("%B %d, %Y")
    today_date = datetime.now()
    yesterday = (today_date - timedelta(days=1)).strftime("%B %d, %Y")
    day_before = (today_date - timedelta(days=2)).strftime("%B %d, %Y")
    week_ago = (today_date - timedelta(days=7)).strftime("%B %d, %Y")
    
    # STEP 1: Data Gathering with STRICT verification
    try:
        print("\n" + "=" * 60)
        print("STEP 1: Gathering verified data (5-7 minutes)...")
        print("=" * 60)
        
        step1_prompt = f"""Today is {today}. Research these 2 Australian stocks:

1. AUB Group Limited (AUB.AX)
2. Mineral Resources Limited (MIN.AX)

═══════════════════════════════════════════════════════════
SECTION 1: PRICE DATA (MANDATORY - FETCH YAHOO FINANCE PAGE)
═══════════════════════════════════════════════════════════

You MUST use web_fetch tool to retrieve the Yahoo Finance historical data page:

For AUB.AX: Use web_fetch on https://au.finance.yahoo.com/quote/AUB.AX/history/
For MIN.AX: Use web_fetch on https://au.finance.yahoo.com/quote/MIN.AX/history/

Look at the historical prices table in the fetched page.
Find the most recent 2 complete trading days.
Report the CLOSE prices from the table.

Example from the table:
Date          Open    High    Low     Close*   Adj Close**  Volume
Jan 21, 2026  31.50   31.80   31.00   31.10    31.10       X
Jan 20, 2026  37.00   37.50   36.80   37.25    37.25       X

Report:
- Yesterday Close (Jan 21): A$31.10
- Previous Day Close (Jan 20): A$37.25
- Change: ((31.10 - 37.25) / 37.25) × 100 = -16.51%

⚠️ YOU MUST USE WEB_FETCH TO GET THE ACTUAL PAGE
⚠️ DO NOT GUESS - Only use data from the fetched page

═══════════════════════════════════════════════════════════
SECTION 2: REASON FOR MOVE (Last 7 days: {week_ago} to {today})
═══════════════════════════════════════════════════════════

Search for news from last 7 days ONLY.
If NO news from last 7 days: "No material company announcements in the past week"
Include hyperlinked source

═══════════════════════════════════════════════════════════
SECTION 3: COMPANY DEVELOPMENTS (Last 7 days only)
═══════════════════════════════════════════════════════════

Last 7 days only or "No new developments reported this week"

═══════════════════════════════════════════════════════════
SECTION 4: LAST PRICE-SENSITIVE ANNOUNCEMENT
═══════════════════════════════════════════════════════════

Search: "site:asx.com.au [ticker] guidance" OR "trading update" OR "profit"
Find most recent PRICE-SENSITIVE announcement
MUST include:
- Date
- Summary with SPECIFIC FINANCIAL GUIDANCE NUMBERS if given (e.g., "FY26 NPAT guidance of $215-227M")
- Full ASX PDF URL

⚠️ Be PRESCRIPTIVE about financial guidance - include the actual numbers

═══════════════════════════════════════════════════════════
SECTION 5: LAST EARNINGS REPORT
═══════════════════════════════════════════════════════════

Search: "site:asx.com.au [ticker] results"
Find last financial results
MUST include KEY NUMBERS:
- Revenue growth: X% to $XXM
- NPAT/Profit growth: X% to $XXM  
- EBITDA margin: X%
- EPS growth: X% to $X.XX
- Dividend: X cents per share

Full ASX PDF URL

═══════════════════════════════════════════════════════════
SECTION 6: INDUSTRY DYNAMICS (3 points - SEPARATE FROM COMPETITORS)
═══════════════════════════════════════════════════════════

Find 3 points about THE INDUSTRY (not competitors):
- Market trends, regulatory changes, industry-wide data
- Each with date, numbers, real URL

⚠️ This section is about INDUSTRY, not individual competitors

═══════════════════════════════════════════════════════════
SECTION 7: COMPETITIVE DYNAMICS (2 points - COMPETITOR NEWS ONLY)
═══════════════════════════════════════════════════════════

Find 2 points about COMPETITOR companies:
- Specific competitor announcements, results
- Each with date and real URL

⚠️ This section is about COMPETITORS, not general industry
⚠️ If no competitor news: "No material competitor developments to report"

Research thoroughly using web_search and web_fetch."""

        message1 = client.messages.create(
            model="claude-opus-4-20250514",  # Changed to Opus 4.5
            max_tokens=25000,
            tools=[
                {"type": "web_search_20250305", "name": "web_search"},
                {"type": "web_fetch_20250305", "name": "web_fetch"}
            ],
            messages=[{"role": "user", "content": step1_prompt}]
        )
        
        research_content = ""
        for block in message1.content:
            if block.type == "text":
                research_content += block.text
        
        print(f"✅ Research: {len(research_content)} characters")
        
    except Exception as e:
        print(f"❌ Step 1 error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # STEP 2: Convert to HTML with STRICT format
    try:
        print("\n" + "=" * 60)
        print("STEP 2: Converting to HTML...")
        print("=" * 60)
        
        step2_prompt = f"""Convert the research to HTML email format for {today}.

RESEARCH DATA:
{research_content}

Create clean HTML:

<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;font-family:Arial,sans-serif;background-color:#f4f4f4;">
<table width="100%" cellpadding="0" cellspacing="0" border="0">
<tr>
<td align="center" style="padding:20px;">
<table width="1000" cellpadding="0" cellspacing="0" border="0" style="background-color:#ffffff;border:1px solid #ddd;">
<tr>
<td style="padding:30px;">

<h1 style="color:#2c3e50;font-size:24px;margin:0 0 20px 0;padding:0 0 10px 0;border-bottom:3px solid #3498db;">Berkholts Stock Summaries - {today}</h1>

<h2 style="color:#34495e;font-size:20px;margin:30px 0 15px 0;padding:0 0 8px 0;border-bottom:2px solid #95a5a6;">1. AUB Group Limited (AUB.AX)</h2>

<p style="margin:10px 0;line-height:1.6;font-size:14px;">
<strong style="color:#2980b9;">YESTERDAY:</strong> A$XX.XX | 
<strong style="color:#2980b9;">PREVIOUS DAY:</strong> A$YY.YY | 
<strong style="color:#2980b9;">CHANGE:</strong> <span style="color:#00AA00;font-weight:bold;">+X.XX%</span>
</p>

<p style="margin:10px 0;line-height:1.6;font-size:14px;">
<strong style="color:#2980b9;">REASON FOR MOVE:</strong> [Info or "No material announcements"]
</p>

<p style="margin:15px 0 5px 0;font-size:14px;"><strong style="color:#2980b9;">COMPANY DEVELOPMENTS (Past Week):</strong></p>
<ul style="margin:5px 0 10px 20px;padding:0;line-height:1.8;font-size:14px;">
<li>Items or "No new developments reported this week"</li>
</ul>

<p style="margin:15px 0 5px 0;font-size:14px;"><strong style="color:#2980b9;">LAST COMPANY ANNOUNCEMENT:</strong></p>
<ul style="margin:5px 0 10px 20px;padding:0;line-height:1.8;font-size:14px;">
<li><strong>Date:</strong> Date</li>
<li><strong>Summary:</strong> Summary</li>
<li><strong>Source:</strong> <a href="REAL_URL" style="color:#3498db;text-decoration:underline;">ASX Announcement</a></li>
</ul>

<p style="margin:15px 0 5px 0;font-size:14px;"><strong style="color:#2980b9;">LAST EARNINGS REPORT:</strong></p>
<ul style="margin:5px 0 10px 20px;padding:0;line-height:1.8;font-size:14px;">
<li><strong>Date:</strong> Date</li>
<li><strong>Type:</strong> Type</li>
<li><strong>Summary:</strong> Summary</li>
<li><strong>Source:</strong> <a href="REAL_URL" style="color:#3498db;text-decoration:underline;">ASX Announcement</a></li>
</ul>

<p style="margin:15px 0 5px 0;font-size:14px;"><strong style="color:#2980b9;">INDUSTRY DYNAMICS:</strong></p>
<ul style="margin:5px 0 10px 20px;padding:0;line-height:1.8;font-size:14px;">
<li><strong>Date:</strong> Industry-wide data point - <a href="REAL_URL" style="color:#3498db;text-decoration:underline;">Source</a></li>
<li><strong>Date:</strong> Market trend or regulatory change - <a href="REAL_URL" style="color:#3498db;text-decoration:underline;">Source</a></li>
<li><strong>Date:</strong> Industry statistics - <a href="REAL_URL" style="color:#3498db;text-decoration:underline;">Source</a></li>
</ul>

<p style="margin:15px 0 5px 0;font-size:14px;"><strong style="color:#2980b9;">COMPETITIVE DYNAMICS:</strong></p>
<ul style="margin:5px 0 10px 20px;padding:0;line-height:1.8;font-size:14px;">
<li><strong>Date:</strong> Specific competitor name and news - <a href="REAL_URL" style="color:#3498db;text-decoration:underline;">Source</a></li>
<li><strong>Date:</strong> Another competitor name and news - <a href="REAL_URL" style="color:#3498db;text-decoration:underline;">Source</a></li>
<li>OR if no competitor news: "No material competitor developments to report"</li>
</ul>

<hr style="border:0;border-top:2px solid #ddd;margin:30px 0;">

[Repeat for stock 2]

</td></tr></table></td></tr></table>
</body>
</html>

RULES:
- Use ONLY URLs from the research
- Green: style="color:#00AA00;font-weight:bold;"
- Red: style="color:#DD0000;font-weight:bold;"
- ⚠️ CRITICAL: Create TWO COMPLETELY SEPARATE sections:
  1. INDUSTRY DYNAMICS (about the industry/market, not specific competitors)
  2. COMPETITIVE DYNAMICS (about specific competitor companies)
- For Last Price-Sensitive Announcement: Include specific financial guidance numbers if provided
- For Last Earnings Report: Include key growth numbers (revenue %, profit %, margins, EPS, dividend)
- Start with <!DOCTYPE html>, end with </html>"""

        message2 = client.messages.create(
            model="claude-opus-4-20250514",  # Changed to Opus 4.5
            max_tokens=15000,
            messages=[{"role": "user", "content": step2_prompt}]
        )
        
        html_content = ""
        for block in message2.content:
            if block.type == "text":
                html_content += block.text
        
        # Extract HTML
        import re
        html_match = re.search(r'(<!DOCTYPE[^>]*>)?\s*<html.*?</html>', html_content, re.DOTALL | re.IGNORECASE)
        if html_match:
            html_content = html_match.group(0)
        
        print(f"✅ HTML: {len(html_content)} characters")
        
    except Exception as e:
        print(f"❌ Step 2 error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # STEP 3: Send
    try:
        print("\n📧 Sending emails...")
        
        for recipient in recipient_emails:
            print(f"📤 {recipient}...")
            
            msg = MIMEText(html_content, 'html', 'utf-8')
            msg['Subject'] = f"Berkholts Stock Summaries - {today}"
            msg['From'] = smtp_email
            msg['To'] = recipient
            msg['Content-Type'] = 'text/html; charset=utf-8'
            
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(smtp_email, smtp_password)
                server.send_message(msg)
            
            print(f"   ✅ Sent!")
        
        print("\n✅ COMPLETE!")
        
    except Exception as e:
        print(f"❌ Send error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
