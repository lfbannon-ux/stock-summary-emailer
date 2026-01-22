#!/usr/bin/env python3
import os
import sys
import sendgrid
from sendgrid.helpers.mail import Mail, Email, To, Content
from datetime import datetime
import anthropic
import re

def main():
    """Main function to generate and send daily stock summary"""
    
    print("=" * 60)
    print(f"🚀 Berkholts Daily Stock Summary Emailer (10 Stocks)")
    print(f"⏰ Started at: {datetime.now()}")
    print("=" * 60)
    
    # Check environment variables
    anthropic_key = os.getenv('ANTHROPIC_API_KEY')
    sendgrid_key = os.getenv('SENDGRID_API_KEY')
    from_email = os.getenv('FROM_EMAIL')
    recipient_emails_str = os.getenv('RECIPIENT_EMAILS')
    
    if not all([anthropic_key, sendgrid_key, from_email, recipient_emails_str]):
        print("\n❌ ERROR: Missing required environment variables!")
        sys.exit(1)
    
    recipient_emails = [email.strip() for email in recipient_emails_str.split(',') if email.strip()]
    print(f"✅ Recipients: {len(recipient_emails)}")
    
    # Generate summary
    try:
        print("\n📊 Generating stock summaries...")
        print("⏱️  This will take 3-5 minutes for 10 stocks...")
        
        client = anthropic.Anthropic(api_key=anthropic_key)
        today = datetime.now().strftime("%B %d, %Y")
        
        prompt = f"""Generate a professional HTML email report for {today} with these 10 Australian stocks:

1. AUB Group Limited (AUB.AX) - Insurance broker
2. Mineral Resources Limited (MIN.AX) - Mining and resources
3. Charter Hall Group (CHC.AX) - Commercial property REIT
4. HUB24 Limited (HUB.AX) - Wealth management platform
5. Macquarie Group Limited (MQG.AX) - Investment bank
6. CSL Limited (CSL.AX) - Biopharmaceutical company
7. Dicker Data Limited (DDR.AX) - IT distributor
8. Hansen Technologies Limited (HSN.AX) - Software company
9. Growthpoint Properties Australia (GOZ.AX) - Industrial property REIT
10. Propel Funeral Partners Limited (PFP.AX) - Funeral services

STRUCTURE:
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;max-width:900px;margin:0 auto;padding:20px;background-color:#ffffff;">

<h1 style="color:#2c3e50;border-bottom:3px solid #3498db;padding-bottom:10px;margin-bottom:30px;">Berkholts Stock Summaries - {today}</h1>

FOR EACH OF THE 10 STOCKS:

<h2 style="color:#34495e;margin-top:40px;border-bottom:2px solid #95a5a6;padding-bottom:8px;">N. Company Name (TICKER)</h2>

<p style="line-height:1.6;margin:10px 0;"><strong style="color:#2980b9;">PRICE:</strong> A$XX.XX | <strong style="color:#2980b9;">YESTERDAY:</strong> <span style="color:#00AA00;font-weight:bold;">+A$X.XX (+X.XX%)</span></p>

<p style="line-height:1.6;margin:10px 0;"><strong style="color:#2980b9;">REASON FOR MOVE:</strong> [Recent announcement from last 7 days with specific date, OR "No material company announcements in the past week."]</p>

<p style="line-height:1.6;margin:10px 0;"><strong style="color:#2980b9;">COMPANY DEVELOPMENTS (Past Week):</strong></p>
<ul style="line-height:1.8;margin:10px 0;">
<li><span style="color:#FF8800;font-weight:bold;">[NEW]</span> <strong>Date:</strong> Development description - <a href="actual-url" style="color:#3498db;text-decoration:none;">Source Name</a></li>
<li>OR: No new developments reported this week</li>
</ul>

<p style="line-height:1.6;margin:10px 0;"><strong style="color:#2980b9;">LAST COMPANY ANNOUNCEMENT:</strong></p>
<ul style="line-height:1.8;margin:10px 0;">
<li><strong>Date:</strong> Month Day, Year</li>
<li><strong>Summary:</strong> 2-3 sentences with specific numbers, guidance, key metrics</li>
<li><strong>Source:</strong> <a href="https://announcements.asx.com.au/asxpdf/..." style="color:#3498db;text-decoration:none;">ASX Announcement</a></li>
</ul>

<p style="line-height:1.6;margin:10px 0;"><strong style="color:#2980b9;">INDUSTRY/COMPETITIVE DYNAMICS:</strong></p>
<ul style="line-height:1.8;margin:10px 0;">
<li><strong>Month Year:</strong> Specific data point with percentages/numbers - <a href="url" style="color:#3498db;text-decoration:none;">Credible Source Name</a></li>
<li><strong>Month Year:</strong> Another data point with metrics - <a href="url" style="color:#3498db;text-decoration:none;">Source Name</a></li>
<li><strong>Month Year:</strong> Third data point - <a href="url" style="color:#3498db;text-decoration:none;">Source Name</a></li>
</ul>

<hr style="border:none;border-top:1px solid #ddd;margin:30px 0;">

[Repeat for all 10 stocks]

</body>
</html>

SEARCH REQUIREMENTS - YOU MUST SEARCH FOR:
1. Current stock price: "[company name] [ticker] stock price January 2026"
2. ASX announcements: "site:asx.com.au [ticker] announcement"
3. Recent news: "[company name] news January 2026"
4. Industry data: "[industry] Australia 2025 2026 data"

DO NOT write "data not available" - search multiple times with different terms until you find real data.

LINK FORMATTING RULES:
✅ CORRECT: <a href="https://actual-url.com" style="color:#3498db;text-decoration:none;">Source Name</a>
❌ WRONG: <https://url.com>
❌ WRONG: https://url.com
NEVER show raw URLs. ALL sources must be proper HTML anchor tags.

COLOR RULES:
- Gains: <span style="color:#00AA00;font-weight:bold;">+$X.XX (+X%)</span>
- Losses: <span style="color:#DD0000;font-weight:bold;">-$X.XX (-X%)</span>
- [NEW] tags: <span style="color:#FF8800;font-weight:bold;">[NEW]</span>

QUALITY STANDARDS:
- Find actual current prices (not "data not available")
- Find actual ASX announcements with real URLs
- Use credible sources: AFR, Bloomberg, Reuters, industry magazines, government data
- Exclude: Motley Fool, Simply Wall St, TradingView
- All 10 stocks must be complete with real data

Generate the complete HTML report now."""

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=32000,
            system="You generate HTML reports. Output ONLY HTML from <!DOCTYPE html> to </html>. No explanations. No disclaimers. No text outside HTML. All URLs must be in <a href> tags, never raw. Search thoroughly until you find real data for all 10 stocks.",
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Extract HTML
        html_content = ""
        for block in message.content:
            if block.type == "text":
                html_content += block.text
        
        # Clean: remove any text before <!DOCTYPE or <html> and after </html>
        html_match = re.search(r'(<!DOCTYPE[^>]*>)?\s*<html.*?</html>', html_content, re.DOTALL | re.IGNORECASE)
        if html_match:
            html_content = html_match.group(0)
        else:
            # Fallback: wrap content
            body_match = re.search(r'<h1.*$', html_content, re.DOTALL | re.IGNORECASE)
            if body_match:
                html_content = f'<!DOCTYPE html><html><head><meta charset="UTF-8"></head><body style="font-family:Arial,sans-serif;max-width:900px;margin:0 auto;padding:20px;background-color:#ffffff;">{body_match.group(0)}</body></html>'
        
        print(f"✅ Generated {len(html_content)} characters")
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Send emails
    try:
        print("\n📧 Sending emails...")
        
        sg = sendgrid.SendGridAPIClient(api_key=sendgrid_key)
        subject = f"Berkholts Stock Summaries - {today}"
        from_email_obj = Email(from_email)
        
        for i, recipient in enumerate(recipient_emails, 1):
            print(f"📤 Sending to {recipient}...")
            
            to_email = To(recipient)
            content = Content("text/html", html_content)
            mail = Mail(from_email_obj, to_email, subject, content)
            
            try:
                response = sg.client.mail.send.post(request_body=mail.get())
                print(f"   ✅ Status: {response.status_code}")
            except Exception as e:
                print(f"   ❌ Failed: {str(e)}")
        
        print("\n✅ COMPLETE!")
        print(f"⏰ Finished: {datetime.now()}")
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()