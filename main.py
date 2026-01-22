#!/usr/bin/env python3
import os
import sys
import sendgrid
from sendgrid.helpers.mail import Mail, Email, To, Content
from datetime import datetime
import anthropic
import json

def main():
    """Generate and send daily stock summary using two-step approach"""
    
    print("=" * 60)
    print(f"🚀 Berkholts Daily Stock Summary (2-Step Approach)")
    print(f"📊 2 Companies")
    print(f"⏰ {datetime.now()}")
    print("=" * 60)
    
    # Get environment variables
    anthropic_key = os.getenv('ANTHROPIC_API_KEY')
    sendgrid_key = os.getenv('SENDGRID_API_KEY')
    from_email = os.getenv('FROM_EMAIL')
    recipient_emails_str = os.getenv('RECIPIENT_EMAILS')
    
    if not all([anthropic_key, sendgrid_key, from_email, recipient_emails_str]):
        print("❌ Missing environment variables!")
        sys.exit(1)
    
    recipient_emails = [e.strip() for e in recipient_emails_str.split(',') if e.strip()]
    print(f"✅ Recipients: {recipient_emails}")
    
    client = anthropic.Anthropic(api_key=anthropic_key)
    today = datetime.now().strftime("%B %d, %Y")
    
    # STEP 1: Gather data naturally (let Claude explain and search)
    try:
        print("\n" + "=" * 60)
        print("STEP 1: Gathering data (2-3 minutes)...")
        print("=" * 60)
        
        step1_prompt = f"""Research and gather information for a stock summary report covering these 2 Australian companies:

1. AUB Group Limited (AUB.AX) - Insurance broker
2. Mineral Resources Limited (MIN.AX) - Mining and resources

For each company, find and provide:

**CURRENT PRICE & YESTERDAY'S CHANGE**
Search for current stock price and yesterday's movement

**REASON FOR MOVE (Last 7 days only)**
Find any material news or company announcements from the last 7 days
Include specific dates
If nothing material in last 7 days, note that

**COMPANY DEVELOPMENTS (Last 7 days only)**
Any new developments from the past week
Include dates and sources

**LAST COMPANY ANNOUNCEMENT**
Search: site:asx.com.au [ticker] announcement
Find the most recent material ASX announcement
Include: date, summary with specific numbers/guidance, and the ASX announcement URL

**INDUSTRY/COMPETITIVE DYNAMICS (Last month)**
3 data points with:
- Specific dates
- Hard data (percentages, dollar amounts, volumes)
- Sources from: AFR, Bloomberg, Reuters, industry magazines, government data
- Exclude: Motley Fool, Simply Wall St, TradingView

Please research thoroughly and provide all the information you find. You can explain your search process - this is just for data gathering."""

        message1 = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=16000,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": step1_prompt}]
        )
        
        # Extract the research content
        research_content = ""
        for block in message1.content:
            if block.type == "text":
                research_content += block.text
        
        print(f"✅ Research gathered: {len(research_content)} characters")
        print("\nResearch preview (first 500 chars):")
        print(research_content[:500])
        print("...\n")
        
    except Exception as e:
        print(f"❌ Error in Step 1: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # STEP 2: Convert to clean HTML
    try:
        print("=" * 60)
        print("STEP 2: Converting to HTML...")
        print("=" * 60)
        
        step2_prompt = f"""Take the research data below and convert it into a clean HTML email report.

RESEARCH DATA:
{research_content}

OUTPUT REQUIREMENTS:
Create a properly formatted HTML email with this EXACT structure:

<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family:Arial,sans-serif;max-width:900px;margin:0 auto;padding:20px;background-color:#ffffff;">

<h1 style="color:#2c3e50;border-bottom:3px solid #3498db;padding-bottom:10px;margin-bottom:30px;">Berkholts Stock Summaries - {today}</h1>

<h2 style="color:#34495e;margin-top:40px;border-bottom:2px solid #95a5a6;padding-bottom:8px;">1. AUB Group Limited (AUB.AX)</h2>

<p style="line-height:1.6;margin:10px 0;"><strong style="color:#2980b9;">PRICE:</strong> A$XX.XX | <strong style="color:#2980b9;">YESTERDAY:</strong> <span style="color:#00AA00;font-weight:bold;">+A$X.XX (+X.XX%)</span></p>

<p style="line-height:1.6;margin:10px 0;"><strong style="color:#2980b9;">REASON FOR MOVE:</strong> [Info from research]</p>

<p style="line-height:1.6;margin:10px 0;"><strong style="color:#2980b9;">COMPANY DEVELOPMENTS (Past Week):</strong></p>
<ul style="line-height:1.8;margin:10px 0;">
<li><span style="color:#FF8800;font-weight:bold;">[NEW]</span> <strong>Date:</strong> Development - <a href="URL" style="color:#3498db;text-decoration:none;">Source</a></li>
</ul>

<p style="line-height:1.6;margin:10px 0;"><strong style="color:#2980b9;">LAST COMPANY ANNOUNCEMENT:</strong></p>
<ul style="line-height:1.8;margin:10px 0;">
<li><strong>Date:</strong> [Date]</li>
<li><strong>Summary:</strong> [Summary with numbers]</li>
<li><strong>Source:</strong> <a href="[ASX URL]" style="color:#3498db;text-decoration:none;">ASX Announcement</a></li>
</ul>

<p style="line-height:1.6;margin:10px 0;"><strong style="color:#2980b9;">INDUSTRY/COMPETITIVE DYNAMICS:</strong></p>
<ul style="line-height:1.8;margin:10px 0;">
<li><strong>Date:</strong> Data point - <a href="URL" style="color:#3498db;text-decoration:none;">Source Name</a></li>
<li><strong>Date:</strong> Data point - <a href="URL" style="color:#3498db;text-decoration:none;">Source Name</a></li>
<li><strong>Date:</strong> Data point - <a href="URL" style="color:#3498db;text-decoration:none;">Source Name</a></li>
</ul>

<hr style="border:none;border-top:1px solid #ddd;margin:30px 0;">

[Repeat for company 2]

</body>
</html>

CRITICAL RULES:
- Start your response with <!DOCTYPE html> - nothing before it
- End with </html> - nothing after it
- Use <span style="color:#00AA00;font-weight:bold;"> for positive price changes
- Use <span style="color:#DD0000;font-weight:bold;"> for negative price changes
- ALL URLs must be in <a href="URL" style="color:#3498db;text-decoration:none;">Text</a> format
- NEVER show raw URLs like https://... or <https://...>
- Use the data from the research above

Generate the HTML now. Your entire response should be valid HTML from <!DOCTYPE to </html>."""

        message2 = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            messages=[{"role": "user", "content": step2_prompt}]
        )
        
        # Extract HTML
        html_content = ""
        for block in message2.content:
            if block.type == "text":
                html_content += block.text
        
        # Clean up - remove any text before <!DOCTYPE or <html
        import re
        html_match = re.search(r'(<!DOCTYPE[^>]*>)?\s*<html.*?</html>', html_content, re.DOTALL | re.IGNORECASE)
        if html_match:
            html_content = html_match.group(0)
        
        print(f"✅ HTML generated: {len(html_content)} characters")
        
    except Exception as e:
        print(f"❌ Error in Step 2: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Send emails
    try:
        print("\n" + "=" * 60)
        print("STEP 3: Sending emails...")
        print("=" * 60)
        
        sg = sendgrid.SendGridAPIClient(api_key=sendgrid_key)
        subject = f"Berkholts Stock Summaries - {today}"
        
        for recipient in recipient_emails:
            print(f"📤 Sending to {recipient}...")
            
            mail = Mail(
                from_email=Email(from_email),
                to_emails=To(recipient),
                subject=subject,
                html_content=Content("text/html", html_content)
            )
            
            response = sg.client.mail.send.post(request_body=mail.get())
            print(f"   ✅ Sent! Status: {response.status_code}")
        
        print("\n" + "=" * 60)
        print("✅ COMPLETE!")
        print(f"⏰ Finished: {datetime.now()}")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error sending: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
