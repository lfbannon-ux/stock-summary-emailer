#!/usr/bin/env python3
"""
Berkholts Daily Stock Summary Emailer - V3 IMPROVED
====================================================
Key improvements:
1. Separate API calls for each research task (more reliable search triggers)
2. Explicit validation and fallback handling
3. Better prompts that acknowledge when data isn't found
4. Uses ASX company pages (always valid) rather than trying to guess PDF URLs
"""

import os
import sys
import smtplib
import json
import re
from email.mime.text import MIMEText
from datetime import datetime
import anthropic
import yfinance as yf


STOCKS = [
    {
        "name": "AUB Group Limited",
        "ticker": "AUB.AX",
        "asx_code": "AUB",
        "industry": "insurance broking",
        "competitors": ["Steadfast Group (SDF.AX)", "PSC Insurance (PSI.AX)"],
        "asx_url": "https://www.asx.com.au/markets/company/AUB"
    },
    {
        "name": "Mineral Resources Limited",
        "ticker": "MIN.AX",
        "asx_code": "MIN",
        "industry": "mining services and lithium",
        "competitors": ["Pilbara Minerals (PLS.AX)", "Fortescue Metals (FMG.AX)"],
        "asx_url": "https://www.asx.com.au/markets/company/MIN"
    },
]


def get_stock_price(ticker: str) -> dict:
    """Get accurate stock price from Yahoo Finance."""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5d")
        
        if len(hist) < 2:
            return {"error": f"Not enough history for {ticker}"}
        
        yesterday_close = float(hist['Close'].iloc[-1])
        previous_close = float(hist['Close'].iloc[-2])
        yesterday_date = hist.index[-1].strftime("%B %d, %Y")
        previous_date = hist.index[-2].strftime("%B %d, %Y")
        change_percent = ((yesterday_close - previous_close) / previous_close) * 100
        
        return {
            "yesterday_close": round(yesterday_close, 2),
            "yesterday_date": yesterday_date,
            "previous_close": round(previous_close, 2),
            "previous_date": previous_date,
            "change_percent": round(change_percent, 2),
            "error": None
        }
    except Exception as e:
        return {"error": str(e)}


def call_claude_with_search(client: anthropic.Anthropic, prompt: str, max_searches: int = 5) -> str:
    """
    Call Claude API with web search tool enabled.
    Returns the text response. Always returns a string, never None.
    """
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            tools=[{
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": max_searches
            }],
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Extract text from response
        result = ""
        for block in response.content:
            if hasattr(block, 'text') and block.text is not None:
                result += block.text
        
        return result.strip() if result else "NO_RESPONSE"
        
    except Exception as e:
        return f"ERROR: {str(e)}"


def research_announcements(client: anthropic.Anthropic, stock: dict) -> dict:
    """
    Research the company's recent ASX announcements.
    Returns structured data about announcements.
    """
    prompt = f"""Search the web for recent ASX announcements from {stock['name']} (ASX: {stock['asx_code']}).

Search for: "{stock['asx_code']} ASX announcement 2025 2026"
Also search: "{stock['name']} announcement investor"

After searching, provide the following in JSON format only (no other text):
{{
    "last_announcement": {{
        "date": "the date or 'Not found'",
        "title": "title of the announcement or 'Not found'",
        "summary": "1-2 sentence summary with specific numbers if available, or 'Not found'",
        "source_url": "actual URL from search results, or null if not found"
    }},
    "price_sensitive_news": {{
        "found": true or false,
        "description": "what news might explain recent price moves, or 'No material news found in last 3 days'",
        "source_url": "URL or null"
    }}
}}

IMPORTANT RULES:
- Only include information you actually found in search results
- If you can't find something, say "Not found" - do NOT make up dates or details
- For URLs, only use real URLs from your search results - do NOT invent URLs
- If no announcement source URL is found, use null (the system will use the ASX company page instead)
"""
    
    result = call_claude_with_search(client, prompt, max_searches=3)
    
    # Try to parse JSON from response
    try:
        # Find JSON in the response (might be wrapped in markdown)
        json_match = re.search(r'\{[\s\S]*\}', result)
        if json_match:
            data = json.loads(json_match.group())
            return data
    except (json.JSONDecodeError, AttributeError):
        pass
    
    # Return fallback structure
    return {
        "last_announcement": {
            "date": "Not found",
            "title": "Not found",
            "summary": "Unable to retrieve announcement data",
            "source_url": None
        },
        "price_sensitive_news": {
            "found": False,
            "description": "No material news found in last 3 days",
            "source_url": None
        }
    }


def research_earnings(client: anthropic.Anthropic, stock: dict) -> dict:
    """
    Research the company's last earnings report.
    """
    prompt = f"""Search the web for {stock['name']} (ASX: {stock['asx_code']}) earnings results and financial reports.

Search for: "{stock['asx_code']} earnings results FY2025 revenue profit"
Also search: "{stock['name']} half year results annual report"

After searching, provide the following in JSON format only (no other text):
{{
    "report_type": "Annual/Half-Year/Quarterly or 'Not found'",
    "report_date": "date of the report or 'Not found'",
    "period": "e.g., 'FY2025' or 'H1 FY2025' or 'Not found'",
    "revenue": "revenue figure with currency or 'Not found'",
    "npat": "net profit after tax or 'Not found'",
    "ebitda": "EBITDA if available or 'Not found'",
    "eps": "earnings per share or 'Not found'",
    "dividend": "dividend info or 'Not found'",
    "guidance": "any forward guidance mentioned or 'None mentioned'",
    "source_url": "URL from search results or null"
}}

IMPORTANT: Only report numbers you actually found. Do NOT make up financial figures.
"""
    
    result = call_claude_with_search(client, prompt, max_searches=3)
    
    try:
        json_match = re.search(r'\{[\s\S]*\}', result)
        if json_match:
            data = json.loads(json_match.group())
            return data
    except (json.JSONDecodeError, AttributeError):
        pass
    
    return {
        "report_type": "Not found",
        "report_date": "Not found",
        "period": "Not found",
        "revenue": "Not found",
        "npat": "Not found",
        "ebitda": "Not found",
        "eps": "Not found",
        "dividend": "Not found",
        "guidance": "None mentioned",
        "source_url": None
    }


def research_industry(client: anthropic.Anthropic, stock: dict) -> dict:
    """
    Research industry dynamics with specific data points.
    """
    prompt = f"""Search for recent news and data about the Australian {stock['industry']} industry.

Search for: "Australian {stock['industry']} industry 2025 2026"
Also search: "{stock['industry']} market trends Australia"

After searching, provide the following in JSON format only (no other text):
{{
    "data_points": [
        {{
            "fact": "A specific statistic, trend, or data point with numbers",
            "source": "Name of the source (e.g., 'Australian Financial Review', 'IBISWorld')",
            "source_url": "URL or null",
            "relevance": "How this relates to {stock['name']}"
        }},
        {{
            "fact": "Another specific data point",
            "source": "Source name",
            "source_url": "URL or null",
            "relevance": "Relevance to the company"
        }}
    ]
}}

IMPORTANT:
- Provide 2-3 specific data points with actual numbers/percentages
- Only include facts you actually found - do NOT make up statistics
- Include the source name for each fact
"""
    
    result = call_claude_with_search(client, prompt, max_searches=3)
    
    try:
        json_match = re.search(r'\{[\s\S]*\}', result)
        if json_match:
            data = json.loads(json_match.group())
            return data
    except (json.JSONDecodeError, AttributeError):
        pass
    
    return {
        "data_points": [
            {
                "fact": "No specific industry data found in recent search",
                "source": "N/A",
                "source_url": None,
                "relevance": "N/A"
            }
        ]
    }


def research_competitors(client: anthropic.Anthropic, stock: dict) -> dict:
    """
    Research competitor news and announcements.
    """
    competitors_str = ", ".join(stock['competitors'])
    
    prompt = f"""Search for recent news about competitors of {stock['name']} in the Australian market.
    
Key competitors: {competitors_str}

Search for: "{stock['competitors'][0]} ASX announcement 2025"
Also search: "{stock['competitors'][1] if len(stock['competitors']) > 1 else stock['competitors'][0]} news Australia"

After searching, provide the following in JSON format only (no other text):
{{
    "competitor_news": [
        {{
            "competitor": "Company name",
            "news": "Specific news item or announcement with details",
            "date": "Date or approximate timeframe",
            "implications": "What this might mean for {stock['name']}",
            "source_url": "URL or null"
        }}
    ]
}}

IMPORTANT:
- Only include news you actually found in search results
- Be specific about what competitors announced or reported
- If no recent competitor news found, return an empty list
"""
    
    result = call_claude_with_search(client, prompt, max_searches=3)
    
    try:
        json_match = re.search(r'\{[\s\S]*\}', result)
        if json_match:
            data = json.loads(json_match.group())
            return data
    except (json.JSONDecodeError, AttributeError):
        pass
    
    return {
        "competitor_news": []
    }


def format_stock_html(stock: dict, price_data: dict, announcements: dict, earnings: dict, 
                      industry: dict, competitors: dict, stock_num: int) -> str:
    """
    Format all researched data into HTML.
    Uses fallback URLs when real URLs aren't available.
    Always returns a valid HTML string, never None.
    """
    
    # Ensure all inputs are dicts (not None)
    price_data = price_data or {}
    announcements = announcements or {}
    earnings = earnings or {}
    industry = industry or {}
    competitors = competitors or {}
    
    # Price section
    if price_data.get('error'):
        price_html = f'<span style="color:#e74c3c;">Price data unavailable: {price_data.get("error", "Unknown error")}</span>'
    else:
        change_pct = price_data.get('change_percent', 0) or 0
        change_color = "#27ae60" if change_pct >= 0 else "#e74c3c"
        change_sign = "+" if change_pct >= 0 else ""
        price_html = f"""<strong style="color:#2980b9;">YESTERDAY ({price_data.get('yesterday_date', 'N/A')}):</strong> A${price_data.get('yesterday_close', 0):.2f} | 
<strong style="color:#2980b9;">PREVIOUS ({price_data.get('previous_date', 'N/A')}):</strong> A${price_data.get('previous_close', 0):.2f} | 
<strong style="color:#2980b9;">CHANGE:</strong> <span style="color:{change_color};">{change_sign}{change_pct:.2f}%</span>"""
    
    # Reason for move
    news = announcements.get('price_sensitive_news') or {}
    if news.get('found'):
        reason_text = news.get('description') or 'No specific catalyst identified'
        if news.get('source_url'):
            reason_text += f' <a href="{news["source_url"]}" style="color:#3498db;">[Source]</a>'
    else:
        reason_text = news.get('description') or 'No material announcements in the past 3 days that would explain the price movement.'
    
    # Last announcement
    ann = announcements.get('last_announcement') or {}
    ann_url = ann.get('source_url') or stock.get('asx_url', '#')
    ann_date = ann.get('date') or 'Not found'
    ann_title = ann.get('title') or 'Not found'
    ann_summary = ann.get('summary') or 'Unable to retrieve'
    
    # Earnings
    earn = earnings or {}
    earn_url = earn.get('source_url') or stock.get('asx_url', '#')
    
    earnings_parts = []
    if earn.get('report_type') and earn.get('report_type') != 'Not found':
        earnings_parts.append(f"<strong>Report:</strong> {earn.get('report_type')} ({earn.get('period') or 'N/A'})")
    if earn.get('report_date') and earn.get('report_date') != 'Not found':
        earnings_parts.append(f"<strong>Date:</strong> {earn.get('report_date')}")
    if earn.get('revenue') and earn.get('revenue') != 'Not found':
        earnings_parts.append(f"<strong>Revenue:</strong> {earn.get('revenue')}")
    if earn.get('npat') and earn.get('npat') != 'Not found':
        earnings_parts.append(f"<strong>NPAT:</strong> {earn.get('npat')}")
    if earn.get('ebitda') and earn.get('ebitda') != 'Not found':
        earnings_parts.append(f"<strong>EBITDA:</strong> {earn.get('ebitda')}")
    if earn.get('eps') and earn.get('eps') != 'Not found':
        earnings_parts.append(f"<strong>EPS:</strong> {earn.get('eps')}")
    if earn.get('dividend') and earn.get('dividend') != 'Not found':
        earnings_parts.append(f"<strong>Dividend:</strong> {earn.get('dividend')}")
    if earn.get('guidance') and earn.get('guidance') != 'None mentioned':
        earnings_parts.append(f"<strong>Guidance:</strong> {earn.get('guidance')}")
    
    if not earnings_parts:
        earnings_html = "Earnings data not found in recent search"
    else:
        earnings_html = "<br>".join(earnings_parts)
    
    # Industry dynamics
    ind_points = industry.get('data_points') or []
    if ind_points:
        ind_items = []
        for point in ind_points:
            if point is None:
                continue
            item = point.get('fact') or ''
            source = point.get('source')
            if source and source != 'N/A':
                source_url = point.get('source_url')
                if source_url:
                    item += f' <a href="{source_url}" style="color:#3498db;">({source})</a>'
                else:
                    item += f' ({source})'
            if item:
                ind_items.append(f'<li>{item}</li>')
        industry_html = "\n".join(ind_items) if ind_items else "<li>No specific industry data found</li>"
    else:
        industry_html = "<li>No specific industry data found</li>"
    
    # Competitor dynamics
    comp_news = competitors.get('competitor_news') or []
    if comp_news:
        comp_items = []
        for news_item in comp_news:
            if news_item is None:
                continue
            competitor_name = news_item.get('competitor') or 'Unknown'
            news_desc = news_item.get('news') or ''
            item = f"<strong>{competitor_name}:</strong> {news_desc}"
            news_date = news_item.get('date')
            if news_date:
                item += f" ({news_date})"
            source_url = news_item.get('source_url')
            if source_url:
                item += f' <a href="{source_url}" style="color:#3498db;">[Source]</a>'
            implications = news_item.get('implications')
            if implications:
                item += f"<br><em>Implications: {implications}</em>"
            comp_items.append(f'<li>{item}</li>')
        competitor_html = "\n".join(comp_items) if comp_items else "<li>No recent competitor announcements found</li>"
    else:
        competitor_html = "<li>No recent competitor announcements found in the last 2 weeks</li>"
    
    # Assemble HTML
    html = f"""
<h2 style="color:#34495e;margin-top:30px;border-bottom:2px solid #ecf0f1;padding-bottom:8px;">
{stock_num}. {stock['name']} ({stock['ticker']})
</h2>

<p style="margin:10px 0;line-height:1.6;">
{price_html}
</p>

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">REASON FOR MOVE:</strong><br>
{reason_text}
</p>

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">LAST PRICE-SENSITIVE ANNOUNCEMENT:</strong><br>
<strong>Date:</strong> {ann_date}<br>
<strong>Title:</strong> {ann_title}<br>
<strong>Summary:</strong> {ann_summary}<br>
<strong>Source:</strong> <a href="{ann_url}" style="color:#3498db;">ASX Company Page</a>
</p>

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">LAST EARNINGS REPORT:</strong><br>
{earnings_html}<br>
<strong>Source:</strong> <a href="{earn_url}" style="color:#3498db;">ASX Company Page</a>
</p>

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">INDUSTRY DYNAMICS:</strong>
</p>
<ul style="margin:5px 0 15px 20px;line-height:1.8;">
{industry_html}
</ul>

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">COMPETITIVE DYNAMICS:</strong>
</p>
<ul style="margin:5px 0 15px 20px;line-height:1.8;">
{competitor_html}
</ul>

<hr style="border:none;border-top:1px solid #ecf0f1;margin:30px 0;">
"""
    return html


def wrap_in_template(content: str, today: str) -> str:
    """Wrap in email template."""
    return f'''<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
</head>
<body style="font-family:Arial,sans-serif;margin:0;padding:0;background-color:#f4f4f4;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f4;">
<tr><td align="center" style="padding:20px;">
<table width="1000" cellpadding="20" cellspacing="0" style="background-color:#ffffff;border:1px solid #dddddd;">
<tr><td>

<h1 style="color:#2c3e50;border-bottom:3px solid #3498db;padding-bottom:10px;margin-top:0;">
Berkholts Stock Summaries - {today}
</h1>

{content}

<p style="color:#7f8c8d;font-size:12px;margin-top:30px;text-align:center;">
Generated by Berkholts Stock Summary System<br>
Prices: Yahoo Finance | Research: Claude AI with Web Search<br>
Note: ASX Company Page links provided for verification. Click to view official announcements.
</p>

</td></tr>
</table>
</td></tr>
</table>
</body>
</html>'''


def send_email(html: str, recipient: str, smtp_email: str, smtp_password: str, subject: str):
    """Send email."""
    msg = MIMEText(html, 'html', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = smtp_email
    msg['To'] = recipient
    
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(smtp_email, smtp_password)
        server.sendmail(smtp_email, recipient, msg.as_string())


def main():
    print("=" * 70)
    print("🚀 Berkholts Stock Emailer - V3 IMPROVED (Multi-Step Research)")
    print(f"⏰ Started: {datetime.now()}")
    print("=" * 70)
    
    # Check env vars
    anthropic_key = os.getenv('ANTHROPIC_API_KEY')
    smtp_email = os.getenv('SMTP_EMAIL')
    smtp_password = os.getenv('SMTP_PASSWORD')
    recipient_emails_str = os.getenv('RECIPIENT_EMAILS')
    
    missing = []
    if not anthropic_key: missing.append('ANTHROPIC_API_KEY')
    if not smtp_email: missing.append('SMTP_EMAIL')
    if not smtp_password: missing.append('SMTP_PASSWORD')
    if not recipient_emails_str: missing.append('RECIPIENT_EMAILS')
    
    if missing:
        print(f"❌ Missing: {', '.join(missing)}")
        sys.exit(1)
    
    recipients = [e.strip() for e in recipient_emails_str.split(',') if e.strip()]
    print(f"📧 Recipients: {', '.join(recipients)}")
    
    client = anthropic.Anthropic(api_key=anthropic_key)
    today_str = datetime.now().strftime("%B %d, %Y")
    
    all_html = ""
    
    for i, stock in enumerate(STOCKS, 1):
        print(f"\n{'=' * 70}")
        print(f"📊 STOCK {i}/{len(STOCKS)}: {stock['name']}")
        print("=" * 70)
        
        # Step 1: Get price (yfinance - always accurate)
        print("   💰 Getting price...", end=" ")
        price = get_stock_price(stock['ticker'])
        if price.get('error'):
            print(f"⚠️ {price['error']}")
        else:
            print(f"✅ A${price['yesterday_close']:.2f} ({price['change_percent']:+.2f}%)")
        
        # Step 2: Research announcements (separate API call)
        print("   📢 Researching announcements...", end=" ")
        announcements = research_announcements(client, stock)
        ann_status = "✅" if announcements.get('last_announcement', {}).get('date') != 'Not found' else "⚠️"
        print(ann_status)
        
        # Step 3: Research earnings (separate API call)
        print("   💹 Researching earnings...", end=" ")
        earnings = research_earnings(client, stock)
        earn_status = "✅" if earnings.get('report_type') != 'Not found' else "⚠️"
        print(earn_status)
        
        # Step 4: Research industry (separate API call)
        print("   🏭 Researching industry...", end=" ")
        industry = research_industry(client, stock)
        ind_status = "✅" if len(industry.get('data_points', [])) > 0 else "⚠️"
        print(ind_status)
        
        # Step 5: Research competitors (separate API call)
        print("   🏁 Researching competitors...", end=" ")
        competitors = research_competitors(client, stock)
        comp_status = "✅" if len(competitors.get('competitor_news', [])) > 0 else "⚠️"
        print(comp_status)
        
        # Step 6: Format HTML
        print("   📝 Formatting HTML...", end=" ")
        try:
            stock_html = format_stock_html(stock, price, announcements, earnings, industry, competitors, i)
            if stock_html is None:
                stock_html = f"<h2>{stock['name']} - Error formatting data</h2><hr>"
            print("✅")
        except Exception as e:
            print(f"❌ {e}")
            stock_html = f"<h2>{stock['name']} - Error: {str(e)}</h2><hr>"
        
        all_html += stock_html
    
    # Final assembly
    print(f"\n📧 Assembling email...")
    final_html = wrap_in_template(all_html, today_str)
    print(f"📄 Total: {len(final_html)} chars")
    
    # Send
    subject = f"Berkholts Stock Summaries - {today_str}"
    for recipient in recipients:
        try:
            print(f"📤 Sending to {recipient}...", end=" ")
            send_email(final_html, recipient, smtp_email, smtp_password, subject)
            print("✅")
        except Exception as e:
            print(f"❌ {e}")
    
    print(f"\n✅ DONE at {datetime.now()}")


if __name__ == "__main__":
    main()
