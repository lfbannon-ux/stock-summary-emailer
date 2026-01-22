#!/usr/bin/env python3
import os
import sys
import sendgrid
from sendgrid.helpers.mail import Mail, Email, To, Content
from datetime import datetime
import anthropic

def main():
    """Main function to generate and send daily stock summary"""
    
    print("=" * 60)
    print(f"🚀 Daily Stock Summary Emailer")
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
        print("⏱️  This will take 1-2 minutes...")
        print("=" * 60)
        
        client = anthropic.Anthropic(api_key=anthropic_key)
        today = datetime.now().strftime("%B %d, %Y")
        
        prompt = f"""Generate a comprehensive daily stock summary report for {today} for the following 10 Australian stocks:

1. Charter Hall Group (CHC.AX)
2. Macquarie Group (MQG.AX)
3. Hansen Technologies (HSN.AX)
4. HUB24 (HUB.AX)
5. PEXA (PXA.AX)
6. Sigma Healthcare (SIG.AX)
7. Mineral Resources (MIN.AX)
8. Supply Network (SNL.AX)
9. Dicker Data (DDR.AX)
10. CSL Limited (CSL.AX)

For EACH stock, provide:

**PRICE:** [Current price] | **YESTERDAY:** [Change and %]

**REASON FOR MOVE:** [Fundamental catalyst only - exclude technical analysis unless materially significant]

**COMPANY DEVELOPMENTS (Past Week):**
- Tag any NEW developments with [NEW]
- Focus on: earnings, guidance changes, major contracts, acquisitions, management changes
- Include dates and sources

**INDUSTRY/COMPETITIVE DYNAMICS (2-3 key points):**
- Each point must include: DATE and SOURCE
- Focus on: volumes, pricing, customers, competitive dynamics, industry structure, regulatory changes
- Warren Buffett-style fundamental analysis only

CRITICAL REQUIREMENTS:
- Use web search to find current prices and recent news
- All industry trends must be DATED and SOURCED
- Tag anything that's new information since yesterday with [NEW]
- Focus on business fundamentals that affect: volumes, pricing, customers, margins, competitive position
- Exclude pure technical analysis (chart patterns, moving averages, etc.)
- Keep each stock section concise but informative

Format the output as clean, professional HTML with:
- Clear headers for each stock
- Green for positive moves, red for negative
- [NEW] tags highlighted in orange
- Sources in italics
- Professional styling suitable for email

Begin with an <h1> title "Daily Stock Summaries - {today}" and format everything ready to send as an email body."""

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=16000,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Extract HTML content
        html_content = ""
        for block in message.content:
            if block.type == "text":
                html_content += block.text
        
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
        subject = f"Daily Stock Summaries - {today}"
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