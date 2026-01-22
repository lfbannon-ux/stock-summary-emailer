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
SECTION 1: PRICE DATA (MANDATORY - SEARCH YAHOO FINANCE)
═══════════════════════════════════════════════════════════

For EACH stock:
1. Search: "AUB.AX Yahoo Finance historical prices" (or MIN.AX)
2. Look for Yahoo Finance results showing historical data table
3. Find the most recent 2 trading days' CLOSE prices
4. Report the EXACT numbers you find

The Yahoo Finance historical data shows a table like:
Date          | Close*
Jan 21, 2026  | 31.10
Jan 20, 2026  | 37.25

You MUST report:
- Source: Yahoo Finance Historical Data
- Yesterday ({yesterday}) Close: A$XX.XX
- Previous Day ({day_before}) Close: A$YY.YY  
- Change: Calculate ((Yesterday - Previous) / Previous) × 100 = X.XX%

⚠️ CRITICAL: Search for Yahoo Finance and use the ACTUAL close prices shown
⚠️ If you cannot find Yahoo Finance data, search "site:au.finance.yahoo.com AUB.AX"

═══════════════════════════════════════════════════════════
SECTION 2: REASON FOR MOVE (Last 7 days: {week_ago} to {today})
═══════════════════════════════════════════════════════════

Search for news from last 7 days ONLY.
If NO news from last 7 days: "No material company announcements in the past week"
Include hyperlinked source if news found

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
- Summary with SPECIFIC FINANCIAL GUIDANCE NUMBERS if provided
  Example: "FY26 NPAT guidance of A$215-227M representing 7.4-13.4% growth"
- Full ASX PDF URL from search results

⚠️ Be PRESCRIPTIVE - include actual dollar amounts and percentages from the announcement

═══════════════════════════════════════════════════════════
SECTION 5: LAST EARNINGS REPORT
═══════════════════════════════════════════════════════════

Search: "site:asx.com.au [ticker] annual results" OR "half year results"
Find last financial results announcement

MUST include SPECIFIC KEY NUMBERS:
- Revenue: A$XXM (up/down X%)
- NPAT/Profit: A$XXM (up/down X%)
- EBITDA margin: X.X%
- EPS: A$X.XX (up/down X%)
- Dividend: X.X cents per share

Full ASX PDF URL from search results

⚠️ Include the ACTUAL numbers from the announcement, not generic descriptions

═══════════════════════════════════════════════════════════
SECTION 6: INDUSTRY DYNAMICS (3 points - INDUSTRY ONLY)
═══════════════════════════════════════════════════════════

Find 3 points about THE INDUSTRY/MARKET (NOT individual competitors):
- Market-wide trends, regulatory changes, industry statistics
- Each with: Date, hard numbers, real URL

Examples of INDUSTRY topics:
- "Australian insurance premiums rose 8.5% to $47B" 
- "Mining sector iron ore production up 2.3%"
- "New regulations affecting insurance brokers"

⚠️ This is about the INDUSTRY, not specific competitor companies

═══════════════════════════════════════════════════════════
SECTION 7: COMPETITIVE DYNAMICS (2 points - COMPETITORS ONLY)
═══════════════════════════════════════════════════════════

Find 2 points about SPECIFIC COMPETITOR COMPANIES:
- Name the competitor company
- Their announcements, results, strategic moves
- Each with: Date, company name, specific info, real URL

Examples of COMPETITOR topics:
- "Steadfast Group reported 11% profit growth to $89M"
- "Pilbara Minerals increased production 15% to 195kt"

⚠️ This is about NAMED COMPETITORS, not general industry trends
⚠️ If no competitor news found: "No material competitor developments to report"

═══════════════════════════════════════════════════════════
🚨 CRITICAL RULES 🚨
═══════════════════════════════════════════════════════════

1. PRICE DATA: Must come from Yahoo Finance search results
2. GUIDANCE: Must include specific dollar amounts and percentages  
3. EARNINGS: Must include specific numbers (revenue, profit, margins, etc.)
4. URLS: Every URL must be from your actual search results - NO FAKE URLS
5. SECTIONS 6 & 7: Completely separate - INDUSTRY vs COMPETITORS

Research thoroughly using web_search."""

        message1 = client.messages.create(
            model="claude-opus-4-20250514",
            max_tokens=25000,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
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
