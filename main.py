#!/usr/bin/env python3
import os
import sys
import sendgrid
from sendgrid.helpers.mail import Mail, Email, To, Content
from datetime import datetime
import anthropic

def main():
    """Generate and send daily stock summary using two-step approach"""
    
    print("=" * 60)
    print(f"🚀 Berkholts Daily Stock Summary (Outlook-Compatible)")
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
    
    # STEP 1: Gather data
    try:
        print("\n" + "=" * 60)
        print("STEP 1: Gathering data (2-3 minutes)...")
        print("=" * 60)
        
        step1_prompt = f"""Research and gather information for a stock summary report covering these 2 Australian companies:

1. AUB Group Limited (AUB.AX) - Insurance broker
2. Mineral Resources Limited (MIN.AX) - Mining and resources

For each company, YOU MUST find and provide ALL of the following:

**CURRENT PRICE & YESTERDAY'S CHANGE**
Search for current ASX stock price

**REASON FOR MOVE (Last 7 days only)**
Material news or announcements from last 7 days with specific dates and hyperlinked sources

**COMPANY DEVELOPMENTS (Last 7 days only)**
New developments from past week with dates and hyperlinked sources

**LAST COMPANY ANNOUNCEMENT**
Search: site:asx.com.au [ticker] announcement (focus on price sensitive announcements)
Find the most recent material ASX announcement
Provide: date, summary with specific numbers, and ASX announcement URL

**LAST EARNINGS REPORT** ⚠️ MANDATORY - DO NOT SKIP
Search: site:asx.com.au [ticker] "financial report" OR "trading update" OR "quarterly"
Find the last time the company reported: Annual Report, Half-Yearly Report, Quarterly Report, or Trading Update
Provide: date, type of report, key financial metrics (revenue, profit, guidance), and ASX announcement URL
This is a REQUIRED section - you must find this information

**INDUSTRY/COMPETITIVE DYNAMICS (Last month)**
Find EXACTLY 4 data points, each with:
- Specific date (month and year)
- Hard data (percentages, dollar amounts, volumes, growth rates)
- Hyperlinked source from credible publications: Trade magazines, WSJ, FT, AFR, Bloomberg, Reuters, government data, competitor filings
EXCLUDE: Motley Fool, Simply Wall St, TradingView and any unsophisticated publications
CRITICAL: Each data point MUST have a specific URL that you can hyperlink

Research thoroughly. Every piece of information needs a source URL."""

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
    
    # STEP 2: Convert to Outlook-compatible HTML
    try:
        print("\n" + "=" * 60)
        print("STEP 2: Converting to Outlook-compatible HTML...")
        print("=" * 60)
        
        step2_prompt = f"""Convert the research below into HTML email format.

RESEARCH DATA:
{research_content}

Create HTML with this EXACT structure (Outlook-compatible):

<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
</head>
<body style="margin:0;padding:0;font-family:Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f4f4f4;">
<tr>
<td align="center" style="padding:20px;">
<table width="600" cellpadding="0" cellspacing="0" border="0" style="background-color:#ffffff;">
<tr>
<td style="padding:30px;">

<h1 style="color:#2c3e50;font-size:24px;margin:0 0 10px 0;padding:0 0 10px 0;border-bottom:3px solid #3498db;">Berkholts Stock Summaries - {today}</h1>

<h2 style="color:#34495e;font-size:20px;margin:30px 0 10px 0;padding:0 0 8px 0;border-bottom:2px solid #95a5a6;">1. AUB Group Limited (AUB.AX)</h2>

<p style="margin:10px 0;line-height:1.6;"><strong style="color:#2980b9;">PRICE:</strong> A$XX.XX | <strong style="color:#2980b9;">YESTERDAY:</strong> <span style="color:#00AA00;font-weight:bold;">+A$X.XX (+X.XX%)</span></p>

<p style="margin:10px 0;line-height:1.6;"><strong style="color:#2980b9;">REASON FOR MOVE:</strong> [Info with hyperlinked source]</p>

<p style="margin:10px 0;line-height:1.6;"><strong style="color:#2980b9;">COMPANY DEVELOPMENTS (Past Week):</strong></p>
<ul style="margin:10px 0;padding-left:20px;line-height:1.8;">
<li><span style="color:#FF8800;font-weight:bold;">[NEW]</span> <strong>Date:</strong> Development - <a href="URL" style="color:#3498db;text-decoration:none;">Source</a></li>
</ul>

<p style="margin:10px 0;line-height:1.6;"><strong style="color:#2980b9;">LAST COMPANY ANNOUNCEMENT:</strong></p>
<ul style="margin:10px 0;padding-left:20px;line-height:1.8;">
<li><strong>Date:</strong> [Date]</li>
<li><strong>Summary:</strong> [Summary]</li>
<li><strong>Source:</strong> <a href="[URL]" style="color:#3498db;text-decoration:none;">ASX Announcement</a></li>
</ul>

<p style="margin:10px 0;line-height:1.6;"><strong style="color:#2980b9;">LAST EARNINGS REPORT:</strong></p>
<ul style="margin:10px 0;padding-left:20px;line-height:1.8;">
<li><strong>Date:</strong> [Date]</li>
<li><strong>Type:</strong> [Annual/Half-Yearly/Quarterly/Trading Update]</li>
<li><strong>Summary:</strong> [Key metrics and highlights]</li>
<li><strong>Source:</strong> <a href="[URL]" style="color:#3498db;text-decoration:none;">ASX Announcement</a></li>
</ul>

<p style="margin:10px 0;line-height:1.6;"><strong style="color:#2980b9;">INDUSTRY/COMPETITIVE DYNAMICS:</strong></p>
<ul style="margin:10px 0;padding-left:20px;line-height:1.8;">
<li><strong>Date:</strong> Data point with numbers - <a href="URL" style="color:#3498db;text-decoration:none;">Source</a></li>
<li><strong>Date:</strong> Data point with numbers - <a href="URL" style="color:#3498db;text-decoration:none;">Source</a></li>
<li><strong>Date:</strong> Data point with numbers - <a href="URL" style="color:#3498db;text-decoration:none;">Source</a></li>
<li><strong>Date:</strong> Data point with numbers - <a href="URL" style="color:#3498db;text-decoration:none;">Source</a></li>
</ul>

<hr style="border:0;border-top:1px solid #ddd;margin:30px 0;">

[Repeat for company 2]

</td>
</tr>
</table>
</td>
</tr>
</table>
</body>
</html>

KEY RULES:
- Use TABLE layout (Outlook needs this)
- Fixed width: 600px
- All styles inline
- Green for gains: style="color:#00AA00;font-weight:bold;"
- Red for losses: style="color:#DD0000;font-weight:bold;"
- ALL sources MUST be hyperlinked: <a href="URL" style="color:#3498db;text-decoration:none;">Source Name</a>
- NEVER show raw URLs
- EVERY piece of information needs a hyperlinked source

Start with <!DOCTYPE html> and end with </html>. Nothing before or after."""

        message2 = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            messages=[{"role": "user", "content": step2_prompt}]
        )
        
        html_content = ""
        for block in message2.content:
            if block.type == "text":
                html_content += block.text
        
        # AGGRESSIVE POST-PROCESSING TO FIX URLS
        import re
        
        # Step 1: Clean HTML extraction
        html_match = re.search(r'(<!DOCTYPE[^>]*>)?\s*<html.*?</html>', html_content, re.DOTALL | re.IGNORECASE)
        if html_match:
            html_content = html_match.group(0)
        
        # Step 2: Fix SendGrid tracking URLs and angle bracket URLs
        # <https://u59134112.ct.sendgrid.net/...> → <a href="...">ASX Announcement</a>
        def fix_angle_url(match):
            url = match.group(1)
            if 'asx.com.au' in url or 'sendgrid' in url:
                link_text = 'ASX Announcement'
            elif 'afr.com' in url:
                link_text = 'AFR'
            elif 'bloomberg' in url:
                link_text = 'Bloomberg'
            elif 'reuters' in url:
                link_text = 'Reuters'
            elif 'wsj.com' in url:
                link_text = 'WSJ'
            elif 'ft.com' in url:
                link_text = 'Financial Times'
            else:
                link_text = 'Source'
            return f'<a href="{url}" style="color:#3498db;text-decoration:none;">{link_text}</a>'
        
        html_content = re.sub(r'<(https://[^>]+)>', fix_angle_url, html_content)
        
        # Step 3: Fix any remaining bare URLs (not in href or angle brackets)
        def fix_bare_urls(text):
            # Don't replace URLs already in href=""
            parts = re.split(r'(href="[^"]*")', text)
            result = []
            for i, part in enumerate(parts):
                if i % 2 == 0:  # Not inside href=""
                    # Replace standalone https:// URLs
                    part = re.sub(
                        r'(?<!href=")(?<!">)(https://[^\s<>"]+)',
                        lambda m: f'<a href="{m.group(0)}" style="color:#3498db;text-decoration:none;">Source</a>',
                        part
                    )
                result.append(part)
            return ''.join(result)
        
        html_content = fix_bare_urls(html_content)
        
        print(f"✅ HTML: {len(html_content)} characters")
        print("✅ All URLs converted to proper hyperlinks")
        
    except Exception as e:
        print(f"❌ Step 2 error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Send
    try:
        print("\n" + "=" * 60)
        print("Sending emails...")
        print("=" * 60)
        
        sg = sendgrid.SendGridAPIClient(api_key=sendgrid_key)
        subject = f"Berkholts Stock Summaries - {today}"
        
        for recipient in recipient_emails:
            print(f"📤 {recipient}...")
            
            from sendgrid.helpers.mail import HtmlContent
            
            message = Mail(
                from_email=from_email,
                to_emails=recipient,
                subject=subject
            )
            
            # Set HTML content explicitly (no plain text version)
            message.add_content(HtmlContent(html_content))
            
            response = sg.client.mail.send.post(request_body=message.get())
            print(f"   ✅ Status: {response.status_code}")
        
        print("\n✅ COMPLETE!")
        
    except Exception as e:
        print(f"❌ Send error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
