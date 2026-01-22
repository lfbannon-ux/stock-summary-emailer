#!/usr/bin/env python3
import os
import sys
import sendgrid
from sendgrid.helpers.mail import Mail, Email, To, Content
from datetime import datetime
import anthropic
import re

def extract_and_clean_html(raw_text):
    """Nuclear option: Extract only HTML content and fix all issues"""
    
    print("\n🔧 AGGRESSIVE HTML EXTRACTION AND CLEANING...")
    print(f"📄 Input length: {len(raw_text)} characters")
    
    # Step 1: Remove everything before the first <h1> or <html> tag
    # This removes Claude's preambles and explanations
    start_patterns = [
        r'<html[^>]*>',
        r'<!DOCTYPE[^>]*>',
        r'<h1[^>]*>',
    ]
    
    html_content = raw_text
    for pattern in start_patterns:
        match = re.search(pattern, html_content, re.IGNORECASE)
        if match:
            html_content = html_content[match.start():]
            print(f"✅ Trimmed content before {pattern}")
            break
    
    # Step 2: Remove everything after </html> or last </h2> section
    end_patterns = [
        r'</html>',
        r'</body>',
    ]
    
    for pattern in end_patterns:
        matches = list(re.finditer(pattern, html_content, re.IGNORECASE))
        if matches:
            last_match = matches[-1]
            html_content = html_content[:last_match.end()]
            print(f"✅ Trimmed content after {pattern}")
            break
    
    # Step 3: Fix SendGrid tracking URLs - convert to simple text links
    # Pattern: <https://u59134112.ct.sendgrid.net/...>
    def fix_sendgrid_url(match):
        url = match.group(1)
        return '<a href="' + url + '" style="color:#3498db;text-decoration:none;">View Source</a>'
    
    html_content = re.sub(r'<(https://u59134112\.ct\.sendgrid\.net/[^>]+)>', fix_sendgrid_url, html_content)
    print("✅ Fixed SendGrid tracking URLs")
    
    # Step 4: Fix any remaining angle bracket URLs: <https://...>
    def fix_angle_url(match):
        url = match.group(1)
        # Try to extract a readable name from the URL
        if 'asx.com.au' in url:
            link_text = 'ASX Announcement'
        elif 'afr.com' in url:
            link_text = 'AFR'
        elif 'bloomberg' in url:
            link_text = 'Bloomberg'
        elif 'reuters' in url:
            link_text = 'Reuters'
        else:
            # Extract domain
            domain_match = re.search(r'https?://([^/]+)', url)
            link_text = domain_match.group(1) if domain_match else 'Source'
        
        return f'<a href="{url}" style="color:#3498db;text-decoration:none;">{link_text}</a>'
    
    html_content = re.sub(r'<(https?://[^>]+)>', fix_angle_url, html_content)
    print("✅ Fixed angle bracket URLs")
    
    # Step 5: Fix bare URLs that aren't in any tags
    # But be careful not to touch URLs already in href attributes
    def fix_bare_urls(text):
        # Split by href attributes to avoid double-processing
        parts = re.split(r'(href="[^"]*")', text)
        result = []
        
        for i, part in enumerate(parts):
            if i % 2 == 0:  # Not inside href=""
                # Replace standalone URLs
                part = re.sub(
                    r'(?<!href=")(?<!")(?<!>)(https?://[^\s<>"]+)',
                    lambda m: f'<a href="{m.group(0)}" style="color:#3498db;text-decoration:none;">Source</a>',
                    part
                )
            result.append(part)
        
        return ''.join(result)
    
    html_content = fix_bare_urls(html_content)
    print("✅ Fixed bare URLs")
    
    # Step 6: Wrap in proper HTML structure if not already wrapped
    if not html_content.strip().startswith('<!DOCTYPE') and not html_content.strip().startswith('<html'):
        html_content = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family:Arial,sans-serif;max-width:900px;margin:0 auto;padding:20px;background-color:#ffffff;">
{html_content}
</body>
</html>'''
        print("✅ Wrapped content in HTML structure")
    
    # Step 7: Ensure closing tags
    if '</body>' not in html_content:
        html_content = html_content.replace('</html>', '</body></html>')
    
    print(f"✅ Final HTML length: {len(html_content)} characters")
    
    return html_content

def main():
    """Main function to generate and send daily stock summary"""
    
    print("=" * 60)
    print(f"🚀 Berkholts Daily Stock Summary Emailer")
    print(f"📊 10 Stocks with Nuclear Post-Processing")
    print(f"⏰ Started: {datetime.now()}")
    print("=" * 60)
    
    # Environment variables
    anthropic_key = os.getenv('ANTHROPIC_API_KEY')
    sendgrid_key = os.getenv('SENDGRID_API_KEY')
    from_email = os.getenv('FROM_EMAIL')
    recipient_emails_str = os.getenv('RECIPIENT_EMAILS')
    
    if not all([anthropic_key, sendgrid_key, from_email, recipient_emails_str]):
        print("\n❌ Missing environment variables!")
        sys.exit(1)
    
    recipient_emails = [e.strip() for e in recipient_emails_str.split(',') if e.strip()]
    print(f"✅ Recipients: {recipient_emails}")
    
    # Generate
    try:
        print("\n📊 Generating stock summaries...")
        
        client = anthropic.Anthropic(api_key=anthropic_key)
        today = datetime.now().strftime("%B %d, %Y")
        
        prompt = f"""Generate HTML email for {today}. Cover these 10 Australian stocks:

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

FORMAT:
<h1 style="color:#2c3e50;border-bottom:3px solid #3498db;padding-bottom:10px;">Berkholts Stock Summaries - {today}</h1>

Each stock:
<h2 style="color:#34495e;margin-top:40px;border-bottom:2px solid #95a5a6;padding-bottom:8px;">N. Name (TICKER)</h2>
<p style="line-height:1.6;margin:10px 0;"><strong style="color:#2980b9;">PRICE:</strong> A$XX.XX | <strong style="color:#2980b9;">YESTERDAY:</strong> change</p>
<p style="line-height:1.6;margin:10px 0;"><strong style="color:#2980b9;">REASON FOR MOVE:</strong> recent news or "No material announcements"</p>
<p style="line-height:1.6;margin:10px 0;"><strong style="color:#2980b9;">COMPANY DEVELOPMENTS (Past Week):</strong></p>
<ul style="line-height:1.8;margin:10px 0;"><li>developments</li></ul>
<p style="line-height:1.6;margin:10px 0;"><strong style="color:#2980b9;">LAST COMPANY ANNOUNCEMENT:</strong></p>
<ul style="line-height:1.8;margin:10px 0;">
<li><strong>Date:</strong> date</li>
<li><strong>Summary:</strong> summary</li>
<li><strong>Source:</strong> <a href="url" style="color:#3498db;text-decoration:none;">ASX</a></li>
</ul>
<p style="line-height:1.6;margin:10px 0;"><strong style="color:#2980b9;">INDUSTRY/COMPETITIVE DYNAMICS:</strong></p>
<ul style="line-height:1.8;margin:10px 0;"><li>data points with sources</li></ul>
<hr style="border:none;border-top:1px solid #ddd;margin:30px 0;">

Use web search to find real data. Generate all 10 stocks."""

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=32000,
            system="Generate HTML report. Start with <h1> tag immediately. No explanations.",
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Extract raw response
        raw_text = ""
        for block in message.content:
            if block.type == "text":
                raw_text += block.text
        
        print(f"📄 Received {len(raw_text)} characters from Claude")
        
        # NUCLEAR CLEANING
        html_content = extract_and_clean_html(raw_text)
        
    except Exception as e:
        print(f"\n❌ Generation error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Send
    try:
        print("\n📧 Sending emails...")
        
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
            
            try:
                response = sg.client.mail.send.post(request_body=mail.get())
                print(f"   ✅ Sent! Status: {response.status_code}")
            except Exception as e:
                print(f"   ❌ Failed: {e}")
        
        print("\n" + "=" * 60)
        print("✅ COMPLETE!")
        print(f"⏰ Finished: {datetime.now()}")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Send error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()