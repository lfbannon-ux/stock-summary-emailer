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
        
        prompt = f"""Generate a comprehensive daily stock summary report for {today} for these 19 Australian stocks:

1. AUB Group Limited (AUB.AX) - Australian insurance broker
2. Mineral Resources Limited (MIN.AX) - Mining and resources
3. Charter Hall Group (CHC.AX) - Commercial property REIT
4. HUB24 Limited (HUB.AX) - Wealth management platform
5. Macquarie Group Limited (MQG.AX) - Investment bank
6. CSL Limited (CSL.AX) - Biopharmaceutical company
7. Dicker Data Limited (DDR.AX) - IT distributor
8. Hansen Technologies Limited (HSN.AX) - Software company
9. Growthpoint Properties Australia (GOZ.AX) - Industrial property REIT
10. Propel Funeral Partners Limited (PFP.AX) - Funeral services
11. Nick Scali Limited (NCK.AX) - Furniture retailer
12. Xero Limited (XRO.AX) - Cloud accounting software
13. Block Inc (SQ2.AX) - Digital payments (Square)
14. Commonwealth Bank of Australia (CBA.AX) - Major bank
15. News Corp (NWS.AX) - Media conglomerate
16. Sigma Healthcare Limited (SIG.AX) - Pharmacy and healthcare
17. Supply Network Limited (SNL.AX) - Logistics and supply chain
18. James Hardie Industries plc (JHX.AX) - Building materials
19. PEXA Group Limited (PXA.AX) - Property exchange platform

For EACH stock, provide the following sections:

**PRICE:** [Current price] | **YESTERDAY:** [Change and %]

**REASON FOR MOVE:** 
- ONLY include NEW fundamental information from the last 7 days
- Must be timestamped with specific date
- Preferably from company ASX announcements or major credible news
- If no material news in last 7 days, state "No material company announcements in the past week" and note broader market factors if relevant
- Exclude technical analysis unless materially significant

**COMPANY DEVELOPMENTS (Past Week):**
- Tag any NEW developments with [NEW]
- ONLY include developments from the last 7 days
- Focus on: earnings, guidance changes, major contracts, acquisitions, management changes
- Include dates and hyperlinked sources
- If nothing in past week, state "No new developments reported this week"

**LAST COMPANY ANNOUNCEMENT:**
This is a CRITICAL section - you must search thoroughly for this information:
- **Date:** [Date of most recent material ASX announcement]
- **Summary:** [Detailed 2-3 sentence summary of what was announced, with specific numbers and guidance if applicable]
- **Source:** [Hyperlinked ASX announcement URL]

SEARCH STRATEGY FOR FINDING LAST ANNOUNCEMENT:
1. Search: "site:asx.com.au [ticker] announcement 2025 2026"
2. Search: "[Company name] ASX guidance update 2025"
3. Search: "[Company name] trading update"
4. Look for announcements containing: guidance, outlook, earnings, trading update, AGM
5. Prioritize the MOST RECENT material announcement (not just price-sensitive)
6. Common announcement types to look for: quarterly updates, AGM addresses, guidance updates, results

**INDUSTRY/COMPETITIVE DYNAMICS (3 key points):**
Each point MUST include:
- Specific DATE (month and year minimum)
- HARD DATA (percentages, dollar values, volumes, growth rates)
- HYPERLINKED credible SOURCE

SOURCE QUALITY REQUIREMENTS:
✅ PRIORITIZE THESE SOURCES:
- Industry trade magazines and journals
- Major credible news outlets (AFR, Bloomberg, Reuters, Financial Times)
- Government/regulatory data (ABS, RBA, ASIC, industry regulators)
- Industry associations and research firms (Gartner, IDC, JLL, CBRE, etc.)
- Company financial reports and industry reports
- Specialist financial research firms

❌ EXCLUDE THESE SOURCES:
- Motley Fool
- Simply Wall St
- TradingView
- DailyForex
- Property listing sites (Domain, realestate.com.au) unless citing hard data
- General investment advice websites
- Retail investor forums

Focus on information that materially affects: volumes, pricing, customer behavior, margins, competitive position, regulatory changes, industry structure

CRITICAL REQUIREMENTS FOR ALL SECTIONS:
- Output ONLY the HTML report - no preambles, explanations, or apologies about data limitations
- Use web search extensively to find current prices, recent ASX announcements, and credible industry news
- ALL sources must be HYPERLINKED using proper HTML anchor tags with descriptive text
- NEVER display raw URLs - always hide them inside anchor tags with readable link text
- Example: <a href="URL" style="color: #3498db;">Australian Financial Review - January 22, 2026</a>
- All dates must be specific (not "recently" or "last week")
- Focus on business fundamentals, not technical chart analysis
- Maintain consistent professional tone throughout
- If you cannot find recent news for a stock, state "No material company announcements in the past week" - do NOT apologize or explain data limitations

FORMAT AS PROFESSIONAL HTML EMAIL:
- Begin IMMEDIATELY with: <h1 style="color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px;">Berkholts Stock Summaries - {today}</h1>
- NO text or content above this heading
- NO preambles about data limitations or real-time access
- Use <h2 style="color: #34495e; margin-top: 30px; border-bottom: 2px solid #95a5a6; padding-bottom: 8px;"> for each stock name and ticker
- Use <strong style="color: #2980b9;"> for section headers (PRICE, REASON FOR MOVE, etc.)
- Use <span style="color: #00AA00; font-weight: bold;"> for positive price moves
- Use <span style="color: #DD0000; font-weight: bold;"> for negative price moves  
- Use <span style="color: #FF8800; font-weight: bold;">[NEW]</span> for new tags
- Use <p style="line-height: 1.6; margin: 10px 0;"> for paragraphs
- Use <ul style="line-height: 1.8;"> for lists
- All sources must be clickable hyperlinks with style: <a href="URL" style="color: #3498db; text-decoration: none;">Source Name</a>
- NEVER show raw URLs in angle brackets like <https://...>
- NEVER show URLs as plain text
- ALL citations must use this format: <a href="actual-url">Source Name - Date</a>
- Example CORRECT: <a href="https://announcements.asx.com.au/asxpdf/20251201/pdf/06sr2bsh6yv802.pdf" style="color: #3498db; text-decoration: none;">ASX Announcement - December 1, 2025</a>
- Example WRONG: <https://announcements.asx.com.au/asxpdf/20251201/pdf/06sr2bsh6yv802.pdf>
- URLs must ALWAYS be hidden inside anchor tags, never displayed as text
- Use INLINE STYLES only - no <style> tags or external CSS
- All formatting must be inline style attributes on each element
- Professional styling suitable for email viewing

Generate the complete report with ALL 19 stocks. Do not abbreviate or skip any stocks."""

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=32000,
            system="You are an HTML report generator. Your response must contain ONLY valid HTML code and absolutely nothing else. Do not include any disclaimers, notes, explanations, or text outside the HTML tags. Your response must start with <html> or <!DOCTYPE html> and end with </html>. Everything you output will be sent directly as an email body. No preambles. No explanations. No meta-commentary. Only HTML.",
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Extract HTML content
        html_content = ""
        for block in message.content:
            if block.type == "text":
                html_content += block.text
        
        # Strip any text before <html> or <!DOCTYPE and after </html>
        import re
        # Find the HTML content between tags
        html_match = re.search(r'(<!DOCTYPE[^>]*>)?\s*<html.*?</html>', html_content, re.DOTALL | re.IGNORECASE)
        if html_match:
            html_content = html_match.group(0)
        else:
            # If no full HTML structure, look for content starting with <h1>
            html_match = re.search(r'<h1.*$', html_content, re.DOTALL | re.IGNORECASE)
            if html_match:
                html_content = html_match.group(0)
        
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