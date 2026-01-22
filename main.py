#!/usr/bin/env python3
import os
import sys
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import anthropic

def main():
    """Generate and send daily stock summary - HTML ONLY"""
    
    print("=" * 60)
    print(f"🚀 Berkholts Daily Stock Summary (HTML ONLY)")
    print(f"📊 2 Companies")
    print(f"⏰ {datetime.now()}")
    print("=" * 60)
    
    # Get environment variables
    anthropic_key = os.getenv('ANTHROPIC_API_KEY')
    smtp_email = os.getenv('SMTP_EMAIL')
    smtp_password = os.getenv('SMTP_PASSWORD')
    recipient_emails_str = os.getenv('RECIPIENT_EMAILS')
    
    if not all([anthropic_key, smtp_email, smtp_password, recipient_emails_str]):
        print("❌ Missing environment variables!")
        sys.exit(1)
    
    recipient_emails = [e.strip() for e in recipient_emails_str.split(',') if e.strip()]
    print(f"✅ Recipients: {recipient_emails}")
    
    client = anthropic.Anthropic(api_key=anthropic_key)
    today = datetime.now().strftime("%B %d, %Y")
    
    # STEP 1: Gather data
    try:
        print("\n" + "=" * 60)
        print("STEP 1: Gathering data (2-3 minutes)...")
        print("=" * 60)
        
        step1_prompt = f"""Research and gather information for a stock summary report covering these 2 Australian companies for {today}:

1. AUB Group Limited (AUB.AX) - Insurance broker
2. Mineral Resources Limited (MIN.AX) - Mining and resources

For each company, YOU MUST find and provide ALL of the following:

**CURRENT PRICE & YESTERDAY'S CHANGE**
Search for: "AUB.AX stock price" or "MIN.AX stock price" to find TODAY'S actual current price
Be VERY careful to get the correct, current price for {today}

**REASON FOR MOVE (Last 7 days only)**
Material news from last 7 days with specific dates and sources

**COMPANY DEVELOPMENTS (Last 7 days only)**
New developments from past week with dates and sources

**LAST COMPANY ANNOUNCEMENT**
Search: site:asx.com.au [ticker] announcement
Find most recent price-sensitive announcement with date, summary, and DIRECT ASX.com.au URL

**LAST EARNINGS REPORT** ⚠️ MANDATORY
Search: site:asx.com.au [ticker] "results" OR "trading update"
Find the last financial report with date, type, metrics, and DIRECT ASX.com.au URL

**INDUSTRY/COMPETITIVE DYNAMICS (Last month)**
Find EXACTLY 4 data points with dates, hard data, and DIRECT URLs from: WSJ, FT, AFR, Bloomberg, Reuters, trade magazines

CRITICAL: Provide DIRECT URLs to original sources (not search result URLs)."""

        message1 = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=16000,
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
    
    # STEP 2: Convert to HTML
    try:
        print("\n" + "=" * 60)
        print("STEP 2: Converting to HTML...")
        print("=" * 60)
        
        step2_prompt = f"""Convert the research below into clean HTML.

RESEARCH DATA:
{research_content}

Create HTML with this structure:

<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Berkholts Stock Summaries</title>
</head>
<body style="margin:0;padding:0;font-family:Arial,Helvetica,sans-serif;background-color:#f4f4f4;">
<table width="100%" cellpadding="0" cellspacing="0" border="0">
<tr>
<td align="center" style="padding:20px;">
<table width="600" cellpadding="0" cellspacing="0" border="0" style="background-color:#ffffff;border:1px solid #ddd;">
<tr>
<td style="padding:30px;">

<h1 style="color:#2c3e50;font-size:24px;margin:0 0 20px 0;padding:0 0 10px 0;border-bottom:3px solid #3498db;font-family:Arial,Helvetica,sans-serif;">Berkholts Stock Summaries - {today}</h1>

<h2 style="color:#34495e;font-size:20px;margin:30px 0 15px 0;padding:0 0 8px 0;border-bottom:2px solid #95a5a6;font-family:Arial,Helvetica,sans-serif;">1. AUB Group Limited (AUB.AX)</h2>

<p style="margin:10px 0;line-height:1.6;font-family:Arial,Helvetica,sans-serif;font-size:14px;">
<strong style="color:#2980b9;">PRICE:</strong> A$XX.XX | 
<strong style="color:#2980b9;">YESTERDAY:</strong> <span style="color:#00AA00;font-weight:bold;">+A$X.XX (+X.XX%)</span>
</p>

<p style="margin:10px 0;line-height:1.6;font-family:Arial,Helvetica,sans-serif;font-size:14px;">
<strong style="color:#2980b9;">REASON FOR MOVE:</strong> Text with <a href="DIRECT_URL" style="color:#3498db;text-decoration:underline;">source</a>
</p>

<p style="margin:15px 0 5px 0;font-family:Arial,Helvetica,sans-serif;font-size:14px;">
<strong style="color:#2980b9;">COMPANY DEVELOPMENTS (Past Week):</strong>
</p>
<ul style="margin:5px 0 10px 20px;padding:0;line-height:1.8;font-family:Arial,Helvetica,sans-serif;font-size:14px;">
<li><span style="color:#FF8800;font-weight:bold;">[NEW]</span> Date: Info - <a href="URL" style="color:#3498db;text-decoration:underline;">Source</a></li>
</ul>

<p style="margin:15px 0 5px 0;font-family:Arial,Helvetica,sans-serif;font-size:14px;">
<strong style="color:#2980b9;">LAST COMPANY ANNOUNCEMENT:</strong>
</p>
<ul style="margin:5px 0 10px 20px;padding:0;line-height:1.8;font-family:Arial,Helvetica,sans-serif;font-size:14px;">
<li><strong>Date:</strong> Date</li>
<li><strong>Summary:</strong> Summary</li>
<li><strong>Source:</strong> <a href="https://announcements.asx.com.au/..." style="color:#3498db;text-decoration:underline;">ASX Announcement</a></li>
</ul>

<p style="margin:15px 0 5px 0;font-family:Arial,Helvetica,sans-serif;font-size:14px;">
<strong style="color:#2980b9;">LAST EARNINGS REPORT:</strong>
</p>
<ul style="margin:5px 0 10px 20px;padding:0;line-height:1.8;font-family:Arial,Helvetica,sans-serif;font-size:14px;">
<li><strong>Date:</strong> Date</li>
<li><strong>Type:</strong> Type</li>
<li><strong>Summary:</strong> Summary</li>
<li><strong>Source:</strong> <a href="https://announcements.asx.com.au/..." style="color:#3498db;text-decoration:underline;">ASX Announcement</a></li>
</ul>

<p style="margin:15px 0 5px 0;font-family:Arial,Helvetica,sans-serif;font-size:14px;">
<strong style="color:#2980b9;">INDUSTRY/COMPETITIVE DYNAMICS:</strong>
</p>
<ul style="margin:5px 0 10px 20px;padding:0;line-height:1.8;font-family:Arial,Helvetica,sans-serif;font-size:14px;">
<li><strong>Date:</strong> Data - <a href="URL" style="color:#3498db;text-decoration:underline;">Source</a></li>
<li><strong>Date:</strong> Data - <a href="URL" style="color:#3498db;text-decoration:underline;">Source</a></li>
<li><strong>Date:</strong> Data - <a href="URL" style="color:#3498db;text-decoration:underline;">Source</a></li>
<li><strong>Date:</strong> Data - <a href="URL" style="color:#3498db;text-decoration:underline;">Source</a></li>
</ul>

<hr style="border:0;border-top:2px solid #ddd;margin:30px 0;">

[Repeat for company 2]

</td>
</tr>
</table>
</td>
</tr>
</table>
</body>
</html>

CRITICAL:
- Use DIRECT URLs from research (no tracking, no redirects)
- Green for positive: style="color:#00AA00;font-weight:bold;"
- Red for negative: style="color:#DD0000;font-weight:bold;"
- All links must have text-decoration:underline
- Start with <!DOCTYPE html>, end with </html>
- No text before or after HTML"""

        message2 = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
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
    
    # STEP 3: Send - HTML ONLY (no multipart, no plain text)
    try:
        print("\n" + "=" * 60)
        print("STEP 3: Sending HTML-only email...")
        print("=" * 60)
        
        for recipient in recipient_emails:
            print(f"📤 Sending to {recipient}...")
            
            # Create HTML-only message (NOT multipart)
            msg = MIMEText(html_content, 'html', 'utf-8')
            msg['Subject'] = f"Berkholts Stock Summaries - {today}"
            msg['From'] = smtp_email
            msg['To'] = recipient
            msg['Content-Type'] = 'text/html; charset=utf-8'
            
            # Send via Gmail SMTP
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(smtp_email, smtp_password)
                server.send_message(msg)
            
            print(f"   ✅ Sent!")
        
        print("\n✅ COMPLETE!")
        print(f"⏰ {datetime.now()}")
        
    except Exception as e:
        print(f"❌ Send error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
