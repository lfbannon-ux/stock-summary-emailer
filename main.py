#!/usr/bin/env python3
import os
import sys
import sendgrid
from sendgrid.helpers.mail import Mail, Email, To, Content
from datetime import datetime
import anthropic

def main():
    """Generate and send daily stock summary"""
    
    print("=" * 60)
    print(f"🚀 Berkholts Daily Stock Summary (3 Stocks)")
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
    
    # Generate summary with Claude
    try:
        print("\n📊 Generating summaries (2-3 minutes)...")
        
        client = anthropic.Anthropic(api_key=anthropic_key)
        today = datetime.now().strftime("%B %d, %Y")
        
        prompt = f"""Create a professional HTML email report for {today} covering these 3 Australian stocks:

1. AUB Group Limited (AUB.AX) - Insurance broker
2. Mineral Resources Limited (MIN.AX) - Mining and resources
3. Charter Hall Group (CHC.AX) - Commercial property REIT

For each stock, include these sections:

**PRICE:** A$XX.XX | **YESTERDAY:** +/-A$X.XX (+/-X.XX%)

**REASON FOR MOVE:** 
- ONLY include NEW fundamental information from the LAST 7 DAYS with specific date
- Information should be from company announcements or major credible news
- If no material news in last 7 days: "No material company announcements in the past week"

**COMPANY DEVELOPMENTS (Past Week):**
- ONLY developments from the LAST 7 DAYS
- Tag with [NEW] in orange
- If nothing: "No new developments reported this week"

**LAST COMPANY ANNOUNCEMENT:**
- Date: [Date of most recent material ASX announcement]
- Summary: [2-3 sentences describing what was announced, with specific numbers and guidance]
- Source: [Hyperlink to actual ASX announcement URL]
Search: "site:asx.com.au [ticker] announcement" to find this

**INDUSTRY/COMPETITIVE DYNAMICS:**
- 3 key points from the LAST MONTH
- Each point MUST include: specific date, hard data (percentages, dollar values), and credible source
- PRIORITIZE: Industry trade magazines, AFR, Bloomberg, Reuters, Financial Times, government data, industry research firms
- EXCLUDE: Motley Fool, Simply Wall St, TradingView, DailyForex

Format as clean HTML:

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

<p style="line-height:1.6;margin:10px 0;"><strong style="color:#2980b9;">REASON FOR MOVE:</strong> [Recent news from last 7 days with date]</p>

<p style="line-height:1.6;margin:10px 0;"><strong style="color:#2980b9;">COMPANY DEVELOPMENTS (Past Week):</strong></p>
<ul style="line-height:1.8;margin:10px 0;">
<li><span style="color:#FF8800;font-weight:bold;">[NEW]</span> <strong>Date:</strong> Development - <a href="URL" style="color:#3498db;text-decoration:none;">Source Name</a></li>
</ul>

<p style="line-height:1.6;margin:10px 0;"><strong style="color:#2980b9;">LAST COMPANY ANNOUNCEMENT:</strong></p>
<ul style="line-height:1.8;margin:10px 0;">
<li><strong>Date:</strong> Month Day, Year</li>
<li><strong>Summary:</strong> What was announced with specific numbers</li>
<li><strong>Source:</strong> <a href="https://announcements.asx.com.au/..." style="color:#3498db;text-decoration:none;">ASX Announcement</a></li>
</ul>

<p style="line-height:1.6;margin:10px 0;"><strong style="color:#2980b9;">INDUSTRY/COMPETITIVE DYNAMICS:</strong></p>
<ul style="line-height:1.8;margin:10px 0;">
<li><strong>Month Year:</strong> Specific data point with numbers - <a href="URL" style="color:#3498db;text-decoration:none;">Credible Source</a></li>
<li><strong>Month Year:</strong> Another data point - <a href="URL" style="color:#3498db;text-decoration:none;">Source Name</a></li>
<li><strong>Month Year:</strong> Third data point - <a href="URL" style="color:#3498db;text-decoration:none;">Source Name</a></li>
</ul>

<hr style="border:none;border-top:1px solid #ddd;margin:30px 0;">

[Repeat this format for stocks 2 and 3]

</body>
</html>

CRITICAL LINK FORMATTING:
- ALL sources MUST be proper HTML hyperlinks: <a href="URL" style="color:#3498db;text-decoration:none;">Link Text</a>
- NEVER use raw URLs like <https://...> or https://...
- Link text should be descriptive: "ASX Announcement", "Bloomberg", "AFR", etc.

SEARCH INSTRUCTIONS:
- Search for "[company name] stock price ASX" for current prices
- Search for "site:asx.com.au [ticker] announcement 2025 2026" for ASX announcements
- Search for "[company name] news January 2026" for recent developments
- Search for "[industry] Australia data 2025 2026" for industry dynamics

Generate the complete HTML report for all 3 stocks with real data."""

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=16000,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Extract HTML
        html_content = ""
        for block in message.content:
            if block.type == "text":
                html_content += block.text
        
        # Simple cleanup: if content doesn't start with <!DOCTYPE or <html, wrap it
        content_stripped = html_content.strip()
        if not (content_stripped.startswith('<!DOCTYPE') or content_stripped.startswith('<html')):
            html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family:Arial,sans-serif;max-width:900px;margin:0 auto;padding:20px;background-color:#ffffff;">
{html_content}
</body>
</html>"""
        
        print(f"✅ Generated {len(html_content)} characters")
        
    except Exception as e:
        print(f"❌ Error generating: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Send emails
    try:
        print("\n📧 Sending emails...")
        
        sg = sendgrid.SendGridAPIClient(api_key=sendgrid_key)
        subject = f"Berkholts Stock Summaries - {today}"
        
        for recipient in recipient_emails:
            print(f"   → {recipient}")
            
            mail = Mail(
                from_email=Email(from_email),
                to_emails=To(recipient),
                subject=subject,
                html_content=Content("text/html", html_content)
            )
            
            response = sg.client.mail.send.post(request_body=mail.get())
            print(f"   ✅ Sent (Status: {response.status_code})")
        
        print("\n✅ DONE!")
        
    except Exception as e:
        print(f"❌ Error sending: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()