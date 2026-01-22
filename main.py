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
    print(f"🚀 Berkholts Daily Stock Summary Emailer")
    print(f"⏰ Started at: {datetime.now()}")
    print("=" * 60)
    
    # Check environment variables
    anthropic_key = os.getenv('ANTHROPIC_API_KEY')
    sendgrid_key = os.getenv('SENDGRID_API_KEY')
    from_email = os.getenv('FROM_EMAIL')
    recipient_emails_str = os.getenv('RECIPIENT_EMAILS')
    
    # Validate all required variables
    if not all([anthropic_key, sendgrid_key, from_email, recipient_emails_str]):
        print("\n❌ ERROR: Missing required environment variables!")
        sys.exit(1)
    
    recipient_emails = [email.strip() for email in recipient_emails_str.split(',') if email.strip()]
    
    if not recipient_emails:
        print("\n❌ ERROR: No valid email addresses found!")
        sys.exit(1)
    
    print(f"✅ Recipients: {len(recipient_emails)}")
    
    # Generate summary
    try:
        print("\n📊 Generating stock summaries...")
        print("⏱️  This will take 5-8 minutes...")
        
        client = anthropic.Anthropic(api_key=anthropic_key)
        today = datetime.now().strftime("%B %d, %Y")
        
        prompt = f"""Create an HTML email report for {today} covering these 19 Australian stocks:

1. AUB Group Limited (AUB.AX)
2. Mineral Resources Limited (MIN.AX)
3. Charter Hall Group (CHC.AX)
4. HUB24 Limited (HUB.AX)
5. Macquarie Group Limited (MQG.AX)
6. CSL Limited (CSL.AX)
7. Dicker Data Limited (DDR.AX)
8. Hansen Technologies Limited (HSN.AX)
9. Growthpoint Properties Australia (GOZ.AX)
10. Propel Funeral Partners Limited (PFP.AX)
11. Nick Scali Limited (NCK.AX)
12. Xero Limited (XRO.AX)
13. Block Inc (SQ2.AX)
14. Commonwealth Bank of Australia (CBA.AX)
15. News Corp (NWS.AX)
16. Sigma Healthcare Limited (SIG.AX)
17. Supply Network Limited (SNL.AX)
18. James Hardie Industries plc (JHX.AX)
19. PEXA Group Limited (PXA.AX)

SEARCH REQUIREMENTS - YOU MUST:
- Search for "[company name] [ticker] stock price" for current prices
- Search for "site:asx.com.au [ticker] announcement" for ASX announcements
- Search for "[company name] news {today}" for recent developments
- Find at least one credible source for industry dynamics

FOR EACH STOCK PROVIDE:
<h2 style="color:#34495e;margin-top:40px;border-bottom:2px solid #95a5a6;padding-bottom:8px;">N. Company Name (TICKER)</h2>

<p style="line-height:1.6;margin:10px 0;"><strong style="color:#2980b9;">PRICE:</strong> A$X.XX | <strong style="color:#2980b9;">YESTERDAY:</strong> <span style="color:#00AA00;font-weight:bold;">+A$X.XX (+X%)</span></p>

<p style="line-height:1.6;margin:10px 0;"><strong style="color:#2980b9;">REASON FOR MOVE:</strong> [Recent news from last 7 days with date, OR "No material company announcements in the past week."]</p>

<p style="line-height:1.6;margin:10px 0;"><strong style="color:#2980b9;">COMPANY DEVELOPMENTS (Past Week):</strong></p>
<ul style="line-height:1.8;margin:10px 0;">
<li><span style="color:#FF8800;font-weight:bold;">[NEW]</span> Development with date - <a href="URL" style="color:#3498db;text-decoration:none;">Source</a></li>
<li>Or: No new developments reported this week</li>
</ul>

<p style="line-height:1.6;margin:10px 0;"><strong style="color:#2980b9;">LAST COMPANY ANNOUNCEMENT:</strong></p>
<ul style="line-height:1.8;margin:10px 0;">
<li><strong>Date:</strong> [Actual date]</li>
<li><strong>Summary:</strong> [2-3 sentences with specific numbers]</li>
<li><strong>Source:</strong> <a href="ACTUAL_ASX_URL" style="color:#3498db;text-decoration:none;">ASX Announcement</a></li>
</ul>

<p style="line-height:1.6;margin:10px 0;"><strong style="color:#2980b9;">INDUSTRY/COMPETITIVE DYNAMICS:</strong></p>
<ul style="line-height:1.8;margin:10px 0;">
<li><strong>Date:</strong> [Specific data point] - <a href="URL" style="color:#3498db;text-decoration:none;">Source Name</a></li>
</ul>

<hr style="border:none;border-top:1px solid #ddd;margin:30px 0;">

CRITICAL FORMATTING RULES:
1. Start with: <!DOCTYPE html><html><head><meta charset="UTF-8"></head><body style="font-family:Arial,sans-serif;max-width:900px;margin:0 auto;padding:20px;background-color:#ffffff;">
2. Title: <h1 style="color:#2c3e50;border-bottom:3px solid #3498db;padding-bottom:10px;margin-bottom:30px;">Berkholts Stock Summaries - {today}</h1>
3. ALL hyperlinks MUST be: <a href="actual-url" style="color:#3498db;text-decoration:none;">Link Text</a>
4. NEVER write: <https://...> or https://... (raw URLs)
5. Green for gains: style="color:#00AA00;font-weight:bold;"
6. Red for losses: style="color:#DD0000;font-weight:bold;"
7. End with: </body></html>

QUALITY REQUIREMENTS:
- You MUST find actual stock prices (search until you find them)
- You MUST find actual ASX announcements (they exist for all companies)
- You MUST provide real source URLs (not "data not available")
- You MUST generate all 19 stocks (no shortcuts)

If you cannot find data after searching, search again with different terms. Do not give up."""

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=32000,
            system="""You are an HTML report generator. Rules:
1. Output ONLY HTML (<!DOCTYPE html> to </html>)
2. Zero text before or after HTML
3. All URLs in <a href="URL">text</a> format
4. Never show raw URLs like <https://...>
5. Search thoroughly - don't give up if first search fails
6. All 19 stocks required - no exceptions""",
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Extract and clean HTML
        html_content = ""
        for block in message.content:
            if block.type == "text":
                html_content += block.text
        
        # Remove any text before/after HTML tags
        html_match = re.search(r'(<!DOCTYPE[^>]*>)?\s*<html.*?</html>', html_content, re.DOTALL | re.IGNORECASE)
        if html_match:
            html_content = html_match.group(0)
        else:
            # Wrap if needed
            html_content = f'<!DOCTYPE html><html><head><meta charset="UTF-8"></head><body style="font-family:Arial,sans-serif;max-width:900px;margin:0 auto;padding:20px;">{html_content}</body></html>'
        
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
                print(f"   ✅ Sent! Status: {response.status_code}")
            except Exception as e:
                print(f"   ❌ Failed: {str(e)}")
        
        print("\n✅ ALL EMAILS SENT!")
        print(f"⏰ Completed at: {datetime.now()}")
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()