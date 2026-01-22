import os
import sendgrid
from sendgrid.helpers.mail import Mail, Email, To, Content
from datetime import datetime
import anthropic
import json

def generate_stock_summary_with_claude():
    """
    Use Claude API to generate fresh daily stock summaries with research
    """
    # Initialize Anthropic client
    client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))
    
    today = datetime.now().strftime("%B %d, %Y")
    
    # The prompt that Claude will use to generate summaries
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
- Examples: "Dec 15, 2025 - Premium pricing: Health insurance premiums projected to rise 4-5%... (Source)"

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

    # Call Claude API with web search enabled
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=16000,
        tools=[
            {
                "type": "web_search_20250305",
                "name": "web_search"
            }
        ],
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )
    
    # Extract the HTML content from Claude's response
    html_content = ""
    for block in message.content:
        if block.type == "text":
            html_content += block.text
    
    return html_content


def send_email(recipient_emails, subject, html_content):
    """
    Send email via SendGrid
    """
    sg = sendgrid.SendGridAPIClient(api_key=os.environ.get('SENDGRID_API_KEY'))
    from_email = Email(os.environ.get('FROM_EMAIL'))
    
    # Send to each recipient
    for recipient in recipient_emails:
        to_email = To(recipient)
        content = Content("text/html", html_content)
        mail = Mail(from_email, to_email, subject, content)
        
        try:
            response = sg.client.mail.send.post(request_body=mail.get())
            print(f"✅ Email sent to {recipient}: Status {response.status_code}")
        except Exception as e:
            print(f"❌ Error sending to {recipient}: {str(e)}")


def main():
    """
    Main function to generate and send daily stock summary
    """
    print(f"🚀 Starting daily stock summary generation at {datetime.now()}")
    
    # Get recipient emails from environment variables
    recipient_emails = os.environ.get('RECIPIENT_EMAILS', '').split(',')
    recipient_emails = [email.strip() for email in recipient_emails if email.strip()]
    
    if not recipient_emails:
        print("❌ Error: No recipient emails configured")
        return
    
    # Check required environment variables
    required_vars = ['ANTHROPIC_API_KEY', 'SENDGRID_API_KEY', 'FROM_EMAIL']
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        print(f"❌ Error: Missing required environment variables: {', '.join(missing_vars)}")
        return
    
    try:
        # Generate the summary using Claude API
        print("📊 Generating stock summaries with Claude API (this may take 1-2 minutes)...")
        html_content = generate_stock_summary_with_claude()
        print("✅ Summary generated successfully")
        
        # Generate today's date for subject
        today = datetime.now().strftime("%B %d, %Y")
        subject = f"Daily Stock Summaries - {today}"
        
        # Send the email
        print(f"📧 Sending emails to {len(recipient_emails)} recipients...")
        send_email(recipient_emails, subject, html_content)
        
        print(f"✅ Daily summary sent successfully to {len(recipient_emails)} recipients")
        print(f"⏰ Completed at {datetime.now()}")
        
    except Exception as e:
        print(f"❌ Error in main execution: {str(e)}")
        raise


if __name__ == "__main__":
    main()
