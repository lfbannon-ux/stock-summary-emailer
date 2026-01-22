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
    
    # Step 1: Check all environment variables
    print("\n📋 Checking environment variables...")
    
    anthropic_key = os.getenv('ANTHROPIC_API_KEY')
    sendgrid_key = os.getenv('SENDGRID_API_KEY')
    from_email = os.getenv('FROM_EMAIL')
    recipient_emails_str = os.getenv('RECIPIENT_EMAILS')
    
    print(f"  ANTHROPIC_API_KEY: {'✅ Found' if anthropic_key else '❌ Missing'}")
    print(f"  SENDGRID_API_KEY: {'✅ Found' if sendgrid_key else '❌ Missing'}")
    print(f"  FROM_EMAIL: {'✅ Found' if from_email else '❌ Missing'}")
    print(f"  RECIPIENT_EMAILS: {'✅ Found' if recipient_emails_str else '❌ Missing'}")
    
    # Step 2: Validate we have recipient emails
    if not recipient_emails_str:
        print("\n❌ ERROR: RECIPIENT_EMAILS environment variable is not set!")
        print("💡 Please add it in Railway Variables tab")
        print("💡 Format: email1@domain.com,email2@domain.com")
        sys.exit(1)
    
    print(f"\n📧 Raw RECIPIENT_EMAILS: '{recipient_emails_str}'")
    
    # Parse recipient emails
    recipient_emails = [email.strip() for email in recipient_emails_str.split(',') if email.strip()]
    
    print(f"📧 Parsed {len(recipient_emails)} recipient(s):")
    for i, email in enumerate(recipient_emails, 1):
        print(f"   {i}. {email}")
    
    if len(recipient_emails) == 0:
        print("\n❌ ERROR: No valid email addresses found after parsing!")
        sys.exit(1)
    
    # Step 3: Check other required variables
    if not anthropic_key:
        print("\n❌ ERROR: ANTHROPIC_API_KEY is missing!")
        sys.exit(1)
    
    if not sendgrid_key:
        print("\n❌ ERROR: SENDGRID_API_KEY is missing!")
        sys.exit(1)
        
    if not from_email:
        print("\n❌ ERROR: FROM_EMAIL is missing!")
        sys.exit(1)
    
    print(f"\n✅ All environment variables validated!")
    print(f"✅ FROM_EMAIL: {from_email}")
    print(f"✅ Recipients: {len(recipient_emails)}")
    
    # Step 4: Generate summary with Claude
    try:
        print("\n" + "=" * 60)
        print("📊 Generating stock summaries with Claude API...")
        print("⏱️  This will take 5-8 minutes for all 19 stocks...")
        print("=" * 60)
        
        client = anthropic.Anthropic(api_key=anthropic_key)
        today = datetime.now().strftime("%B %d, %Y")
        
        prompt = f"""Generate a professional HTML email report with stock summaries for {today}.

STOCKS TO COVER (all 19):
1. AUB Group Limited (AUB.AX) - Insurance broker
2. Mineral Resources Limited (MIN.AX) - Mining
3. Charter Hall Group (CHC.AX) - Commercial property REIT
4. HUB24 Limited (HUB.AX) - Wealth platform
5. Macquarie Group Limited (MQG.AX) - Investment bank
6. CSL Limited (CSL.AX) - Biopharmaceutical
7. Dicker Data Limited (DDR.AX) - IT distributor
8. Hansen Technologies Limited (HSN.AX) - Software
9. Growthpoint Properties Australia (GOZ.AX) - Industrial REIT
10. Propel Funeral Partners Limited (PFP.AX) - Funeral services
11. Nick Scali Limited (NCK.AX) - Furniture retailer
12. Xero Limited (XRO.AX) - Cloud accounting
13. Block Inc (SQ2.AX) - Digital payments
14. Commonwealth Bank of Australia (CBA.AX) - Bank
15. News Corp (NWS.AX) - Media
16. Sigma Healthcare Limited (SIG.AX) - Pharmacy
17. Supply Network Limited (SNL.AX) - Logistics
18. James Hardie Industries plc (JHX.AX) - Building materials
19. PEXA Group Limited (PXA.AX) - Property platform

FOR EACH STOCK INCLUDE:
- PRICE: [current] | YESTERDAY: [change with color]
- REASON FOR MOVE: Recent news (last 7 days) or "No material announcements"
- COMPANY DEVELOPMENTS: List with [NEW] tags
- LAST COMPANY ANNOUNCEMENT: Date, summary, ASX link
- INDUSTRY/COMPETITIVE DYNAMICS: 3 points with data and sources

FORMAT REQUIREMENTS:
- Start with: <!DOCTYPE html><html><head><meta charset="UTF-8"></head><body style="font-family: Arial, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px;">
- Title: <h1 style="color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px;">Berkholts Stock Summaries - {today}</h1>
- Each stock: <h2 style="color: #34495e; margin-top: 40px; border-bottom: 2px solid #95a5a6; padding-bottom: 8px;">N. Company Name (TICKER)</h2>
- Sections: <p style="line-height: 1.6; margin: 10px 0;"><strong style="color: #2980b9;">SECTION:</strong> content</p>
- Lists: <ul style="line-height: 1.8; margin: 10px 0;"><li>item</li></ul>
- Green for gains: <span style="color: #00AA00; font-weight: bold;">+$X.XX (+X.XX%)</span>
- Red for losses: <span style="color: #DD0000; font-weight: bold;">-$X.XX (-X.XX%)</span>
- Orange for NEW: <span style="color: #FF8800; font-weight: bold;">[NEW]</span>
- Links: <a href="URL" style="color: #3498db; text-decoration: none;">Source Name</a>
- Separator: <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
- End with: </body></html>

LINK FORMATTING (CRITICAL):
✅ CORRECT: <a href="https://announcements.asx.com.au/asxpdf/20251201/pdf/abc.pdf" style="color: #3498db; text-decoration: none;">ASX Announcement</a>
❌ WRONG: <https://announcements.asx.com.au/...>
❌ WRONG: https://announcements.asx.com.au/...

Never show raw URLs. Always use <a href="URL">descriptive text</a>.

Generate the complete HTML for all 19 stocks now."""

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=32000,
            system="You generate HTML email reports. Output ONLY HTML code starting with <!DOCTYPE html> and ending with </html>. No explanations, no disclaimers, no text outside HTML tags. All URLs must be in <a href> tags, never as raw text.",
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Extract HTML content
        html_content = ""
        for block in message.content:
            if block.type == "text":
                html_content += block.text
        
        # Strip any text before <!DOCTYPE or <html> and after </html>
        html_match = re.search(r'(<!DOCTYPE[^>]*>)?\s*<html.*?</html>', html_content, re.DOTALL | re.IGNORECASE)
        if html_match:
            html_content = html_match.group(0)
        else:
            # Fallback: look for content starting with <h1>
            html_match = re.search(r'<h1.*$', html_content, re.DOTALL | re.IGNORECASE)
            if html_match:
                # Wrap in basic HTML structure
                html_content = f"<!DOCTYPE html><html><head><meta charset='UTF-8'></head><body>{html_match.group(0)}</body></html>"
        
        print("✅ Summary generated successfully!")
        print(f"📄 Content length: {len(html_content)} characters")
        
    except Exception as e:
        print(f"\n❌ ERROR generating summary: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Step 5: Send emails
    try:
        print("\n" + "=" * 60)
        print("📧 Sending emails via SendGrid...")
        print("=" * 60)
        
        sg = sendgrid.SendGridAPIClient(api_key=sendgrid_key)
        subject = f"Berkholts Stock Summaries - {today}"
        from_email_obj = Email(from_email)
        
        for i, recipient in enumerate(recipient_emails, 1):
            print(f"\n📤 Sending to recipient {i}/{len(recipient_emails)}: {recipient}")
            
            to_email = To(recipient)
            content = Content("text/html", html_content)
            mail = Mail(from_email_obj, to_email, subject, content)
            
            try:
                response = sg.client.mail.send.post(request_body=mail.get())
                print(f"   ✅ Sent successfully! Status: {response.status_code}")
            except Exception as e:
                print(f"   ❌ Failed to send: {str(e)}")
        
        print("\n" + "=" * 60)
        print("✅ ALL EMAILS SENT SUCCESSFULLY!")
        print(f"⏰ Completed at: {datetime.now()}")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ ERROR sending emails: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()